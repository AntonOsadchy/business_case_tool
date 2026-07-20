# BESS Business Case Calculator

A standalone Python tool that calculates the business case (NPV, IRR, payback)
for a Battery Energy Storage System (BESS) project. It reimplements the
calculation logic of the **BC** tab in `Business CasecSolar PV and BESS.xlsx`,
without needing Excel.

Scope note: this tool covers the **BESS side only**. The source workbook's BC
tab also has a Solar PV branch, but it is out of scope here.

## Setup

### Option A: Docker (recommended, no local Python needed)

Requires Docker and `make`.

```bash
make build
make run
```

`make run` passes through any CLI flags via `ARGS`, and mounts the current
directory into the container so file output (e.g. `--csv`) lands on your
host filesystem:

```bash
make run ARGS="--bess-size-mw 5 --debt-share-pct 0.5 --csv results.csv"
```

Other targets:

```bash
make test       # run the pytest suite inside the container
make validate   # validate against the source .xlsx inside the container
make shell      # drop into a shell inside the container
make clean      # remove the built image
```

### Option B: Local Python

Requires Python 3.9+ and `pandas`.

```bash
pip install pandas
# optional, for tests/validation against the source workbook:
pip install openpyxl pytest
```

No installation step is required to run the tool — just run it as a module
from the repo root (see below). If you'd rather install it as a package:

```bash
pip install -e .
bess-bc --help
```

## Usage

The examples below use `python3 -m bess_bc.cli` directly (Option B). If
you're using Docker (Option A), run the same thing via
`make run ARGS="..."` instead.

