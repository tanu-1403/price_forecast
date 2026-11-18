# Maharashtra Daily Crop Price Forecast (Wheat & Maize)

Forecasts the **daily mandi price (Rs per quintal)** of **wheat** and **maize** in **Maharashtra**
for the next N days. Adapted from the `forecasting_agro` project (monthly World Bank prices ->
daily Agmarknet mandi prices).

## What changed compared with the original repo

| Original (`forecasting_agro`) | This repo |
|---|---|
| World Bank Pink Sheet, **monthly**, USD/tonne, Soy / Wheat / Beef | Agmarknet mandi data, **daily**, Rs/quintal, **Maharashtra Wheat & Maize** |
| One global price per month | Median modal price across all reporting Maharashtra mandis per day |
| Lags 1 & 12 months, month dummies | Daily lags, rolling stats, momentum, day-of-week, day-of-year sin/cos |
| Predicts price level | Predicts 1-day **log-return**, then rebuilds price (trees can't extrapolate levels) |
| SARIMAX / XGBoost / LSTM in notebooks | XGBoost in scripts (SARIMAX/LSTM dropped, see "Extensions") |
| Compared models only against each other | Compared against a **naive "price stays the same" baseline** over 1/3/7/14-day horizons |
| Manual run | CLI + one-command daily job + GitHub Actions cron |

## Layout
```
src/config.py          commodities, state, API id, horizons  (edit here)
src/fetch_data.py      data.gov.in API fetch + CSV backfill importer
src/data.py            raw mandi rows -> clean daily series
src/features.py        feature engineering
src/models.py          XGBoost (falls back to sklearn GB if xgboost missing) + recursive forecast
src/train.py           tuning, walk-forward backtest vs naive, saves models/<crop>_model.pkl
src/predict.py         N-day forecast + 80% band -> output/forecast_<crop>.csv / .png
src/run_daily.py       fetch -> retrain -> forecast, in one command
src/make_synthetic.py  FAKE data generator, for testing the pipeline only
tests/                 smoke tests
.github/workflows/daily.yml   runs run_daily every evening
```

## Setup
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Getting the data (the part that decides whether this works)

The free data.gov.in mandi API only returns the **latest day(s)**, not history. You need history to train
(>= 300 days, ideally 3+ years). So:

1. **Backfill once.** Download historical Maharashtra Wheat / Maize daily prices as CSV from
   [agmarknet.gov.in](https://agmarknet.gov.in) (Price & Arrivals reports), data.gov.in, or a Kaggle mirror, then:
   ```bash
   python -m src.fetch_data --commodity wheat --import-csv path/to/wheat_history.csv
   python -m src.fetch_data --commodity maize --import-csv path/to/maize_history.csv
   ```
   Columns needed (any common Agmarknet header style works): state, market, commodity, arrival date, modal price.
2. **Get a free API key** at https://data.gov.in and `export DATA_GOV_API_KEY=your_key`.
3. **Fetch daily** (appends to `data/raw/<crop>.csv`):
   ```bash
   python -m src.fetch_data
   ```

## Run
```bash
python -m src.train   --commodity all            # tune + backtest + save models   (add --no-tune for speed)
python -m src.predict --commodity all --days 14  # writes output/forecast_wheat.csv, forecast_maize.csv, PNGs
```
Or everything at once: `python -m src.run_daily`.

Try it first on fake data: `python -m src.make_synthetic && python -m src.train --synthetic && python -m src.predict --synthetic`

## Daily automation
Push the repo to GitHub, add repo secret `DATA_GOV_API_KEY`, commit your backfilled `data/raw/*.csv`.
`.github/workflows/daily.yml` then fetches, retrains and commits fresh forecasts every day at 20:00 IST.
(Or use cron / Windows Task Scheduler to run `python -m src.run_daily`.)

## Output
`output/forecast_<crop>.csv`: date, forecast_rs_per_quintal, lower_80, upper_80, last actual date/price.
The forecast starts the day after the **last date in your data**. If the API is a few days stale, the
first rows are already in the past. The 80% band is approximate (backtest 1-day error x sqrt(horizon)).

## Read this before trusting the numbers
* **Daily mandi prices are close to a random walk.** The backtest prints, for every horizon, whether the model
  beats the naive baseline. If it doesn't for your data, believe that message over the model.
* Mandi prices are driven by things not in this model: MSP announcements, export/import duty changes, stock limits,
  monsoon / rabi weather, and (for maize) ethanol and poultry-feed demand. Add them as features (below).
* Median across mandis hides regional gaps. For one mandi (e.g. Pune or Nagpur) filter `market` in
  `src/data.py::build_daily_series` before the groupby.
* Sundays/holidays are forward-filled (max 7 days) and then forecasted like any other day.
* Synthetic data is for testing the code only.

## Extensions
* Per-mandi models, arrival volumes (the API has no quantity; Agmarknet reports do), rainfall/temperature
  (IMD / NASA POWER), MSP as a step feature, international wheat/maize price, USD-INR.
* Re-add SARIMAX/LSTM from the original notebooks as extra candidates in `src/models.py`.
* Direct multi-horizon models (one per horizon) instead of recursive if 7-14 day accuracy matters.
