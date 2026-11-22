#!/usr/bin/env python3
"""E018 - 15-minute commodity / FX / index / yield markets (Pyth- or S&P-settled).

No free intraday history of the settlement feeds exists any more (Pyth Benchmarks and Hermes need a
paid key since 2026-08-26; probe-005), so this experiment uses:
  * the Kalshi books themselves (own mid, drift, spread, minutes left),
  * cross-market moves inside the group (e.g. EURUSD vs GBPUSD vs AUDUSD, gold vs silver),
  * a free 24/7 proxy where one exists (PAXG-USD on Coinbase for gold; returns only, never levels).

Model: logistic on [mid logit, mid change 1/3/5 min, spread, minutes left, cross-market signed mid change,
proxy z-score]. Fit on the first 60% of days, threshold fixed at E010's 8c (no tuning), read on the next
20% ("val"); the last 20% stays closed. Fills: (a) the minute-end quote (optimistic: E003 showed such
edges vanish within a minute), (b) the next minute's close quote (one-minute delay). Real fills would need
public prints; only pulled if (b) is positive.

usage: e018_fin15.py <run> <group> [proxy_csv]
  groups: fx = EURUSD,GBPUSD,AUDUSD (+) USDJPY,USDCAD (-); metals = GOLD,SILVER,PLATINUM,PALLADIUM,COPPER;
          energy = WTI,BRENT,NATGAS; rates = 2Y,5Y,10Y,30Y
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e001_calibration import load  # noqa: E402
from e012_frozen_new_periods import ci  # noqa: E402

GROUPS = {
    "fx": {"KXEURUSD15M": 1, "KXGBPUSD15M": 1, "KXAUDUSD15M": 1, "KXUSDJPY15M": -1, "KXUSDCAD15M": -1},
    "metals": {"KXGOLD15M": 1, "KXSILVER15M": 1, "KXPLATINUM15M": 1, "KXPALLADIUM15M": 1, "KXCOPPER15M": 1},
    "energy": {"KXWTI15M": 1, "KXBRENT15M": 1, "KXNATGAS15M": 1},
    "rates": {"KX2YRRATE15M": 1, "KX5YRRATE15M": 1, "KX10YRRATE15M": 1, "KX30YRRATE15M": 1},
}
THR = 0.08
FEAT = ["lmid", "d1", "d3", "d5", "spread", "minutes_left", "cross", "cross3"]


def fee(p):
    return 0.07 * p * (1 - p)


def logit(p):
    p = np.clip(p, 0.01, 0.99)
    return np.log(p / (1 - p))


def main():
    run, group = sys.argv[1], sys.argv[2]
    proxy = sys.argv[3] if len(sys.argv) > 3 else None
    signs = GROUPS[group]
    mk, df = load(run)
    df = df[df["series"].isin(signs)].copy()
    df = df[(df.bid_c > 0) & (df.ask_c < 1) & (df.ask_c > df.bid_c)]
    df["mid"] = (df.bid_c + df.ask_c) / 2
    df["spread"] = df.ask_c - df.bid_c
    df = df.sort_values(["ticker", "end_period_ts"])
    g = df.groupby("ticker")["mid"]
    for k in (1, 3, 5):
        df[f"d{k}"] = (df["mid"] - g.shift(k)).fillna(0.0)
    df["lmid"] = logit(df["mid"])
    df["next_bid"] = df.groupby("ticker")["bid_c"].shift(-1)
    df["next_ask"] = df.groupby("ticker")["ask_c"].shift(-1)
    # cross-market: mean signed 1-min and 3-min mid change of the OTHER series at the same minute end
    df["sd1"] = df["d1"] * df["series"].map(signs)
    df["sd3"] = df["d3"] * df["series"].map(signs)
    tot = df.groupby("end_period_ts").agg(s1=("sd1", "sum"), s3=("sd3", "sum"), n=("sd1", "size"))
    df = df.join(tot, on="end_period_ts")
    nn = (df["n"] - 1).clip(lower=1)
    sg = df["series"].map(signs)
    df["cross"] = sg * (df["s1"] - df["sd1"]) / nn
    df["cross3"] = sg * (df["s3"] - df["sd3"]) / nn
    feats = list(FEAT)
    if proxy:
        p = pd.read_csv(proxy)
        tcol = "time" if "time" in p else p.columns[0]
        p["ts"] = p[tcol].astype(int) + 60          # Coinbase bucket start -> close at +60
        p = p.sort_values("ts").drop_duplicates("ts")
        px = p.set_index("ts")["close"]
        r = np.log(px).diff()
        vol = r.rolling(60, min_periods=20).std()
        df["px_t"] = df["end_period_ts"].map(px)
        df["px_0"] = df["open_ts"].map(px)
        df["vol"] = df["end_period_ts"].map(vol)
        tau = np.sqrt(df["minutes_left"].clip(lower=0.5))
        df["z"] = (np.log(df["px_t"] / df["px_0"]) / (df["vol"] * tau)).clip(-6, 6)
        cov = df["z"].notna().mean()
        print(f"proxy coverage {cov:.1%}")
        df["z"] = df["z"].fillna(0.0)
        feats.append("z")
    days = sorted(df["day"].unique())
    n = len(days)
    tr, va = days[: int(n * 0.6)], days[int(n * 0.6): int(n * 0.8)]
    print(f"{group}: {df.ticker.nunique()} markets, {len(df)} two-sided minute rows, days {days[0]}..{days[-1]} "
          f"train {tr[0]}..{tr[-1]} val {va[0]}..{va[-1]} (last 20% closed)")
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    T = df[df.day.isin(tr)]
    V = df[df.day.isin(va)].copy()
    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500)).fit(T[feats].values, T["y"].values)
    coef = dict(zip(feats, np.round(m[-1].coef_[0], 3)))
    print("coefficients (standardised):", coef)
    for name, D in (("train", T.copy()), ("val", V)):
        D["q"] = m.predict_proba(D[feats].values)[:, 1]
        print(f"  {name}: Brier mid {np.mean((D.mid - D.y) ** 2):.5f}  model {np.mean((D.q - D.y) ** 2):.5f}")
        ey = D.q - D.ask_c - fee(D.ask_c)
        en = (1 - D.q) - (1 - D.bid_c) - fee(1 - D.bid_c)
        D["side"] = np.where((ey > THR) & (ey >= en), 1, np.where(en > THR, -1, 0))
        S = D[D.side != 0].copy()
        if not len(S):
            print("    no signals")
            continue
        pa = np.where(S.side == 1, S.ask_c, 1 - S.bid_c)
        S["pnl_now"] = np.where(S.side == 1, S.y, 1 - S.y) - pa - fee(pa)
        pn = np.where(S.side == 1, S.next_ask, 1 - S.next_bid)
        S["pnl_next"] = np.where(S.side == 1, S.y, 1 - S.y) - pn - fee(pn)
        for col in ("pnl_now", "pnl_next"):
            v = S.dropna(subset=[col])
            lo, hi = ci(v[col].values, v["day"].values)
            print(f"    {col}: n={len(v)} ({len(v) / len(set(v.day)):.0f}/day, {v.ticker.nunique()} markets) "
                  f"{v[col].mean() * 100:+.2f}c [{lo * 100:+.2f},{hi * 100:+.2f}]")
        print("    by series (next-minute fill):", S.dropna(subset=["pnl_next"]).groupby("series").pnl_next.agg(["count", "mean"]).round(4).to_dict("index"))


if __name__ == "__main__":
    main()
