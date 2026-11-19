"""STEP 4 - Data-quality report built from the tables actually produced."""
import json
import logging

import pandas as pd

from . import config
from .clean import district_review_list

log = logging.getLogger(__name__)


def build_report(clean, clean_summary, mkt, dd, panel, thin):
    rep = {}
    last = dd["arrival_date"].max()
    rep["date_min"] = str(dd["arrival_date"].min().date())
    rep["date_max"] = str(last.date())
    rep["days_since_last_price"] = int((pd.Timestamp.today().normalize() - last).days)
    rep["stale_warning"] = rep["days_since_last_price"] > config.STALE_WARNING_DAYS
    rep["rows_extracted"] = clean_summary["rows"]
    rep["rows_usable"] = clean_summary["usable_rows"]
    rep["market_days"] = int(len(mkt))
    rep["district_days"] = int(len(dd))
    rep["districts"] = int(dd["district"].nunique())
    rep["markets"] = int(mkt["market"].nunique())
    rep["series_in_panel"] = int(panel.groupby(["district", "commodity"]).ngroups)
    rep["thin_series_excluded"] = int(len(thin))
    rep["arrivals_available"] = False            # source has no arrivals column
    rep["flags"] = {k: v for k, v in clean_summary.items() if k.startswith("flag_")}
    rep["share_single_mandi_district_days"] = round(float((dd["n_mandis"] == 1).mean()), 4)

    multi = dd[dd["n_mandis"] >= 2]
    rel = (multi["price_mean"] - multi["price_median"]).abs() / multi["price_mean"]
    rep["mean_vs_median_gt2pct_share_of_multi_mandi_days"] = (
        round(float((rel > 0.02).mean()), 4) if len(multi) else None)

    year = (dd.assign(year=dd["arrival_date"].dt.year)
              .groupby(["commodity", "year"])
              .agg(district_days=("district", "size"), districts=("district", "nunique"),
                   mean_mandis=("n_mandis", "mean"), mean_price=("district_modal_price", "mean"))
              .round(2).reset_index())
    pw = panel[panel["in_window"] == 1]
    series = (pw.groupby(["commodity", "district"])
                .agg(observed_days=("observed", "sum"), window_days=("in_window", "sum"))
                .reset_index())
    series["coverage_pct"] = (100 * series["observed_days"] / series["window_days"]).round(1)

    REPORT = config.REPORT_DIR
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "data_quality_summary.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    year.to_csv(REPORT / "yearwise_coverage.csv", index=False)
    series.to_csv(REPORT / "series_coverage.csv", index=False)
    thin.to_csv(REPORT / "thin_series_excluded.csv", index=False)
    district_review_list(clean).to_csv(REPORT / "district_names_seen.csv", index=False)

    log.info("report written to %s", REPORT)
    if rep["stale_warning"]:
        log.warning("NEWEST PRICE IS %d DAYS OLD (%s). Forecasts would start from that date.",
                    rep["days_since_last_price"], rep["date_max"])
    return rep
