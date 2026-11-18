"""Feature engineering for daily price forecasting.

The target is the log-return over ONE day.  Tree models cannot extrapolate price
*levels* beyond what they saw in training (a real problem when prices trend up
for years) but they can learn return patterns, so we predict the return and
rebuild the price.  Multi-day forecasts are produced recursively.
"""
import numpy as np
import pandas as pd

LAGS = [1, 2, 3, 5, 7, 14, 21, 28]
WINDOWS = [7, 14, 30, 60]


def make_features(price: pd.Series) -> pd.DataFrame:
    """Features for every date, using only information up to and including that date."""
    lp = np.log(price)
    ret = lp.diff()
    f = pd.DataFrame(index=price.index)

    for l in LAGS:
        f[f"ret_lag_{l}"] = ret.shift(l - 1)           # ret_lag_1 == today's return
    for w in WINDOWS:
        f[f"ret_mean_{w}"] = ret.rolling(w).mean()
        f[f"ret_std_{w}"] = ret.rolling(w).std()
        f[f"dev_ma_{w}"] = lp - lp.rolling(w).mean()    # distance from moving average (mean reversion)
    f["mom_7"] = lp - lp.shift(7)
    f["mom_30"] = lp - lp.shift(30)
    f["mom_90"] = lp - lp.shift(90)
    f["dev_365"] = lp - lp.rolling(365, min_periods=180).mean()

    # Calendar. Seasonality matters: wheat arrivals peak Mar-May (rabi harvest),
    # maize has kharif (Oct-Nov) and rabi (Mar-Apr) harvests.
    doy = price.index.dayofyear
    f["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    f["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    f["dow"] = price.index.dayofweek
    f["month"] = price.index.month
    return f


def make_target(price: pd.Series, horizon: int = 1) -> pd.Series:
    """Log-return from t to t+horizon, stored at t."""
    lp = np.log(price)
    return (lp.shift(-horizon) - lp).rename("target")
