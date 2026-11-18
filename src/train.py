"""Train + backtest the daily price model.   python -m src.train --commodity all"""
import argparse
import json

import joblib
import numpy as np
import pandas as pd

from .config import (COMMODITIES, HORIZON_DAYS, MAX_DAILY_MOVE, MIN_HISTORY_DAYS, MODEL_DIR,
                     OUT_DIR, SYN_DIR, TEST_DAYS)
from .data import load_daily
from .features import make_features, make_target
from .models import fit_model, recursive_forecast


def build_xy(price: pd.Series):
    X = make_features(price)
    y = make_target(price, 1)
    d = X.join(y).dropna()
    return d.drop(columns="target"), d["target"]


def backtest(price, model, feature_names, split_date, horizon, stride=3):
    """Walk-forward test on the held-out tail: every `stride` days, forecast `horizon`
    days ahead from real history and compare with what actually happened.
    Baseline = 'tomorrow's price equals today's price' (naive)."""
    idx = price.index
    origins = [t for t in idx[idx >= split_date] if t + pd.Timedelta(days=horizon) <= idx[-1]][::stride]
    rows = []
    for t in origins:
        hist = price.loc[:t]
        fc = recursive_forecast(model, feature_names, hist, horizon)
        act = price.reindex(fc.index)
        for h, (f, a) in enumerate(zip(fc.values, act.values), start=1):
            rows.append(dict(origin=t, h=h, actual=a, model=f, naive=hist.iloc[-1]))
    bt = pd.DataFrame(rows)
    bt["model_ape"] = (bt["model"] - bt["actual"]).abs() / bt["actual"] * 100
    bt["naive_ape"] = (bt["naive"] - bt["actual"]).abs() / bt["actual"] * 100
    bt["model_ae"] = (bt["model"] - bt["actual"]).abs()
    bt["naive_ae"] = (bt["naive"] - bt["actual"]).abs()
    return bt


def summarise(bt, horizon):
    out = {}
    for h in sorted({1, 3, 7, horizon}):
        if h > horizon:
            continue
        s = bt[bt.h == h]
        out[f"h{h}"] = dict(
            model_mape=round(s.model_ape.mean(), 2), naive_mape=round(s.naive_ape.mean(), 2),
            model_mae=round(s.model_ae.mean(), 1), naive_mae=round(s.naive_ae.mean(), 1),
            n=int(len(s)))
    return out


def train(key, raw_dir=None, tune=True, test_days=TEST_DAYS, horizon=HORIZON_DAYS, verbose=True):
    daily = load_daily(key, raw_dir)
    price = daily["price"]
    if len(price) < MIN_HISTORY_DAYS:
        raise ValueError(f"[{key}] only {len(price)} days of history; need >= {MIN_HISTORY_DAYS}. "
                         f"Backfill more data (see README).")

    X, y = build_xy(price)
    split_date = X.index[-1] - pd.Timedelta(days=test_days)
    Xtr, ytr = X[X.index < split_date], y[y.index < split_date]
    Xte, yte = X[X.index >= split_date], y[y.index >= split_date]

    # 1) honest evaluation: fit on the past only, test on the held-out tail
    m_eval, name, params = fit_model(Xtr, ytr, tune)
    sigma = float((yte - m_eval.predict(Xte)).std())           # 1-day return error -> used for intervals
    bt = backtest(price[price.index < X.index[-1]], m_eval, list(X.columns), split_date, horizon)
    metrics = summarise(bt, horizon)

    # 2) final model: refit on ALL data
    model, _, params = fit_model(X, y, tune)

    bundle = dict(model=model, feature_names=list(X.columns), commodity=key, model_name=name,
                  params=params, sigma=sigma, trained_through=str(price.index[-1].date()),
                  n_days=int(len(price)), metrics=metrics)
    MODEL_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)
    joblib.dump(bundle, MODEL_DIR / f"{key}_model.pkl")
    (MODEL_DIR / f"{key}_metrics.json").write_text(json.dumps(
        dict(trained_through=bundle["trained_through"], model=name, params={k: int(v) for k, v in params.items()},
             sigma_1d=round(sigma, 5), backtest=metrics), indent=2))
    bt.to_csv(OUT_DIR / f"backtest_{key}.csv", index=False)

    if verbose:
        print(f"\n[{key}] {name}  history={len(price)} days  trained through {bundle['trained_through']}")
        print(f"[{key}] backtest on last {test_days} days  (MAPE % / MAE Rs per quintal; lower is better)")
        for h, m in metrics.items():
            verdict = "BEATS naive" if m["model_mape"] < m["naive_mape"] else "does NOT beat naive"
            print(f"   {h:>4}: model {m['model_mape']:.2f}% / {m['model_mae']:.0f}   "
                  f"naive {m['naive_mape']:.2f}% / {m['naive_mae']:.0f}   -> {verdict}")
    return bundle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commodity", choices=list(COMMODITIES) + ["all"], default="all")
    ap.add_argument("--raw-dir", help="Folder with <commodity>.csv (default data/raw)")
    ap.add_argument("--synthetic", action="store_true", help="Use data/synthetic (demo data)")
    ap.add_argument("--no-tune", action="store_true", help="Skip grid search (faster)")
    ap.add_argument("--test-days", type=int, default=TEST_DAYS)
    ap.add_argument("--horizon", type=int, default=HORIZON_DAYS)
    a = ap.parse_args()
    raw_dir = a.raw_dir or (SYN_DIR if a.synthetic else None)
    for k in (COMMODITIES if a.commodity == "all" else [a.commodity]):
        train(k, raw_dir, tune=not a.no_tune, test_days=a.test_days, horizon=a.horizon)


if __name__ == "__main__":
    main()