Run with all defaults (matches the BC tab's default scenario):

```bash
python3 -m bess_bc.cli
```

Override any input with a `--flag`:

```bash
python3 -m bess_bc.cli --bess-size-mw 5 --debt-share-pct 0.5 --debt-term-years 10
```

Export the full year-by-year table to CSV:

```bash
python3 -m bess_bc.cli --csv results.csv
```

Print every calculated column (not just the summary columns) in the table:

```bash
python3 -m bess_bc.cli --full-table
```

Run `python3 -m bess_bc.cli --help` for the full list of flags — there is one
`--flag` per input parameter, listed below.

## Inputs

| Flag | Field | Default | Meaning |
|---|---|---|---|
| `--bess-size-mw` | `bess_size_mw` | 1.0 | Power rating (MW) |
| `--bess-duration-hours` | `bess_duration_hours` | 2.0 | Storage duration (hours); energy = size × duration |
| `--bess-lifetime-years` | `bess_lifetime_years` | 20 | Years before the battery is fully degraded / retired (no replacement modeled) |
| `--bess-capex-eur-per-mwh` | `bess_capex_eur_per_mwh` | 160,000 | Capex rate, €/MWh of energy capacity |
| `--bess-opex-eur-per-mwh-year` | `bess_opex_eur_per_mwh_year` | 2,300 | Annual opex rate, €/MWh-year |
| `--grid-fee-eur-per-mw` | `grid_fee_eur_per_mw` | 100,000 | One-off year-0 grid connection fee, €/MW (combines what were originally separate consumption/production fee inputs) |
| `--other-capex-eur-per-mw` | `other_capex_eur_per_mw` | 0 | *Extension.* Catch-all one-off year-0 capex, €/MW — consolidates what were previously two separate fields, `transformer_eur_per_mw` (MV-to-HV transformer) and `balance_of_plant_eur_per_mwh` (ancillary civil/electrical works, previously €/MWh) |
| `--fixed-yearly-grid-fee-eur-per-mw-year` | `fixed_yearly_grid_fee_eur_per_mw_year` | 7,106 | Recurring annual grid fee, € (flat amount — see note below) |
| `--other-opex-eur-per-mwh-year` | `other_opex_eur_per_mwh_year` | 0 | *Extension.* Catch-all recurring annual opex, €/MWh-year (scaled like `bess_opex_eur_per_mwh_year`) — consolidates what were previously two separate flat-€/year fields, `land_lease_eur_per_year` and `insurance_eur_per_year` |
| `--inflation-pct` | `inflation_pct` | 0.02 | Annual inflation, applied to nominalize the cash flow |
| `--include-degradation` / `--no-include-degradation` | `include_degradation` | on | Whether the battery follows the SoH degradation curve or runs at 100% for its full lifetime |
| `--profit-share-pct` | `profit_share_pct` | 0.05 | Share of operational profit paid to a route-to-market optimizer |
| `--debt-share-pct` | `debt_share_pct` | 0.0 | Share of capex financed by debt (0–1) |
| `--debt-rate-pct` | `debt_rate_pct` | 0.09 | Loan interest rate |
| `--debt-term-years` | `debt_term_years` | 10 | Loan tenor, years |
| `--wacc-pct` | `wacc_pct` | 0.05 | Discount rate used for NPV |
| `--tax-pct` | `tax_pct` | 0.0 | Corporate tax rate |
| `--depreciation-rate-pct` | `depreciation_rate_pct` | 0.15 | Cap on the declining-balance annual depreciation rate |
| `--spread-capture-price-eur-per-mwh` | `spread_capture_price_eur_per_mwh` | 168.0 | Flat trading spread capture price, €/MWh (never escalated by inflation) — used as the revenue driver only when `cycles_per_year` is left at 0 |
| `--trading-profit-eur-per-cycle` | `trading_profit_eur_per_cycle` | 0 | *Extension.* Measured trading profit per cycle, € — used with `cycles_per_year` in place of the spread-price formula |
| `--cycles-per-year` | `cycles_per_year` | 0 | *Extension.* Measured cycles/year. When > 0, revenue is `trading_profit_eur_per_cycle * cycles_per_year * soh[year]` instead of the spread-price formula |
| `--horizon-years` | `horizon_years` | 40 | Modeling horizon in years (0..N) |
| `--truncate-at-full-degradation` / `--no-truncate-at-full-degradation` | `truncate_at_full_degradation` | off | *Extension.* When on, the returned table stops the year before SoH first reaches zero instead of always running to `horizon_years` |

### A note on "Extension" fields

Fields marked *Extension* above aren't part of the source workbook's BC tab -
they were added for callers with real measured trading data (e.g. from a
BESS dispatch simulation) instead of the workbook's flat assumed spread
price, plus a couple of additional cost line items and an option to stop
the table once the battery is fully degraded rather than always running
the full horizon. Every one of them defaults to a value that reproduces
the original BC-tab formulas exactly - `tests/test_extensions.py` covers
what changes once you opt into them; `tests/test_validate_defaults.py` and
`scripts/validate_against_excel.py` (the Excel cross-check) are unaffected
either way, since they only ever exercise the defaults.

## Outputs

Running the tool prints:

- **Payback** — the year cumulative cash flow turns non-negative (linearly interpolated within that year), or "No payback" if it never does within the horizon.
- **IRR** — internal rate of return over the full nominal cash-flow series.
- **NPV** — standard net present value: year-0 cash flow undiscounted, years 1..N discounted by `(1+WACC)^t`.
- A year-by-year table of revenue, costs, and cumulative cash flow (or every calculated column with `--full-table`).

## Validation against the source workbook

`scripts/validate_against_excel.py` re-derives the default scenario and
compares it against the cached values in `Business CasecSolar PV and
BESS.xlsx` (sheet `BC`, cells `C73`/`C74`/`C75`/`W70`/`AQ70`):

```bash
python3 scripts/validate_against_excel.py
# or, via Docker:
make validate
```

The same checks, plus a few extra scenarios (no-degradation, debt financing,
no-payback), are also in the pytest suite:

```bash
python3 -m pytest tests/
# or, via Docker:
make test
```

Both confirm the tool reproduces the workbook's cached Payback (≈9.87 years)
and IRR (≈7.35%) to about 10 significant digits under default inputs. NPV is
checked too, but note the source workbook's cached NPV (≈€77,065) uses
Excel's non-standard `NPV()` convention (see below) — the validation scripts
convert to that convention internally via `bess_bc.finance.excel_npv` before
comparing; the tool's own reported NPV (standard convention) is ≈€80,919 for
the same default scenario.

## Modeling notes / known quirks (inherited from the source workbook)

- **NPV convention**: the source workbook computes NPV as
  `=NPV(D31, C69:AQ69)`, i.e. it passes Excel's `NPV()` function the *entire*
  cash-flow range including year 0. Excel's `NPV()` discounts every value in
  its range, including the first one, so this effectively discounts the
  year-0 cash flow by one extra period versus the textbook definition (the
  standard approach would be `C69 + NPV(D31, D69:AQ69)`, adding year 0 back
  undiscounted). This tool reports the **standard** NPV, not this quirk;
  `bess_bc.finance.excel_npv()` still exists internally so the validation
  scripts can reproduce the source workbook's exact cached value.
- **Recurring grid fee is not scaled by BESS size** — despite being labeled
  "€/MW/year", the fixed yearly grid fee is applied as a flat € amount
  regardless of `bess_size_mw`. This matches the source formula exactly.
- **No battery replacement is modeled** — once the battery reaches
  `bess_lifetime_years`, all BESS revenue and opex (and the recurring grid
  fee, which is tied to the battery still operating) drop to zero for the
  rest of the horizon. There's no second-life or replacement capex.
- **Degradation curve source**: the source workbook has two degradation
  curves on its BC sheet (rows 38 and 39); only one of them (row 39) is
  actually wired into the revenue/cost formulas. This tool uses the
  formula-connected curve (see `bess_bc/soh.py`), generalized so it correctly
  respects `bess_lifetime_years` and `include_degradation` for any lifetime
  value (the original hardcoded the curve per year-column and ignored the
  lifetime input for years 1–20).
- **Interest is not tax-deductible** — taxable income is revenue minus
  opex/grid costs minus depreciation only; debt interest is applied after
  tax in the cash-flow waterfall, matching the source model.
- Dropped as dead inputs (present in the original sheet but never referenced
  by any formula): "Number of cycles", "Cycle value", "Include market
  development" flag. The Solar PV branch is dropped entirely per this tool's
  BESS-only scope.

## Project layout

```
Dockerfile / Makefile / .dockerignore   # Docker packaging (make build / make run)
bess_bc/
├── inputs.py     # BessInputs dataclass (all model inputs + validation)
├── soh.py        # Battery State-of-Health degradation curve
├── finance.py    # NPV / IRR / debt amortization helpers
├── engine.py     # Year-by-year cash flow table + summary metrics
└── cli.py        # Command-line interface
scripts/
└── validate_against_excel.py   # Cross-checks output against the source .xlsx
tests/
├── test_validate_defaults.py   # Excel-validated defaults, pytest suite
└── test_extensions.py          # Coverage for the opt-in "Extension" fields
```
