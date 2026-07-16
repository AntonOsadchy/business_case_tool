"""Command-line interface for the BESS business case calculator."""

from __future__ import annotations

import argparse
import dataclasses

import pandas as pd

from bess_bc.engine import build_cashflow_table, compute_summary
from bess_bc.inputs import BessInputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone BESS business case calculator (replicates the BC tab)."
    )
    defaults = BessInputs()
    for field in dataclasses.fields(BessInputs):
        flag = "--" + field.name.replace("_", "-")
        default = getattr(defaults, field.name)
        if field.type is bool:
            parser.add_argument(
                flag,
                dest=field.name,
                action="store_true",
                default=None,
                help=f"default: {default}",
            )
            parser.add_argument(
                "--no-" + field.name.replace("_", "-"),
                dest=field.name,
                action="store_false",
                default=None,
            )
        else:
            caster = int if field.type is int else float
            parser.add_argument(flag, type=caster, default=None, help=f"default: {default}")

    parser.add_argument("--csv", metavar="PATH", help="write the full year-by-year table to this CSV path")
    parser.add_argument(
        "--full-table", action="store_true", help="print every column of the yearly table, not just the summary columns"
    )
    return parser


def inputs_from_args(args: argparse.Namespace) -> BessInputs:
    overrides = {}
    for field in dataclasses.fields(BessInputs):
        value = getattr(args, field.name, None)
        if value is not None:
            overrides[field.name] = value
    return BessInputs(**overrides)


def print_summary(summary, inp: BessInputs) -> None:
    print("BESS Business Case Summary")
    print("=" * 40)
    print(f"Payback:                 {summary.payback_label}")
    irr_str = f"{summary.irr * 100:.2f}%" if summary.irr is not None else "N/A"
    print(f"IRR:                     {irr_str}")
    print(f"NPV:                     EUR {summary.npv:,.2f}")
    print(f"WACC (discount rate):    {summary.wacc_pct * 100:.2f}%")
    print(f"Cumulative cash flow @ year {summary.horizon_years}: EUR {summary.cumulative_cash_flow_final:,.2f}")


def print_table(df: pd.DataFrame, full: bool) -> None:
    print()
    print("Year-by-year cash flow")
    print("=" * 40)
    if full:
        cols = list(df.columns)
    else:
        cols = ["revenue", "costs", "gross_profit_nominal", "cumulative_cash_flow"]
    with pd.option_context("display.float_format", lambda v: f"{v:,.2f}"):
        print(df[cols].to_string())


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    inp = inputs_from_args(args)

    try:
        inp.validate()
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    df = build_cashflow_table(inp)
    summary = compute_summary(df, inp)

    print_summary(summary, inp)
    print_table(df, args.full_table)

    if args.csv:
        df.to_csv(args.csv)
        print(f"\nFull table written to {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
