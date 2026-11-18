"""Generate FAKE Maharashtra mandi data in the same schema as Agmarknet.

Only for testing the pipeline end-to-end. Do NOT use these numbers for decisions.
    python -m src.make_synthetic            # writes data/synthetic/{wheat,maize}.csv
"""
import numpy as np
import pandas as pd

from .config import COMMODITIES, SYN_DIR

MARKETS = [("Pune", "Pune"), ("Nagpur", "Nagpur"), ("Nashik", "Nashik"), ("Lasalgaon", "Nashik"),
           ("Ahmednagar", "Ahmednagar"), ("Solapur", "Solapur"), ("Latur", "Latur"),
           ("Akola", "Akola"), ("Amravati", "Amravati"), ("Jalgaon", "Jalgaon"),
           ("Kolhapur", "Kolhapur"), ("Aurangabad", "Chhatrapati Sambhajinagar")]

# base price Rs/qtl, harvest-dip month, dip depth
SPEC = {"wheat": (2300, 4, 0.05), "maize": (2000, 11, 0.06)}


def generate(key: str, years: int = 5, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed + (0 if key == "wheat" else 1))
    base, dip_m, depth = SPEC[key]
    end = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    days = pd.date_range(end=end, periods=365 * years, freq="D")
    n = len(days)

    t = np.arange(n) / 365.0
    season = -depth * np.cos(2 * np.pi * (days.dayofyear.values / 365.25 - (dip_m - 0.5) / 12))
    ar = np.zeros(n)
    for i in range(1, n):                                    # slow mean-reverting noise
        ar[i] = 0.985 * ar[i - 1] + rng.normal(0, 0.004)
    msp_jump = 0.03 * np.floor(t + 0.25)                      # yearly MSP-style step
    level = base * np.exp(0.04 * t + msp_jump + season + ar)

    rows = []
    for mk, dist in MARKETS:
        off = rng.normal(0, 0.04)
        for i, d in enumerate(days):
            if d.dayofweek == 6 or rng.random() > 0.65:      # closed Sundays; mandis report irregularly
                continue
            p = level[i] * np.exp(off + rng.normal(0, 0.015))
            rows.append(("Maharashtra", dist, mk, COMMODITIES[key], "Other", "FAQ",
                         d.strftime("%d/%m/%Y"), round(p * 0.97), round(p * 1.03), round(p)))
    return pd.DataFrame(rows, columns=["state", "district", "market", "commodity", "variety", "grade",
                                       "arrival_date", "min_price", "max_price", "modal_price"])


def main():
    SYN_DIR.mkdir(parents=True, exist_ok=True)
    for k in COMMODITIES:
        df = generate(k)
        df.to_csv(SYN_DIR / f"{k}.csv", index=False)
        print(f"wrote {SYN_DIR / (k + '.csv')}  ({len(df):,} rows)")


if __name__ == "__main__":
    main()
