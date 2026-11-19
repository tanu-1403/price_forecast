"""STEP 2 - Standardise and VALIDATE rows. Nothing is deleted: suspicious rows get flags.

Output keeps every extracted row, the original text values (district_raw, market_raw),
a set of flag_* columns, and `usable` = the rows that may enter the aggregation.
"""
import logging
import re

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)

REQUIRED = ["state", "district", "market", "commodity", "variety", "grade",
            "arrival_date", "min_price", "max_price", "modal_price"]
FLAGS = ["flag_bad_date", "flag_missing_district_or_market", "flag_nonpositive_modal",
         "flag_min_gt_modal", "flag_modal_gt_max", "flag_min_gt_max",
         "flag_price_outlier", "flag_key_dup", "flag_exact_dup"]
# Flags that remove a row from the aggregation (the others are informational only).
EXCLUDING_FLAGS = ["flag_bad_date", "flag_missing_district_or_market", "flag_nonpositive_modal",
                   "flag_price_outlier", "flag_exact_dup"]


def _text(s):
    return s.astype("string").str.replace(r"\s+", " ", regex=True).str.strip()


def load_district_map(path=config.DISTRICT_MAP):
    if not path.exists():
        return pd.DataFrame(columns=["source_name", "canonical_name", "status", "note"])
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def apply_district_map(df, dmap):
    m = dmap[dmap["canonical_name"].str.strip() != ""]
    lookup = dict(zip(m["source_name"].str.upper().str.strip(), m["canonical_name"].str.strip()))
    mapped = df["district"].str.upper().map(lookup)
    df["district"] = mapped.fillna(df["district"]).astype("string")
    return df


def outlier_flag(df, low=config.OUTLIER_LOW, high=config.OUTLIER_HIGH,
                 window=config.OUTLIER_WINDOW_DAYS):
    """True where modal price < low x or > high x the commodity's centred rolling median."""
    flag = pd.Series(False, index=df.index)
    ok = df["modal_price"].gt(0) & df["arrival_date"].notna()
    for _, g in df[ok].groupby("commodity"):
        daily = g.groupby("arrival_date")["modal_price"].median()
        daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max(), freq="D"))
        ref = daily.rolling(window, center=True, min_periods=5).median().ffill().bfill()
        ratio = g["modal_price"].to_numpy() / ref.reindex(g["arrival_date"]).to_numpy()
        flag.loc[g.index] = (ratio < low) | (ratio > high)
    return flag


def clean_prices(raw, dmap=None):
    """Returns (clean_df, summary_dict)."""
    d = raw.copy()
    d.columns = [c.strip().lower() for c in d.columns]
    d = d.rename(columns={"filename": "source_file"})
    missing = [c for c in REQUIRED if c not in d.columns]
    if missing:
        raise ValueError(f"Columns missing from extracted data: {missing}. Found: {list(d.columns)}")

    d["district_raw"] = d["district"]          # original values kept untouched
    d["market_raw"] = d["market"]
    for c in ["state", "district", "market", "commodity", "variety", "grade"]:
        d[c] = _text(d[c])
    d["state"] = d["state"].str.upper()
    d["commodity"] = d["commodity"].str.upper()
    d = apply_district_map(d, dmap if dmap is not None else load_district_map())

    d["arrival_date"] = pd.to_datetime(d["arrival_date"], errors="coerce")
    for c in ["min_price", "max_price", "modal_price"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    d["flag_bad_date"] = d["arrival_date"].isna()
    d["flag_missing_district_or_market"] = (d["district"].isna() | d["market"].isna()
                                            | (d["district"] == "") | (d["market"] == ""))
    d["flag_nonpositive_modal"] = ~(d["modal_price"] > 0)
    d["flag_min_gt_modal"] = d["min_price"] > d["modal_price"]
    d["flag_modal_gt_max"] = d["modal_price"] > d["max_price"]
    d["flag_min_gt_max"] = d["min_price"] > d["max_price"]
    d["flag_price_outlier"] = outlier_flag(d)
    key = ["arrival_date", "district", "market", "commodity", "variety", "grade"]
    d["flag_key_dup"] = d.duplicated(key, keep=False)
    d["flag_exact_dup"] = d.duplicated(key + ["min_price", "max_price", "modal_price"], keep="first")

    d["usable"] = ~d[EXCLUDING_FLAGS].any(axis=1)

    summary = {"rows": int(len(d)), "usable_rows": int(d["usable"].sum()),
               **{f: int(d[f].sum()) for f in FLAGS}}
    log.info("clean: %s rows, %s usable. Flags: %s", f"{summary['rows']:,}", f"{summary['usable_rows']:,}",
             {k: v for k, v in summary.items() if k.startswith("flag_") and v})
    return d, summary


def district_review_list(clean, dmap=None):
    """Districts still unmapped/under review, with row counts, so a human can decide."""
    dmap = dmap if dmap is not None else load_district_map()
    review = set(dmap.loc[dmap["canonical_name"].str.strip() == "", "source_name"].str.upper())
    counts = clean.groupby("district_raw").size().rename("rows").reset_index()
    counts["needs_review"] = counts["district_raw"].str.upper().str.strip().isin(review)
    return counts.sort_values("rows", ascending=False)
