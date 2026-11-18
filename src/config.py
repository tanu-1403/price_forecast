"""Central configuration. Change things here, not inside the other modules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SYN_DIR = ROOT / "data" / "synthetic"
MODEL_DIR = ROOT / "models"
OUT_DIR = ROOT / "output"

STATE = "Maharashtra"

# short name used on the command line -> commodity name exactly as Agmarknet spells it
COMMODITIES = {
    "wheat": "Wheat",
    "maize": "Maize",
}

# data.gov.in "Current Daily Price of Various Commodities from Various Markets (Mandi)"
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
API_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

PRICE_COL = "modal_price"   # Rs per quintal (100 kg)
HORIZON_DAYS = 14           # default forecast length
TEST_DAYS = 90              # last N days held out for the backtest
MAX_FFILL_DAYS = 7          # longest gap (holidays / no-arrival days) we forward-fill
MIN_MARKETS_PER_DAY = 1     # days with fewer reporting mandis are treated as missing
MIN_HISTORY_DAYS = 300      # refuse to train on less than this
MAX_DAILY_MOVE = 0.05       # clip any predicted one-day move to +/-5 %
