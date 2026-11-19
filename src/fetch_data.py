"""Download daily mandi prices for Maharashtra from data.gov.in (Agmarknet).

IMPORTANT: this API returns the *latest* day(s) of prices, not a full archive.
So the workflow is:
  1. Backfill history ONCE from a CSV export (Agmarknet / data.gov.in / Kaggle):
         python -m src.fetch_data --commodity wheat --import-csv path/to/file.csv
  2. Run `python -m src.fetch_data` every day (cron / GitHub Actions). Each run
     appends the newest snapshot to data/raw/<commodity>.csv, so history keeps growing.

Get a free API key at https://data.gov.in (Register -> My Account) and export it:
    export DATA_GOV_API_KEY=xxxx
"""
import argparse
import os
import sys
import time

import pandas as pd
import requests

from .config import API_URL, COMMODITIES, RAW_DIR, STATE

RAW_COLS = ["state", "district", "market", "commodity", "variety", "grade",
            "arrival_date", "min_price", "max_price", "modal_price"]


def fetch_snapshot(commodity: str, api_key: str, state: str = STATE,
                   page_size: int = 500, max_pages: int = 50) -> pd.DataFrame:
    rows, offset = [], 0
    for _ in range(max_pages):
        params = {"api-key": api_key, "format": "json", "limit": page_size,
                  "offset": offset, "filters[state]": state,
                  "filters[commodity]": commodity}
        for attempt in range(3):
            try:
                r = requests.get(API_URL, params=params, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(3 * (attempt + 1))
        recs = r.json().get("records", [])
        rows += recs
        if len(recs) < page_size:
            break
        offset += page_size
    return pd.DataFrame(rows)


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Make API output and the various Agmarknet CSV exports look the same."""
    df = df.rename(columns=lambda c: c.strip().lower().replace("_x0020_", "_").replace(" ", "_"))
    df = df.rename(columns={"modal": "modal_price", "min": "min_price", "max": "max_price",
                            "price_date": "arrival_date", "reported_date": "arrival_date",
                            "market_name": "market", "district_name": "district",
                            "state_name": "state", "commodity_name": "commodity"})
    for c in ["min_price", "max_price", "modal_price"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["arrival_date", "modal_price"])
    df = df[df["modal_price"] > 0]
    return df[[c for c in RAW_COLS if c in df.columns]]


def append_to_store(new: pd.DataFrame, key: str) -> pd.DataFrame:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{key}.csv"
    new = normalise(new)
    if path.exists():
        old = pd.read_csv(path, parse_dates=["arrival_date"])
        new = pd.concat([old, new], ignore_index=True)
    dedup = [c for c in ["market", "variety", "grade", "arrival_date"] if c in new.columns]
    new = new.drop_duplicates(subset=dedup, keep="last").sort_values("arrival_date")
    new.to_csv(path, index=False)
    return new


def import_csv(csv_path: str, key: str) -> pd.DataFrame:
    """Backfill history from a CSV you downloaded manually."""
    df = normalise(pd.read_csv(csv_path))
    if "state" in df.columns:
        df = df[df["state"].str.strip().str.lower() == STATE.lower()]
    if "commodity" in df.columns:
        df = df[df["commodity"].str.strip().str.lower() == COMMODITIES[key].lower()]
    out = append_to_store(df, key)
    print(f"[{key}] store now has {len(out):,} rows, "
          f"{out['arrival_date'].min().date()} -> {out['arrival_date'].max().date()}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commodity", choices=list(COMMODITIES) + ["all"], default="all")
    ap.add_argument("--import-csv", help="Backfill from a downloaded CSV instead of calling the API")
    args = ap.parse_args()
    keys = list(COMMODITIES) if args.commodity == "all" else [args.commodity]

    if args.import_csv:
        if len(keys) != 1:
            sys.exit("Use --commodity wheat|maize together with --import-csv")
        import_csv(args.import_csv, keys[0])
        return

    api_key = os.getenv("579b464db66ec23bdd000001f5961e2a74914c76781b5b89945bb5af")
    if not api_key:
        sys.exit("Set DATA_GOV_API_KEY (free key from https://data.gov.in)")
    for k in keys:
        snap = fetch_snapshot(COMMODITIES[k], api_key)
        if snap.empty:
            print(f"[{k}] API returned no rows today")
            continue
        out = append_to_store(snap, k)
        print(f"[{k}] fetched {len(snap)} rows; store now {len(out):,} rows, "
              f"latest {out['arrival_date'].max().date()}")


if __name__ == "__main__":
    main()
