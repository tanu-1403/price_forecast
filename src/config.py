"""All settings in one place. Edit here, not inside the other modules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"                 # downloaded source files (never edited)
INTERIM_DIR = DATA_DIR / "intermediate"    # filtered / cleaned tables
PROC_DIR = DATA_DIR / "processed"          # final tables used for analysis
EXTERNAL_DIR = DATA_DIR / "external"       # weather, soil, MSP ... (later)
REPORT_DIR = ROOT / "reports" / "data_quality"
LOG_DIR = ROOT / "logs"
OUTPUT_DIR = ROOT / "output"               # forecasts (later)
DISTRICT_MAP = ROOT / "config" / "district_map.csv"

# ---- source: third-party copy of Agmarknet "Variety-wise Daily Market Prices" -------------
HF_REPO_ID = "DHIVAKARNAIDUSUNKARI/mandi-india-daily-prices-2001-2026"

# ---- scope ------------------------------------------------------------------------------
STATE = "MAHARASHTRA"
COMMODITIES = ("WHEAT", "MAIZE")
START_DATE = "2015-01-01"
END_DATE = "2026-12-31"        # only an upper filter; the panel ends at the last date really observed

# ---- file names -------------------------------------------------------------------------
RAW_FILTERED = INTERIM_DIR / "maha_wheat_maize_raw.parquet"
CLEAN_FILE = INTERIM_DIR / "prices_clean.parquet"
MARKET_DAILY = PROC_DIR / "market_daily.csv"
DISTRICT_DAILY = PROC_DIR / "district_daily.csv"
DISTRICT_PANEL = PROC_DIR / "district_panel.csv"

# ---- validation rules (thresholds are transparent and editable) --------------------------
# A price is flagged as an outlier when it is below LOW x or above HIGH x the commodity's
# centred 31-day rolling median (computed across all Maharashtra rows). Flagged rows are KEPT
# in the clean file; they are only left out of the aggregation.
OUTLIER_LOW = 0.4
OUTLIER_HIGH = 2.5
OUTLIER_WINDOW_DAYS = 31

# A district-commodity series needs at least this many observed days to enter the panel.
MIN_OBS_DAYS = 365

# Warn if the newest price is older than this many days.
STALE_WARNING_DAYS = 7
