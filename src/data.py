"""Raw mandi rows -> one clean DAILY price series for Maharashtra."""
from pathlib import Path

import pandas as pd

from .config import MAX_FFILL_DAYS, MIN_MARKETS_PER_DAY, PRICE_COL, RAW_DIR


def load_raw(key: str, raw_dir=None) -> pd.DataFrame:
    path = Path(raw_dir or RAW_DIR) / f"{key}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `python -m src.fetch_data` "
                                f"(see README) or `python -m src.make_synthetic` for a demo.")
    df = pd.read_csv(path)
    d = pd.to_datetime(df["arrival_date"], format="ISO8601", errors="coerce")   # our own store: 2025-03-05
    d = d.fillna(pd.to_datetime(df["arrival_date"], dayfirst=True, errors="coerce"))  # raw Agmarknet: 05/03/2025
    df["arrival_date"] = d
    return df.dropna(subset=["arrival_date"])


def build_daily_series(raw: pd.DataFrame, price_col: str = PRICE_COL) -> pd.DataFrame:
    """State-level daily price = MEDIAN across reporting mandis (robust to typos).

    Returns a DataFrame indexed by calendar day:
        price      Rs/quintal (forward-filled over short gaps such as Sundays)
        n_markets  number of mandis that reported that day (0 on filled days)
    """
    raw = raw.copy()
    lo, hi = raw[price_col].quantile([0.005, 0.995])       # drop absurd entries (20, 200000 ...)
    raw = raw[(raw[price_col] >= lo * 0.5) & (raw[price_col] <= hi * 1.5)]

    g = raw.groupby("arrival_date")[price_col]
    daily = pd.DataFrame({"price": g.median(), "n_markets": g.count()})
    daily = daily[daily["n_markets"] >= MIN_MARKETS_PER_DAY]

    full = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full)
    daily["n_markets"] = daily["n_markets"].fillna(0)
    daily["price"] = daily["price"].ffill(limit=MAX_FFILL_DAYS)
    daily = daily.dropna(subset=["price"])
    daily.index.name = "date"
    return daily


def load_daily(key: str, raw_dir=None) -> pd.DataFrame:
    return build_daily_series(load_raw(key, raw_dir))
