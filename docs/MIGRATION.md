# Updating your EXISTING repo in place (no delete-and-recreate)

Your repo keeps its history. We change it on a **new branch**, so `main` stays exactly as it is until you decide to merge.
Nothing here commits or pushes for you.

## Before anything: the API key
The key in `src/fetch_data.py` (commit `c738784`, also pushed to `origin/main`) must be **revoked and regenerated at data.gov.in**. This update deletes that file from the working tree, but git history still contains the key.

## What changes

| Action | Files |
|---|---|
| **Keep unchanged** | `data/extract.ipynb` (your original extraction draft), `src/__init__.py`, `tests/__init__.py`, `.git/` |
| **Edit (rewritten)** | `README.md`, `requirements.txt`, `.gitignore`, `src/config.py` |
| **Add** | `src/extract.py`, `src/clean.py`, `src/aggregate.py`, `src/report.py`, `src/read_data.py`, `src/run_pipeline.py`, `tests/test_pipeline.py` (replaces the old one), `config/district_map.csv`, `docs/METHODS.md`, `docs/DATA_SOURCES.md`, `docs/MIGRATION.md`, `CHANGELOG.md`, folder placeholders (`data/raw`, `data/intermediate`, `data/processed`, `data/external`, `logs`, `output`, `reports/data_quality`) |
| **Remove (old, synthetic or unsafe)** | `.github/workflows/daily.yml`, `models/*`, `output/*` (synthetic forecasts), `src/data.py`, `src/features.py`, `src/fetch_data.py`, `src/make_synthetic.py`, `src/models.py`, `src/predict.py`, `src/run_daily.py`, `src/train.py`, `tests/test_agmarket.py`, `data/synthetic/` (untracked) |

Removed code is **not lost**: it stays in git history. To look at an old file later:
`git show b5d2977:src/train.py` (b5d2977 = your latest commit, "base 03").
The modelling code returns later, rebuilt for district-level data (see `METHODS.md`, section 6).

## Route A: apply the patch (recommended)
Open a terminal in your repo folder (File Explorer → address bar → type `cmd`), then:
```
git status
git stash push -u -m "before-prices-pipeline"
git switch -c prices-pipeline
git apply --check update.patch
git apply update.patch
git status
```
- `git stash` safely stores your uncommitted changes (including the deleted workflow and modified synthetic outputs). Restore them any time with `git stash pop`.
- Put `update.patch` in the repo folder first (or give its full path).
- If `git apply --check` complains about **whitespace or line endings** (common on Windows), use `git apply --ignore-whitespace update.patch` instead.
- If it still fails, use Route B.

Then:
```
rmdir /s /q data\synthetic
pip install -r requirements.txt
python -m pytest -q
```
When you are happy: `git add -A` and `git commit -m "Prices-only pipeline"` (your decision; merge into `main` when ready).

## Route B: copy files (no patch tooling)
1. `git switch -c prices-pipeline`
2. Unzip `maha_price_forecast_updated.zip` somewhere and copy **everything except the `.git` folder** over your repo folder, replacing files when asked.
3. Remove the old files:
```
git rm -r .github models output src/data.py src/features.py src/fetch_data.py src/make_synthetic.py src/models.py src/predict.py src/run_daily.py src/train.py tests/test_agmarket.py
rmdir /s /q data\synthetic
```
(If some path says "did not match any files", it was already removed; ignore it.)

## Check it worked
```
python -m pytest -q          # 6 tests should pass
python -m src.run_pipeline   # downloads, cleans, aggregates, reports (see DATA_SOURCES.md)
```
Look at `reports\data_quality\data_quality_summary.json` afterwards.

## Using your existing output folder
Your earlier run saved the 26 downloaded files in `Documents\PROJECT 4\output\mandi_prices\raw`. Reuse them instead of downloading again:
`python -m src.run_pipeline --raw-dir "C:\Users\DELL\Documents\PROJECT 4\output\mandi_prices\raw"`
The new pipeline re-creates the cleaned/aggregated tables itself, so the old CSVs are only a backup.
