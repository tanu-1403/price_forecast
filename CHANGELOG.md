# Changelog

## 2026-11-19: prices-only pipeline (branch `prices-pipeline`)

### Before this change
- Repo held a state-level forecasting prototype (XGBoost, synthetic demo data, a data.gov.in "current price" fetcher), committed models/forecasts built from **synthetic** data, and `data/extract.ipynb` (extraction draft with row-by-row Python loops).
- A real API key was hard-coded in `src/fetch_data.py` (revoke it).

### Added
`src/extract.py`, `clean.py`, `aggregate.py`, `report.py`, `read_data.py`, `run_pipeline.py`; `config/district_map.csv`; `tests/test_pipeline.py` (6 tests); `docs/METHODS.md`, `docs/DATA_SOURCES.md`, `docs/MIGRATION.md`; folder placeholders.

### Changed
- `src/config.py`: rewritten for the new pipeline (paths relative to the repo, thresholds in one place).
- `README.md`, `requirements.txt` (now pandas, numpy, duckdb, pyarrow, huggingface_hub, pytest), `.gitignore` (data and logs not tracked).

### Removed (still in git history)
`src/data.py`, `features.py`, `fetch_data.py`, `make_synthetic.py`, `models.py`, `predict.py`, `run_daily.py`, `train.py`, `tests/test_agmarket.py`, old `tests/test_pipeline.py`, `.github/workflows/daily.yml`, `models/*`, `output/*`, `data/synthetic/`.

### Left unchanged
`data/extract.ipynb`, `src/__init__.py`, `tests/__init__.py`, git history. The upstream Hugging Face dataset is never modified.

### Changes in data definitions
- Rows with odd min/modal/max order are **flagged, not deleted**; only five flag types remove a row from aggregation (bad date, missing district/market, non-positive modal price, price outlier, exact duplicate).
- Prices are **never forward-filled**; the panel is a complete calendar with `observed` indicator, ending at the last observed date (not a configured future date).
- Series with < 365 observed days are excluded from the panel (listed in the report).
- The arrival-weighting branch was removed: the source has no arrivals.
- District spelling variants mapped only through the reviewed table `config/district_map.csv`.

### Efficiency
Row-by-row Python aggregation (≈22 minutes in the earlier run) replaced by vectorised pandas; on a 345,000-row mock table the clean→aggregate→report chain took ≈9 seconds (mock data, not the real file). Extraction downloads only the needed years and filters inside DuckDB.

### Remaining limitations
Data ends 20 Apr 2026; no arrivals; composition effect in district averages; extraction step (Hugging Face / DuckDB) could not be run in the build environment and is verified only against your earlier successful run and the dataset page; no models or external variables yet.

### Reproduce
`pip install -r requirements.txt && python -m src.run_pipeline && python -m pytest -q`
