"""Discounting, IRR, and debt-amortization helpers.

No external finance dependency (e.g. numpy_financial) is required - the
formulas below are closed-form and are cross-checked against Excel's
PMT/IPMT/PPMT/NPV/IRR conventions in scripts/validate_against_excel.py.
"""

from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd


def standard_npv(rate: float, cashflows: Sequence[float]) -> float:
    """NPV with cashflows[0] undiscounted (the usual "year 0" convention)."""
    return sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))


def excel_npv(rate: float, cashflows: Sequence[float]) -> float:
    """Replicates Excel's =NPV(rate, range) - discounts EVERY value, including
    the first one, by one extra period versus ``standard_npv``. The BC sheet
    calls this on C69:AQ69 (i.e. including year 0), which is why the model's
    headline NPV differs from the textbook convention."""
    return standard_npv(rate, cashflows) / (1 + rate)


def _npv_derivative(rate: float, cashflows: Sequence[float]) -> float:
    return sum(-i * cf / (1 + rate) ** (i + 1) for i, cf in enumerate(cashflows))


def irr(
    cashflows: Sequence[float],
    guess: float = 0.1,
    tol: float = 1e-10,
    max_iter: int = 100,
) -> Optional[float]:
    """Solves for rate where standard_npv(rate, cashflows) == 0.

    Tries Newton's method first (matches Excel's IRR for well-behaved cash
    flow series), falling back to bisection over a wide bracket if Newton
    fails to converge or the derivative vanishes.
    """
    rate = guess
    for _ in range(max_iter):
        f = standard_npv(rate, cashflows)
        if abs(f) < tol:
            return rate
        d = _npv_derivative(rate, cashflows)
        if d == 0:
            break
        next_rate = rate - f / d
        if next_rate <= -0.999999:
            next_rate = (rate - 0.999999) / 2
        rate = next_rate

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = standard_npv(lo, cashflows), standard_npv(hi, cashflows)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        return None  # no sign change in bracket - no real IRR found
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = standard_npv(mid, cashflows)
        if abs(f_mid) < tol:
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid
    return (lo + hi) / 2


def debt_schedule(
    debt_amount: float,
    rate: float,
    term_years: int,
    horizon_years: int,
) -> pd.DataFrame:
    """Per-year debt service for years 0..horizon_years.

    Zero for year 0 and for any year beyond ``term_years``. Matches Excel's
    PMT/IPMT/PPMT sign convention: a positive ``debt_amount`` (loan received)
    produces negative payments (cash outflows).
    """
    years = range(horizon_years + 1)
    pmt = 0.0
    if debt_amount > 0 and term_years > 0:
        pmt = -debt_amount * rate / (1 - (1 + rate) ** (-term_years))

    rows = []
    for year in years:
        if debt_amount > 0 and 1 <= year <= term_years:
            k = year
            balance_before = debt_amount * (1 + rate) ** (k - 1) + pmt * (
                (1 + rate) ** (k - 1) - 1
            ) / rate
            interest = -balance_before * rate
            principal = pmt - interest
            rows.append(
                {"pmt": pmt, "interest": interest, "principal": principal, "balance_before": balance_before}
            )
        else:
            rows.append({"pmt": 0.0, "interest": 0.0, "principal": 0.0, "balance_before": 0.0})

    return pd.DataFrame(rows, index=list(years))
