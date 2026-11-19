"""Run the price pipeline.

    python -m src.run_pipeline                      # all steps
    python -m src.run_pipeline --steps clean aggregate report
    python -m src.run_pipeline --raw-dir "D:\\old_download\\raw"   # reuse already-downloaded files
"""
import argparse
import logging
import sys

import pandas as pd

from . import aggregate, clean, config, extract, report

STEPS = ["extract", "clean", "aggregate", "report"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="+", choices=STEPS, default=STEPS)
    ap.add_argument("--raw-dir", default=str(config.RAW_DIR), help="where parquet files are / will be downloaded")
    ap.add_argument("--start", default=config.START_DATE)
    ap.add_argument("--end", default=config.END_DATE)
    ap.add_argument("--force", action="store_true", help="redo extraction even if its output exists")
    a = ap.parse_args(argv)

    for d in (config.INTERIM_DIR, config.PROC_DIR, config.LOG_DIR, config.REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(config.LOG_DIR / "pipeline.log", encoding="utf-8")])
    log = logging.getLogger("pipeline")

    if "extract" in a.steps:
        extract.run(a.raw_dir, config.RAW_FILTERED, a.start, a.end, a.force)

    if any(s in a.steps for s in ("clean", "aggregate", "report")):
        raw = pd.read_parquet(config.RAW_FILTERED)
        clean_df, summary = clean.clean_prices(raw)
        if "clean" in a.steps:
            clean_df.to_parquet(config.CLEAN_FILE, index=False)
    if any(s in a.steps for s in ("aggregate", "report")):
        mkt = aggregate.market_daily(clean_df)
        dd = aggregate.district_daily(mkt)
        panel, thin = aggregate.build_panel(dd, start=a.start)
        mkt.to_csv(config.MARKET_DAILY, index=False)
        dd.to_csv(config.DISTRICT_DAILY, index=False)
        panel.to_csv(config.DISTRICT_PANEL, index=False)
    if "report" in a.steps:
        rep = report.build_report(clean_df, summary, mkt, dd, panel, thin)
        log.info("SUMMARY: %s", {k: rep[k] for k in ("date_min", "date_max", "districts", "markets",
                                                    "district_days", "series_in_panel")})
    log.info("done")


if __name__ == "__main__":
    main()
