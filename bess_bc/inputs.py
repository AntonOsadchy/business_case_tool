"""Input parameters for the BESS business case model.

Field defaults and BC-tab cell references (source: "Business CasecSolar PV
and BESS.xlsx", sheet "BC"). Solar PV and the dead inputs ("Number of
cycles", "Cycle value", "Include market development") from the original
sheet are intentionally omitted - they are never referenced by any formula
in the source model.
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

    # Grid connection (BC!D19:D22)
    grid_fee_consumption_eur_per_mw: float = 100_000.0
    grid_fee_production_eur_per_mw: float = 0.0
    substation_contribution_eur: float = 0.0
    fixed_yearly_grid_fee_eur_per_mw_year: float = 7_106.0

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

    # Revenue assumption (BC!C41)
    spread_capture_price_eur_per_mwh: float = 168.0

    # Model horizon (BC row 36 spans years 0-40)
    horizon_years: int = 40

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
