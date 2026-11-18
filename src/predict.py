"""Forecast the next N days.   python -m src.predict --commodity all --days 14"""
import argparse

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import COMMODITIES, HORIZON_DAYS, MODEL_DIR, OUT_DIR, SYN_DIR
from .data import load_daily
from .models import recursive_forecast

Z80 = 1.2816   # 80 % interval


def forecast(key, days=HORIZON_DAYS, raw_dir=None, save=True):
    bundle = joblib.load(MODEL_DIR / f"{key}_model.pkl")
    price = load_daily(key, raw_dir)["price"]
    fc = recursive_forecast(bundle["model"], bundle["feature_names"], price, days)

    # Approximate interval: 1-day backtest error grows with sqrt(horizon) (random-walk assumption)
    h = np.arange(1, days + 1)
    band = Z80 * bundle["sigma"] * np.sqrt(h)
    out = pd.DataFrame({
        "date": fc.index.date,
        "commodity": COMMODITIES[key],
        "state": "Maharashtra",
        "forecast_rs_per_quintal": fc.values.round(0),
        "lower_80": (fc.values * np.exp(-band)).round(0),
        "upper_80": (fc.values * np.exp(band)).round(0),
    })
    out["last_actual_date"] = price.index[-1].date()
    out["last_actual_price"] = round(float(price.iloc[-1]), 0)

    if save:
        OUT_DIR.mkdir(exist_ok=True)
        out.to_csv(OUT_DIR / f"forecast_{key}.csv", index=False)
        hist = price.iloc[-120:]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(hist.index, hist.values, label="Actual (Maharashtra median modal price)")
        ax.plot(fc.index, fc.values, "--", color="orange", label="Forecast")
        ax.fill_between(fc.index, out["lower_80"], out["upper_80"], alpha=0.25, color="orange", label="80% band")
        ax.set_title(f"{COMMODITIES[key]} - Maharashtra daily price forecast")
        ax.set_ylabel("Rs per quintal")
        ax.grid(True)
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT_DIR / f"forecast_{key}.png", dpi=120)
        plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commodity", choices=list(COMMODITIES) + ["all"], default="all")
    ap.add_argument("--days", type=int, default=HORIZON_DAYS)
    ap.add_argument("--raw-dir")
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    raw_dir = a.raw_dir or (SYN_DIR if a.synthetic else None)
    for k in (COMMODITIES if a.commodity == "all" else [a.commodity]):
        out = forecast(k, a.days, raw_dir)
        print(f"\n{COMMODITIES[k]} - Maharashtra (Rs/quintal), last actual "
              f"{out.last_actual_date.iloc[0]}: {out.last_actual_price.iloc[0]:.0f}")
        print(out[["date", "forecast_rs_per_quintal", "lower_80", "upper_80"]].to_string(index=False))


if __name__ == "__main__":
    main()
