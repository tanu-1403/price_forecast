"""Unit tests on tiny hand-made tables with known answers.   pytest -q"""
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from src import aggregate, clean, config, report
from src.extract import pick_files
from src.read_data import lag_calendar


def _raw(rows):
    cols = ["State", "District", "Market", "Commodity", "Variety", "Grade", "Arrival_Date",
            "Min_Price", "Max_Price", "Modal_Price"]
    return pd.DataFrame(rows, columns=cols)


def _base_rows(n_days=40):
    """Stable background prices so the rolling-median reference exists."""
    rows = []
    for d in pd.date_range("2024-01-01", periods=n_days):
        for m in ("A", "B", "C", "D", "E"):
            rows.append(["Maharashtra", "Pune", m, "Wheat", "Lokwan", "FAQ", d, 2400, 2600, 2500])
    return rows


DMAP = pd.DataFrame({"source_name": ["Amarawati", "Murum"], "canonical_name": ["Amravati", ""],
                     "status": ["x", "REVIEW"], "note": ["", ""]})


def test_pick_files_selects_years_and_keeps_unknown():
    files = ["data/x/mandi_daily_2014.parquet", "data/x/mandi_daily_2015.parquet",
             "data/x/mandi_daily_2026.parquet", "data/x/notes.parquet"]
    sel, unknown = pick_files(files, 2015, 2026)
    assert sel == files[1:]            # 2014 skipped, unknown-name file kept
    assert unknown == ["data/x/notes.parquet"]


def test_clean_flags_but_never_drops():
    rows = _base_rows()
    extra = [
        ["Maharashtra", "Pune", "A", "Wheat", "Dara", "FAQ", pd.Timestamp("2024-01-10"), 2300, 2500, 2400],   # key dup w/ base (variety differs -> not dup)
        ["Maharashtra", "Pune", "F", "Wheat", "Lokwan", "FAQ", pd.Timestamp("2024-01-10"), 1, 3, 2],          # price 2 -> outlier
        ["Maharashtra", "Pune", "G", "Wheat", "Lokwan", "FAQ", pd.Timestamp("2024-01-11"), 2600, 2700, 2500],  # min > modal
        ["Maharashtra", "Pune", "H", "Wheat", "Lokwan", "FAQ", pd.Timestamp("2024-01-11"), 2400, 2450, 2500],  # modal > max
        ["Maharashtra", "Pune", "I", "Wheat", "Lokwan", "FAQ", pd.Timestamp("2024-01-12"), 0, 0, 0],           # non-positive
        ["Maharashtra", "Pune", "J", "Wheat", "Lokwan", "FAQ", "not a date", 2400, 2600, 2500],                # bad date
        ["Maharashtra", " Amarawati ", "K", "Wheat", "Lokwan", "FAQ", pd.Timestamp("2024-01-12"), 2400, 2600, 2500],
        ["Maharashtra", "Pune", "A", "Wheat", "Lokwan", "FAQ", pd.Timestamp("2024-01-01"), 2400, 2600, 2500],  # exact duplicate of a base row
    ]
    raw = _raw(rows + extra)
    out, s = clean.clean_prices(raw, DMAP)

    assert len(out) == len(raw)                                  # nothing dropped
    assert s["flag_price_outlier"] == 1 and s["flag_nonpositive_modal"] == 1
    assert s["flag_bad_date"] == 1 and s["flag_exact_dup"] == 1
    assert s["flag_min_gt_modal"] == 1 and s["flag_modal_gt_max"] == 1
    assert s["usable_rows"] == len(raw) - 4                      # outlier, <=0, bad date, exact dup excluded
    k = out[out["market"] == "K"].iloc[0]
    assert k["district"] == "Amravati" and k["district_raw"] == " Amarawati "   # mapped, original preserved
    assert out["state"].eq("MAHARASHTRA").all() and out["commodity"].eq("WHEAT").all()


