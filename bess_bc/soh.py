"""BESS State-of-Health (SoH) degradation curve.

IMPORTANT: the source workbook has TWO degradation curves on the BC sheet -
row 38 ("SoH input") and row 39 ("SoH BESS"). Only row 39 is ever referenced
by the revenue/cost formulas (rows 48, 51, 52); row 38 is computed but dead.
The values below are taken from row 39, NOT row 38 - using row 38's values
here would silently break the validation against the cached Excel outputs.
"""

# SoH at the end of each year of battery age, for ages 1 through 20.
# Age 0 (commissioning) is always 1.0 and is not part of this table.
SOH_CURVE_AGE_1_TO_20: list[float] = [
    0.972, 0.9275, 0.8975, 0.872, 0.8495, 0.829, 0.8095, 0.7915, 0.775, 0.759,
    0.7435, 0.729, 0.715, 0.701, 0.6875, 0.6745, 0.662, 0.65, 0.644, 0.0,
]


def soh_for_age(age: int, lifetime_years: int, include_degradation: bool) -> float:
    """SoH fraction (0-1) for a battery of the given age (years since commissioning).

    The original sheet hardcodes this curve per year-column regardless of the
    BESS Lifetime input for ages 1-20, which means changing lifetime below 20
    had no effect there. Here the curve is instead generalized by capping it
    at ``lifetime_years``: SoH is zero for any age beyond the battery's
    lifetime (or beyond the 20-year curve, whichever is smaller), and when
    degradation is disabled the battery is treated as running at 100% for its
    full lifetime instead of following the curve.
    """
    if age <= 0:
        return 1.0
    if age > lifetime_years:
        return 0.0
    if not include_degradation:
        return 1.0
    if age > len(SOH_CURVE_AGE_1_TO_20):
        return 0.0
    return SOH_CURVE_AGE_1_TO_20[age - 1]


def soh_series(lifetime_years: int, include_degradation: bool, horizon_years: int) -> list[float]:
    """SoH fraction for every year 0..horizon_years inclusive."""
    return [
        soh_for_age(age, lifetime_years, include_degradation)
        for age in range(horizon_years + 1)
    ]
