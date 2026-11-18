"""Model construction, tuning and recursive multi-day forecasting."""
import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

from .config import MAX_DAILY_MOVE
from .features import make_features

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:                                   # lets the repo run without xgboost
    from sklearn.ensemble import HistGradientBoostingRegressor
    HAS_XGB = False


def make_regressor():
    """Returns (estimator, param_grid, name)."""
    if HAS_XGB:
        est = XGBRegressor(objective="reg:absoluteerror", learning_rate=0.03, subsample=0.8,
                           colsample_bytree=0.8, min_child_weight=5, reg_lambda=2.0,
                           random_state=42, n_jobs=-1)
        grid = {"max_depth": [2, 3, 4], "n_estimators": [200, 400]}
        return est, grid, "xgboost"
    est = HistGradientBoostingRegressor(loss="absolute_error", learning_rate=0.03,
                                        l2_regularization=2.0, random_state=42)
    grid = {"max_depth": [2, 3, 4], "max_iter": [200, 400]}
    return est, grid, "sklearn_hist_gb (xgboost not installed)"


def fit_model(X: pd.DataFrame, y: pd.Series, tune: bool = True):
    est, grid, name = make_regressor()
    if tune:
        gs = GridSearchCV(est, grid, cv=TimeSeriesSplit(n_splits=4),
                          scoring="neg_mean_absolute_error", n_jobs=1)
        gs.fit(X, y)
        return gs.best_estimator_, name, gs.best_params_
    est.set_params(**{k: v[0] for k, v in grid.items()})
    est.fit(X, y)
    return est, name, {k: v[0] for k, v in grid.items()}


def recursive_forecast(model, feature_names, price: pd.Series, steps: int) -> pd.Series:
    """Roll the model forward `steps` calendar days from the end of `price`."""
    p = price.iloc[-500:].copy()                       # enough history for the 365-day features
    for _ in range(steps):
        row = make_features(p).iloc[[-1]][feature_names]
        r = float(np.clip(model.predict(row)[0], -MAX_DAILY_MOVE, MAX_DAILY_MOVE))
        p.loc[p.index[-1] + pd.Timedelta(days=1)] = p.iloc[-1] * np.exp(r)
    return p.iloc[-steps:]
