"""Input parameters for the BESS business case model.

Field defaults and BC-tab cell references (source: "Business CasecSolar PV
and BESS.xlsx", sheet "BC"). Solar PV and the dead inputs ("Number of
cycles", "Cycle value", "Include market development") from the original
sheet are intentionally omitted - they are never referenced by any formula
in the source model.

Fields below marked "extension" are additions beyond the source workbook's
BC tab, added for callers with real measured trading data (e.g. a BESS
dispatch simulation) instead of the workbook's flat assumed spread price -
each one defaults to a value that reproduces the original BC-tab formulas
exactly, so every existing default-input behavior (and the Excel
validation in scripts/validate_against_excel.py / tests/) is unaffected
unless a caller opts in by setting the new field.
"""

from dataclasses import dataclass


@dataclass
class BessInputs:
    # BESS technical / cost (BC!D5:D9)
    bess_size_mw: float = 1.0
    bess_duration_hours: float = 2.0
    bess_lifetime_years: int = 20
    bess_capex_eur_per_mwh: float = 160_000.0
    bess_opex_eur_per_mwh_year: float = 2_300.0
    # Extension: ancillary civil/electrical works beyond the core BESS
    # units, capitalized and depreciated the same way as
    # bess_capex_eur_per_mwh (default 0 - no effect unless set).
    balance_of_plant_eur_per_mwh: float = 0.0

    # Grid connection (BC!D19:D22). Originally split into
    # grid_fee_consumption_eur_per_mw + grid_fee_production_eur_per_mw
    # (BC!D19/D20); combined into one field since callers now source a
    # single already-combined per-MW connection fee - default is the sum
    # of those two original defaults (100,000 + 0), so this reproduces the
    # original BC-tab formula exactly.
    grid_fee_eur_per_mw: float = 100_000.0
    substation_contribution_eur: float = 0.0
    fixed_yearly_grid_fee_eur_per_mw_year: float = 7_106.0

    # Extension: additional recurring yearly costs, applied the same way
    # as fixed_yearly_grid_fee_eur_per_mw_year (zeroed once the battery is
    # fully degraded). Both default 0 - no effect unless set.
    land_lease_eur_per_year: float = 0.0
    insurance_eur_per_year: float = 0.0

    # Financial / macro (BC!D24:D34)
    inflation_pct: float = 0.02
    include_degradation: bool = True
    profit_share_pct: float = 0.05
    debt_share_pct: float = 0.0
    debt_rate_pct: float = 0.09
    debt_term_years: int = 10
    wacc_pct: float = 0.05
    tax_pct: float = 0.0
    depreciation_rate_pct: float = 0.15

    # Revenue assumption (BC!C41) - the source workbook's own flat,
    # never-escalated spread-price assumption. Still the default revenue
    # driver (see engine.py) whenever cycles_per_year is left at 0.
    spread_capture_price_eur_per_mwh: float = 168.0

    # Extension: measured-data alternative to spread_capture_price_eur_per_mwh
    # - when cycles_per_year > 0, engine.py uses
    # `trading_profit_eur_per_cycle * cycles_per_year * soh[year]` as that
    # year's revenue instead of the flat spread-price formula, for callers
    # with a real per-cycle trading profit and cycle count (e.g. from a
    # dispatch simulation) rather than an assumed daily spread. Both
    # default 0, which leaves the original spread-price formula in effect.
    trading_profit_eur_per_cycle: float = 0.0
    cycles_per_year: float = 0.0

    # Model horizon (BC row 36 spans years 0-40)
    horizon_years: int = 40

    # Extension: when True, build_cashflow_table's returned table stops
    # the year *before* SoH first reaches zero (the battery's lifetime is
    # considered ended at that point) instead of always running the full
    # horizon_years ceiling - see build_cashflow_table. Default False
    # preserves the original fixed-horizon table (required by the Excel
    # validation, which indexes specific rows up to horizon_years).
    truncate_at_full_degradation: bool = False

    def validate(self) -> None:
        if self.bess_size_mw <= 0:
            raise ValueError("bess_size_mw must be positive")
        if self.bess_duration_hours <= 0:
            raise ValueError("bess_duration_hours must be positive")
        if self.bess_lifetime_years <= 0:
            raise ValueError("bess_lifetime_years must be positive")
        if not (0.0 <= self.debt_share_pct < 1.0):
            raise ValueError("debt_share_pct must be in [0, 1)")
        if self.debt_share_pct > 0 and self.debt_term_years <= 0:
            raise ValueError("debt_term_years must be positive when debt_share_pct > 0")
        if self.debt_share_pct > 0 and self.debt_rate_pct <= 0:
            raise ValueError("debt_rate_pct must be positive when debt_share_pct > 0")
        if not (0.0 < self.depreciation_rate_pct <= 1.0):
            raise ValueError("depreciation_rate_pct must be in (0, 1]")
        if self.tax_pct < 0 or self.tax_pct > 1:
            raise ValueError("tax_pct must be in [0, 1]")
        if self.inflation_pct < -1:
            raise ValueError("inflation_pct must be >= -1")
        if self.wacc_pct <= -1:
            raise ValueError("wacc_pct must be > -1")
        if self.horizon_years <= 0:
            raise ValueError("horizon_years must be positive")
