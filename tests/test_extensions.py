"""Tests for the extension fields added on top of the source workbook's own
BC-tab model (see the "Extension" field comments in bess_bc/inputs.py):
cycle-based revenue, other capex, other opex, and
truncate_at_full_degradation. Each one defaults to a no-op value, so
tests/test_validate_defaults.py's Excel-validated defaults stay exact -
these tests instead cover what happens once a caller opts in.
"""
import math

from bess_bc.engine import build_cashflow_table, compute_summary
from bess_bc.inputs import BessInputs


def test_cycle_based_revenue_replaces_spread_price_when_set():
    inp = BessInputs(cycles_per_year=300.0, trading_profit_eur_per_cycle=50.0)
    df = build_cashflow_table(inp)
    soh_year1 = df["soh"].iloc[1]
    assert math.isclose(df["revenue"].iloc[1], 50.0 * 300.0 * soh_year1)


def test_cycle_based_revenue_equivalent_to_spread_price_gives_same_summary():
    base = BessInputs()
    base_df = build_cashflow_table(base)
    base_summary = compute_summary(base_df, base)

    # cycles_per_year=1 with trading_profit_eur_per_cycle set to the
    # spread-price formula's own annual total makes the two revenue
    # models produce the same revenue[year] for every year, so every
    # other column (soh, costs, tax, depreciation, debt, NPV/IRR/payback)
    # should match exactly - confirms the two revenue paths only differ
    # in the revenue line itself, not the rest of the engine.
    equivalent = BessInputs(
        cycles_per_year=1.0,
        trading_profit_eur_per_cycle=base.spread_capture_price_eur_per_mwh * 365 * base.bess_size_mw,
    )
    equivalent_df = build_cashflow_table(equivalent)
    equivalent_summary = compute_summary(equivalent_df, equivalent)

    assert math.isclose(base_summary.npv, equivalent_summary.npv, rel_tol=1e-9)
    assert math.isclose(base_summary.irr, equivalent_summary.irr, rel_tol=1e-9)
    assert math.isclose(base_summary.payback_years, equivalent_summary.payback_years, rel_tol=1e-9)
    assert base_df["revenue"].tolist() == equivalent_df["revenue"].tolist()


def test_other_capex_adds_to_grid_cost_and_capex_basis():
    base = BessInputs()
    with_other = BessInputs(other_capex_eur_per_mw=10_000.0)

    base_df = build_cashflow_table(base)
    other_df = build_cashflow_table(with_other)

    extra_capex = with_other.other_capex_eur_per_mw * with_other.bess_size_mw
    assert math.isclose(other_df.attrs["grid_cost0"], base_df.attrs["grid_cost0"] - extra_capex)
    assert math.isclose(other_df.attrs["capex_basis"], base_df.attrs["capex_basis"] + extra_capex)


def test_other_opex_reduces_yearly_costs_until_degraded():
    base = BessInputs()
    with_extra = BessInputs(other_opex_eur_per_mwh_year=1_500.0)

    base_df = build_cashflow_table(base)
    extra_df = build_cashflow_table(with_extra)

    # Year 1: battery is operating (soh > 0), so the extra cost applies,
    # scaled by energy capacity like bess_opex_eur_per_mwh_year.
    extra_cost = with_extra.other_opex_eur_per_mwh_year * with_extra.bess_duration_hours * with_extra.bess_size_mw
    assert math.isclose(extra_df["costs"].iloc[1], base_df["costs"].iloc[1] - extra_cost)
    # Once the battery is fully degraded (soh == 0), no cost applies -
    # matches how the existing grid fee already behaves once retired.
    zero_soh_year = next(y for y in range(1, len(base_df)) if base_df["soh"].iloc[y] == 0)
    assert extra_df["costs"].iloc[zero_soh_year] == 0.0


def test_truncate_at_full_degradation_stops_before_zero_soh():
    full = BessInputs()
    truncated = BessInputs(truncate_at_full_degradation=True)

    full_df = build_cashflow_table(full)
    truncated_df = build_cashflow_table(truncated)

    # Default lifetime=20: the SoH curve's own last entry (age 20) is 0,
    # so the truncated table should stop at year 19 - one year short of
    # the untruncated table's zero-SoH row.
    assert truncated_df.index[-1] == 19
    assert (truncated_df["soh"] > 0).all()
    assert full_df["soh"].iloc[20] == 0.0

    # Every dropped year only ever contributed 0, so summary metrics must
    # match exactly regardless of truncation.
    full_summary = compute_summary(full_df, full)
    truncated_summary = compute_summary(truncated_df, truncated)
    assert math.isclose(full_summary.npv, truncated_summary.npv, rel_tol=1e-9)
    assert math.isclose(full_summary.irr, truncated_summary.irr, rel_tol=1e-9)
    assert math.isclose(full_summary.payback_years, truncated_summary.payback_years, rel_tol=1e-9)
    assert math.isclose(full_summary.cumulative_cash_flow_final, truncated_summary.cumulative_cash_flow_final, rel_tol=1e-9)


def test_truncate_at_full_degradation_floors_at_debt_term():
    # A loan that outlives the battery shouldn't get its remaining
    # repayments silently dropped by truncation.
    inp = BessInputs(
        bess_lifetime_years=5,
        truncate_at_full_degradation=True,
        debt_share_pct=0.5,
        debt_term_years=15,
    )
    df = build_cashflow_table(inp)
    assert df.index[-1] == 15
