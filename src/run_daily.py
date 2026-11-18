"""One-shot daily job: fetch today's prices -> retrain -> forecast.   python -m src.run_daily"""
import argparse
import os

from .config import COMMODITIES
from .fetch_data import append_to_store, fetch_snapshot
from .predict import forecast
from .train import train


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--no-tune", action="store_true")
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()
    key = os.getenv("DATA_GOV_API_KEY")
    for k, name in COMMODITIES.items():
        if not a.skip_fetch:
            if not key:
                raise SystemExit("Set DATA_GOV_API_KEY or pass --skip-fetch")
            snap = fetch_snapshot(name, key)
            if not snap.empty:
                append_to_store(snap, k)
        train(k, tune=not a.no_tune)
        forecast(k, a.days)
        print(f"[{k}] done -> output/forecast_{k}.csv")


if __name__ == "__main__":
    main()
