"""STEP 1 - Extract Maharashtra Wheat & Maize rows from the Hugging Face dataset.

The source is split into yearly Parquet files, so we (a) download only the years we need,
(b) skip files that are already on disk and readable, and (c) let DuckDB filter the files
straight from disk so the full 76-million-row dataset is never loaded into memory.
Nothing in the source is modified; the result is a NEW file in data/intermediate/.
"""
import csv
import logging
import re
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

REQUIRED = ["State", "District", "Market", "Commodity", "Variety", "Grade",
            "Arrival_Date", "Min_Price", "Max_Price", "Modal_Price"]


def pick_files(files, start_year, end_year):
    """Keep parquet files whose NAME contains a year inside [start_year, end_year].
    A file with no year in its name is kept (we cannot prove it is unneeded) and reported."""
    selected, unknown = [], []
    for f in files:
        years = [int(y) for y in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", Path(f).name)]
        if not years:
            unknown.append(f)
            selected.append(f)
        elif any(start_year <= y <= end_year for y in years):
            selected.append(f)
    return selected, unknown


def _readable(path):
    import duckdb
    try:
        duckdb.connect().execute(f"SELECT 1 FROM read_parquet('{_q(path)}') LIMIT 1").fetchall()
        return True
    except Exception as e:                                   # truncated / corrupt download
        log.warning("Unreadable parquet %s: %s", path, e)
        return False


def _q(value):
    """Escape a path/string for use inside single quotes in DuckDB SQL."""
    return str(value).replace("\\", "/").replace("'", "''")


def download_files(files, local_dir):
    """Download each file unless a readable copy already exists. Failures are logged, not fatal."""
    from huggingface_hub import hf_hub_download
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    ok, failed = [], []
    for i, f in enumerate(files, 1):
        target = local_dir / f
        if target.exists() and target.stat().st_size > 0 and _readable(target):
            log.info("[%d/%d] already have %s", i, len(files), f)
            ok.append(str(target))
            continue
        try:
            log.info("[%d/%d] downloading %s", i, len(files), f)
            p = hf_hub_download(repo_id=config.HF_REPO_ID, repo_type="dataset",
                                filename=f, local_dir=str(local_dir))
            if _readable(p):
                ok.append(str(p))
            else:
                failed.append((f, "unreadable after download"))
        except Exception as e:
            log.error("download failed for %s: %s", f, e)
            failed.append((f, str(e)))
    if failed:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.LOG_DIR / "extract_failures.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "reason"])
            w.writerows(failed)
        log.error("%d file(s) failed - see logs/extract_failures.csv. Re-run to retry only those.", len(failed))
    return ok, failed


def extract_maharashtra(local_files, out_path, start=config.START_DATE, end=config.END_DATE):
    """Filter state/commodity/date with DuckDB and write one Parquet file. Returns row count."""
    import duckdb
    con = duckdb.connect()
    flist = "[" + ",".join(f"'{_q(p)}'" for p in local_files) + "]"
    src = f"read_parquet({flist}, union_by_name=true, filename=true)"

    schema = con.execute(f"DESCRIBE SELECT * FROM {src}").df()
    cols = set(schema["column_name"])
    missing = [c for c in REQUIRED if c not in cols]
    if missing:                                  # never assume a column exists
        raise ValueError(f"Source is missing expected columns {missing}. Columns found: {sorted(cols)}")
    log.info("Source schema verified: %s", sorted(cols))

    coms = ",".join(f"'{c}'" for c in config.COMMODITIES)
    where = (f"UPPER(TRIM(CAST(State AS VARCHAR))) = '{config.STATE}' "
             f"AND UPPER(TRIM(CAST(Commodity AS VARCHAR))) IN ({coms}) "
             f"AND Arrival_Date BETWEEN DATE '{start}' AND DATE '{end}'")

    # Safety net: show commodity labels that LOOK like wheat/maize but were not matched exactly.
    near = con.execute(
        f"SELECT DISTINCT Commodity FROM {src} WHERE UPPER(TRIM(CAST(State AS VARCHAR))) = '{config.STATE}' "
        f"AND (UPPER(Commodity) LIKE '%WHEAT%' OR UPPER(Commodity) LIKE '%MAIZE%' OR UPPER(Commodity) LIKE '%CORN%')"
    ).df()["Commodity"].tolist()
    log.info("Commodity labels containing wheat/maize/corn in Maharashtra: %s (exact matches are kept)", near)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    extra = "Commodity_Code, " if "Commodity_Code" in cols else ""
    con.execute(f"COPY (SELECT State, District, Market, Commodity, Variety, Grade, Arrival_Date, "
                f"Min_Price, Max_Price, Modal_Price, {extra}filename AS source_file "
                f"FROM {src} WHERE {where}) TO '{_q(out_path)}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{_q(out_path)}')").fetchone()[0]
    log.info("Wrote %s rows to %s", f"{n:,}", out_path)
    return n


def run(raw_dir=config.RAW_DIR, out_path=config.RAW_FILTERED, start=config.START_DATE,
        end=config.END_DATE, force=False):
    out_path = Path(out_path)
    if out_path.exists() and not force:
        log.info("%s exists - skipping extraction (use --force to redo)", out_path)
        return out_path
    from huggingface_hub import HfApi
    files = [f for f in HfApi().list_repo_files(config.HF_REPO_ID, repo_type="dataset")
             if f.lower().endswith(".parquet")]
    selected, unknown = pick_files(files, int(start[:4]), int(end[:4]))
    log.info("%d parquet files in repo; %d needed for %s..%s", len(files), len(selected), start, end)
    if unknown:
        log.warning("No year found in these names, kept to be safe: %s", unknown)
    local, failed = download_files(selected, raw_dir)
    if failed:
        raise RuntimeError(f"{len(failed)} file(s) could not be downloaded; fix and re-run.")
    extract_maharashtra(local, out_path, start, end)
    return out_path
