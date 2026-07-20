"""Year-by-year cash flow engine for the BESS business case.

Reimplements BC!rows 37-75 (BESS-only) from the source workbook. See the
approved plan (docs in the repo history / conversation) for the full
row-by-row derivation and cell references this was verified against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from bess_bc.finance import debt_schedule, irr, standard_npv
from bess_bc.inputs import BessInputs
from bess_bc.soh import soh_series


def build_cashflow_table(inp: BessInputs) -> pd.DataFrame:
    inp.validate()
    horizon = inp.horizon_years
    years = list(range(horizon + 1))
    soh = soh_series(inp.bess_lifetime_years, inp.include_degradation, horizon)

    capex_cost0 = -(
        inp.bess_duration_hours * inp.bess_capex_eur_per_mwh * inp.bess_size_mw
    ) * (1 - inp.debt_share_pct)
    # other_capex_eur_per_mw is an extension (default 0): a catch-all €/MW
    # one-time cost (MV-to-HV transformer, balance of plant, etc.), added
    # alongside the grid fee and depreciated via capex_basis below.
    grid_cost0 = -(
        (inp.grid_fee_eur_per_mw + inp.other_capex_eur_per_mw) * inp.bess_size_mw
    ) * (1 - inp.debt_share_pct)
    costs0 = capex_cost0 + grid_cost0

    capex_basis = -costs0 / (1 - inp.debt_share_pct)
    debt_amount = 0.0
    if inp.debt_share_pct > 0:
        debt_amount = -costs0 * inp.debt_share_pct / (1 - inp.debt_share_pct)
    debt_df = debt_schedule(debt_amount, inp.debt_rate_pct, inp.debt_term_years, horizon)

    revenue = [0.0] * (horizon + 1)
    opex_cost = [0.0] * (horizon + 1)
    grid_cost = [0.0] * (horizon + 1)
    costs = [0.0] * (horizon + 1)
    operational_profit = [0.0] * (horizon + 1)
    profit_share = [0.0] * (horizon + 1)
    annual_depreciation_rate = [0.0] * (horizon + 1)
    cumulative_depreciation_rate = [0.0] * (horizon + 1)
    depreciation = [0.0] * (horizon + 1)
    taxable_income = [0.0] * (horizon + 1)
    tax = [0.0] * (horizon + 1)
    gross_profit_real = [0.0] * (horizon + 1)

    costs[0] = costs0
    gross_profit_real[0] = revenue[0] + costs[0]

    for year in range(1, horizon + 1):
        # cycles_per_year > 0 opts into the measured-data revenue model
        # (trading_profit_eur_per_cycle * cycles_per_year) in place of the
        # source workbook's flat spread_capture_price_eur_per_mwh * 365
        # assumption - see the field comments in inputs.py.
        if inp.cycles_per_year > 0:
            revenue[year] = inp.trading_profit_eur_per_cycle * inp.cycles_per_year * soh[year]
        else:
            revenue[year] = inp.spread_capture_price_eur_per_mwh * 365 * soh[year] * inp.bess_size_mw
        opex_cost[year] = (
            -inp.bess_opex_eur_per_mwh_year * inp.bess_duration_hours * inp.bess_size_mw
            if soh[year] != 0
            else 0.0
        )
        # other_opex_eur_per_mwh_year is an extension (default 0), scaled
        # by energy capacity like bess_opex_eur_per_mwh_year above.
        other_opex_cost = (
            -inp.other_opex_eur_per_mwh_year * inp.bess_duration_hours * inp.bess_size_mw
            if soh[year] != 0
            else 0.0
        )
        grid_cost[year] = -inp.fixed_yearly_grid_fee_eur_per_mw_year if soh[year] != 0 else 0.0
        costs[year] = opex_cost[year] + other_opex_cost + grid_cost[year]
        operational_profit[year] = revenue[year] + costs[year]
        profit_share[year] = -inp.profit_share_pct * operational_profit[year]

        prev_cum = cumulative_depreciation_rate[year - 1]
        annual_depreciation_rate[year] = (
            min(inp.depreciation_rate_pct, 1 - prev_cum) if prev_cum < 1 else 0.0
        )
        cumulative_depreciation_rate[year] = prev_cum + annual_depreciation_rate[year]
        depreciation[year] = annual_depreciation_rate[year] * capex_basis

        taxable_income[year] = max(0.0, operational_profit[year] - depreciation[year])
        tax[year] = -taxable_income[year] * inp.tax_pct

        gross_profit_real[year] = (
            operational_profit[year] + profit_share[year] + tax[year] + debt_df["pmt"].iloc[year]
        )

    inflation_index = [(1 + inp.inflation_pct) ** year for year in years]
    gross_profit_nominal = [gross_profit_real[y] * inflation_index[y] for y in years]
    cumulative_cash_flow = pd.Series(gross_profit_nominal).cumsum().tolist()

    df = pd.DataFrame(
        {
            "soh": soh,
            "inflation_index": inflation_index,
            "revenue": revenue,
            "opex_cost": opex_cost,
            "grid_cost": grid_cost,
            "costs": costs,
            "operational_profit": operational_profit,
            "profit_share": profit_share,
            "annual_depreciation_rate": annual_depreciation_rate,
            "cumulative_depreciation_rate": cumulative_depreciation_rate,
            "depreciation": depreciation,
            "taxable_income": taxable_income,
            "tax": tax,
            "debt_repayment": debt_df["pmt"].tolist(),
            "debt_interest": debt_df["interest"].tolist(),
            "debt_principal": debt_df["principal"].tolist(),
            "gross_profit_real": gross_profit_real,
            "gross_profit_nominal": gross_profit_nominal,
            "cumulative_cash_flow": cumulative_cash_flow,
        },
        index=years,
    )
    df.index.name = "year"

    # Extension (default off): the battery's lifetime is considered ended
    # the moment SoH reaches zero, so trim the table to the last year with
    # *nonzero* SoH rather than always returning the full horizon_years
    # ceiling - every dropped year's revenue/costs are identically zero
    # anyway (see the loop above), so NPV/IRR/cumulative cash flow are
    # unaffected either way, only the row count changes. Floored at
    # debt_term_years when there's outstanding debt, so a loan that
    # happens to outlive the battery doesn't get its remaining repayments
    # silently dropped. Attrs are set after trimming (not before) since
    # not every pandas version reliably propagates .attrs through .iloc.
    if inp.truncate_at_full_degradation:
        try:
            zero_soh_year = next(y for y in years if y > 0 and soh[y] == 0)
            end_year = zero_soh_year - 1
        except StopIteration:
            end_year = years[-1]
        if inp.debt_share_pct > 0:
            end_year = max(end_year, min(inp.debt_term_years, years[-1]))
        df = df.iloc[: end_year + 1].copy()

    df.attrs["capex_cost0"] = capex_cost0
    df.attrs["grid_cost0"] = grid_cost0
    df.attrs["capex_basis"] = capex_basis
    df.attrs["debt_amount"] = debt_amount
    return df


@dataclass
class Summary:
    payback_years: Optional[float]
    payback_label: str
    irr: Optional[float]
    npv: float
    wacc_pct: float
    cumulative_cash_flow_final: float
    horizon_years: int


def compute_summary(df: pd.DataFrame, inp: BessInputs) -> Summary:
    cum = df["cumulative_cash_flow"]
    nominal = df["gross_profit_nominal"]

    payback_years: Optional[float] = None
    payback_label = "No payback"
    # len(df) rather than inp.horizon_years + 1: identical when df wasn't
    # truncated (the normal case), but safely bounds the loop when
    # truncate_at_full_degradation shortened the table.
    for year in range(1, len(df)):
        if cum.iloc[year] >= 0:
            prior_deficit = -cum.iloc[year - 1]
            payback_years = (year - 1) + prior_deficit / nominal.iloc[year]
            payback_label = f"{payback_years:.2f} years"
            break

    cashflow_series = nominal.tolist()
    irr_value = irr(cashflow_series)
    npv_value = standard_npv(inp.wacc_pct, cashflow_series)

    return Summary(
        payback_years=payback_years,
        payback_label=payback_label,
        irr=irr_value,
        npv=npv_value,
        wacc_pct=inp.wacc_pct,
        cumulative_cash_flow_final=cum.iloc[-1],
        horizon_years=inp.horizon_years,
    )
