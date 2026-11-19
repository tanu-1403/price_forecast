# Methods: what each step does and why

Plain-language explanation of every method in the price pipeline. Each step lists **what** it
does, **why**, the **statistical point** to know, and its **limitation**. Code is in `src/`.

Pipeline: `extract → clean → aggregate (market-day → district-day → panel) → report`

---
## 1. Extraction (`src/extract.py`)
**What.** Reads the Hugging Face dataset `DHIVAKARNAIDUSUNKARI/mandi-india-daily-prices-2001-2026`
(yearly Parquet files, ~76 M rows, all India), and writes one file with only Maharashtra Wheat and Maize
for 2015 onward to `data/intermediate/maha_wheat_maize_raw.parquet`.

**Methods used.**
- *Download only needed years.* File names contain the year, so 2001–2014 are skipped. A file whose name has no year is kept (we cannot prove it is unneeded) and logged.
- *Skip files already on disk.* A file is reused only if it opens correctly, so a half-finished download is detected and fetched again. Failures are written to `logs/extract_failures.csv` and the run can simply be repeated.
- *DuckDB filtering.* DuckDB reads the Parquet files from disk and applies the state/commodity/date filter while reading, so the 76 M rows are never loaded into memory.
- *Schema check.* Before filtering, the code reads the real column names and stops with a clear message if an expected column is missing. Nothing is assumed.
- *Near-miss report.* It logs any commodity label containing "wheat", "maize" or "corn", so you can see if a variant (e.g. a differently spelt label) was not matched by the exact filter.
- *Traceability.* The source file name of every row is kept in `source_file`.

**Limitation.** The compiler says the data was "cleaned, processed and aggregated" but not how. We therefore re-check duplicates and outliers ourselves (step 2). The dataset contains no arrivals column.

---
## 2. Cleaning and validation (`src/clean.py`)
**What.** Standardises text, maps spelling variants of districts, and **flags** suspicious rows. **No row is deleted.**

**Methods used.**
- *Text standardisation.* Extra spaces removed, state and commodity upper-cased. The original district and market text stays in `district_raw` / `market_raw`.
- *District mapping table* (`config/district_map.csv`). Only names listed there are changed, so look-alike names are never merged automatically. Rows marked `REVIEW` (e.g. "Murum", which does not look like a district) are left unchanged and listed in `reports/data_quality/district_names_seen.csv`. **You must verify the proposed mappings.**
- *Flags.* `flag_bad_date`, `flag_missing_district_or_market`, `flag_nonpositive_modal`, `flag_min_gt_modal`, `flag_modal_gt_max`, `flag_min_gt_max`, `flag_price_outlier`, `flag_key_dup`, `flag_exact_dup`.
- *Outlier rule.* For each commodity: take the median modal price per day across all Maharashtra rows, then a centred 31-day rolling median of that. A row is an outlier if its price is below 0.4× or above 2.5× that reference. This catches unit errors (e.g. ₹2/quintal) but keeps genuine price spikes (genuine monthly moves are normally far smaller than 2.5×; check the flagged rows if you doubt this). Thresholds are in `src/config.py`.
- *Duplicates.* "Exact" duplicates (same key and same prices) are excluded from aggregation so they are not counted twice. "Key" duplicates (same market/variety/grade/day but different prices) are only flagged, because they may be real separate lots.
- *`usable` column.* A row is used in aggregation unless it has one of: bad date, missing district/market, non-positive modal price, outlier, exact duplicate. The min-vs-modal-vs-max inconsistencies are informational only, because the modal price is the target and these inconsistencies are common in mandi reporting; deleting them would remove genuine data.

**Statistical point.** Flagging instead of deleting keeps the analysis auditable: you can re-run with the flagged rows included and see whether the conclusions change.

---
## 3. Aggregation hierarchy (`src/aggregate.py`)
Raw rows → **mandi-day** → **district-day** → **calendar panel**.

