#!/usr/bin/env python3
"""E012b — placebo for the E012 fill machinery: random side, random non-signal minutes, same markets,
same F1 fill model (VWAP of same-side prints in (t+1, t+6] at <= quote + 2c). Should lose about the fee.
Usage: e012b_placebo.py <run_dir> <signals_csv> <trades_dirs_comma> [n=6000]
"""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e001_calibration import load
from e012_frozen_new_periods import load_trades, ci, fee

run, sig_csv, dirs = sys.argv[1:4]
n = int(sys.argv[4]) if len(sys.argv) > 4 else 6000
mk, df = load(run)
sig = pd.read_csv(sig_csv)
by = load_trades(dirs, set(sig["ticker"]))
d = df[df["ticker"].isin(by) & (df["k"] >= 1) & (df["k"] <= 14) & (df["bid_c"] > 0) & (df["ask_c"] < 1)]
key = set(zip(sig["ticker"], sig["end_period_ts"]))
d = d[[(a, b) not in key for a, b in zip(d["ticker"], d["end_period_ts"])]].sample(min(n, len(d)), random_state=1)
rng = np.random.default_rng(0)
d = d.assign(side=rng.choice([1, -1], len(d)))
rows = []
for r in d.itertuples():
    g = by[r.ticker]
    own = g[g["taker_side"] == ("yes" if r.side == 1 else "no")]
    t_, c_ = own["ts"].values, own["count"].values.astype(float)
    p_ = (own["yes_price"] if r.side == 1 else own["no_price"]).values.astype(float)
    q = r.ask_c if r.side == 1 else 1 - r.bid_c
    m = (t_ > r.end_period_ts + 1) & (t_ <= r.end_period_ts + 6) & (p_ <= q + 0.02 + 1e-9)
    if m.any():
        px = (p_[m] * c_[m]).sum() / c_[m].sum()
        win = r.y if r.side == 1 else 1 - r.y
        rows.append((r.day, win - px - fee(px), px - q))
x = pd.DataFrame(rows, columns=["day", "pnl", "slip"])
lo, hi = ci(x["pnl"].values, x["day"].values)
print(f"PLACEBO {run}: sampled minutes={len(d)} filled={len(x)} P&L {x['pnl'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] mean price vs quote {x['slip'].mean()*100:+.2f}c")
