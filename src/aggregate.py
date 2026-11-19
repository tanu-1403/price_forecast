"""STEP 3 - Aggregate: variety rows -> mandi-day -> district-day -> complete calendar panel.

Source has NO arrivals column, so no arrival-weighting is possible; every step is an
equal-weight mean (and a median is stored beside it for comparison).
"""
import logging

import pandas as pd

from . import config

log = logging.getLogger(__name__)


def market_daily(clean):
    """One row per (date, district, market, commodity): mean of the usable variety/grade rows."""
    u = clean[clean["usable"]]
    out = (u.groupby(["arrival_date", "district", "market", "commodity"])
             .agg(mandi_modal_price=("modal_price", "mean"),
                  mandi_min_price=("min_price", "mean"),
                  mandi_max_price=("max_price", "mean"),
                  n_rows=("modal_price", "size"),
                  n_varieties=("variety", "nunique"))
             .reset_index())
    log.info("market_daily: %s mandi-days from %s usable rows", f"{len(out):,}", f"{len(u):,}")
    return out


def district_daily(mkt):
    """One row per (date, district, commodity) from the mandi-day prices."""
    out = (mkt.groupby(["arrival_date", "district", "commodity"])
              .agg(price_mean=("mandi_modal_price", "mean"),
                   price_median=("mandi_modal_price", "median"),
                   price_sd=("mandi_modal_price", "std"),      # NaN when only one mandi reported
                   price_min=("mandi_modal_price", "min"),
                   price_max=("mandi_modal_price", "max"),
                   n_mandis=("market", "nunique"),
                   n_source_rows=("n_rows", "sum"))
              .reset_index())
    out["district_modal_price"] = out["price_mean"]            # primary target (see docs/METHODS.md)
    log.info("district_daily: %s district-days", f"{len(out):,}")
    return out


def build_panel(dd, min_obs=config.MIN_OBS_DAYS, start=None):
    """Complete daily calendar for every district-commodity series with >= min_obs observed days.
    Missing days stay NaN (no forward fill). Returns (panel, thin_series)."""
    counts = dd.groupby(["district", "commodity"]).size().rename("n_obs").reset_index()
    keep = counts[counts["n_obs"] >= min_obs][["district", "commodity"]]
    thin = counts[counts["n_obs"] < min_obs].sort_values("n_obs")

    first_day = dd["arrival_date"].min()
    first_day = max(pd.Timestamp(start), first_day) if start else first_day
    last_day = dd["arrival_date"].max()                        # NOT the configured end date
    cal = pd.DataFrame({"arrival_date": pd.date_range(first_day, last_day, freq="D")})

    panel = keep.merge(cal, how="cross").merge(dd, on=["district", "commodity", "arrival_date"], how="left")
    panel["observed"] = panel["n_mandis"].notna().astype(int)
    span = (dd.groupby(["district", "commodity"])["arrival_date"]
              .agg(first_obs="min", last_obs="max").reset_index())
    panel = panel.merge(span, on=["district", "commodity"], how="left")
    panel["in_window"] = ((panel["arrival_date"] >= panel["first_obs"])
                          & (panel["arrival_date"] <= panel["last_obs"])).astype(int)
    panel = panel.drop(columns=["first_obs", "last_obs"]).sort_values(
        ["commodity", "district", "arrival_date"]).reset_index(drop=True)
    log.info("panel: %d series x %d days = %s rows; %d thin series left out",
             len(keep), len(cal), f"{len(panel):,}", len(thin))
    return panel, thin
