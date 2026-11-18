"""Smoke test on synthetic data:  pytest -q"""
import numpy as np
import pandas as pd

from src import config, predict, train
from src.data import build_daily_series
from src.fetch_data import normalise
from src.make_synthetic import generate


def test_normalise_handles_agmarknet_export_headers():
    raw = pd.DataFrame({"State": ["Maharashtra"], "Commodity": ["Wheat"], "Market": ["Pune"],
                        "Arrival_Date": ["05/03/2025"], "Min_x0020_Price": ["2300"],
                        "Max_x0020_Price": ["2500"], "Modal_x0020_Price": ["2400"]})
    out = normalise(raw)
    assert out.loc[0, "modal_price"] == 2400 and out.loc[0, "arrival_date"] == pd.Timestamp("2025-03-05")


def test_daily_series_is_continuous():
    daily = build_daily_series(generate("wheat", years=2))
    assert daily.index.is_monotonic_increasing
    assert (daily.index.to_series().diff().dropna() == pd.Timedelta(days=1)).all()
    assert daily["price"].notna().all()


def test_train_and_predict(tmp_path, monkeypatch):
    monkeypatch.setattr(train, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(train, "OUT_DIR", tmp_path)
    monkeypatch.setattr(predict, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(predict, "OUT_DIR", tmp_path)
    (tmp_path / "raw").mkdir()
    generate("maize", years=3).to_csv(tmp_path / "raw" / "maize.csv", index=False)

    train.train("maize", tmp_path / "raw", tune=False, test_days=60, horizon=7, verbose=False)
    out = predict.forecast("maize", 7, tmp_path / "raw")
    assert len(out) == 7
    assert (out.forecast_rs_per_quintal > 0).all()
    assert (out.lower_80 <= out.forecast_rs_per_quintal).all() and (out.forecast_rs_per_quintal <= out.upper_80).all()
