# Maharashtra Wheat & Maize: Daily Mandi Price Data Pipeline

Builds a clean, district-level **daily modal price (₹/quintal)** dataset for **Wheat** and **Maize** in
Maharashtra from 2015, as the foundation for price forecasting and for studying how weather, soil,
MSP and market variables influence cereal prices.
**Stage 1 (this repo now): prices only.** Forecast models and external variables are added later
on top of the same table (see `docs/METHODS.md`, section 6).

Layout follows the original `forecasting_agro` reference (`src/read_data.py` → eda → models → predict, `output/`),
with data-preparation steps added in front.

## Data source
Third-party Parquet copy on Hugging Face (`DHIVAKARNAIDUSUNKARI/mandi-india-daily-prices-2001-2026`) of
Agmarknet daily prices (data.gov.in "Variety-wise Daily Market Prices", GODL-India). The dataset has **no
arrivals** column. Please cite the original source and the compiler. Details: `docs/DATA_SOURCES.md`.

## Quick start (Windows)
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.run_pipeline
python -m pytest -q
```
Options: `--steps clean aggregate report` (skip download/extract), `--raw-dir <folder>` (reuse downloaded files),
`--force` (redo extraction), `--start/--end`.

## Pipeline
```
extract   Hugging Face yearly Parquet → data/intermediate/maha_wheat_maize_raw.parquet   (DuckDB, only needed years)
clean     standardise + FLAG (never delete) → data/intermediate/prices_clean.parquet
aggregate variety rows → mandi-day → district-day → complete daily panel → data/processed/*.csv
report    reports/data_quality/*   (coverage, flags, staleness warning)
```

## Output tables (`data/processed/`)
| File | One row per | Key columns |
|---|---|---|
| `market_daily.csv` | date × market × commodity | `mandi_modal_price`, `n_rows`, `n_varieties` |
| `district_daily.csv` | date × district × commodity | `district_modal_price` (= `price_mean`), `price_median`, `price_sd`, `price_min/max`, `n_mandis`, `n_source_rows` |
| `district_panel.csv` | every calendar day × district × commodity | as above + `observed` (0/1), `in_window`; missing days are **NaN, not filled** |

## Folder structure
```
config/district_map.csv   reviewed district spelling map
data/{raw,intermediate,processed,external}/   (contents not tracked by git)
docs/                     METHODS.md  DATA_SOURCES.md  MIGRATION.md
reports/data_quality/     generated reports
src/                      config, extract, clean, aggregate, report, read_data, run_pipeline
tests/                    unit tests
data/extract.ipynb        original extraction draft (kept for reference, not used)
```

## Status and limits
- Source ends **20 Apr 2026** for these crops; the report warns when the newest price is stale.
- Rows per district-day are few (often 1–2 mandis): see the composition-effect note in `docs/METHODS.md`.
- `config/district_map.csv` contains **proposed** mappings that you must verify.
- Not yet built: EDA, features, models, external variables.
