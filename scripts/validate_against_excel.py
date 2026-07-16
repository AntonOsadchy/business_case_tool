"""Validates the Python reimplementation against the cached values in the
source Excel workbook's BC tab, using default inputs.

Usage: python3 scripts/validate_against_excel.py
"""

import math
import pathlib
import sys

import openpyxl

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from bess_bc.engine import build_cashflow_table, compute_summary
from bess_bc.inputs import BessInputs

XLSX_PATH = pathlib.Path(__file__).resolve().parent.parent / "Business CasecSolar PV and BESS.xlsx"


def close(a: float, b: float, rel_tol: float) -> bool:
    return math.isclose(a, b, rel_tol=rel_tol)


def main() -> int:
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    bc = wb["BC"]

    expected_payback = bc["C73"].value
    expected_irr = bc["C74"].value
    expected_npv = bc["C75"].value
    expected_plateau_20 = bc["W70"].value
    expected_plateau_40 = bc["AQ70"].value

    inp = BessInputs()
    df = build_cashflow_table(inp)
    summary = compute_summary(df, inp)

    checks = [
        ("Payback (years)", summary.payback_years, expected_payback, 1e-4),
        ("IRR", summary.irr, expected_irr, 1e-6),
        ("NPV (excel convention)", summary.npv_excel, expected_npv, 1e-6),
        ("Cumulative cash flow @ year 20", df["cumulative_cash_flow"].iloc[20], expected_plateau_20, 1e-6),
        ("Cumulative cash flow @ year 40", df["cumulative_cash_flow"].iloc[40], expected_plateau_40, 1e-6),
    ]

    all_pass = True
    for name, actual, expected, rel_tol in checks:
        ok = close(actual, expected, rel_tol)
        all_pass &= ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: actual={actual!r} expected={expected!r}")

    print()
    print("ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