def test_aggregation_hierarchy_not_row_mean():
    d = pd.Timestamp("2024-03-01")
    raw = _raw([  # mandi A has two varieties, mandi B one
        ["Maharashtra", "Pune", "A", "Wheat", "V1", "FAQ", d, 1900, 2100, 2000],
        ["Maharashtra", "Pune", "A", "Wheat", "V2", "FAQ", d, 2100, 2300, 2200],
        ["Maharashtra", "Pune", "B", "Wheat", "V1", "FAQ", d, 2900, 3100, 3000],
    ])
    c, _ = clean.clean_prices(raw, DMAP)
    mk = aggregate.market_daily(c)
    a = mk[mk["market"] == "A"].iloc[0]
    assert a["mandi_modal_price"] == 2100 and a["n_rows"] == 2 and a["n_varieties"] == 2
    dd = aggregate.district_daily(mk).iloc[0]
    assert dd["price_mean"] == (2100 + 3000) / 2 == 2550         # NOT the row mean (2400)
    assert dd["price_median"] == 2550 and dd["n_mandis"] == 2 and dd["n_source_rows"] == 3
    assert round(dd["price_sd"], 3) == round(np.std([2100, 3000], ddof=1), 3)
    assert dd["district_modal_price"] == dd["price_mean"]


def test_panel_calendar_no_forward_fill_and_thin_excluded():
    dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-05", "2024-01-08"])
    dd = pd.DataFrame({"arrival_date": dates, "district": "Pune", "commodity": "WHEAT",
                       "price_mean": [10., 11., 12., 13.], "price_median": [10., 11., 12., 13.],
                       "price_sd": np.nan, "price_min": 1., "price_max": 1.,
                       "n_mandis": 1, "n_source_rows": 1})
    dd["district_modal_price"] = dd["price_mean"]
    thin_row = dd.iloc[:1].assign(district="Tiny")
    both = pd.concat([dd, thin_row], ignore_index=True)
    panel, thin = aggregate.build_panel(both, min_obs=4)

    assert set(panel["district"]) == {"Pune"} and thin["district"].tolist() == ["Tiny"]
    assert len(panel) == 8                                        # 2024-01-01 .. 2024-01-08 inclusive
    assert panel["arrival_date"].max() == pd.Timestamp("2024-01-08")   # ends at last OBSERVED day
    assert panel["observed"].sum() == 4
    assert panel.loc[panel["arrival_date"] == "2024-01-03", "district_modal_price"].isna().all()  # gap NOT filled
    assert panel["in_window"].eq(1).all()


def test_calendar_lag_means_calendar_days():
    idx = pd.date_range("2024-01-01", periods=10)
    s = pd.Series([1, 2, np.nan, 4, 5, 6, 7, 8, np.nan, 10.], index=idx)
    lag7 = lag_calendar(s, 7)
    assert lag7.loc["2024-01-08"] == 1 and lag7.loc["2024-01-09"] == 2 and np.isnan(lag7.loc["2024-01-10"])
    sparse = s.dropna()                                           # row-shifting this would be wrong
    try:
        lag_calendar(sparse, 7)
        raise AssertionError("should refuse a sparse index")
    except ValueError:
        pass


def test_report_builds_and_writes_files():
    raw = _raw(_base_rows(40))
    c, s = clean.clean_prices(raw, DMAP)
    mk = aggregate.market_daily(c)
    dd = aggregate.district_daily(mk)
    panel, thin = aggregate.build_panel(dd, min_obs=10)
    tmp = Path(tempfile.mkdtemp())
    old = config.REPORT_DIR
    config.REPORT_DIR = tmp
    try:
        rep = report.build_report(c, s, mk, dd, panel, thin)
    finally:
        config.REPORT_DIR = old
    assert rep["districts"] == 1 and rep["markets"] == 5 and rep["arrivals_available"] is False
    assert rep["stale_warning"] is True                           # synthetic 2024 dates are old
    for f in ("data_quality_summary.json", "yearwise_coverage.csv", "series_coverage.csv",
              "thin_series_excluded.csv", "district_names_seen.csv"):
        assert (tmp / f).exists()
