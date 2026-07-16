import math
import pathlib

import openpyxl
import pytest

from bess_bc.engine import build_cashflow_table, compute_summary
from bess_bc.inputs import BessInputs

XLSX_PATH = pathlib.Path(__file__).resolve().parent.parent / "Business CasecSolar PV and BESS.xlsx"

pytestmark = pytest.mark.skipif(not XLSX_PATH.exists(), reason="source workbook not present")


@pytest.fixture(scope="module")
def bc_sheet():
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    return wb["BC"]


def test_default_inputs_match_excel(bc_sheet):
    inp = BessInputs()
    df = build_cashflow_table(inp)
    summary = compute_summary(df, inp)

    assert math.isclose(summary.payback_years, bc_sheet["C73"].value, rel_tol=1e-4)
    assert math.isclose(summary.irr, bc_sheet["C74"].value, rel_tol=1e-6)
    assert math.isclose(summary.npv_excel, bc_sheet["C75"].value, rel_tol=1e-6)
    assert math.isclose(df["cumulative_cash_flow"].iloc[20], bc_sheet["W70"].value, rel_tol=1e-6)
    assert math.isclose(df["cumulative_cash_flow"].iloc[40], bc_sheet["AQ70"].value, rel_tol=1e-6)


def test_no_degradation_runs_flat_soh():
    inp = BessInputs(include_degradation=False, bess_lifetime_years=5)
    df = build_cashflow_table(inp)
    assert (df["soh"].iloc[1:6] == 1.0).all()
    assert (df["soh"].iloc[6:] == 0.0).all()


def test_debt_financing_produces_nonzero_debt_service():
    inp = BessInputs(debt_share_pct=0.5, debt_rate_pct=0.09, debt_term_years=10)
    df = build_cashflow_table(inp)
    assert df["debt_repayment"].iloc[1:11].abs().gt(0).all()
    assert (df["debt_repayment"].iloc[11:] == 0.0).all()
    assert df["debt_repayment"].iloc[0] == 0.0


def test_payback_reports_no_payback_when_never_recovered():
    inp = BessInputs(bess_capex_eur_per_mwh=10_000_000.0)
    df = build_cashflow_table(inp)
    summary = compute_summary(df, inp)
    assert summary.payback_years is None
    assert summary.payback_label == "No payback"
