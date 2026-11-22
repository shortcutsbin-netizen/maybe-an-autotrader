#!/usr/bin/env python3
"""E016b - enter S1-D dislocation signals with a resting order instead of an IOC (maker fee is zero).

For each frozen-rule signal at minute-end t (side +1 = buy YES, -1 = buy NO):
  post a YES bid at L = ask - k ticks (buy YES) or a YES offer at U = bid + k ticks (buy NO), k in {1, 2, 3}
  (never crossing: L >= bid, U <= ask; with a 1c spread k=1 means joining the touch),
  live for W seconds in {5, 15, 30, 60}; filled if a public print by a taker on the other side trades
  at or through the price inside (t, t + W] ("touch", optimistic about the queue) or strictly through it
  ("through", conservative). P&L = outcome - price, no fee; unfilled signals earn 0.
Compared with the pre-registered taker fill F1 on the same signals.

usage: e016b_dislocation_maker_entry.py <signals_csv> <trade_dirs_comma> [<signals_csv> <trade_dirs> ...]
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e012_frozen_new_periods import ci, load_trades  # noqa: E402


def tick(p):
    return np.where((p < 0.10) | (p > 0.90), 0.001, 0.01)


def run(sig_csv, dirs):
    s = pd.read_csv(sig_csv)
    tr = load_trades(dirs, set(s.ticker))
    rows = []
    for r in s.itertuples():
        g = tr.get(r.ticker)
        t0 = float(r.end_period_ts)
        out = r.y if r.side == 1 else 1 - r.y
        rec = {"day": r.day, "series": r.series, "side": r.side}
        for k in (1, 2, 3):
            if r.side == 1:
                L = max(r.ask_c - k * float(tick(r.ask_c)), r.bid_c)
            else:
                U = min(r.bid_c + k * float(tick(r.bid_c)), r.ask_c)
            for W in (5, 15, 30, 60):
                fill_t = fill_th = False
                if g is not None:
                    w = g[(g.ts > t0) & (g.ts <= t0 + W)]
                    if r.side == 1:
                        px = w.loc[w.taker_side == "no", "yes_price"].astype(float)
                        fill_t, fill_th = bool((px <= L + 1e-9).any()), bool((px < L - 1e-9).any())
                        pnl = out - L
                    else:
                        px = w.loc[w.taker_side == "yes", "yes_price"].astype(float)
                        fill_t, fill_th = bool((px >= U - 1e-9).any()), bool((px > U + 1e-9).any())
                        pnl = out - (1 - U)
                for nm, f in (("touch", fill_t), ("through", fill_th)):
                    rec[f"{nm}_k{k}_w{W}"] = pnl if f else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def main():
    a = sys.argv[1:]
    res = []
    for i in range(0, len(a), 2):
        d = run(a[i], a[i + 1])
        d["set"] = a[i].rsplit("/", 1)[-1]
        res.append(d)
        print(f"{a[i]}: {len(d)} signals")
    d = pd.concat(res, ignore_index=True)
    cols = [c for c in d.columns if c.startswith(("touch", "through"))]
    print(f"\nall sets: {len(d)} signals, {d.day.nunique()} days")
    print(f"{'variant':22s} {'fill%':>6s} {'per fill':>9s} {'CI':>16s} {'per signal':>11s}")
    for c in cols:
        v = d[c]
        f = v.notna()
        lo, hi = ci(v[f].values, d.loc[f, "day"].values) if f.sum() > 20 else (np.nan, np.nan)
        print(f"{c:22s} {f.mean() * 100:6.1f} {v[f].mean() * 100:+8.2f}c [{lo * 100:+6.2f},{hi * 100:+6.2f}] {v.fillna(0).mean() * 100:+10.2f}c")
    for st, g in d.groupby("set"):
        c = "through_k1_w15"
        v = g[c]
        print(f"  {st}: {c} fill {v.notna().mean():.1%}, per fill {v.mean() * 100:+.2f}c, per signal {v.fillna(0).mean() * 100:+.2f}c")


if __name__ == "__main__":
    main()
