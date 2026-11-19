"""Load the processed panel for analysis / modelling (same role as read_data.py in the
original forecasting_agro repo). Later steps (eda.py, model_*.py, predict.py) start here."""
import pandas as pd

from . import config


def load_panel(commodity=None, observed_only=False, path=config.DISTRICT_PANEL):
    """Complete daily district panel. Missing days are NaN, never forward-filled."""
    df = pd.read_csv(path, parse_dates=["arrival_date"])
    if commodity:
        df = df[df["commodity"] == commodity.upper()]
    if observed_only:
        df = df[df["observed"] == 1]
    return df


def load_series(commodity, district, path=config.DISTRICT_PANEL):
    """One series on a COMPLETE daily index (NaN where not observed)."""
    df = load_panel(commodity, path=path)
    s = df[df["district"] == district].set_index("arrival_date")["district_modal_price"]
    return s.asfreq("D")


def lag_calendar(series, days):
    """Value exactly `days` calendar days earlier. Only valid on a complete daily index
    (what load_series returns); row-shifting a sparse table would NOT mean calendar days."""
    if not (series.index.to_series().diff().dropna() == pd.Timedelta(days=1)).all():
        raise ValueError("Series is not a complete daily index; use load_series().")
    return series.shift(days)