### 3a. Mandi-day
One row per (date, district, market, commodity): the **simple mean of the usable variety/grade rows**. Rows per mandi-day and number of varieties are stored.
*Why first aggregate inside the mandi?* A mandi reporting three varieties should not count three times as much as a mandi reporting one. Test `test_aggregation_hierarchy_not_row_mean` shows the difference (2,550 vs a row-mean of 2,400).
*Limitation.* Different varieties have different quality/price levels, so the day's mean can move when the variety mix changes. Variety-level analysis is a later extension.

### 3b. District-day
One row per (date, district, commodity) from the mandi-day prices: `price_mean`, `price_median`, `price_sd`, `price_min`, `price_max`, `n_mandis`, `n_source_rows`.
**Primary target: `district_modal_price = price_mean`.**

*Why the simple mean?* The source has **no arrivals**, so an arrivals-weighted average is impossible; the equal-weight mean is the natural estimate of the average price among mandis that reported. The median is stored beside it. With 1–2 mandis the two are identical (the median of two numbers is their mean), and the report shows how often they differ by more than 2%.

*Important weakness (composition effect).* The set of reporting mandis changes from day to day. If a cheaper mandi starts reporting, the district mean falls even though no mandi's price changed. In your earlier run about 39% of district-days rested on a single mandi, so this effect is real. Mitigations to add later: mandi fixed effects (price relative to each mandi's own average), or modelling at mandi level. `n_mandis` is kept so that models can control for it.

### 3c. Calendar panel
For each district-commodity series with at least 365 observed days (`MIN_OBS_DAYS`), build a **complete daily calendar** from 2015-01-01 to the **last day actually observed** (not a configured future date). Columns: `observed` (1/0) and `in_window` (between the series' first and last observation).

*Why a complete calendar?* Mandis do not report every day, so "the previous row" is not "yesterday". A 7-day lag must mean 7 **calendar** days. `lag_calendar()` in `src/read_data.py` enforces this and refuses a sparse series.

*Why no forward-fill?* A missing day means "no report", not "price unchanged". Copying yesterday's price into the target would invent observations, understate volatility and flatter a "price stays the same" benchmark. Missing target days stay `NaN`; models later either skip them or are told explicitly.

*Thin series* (fewer than 365 observed days, e.g. maize in some districts) are left out and listed in `thin_series_excluded.csv`; they cannot support a time-series model.

---
## 4. Data-quality report (`src/report.py`)
Written to `reports/data_quality/` from the tables actually produced: date range, rows at each stage, flag counts, share of single-mandi district-days, mean-vs-median disagreement, year-wise coverage, per-series coverage (`observed_days / window_days`), districts seen, thin series, and **how many days old the newest price is** (a warning is logged if > 7 days).

*Why year-wise coverage?* Rising or falling price coverage can come from **more or fewer mandis reporting**, not from the market. Check coverage before interpreting a trend.

---
## 5. Reading data for analysis (`src/read_data.py`)
Same role as `read_data.py` in the original `forecasting_agro` repo. `load_panel`, `load_series` (complete daily index) and `lag_calendar`. Later modules (`eda.py`, `model_*.py`, `predict.py`) start from here.

---
## 6. Not done yet (planned, in order)
1. EDA (trends, seasonality, district comparison, reporting coverage).
2. Calendar features (lags 1/7/14/30/90, rolling means/SDs, season dummies), built only from past data.
3. Benchmarks (naive, seasonal naive), then ARIMA/SARIMA, GARCH, Random Forest, XGBoost, LSTM.
4. Chronological split (train 2015–2023, validation 2024, test 2025–2026, adjusted to real coverage). **No random splits.** Metrics: MAE, RMSE, MAPE (guarding near-zero), sMAPE, directional accuracy, each versus the naive benchmark.
5. External variables (see `DATA_SOURCES.md`), each joined on `(district, date)` using only information available at forecast time.

## 7. Known limitations
- Source ends **20 April 2026** for these crops (as observed in your extraction run); the period after is missing.
- No arrivals data; arrival-weighted prices are impossible.
- District-day prices rest on few mandis (median 2); composition effect described in 3b.
- The upstream compilation's own cleaning is undocumented, and its `LICENSE` file is empty. Cite the original source (Agmarknet via data.gov.in, GODL-India) and the compiler, and check the Kaggle page's own terms.
