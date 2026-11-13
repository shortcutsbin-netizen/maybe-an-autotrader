#!/usr/bin/env python3
"""E011 — the frozen E010 rule applied to the window where the real order book was captured.

Signals are computed exactly as in E010 (minute-end candles + Coinbase candles, model fitted
on 2026-09-13..10-11 from run full-001). For each signal we then read the order book that was
actually displayed 0, 2, 4, 6 and 10 seconds later (live_capture.py) — price AND size.
Small sample (a few hours); the point is to see real displayed quotes, not to estimate EV.
Usage: e011_frozen_on_live_book.py <fit_run> <window_candle_run> <live_run> [threshold=0.08]
"""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import e003_s1_model as E
from e001_calibration import load, split_days
from e007_live_leadlag import load as load_live
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

fit_run, win_run, live_run = sys.argv[1:4]
thr = float(sys.argv[4]) if len(sys.argv) > 4 else 0.08
fee = lambda p: 0.07 * p * (1 - p)
d = E.build(fit_run); mk, _ = load(fit_run); sp = split_days(mk)
d = d.dropna(subset=E.EXT + E.MKT + ["y"]); tr = sp["train"]
fit = d[d["day"].isin(tr[:int(len(tr) * 0.8)])]
m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300)).fit(fit[E.EXT + E.MKT].values, fit["y"].values)
w = E.build(win_run).dropna(subset=E.EXT + E.MKT + ["y"])
B, S, mkl = load_live(live_run)
B["g"] = (B["t"] / 2).round().astype("int64"); B = B.drop_duplicates(["ticker", "g"], keep="last").set_index(["ticker", "g"])
w = w[w["ticker"].isin(B.index.get_level_values(0).unique())].copy()
w["p"] = m.predict_proba(w[E.EXT + E.MKT].values)[:, 1]
ey = w["p"] - w["ask_c"] - fee(w["ask_c"]); en = (1 - w["p"]) - (1 - w["bid_c"]) - fee(1 - w["bid_c"])
w["side"] = np.where((ey > thr) & (ey >= en), 1, np.where(en > thr, -1, 0))
print(f"window rows={len(w)} markets={w['ticker'].nunique()} signals at edge>{thr}: {(w['side']!=0).sum()}  (Brier model {np.mean((w['p']-w['y'])**2):.4f} vs mid {np.mean((w['mid']-w['y'])**2):.4f})")
s = w[w["side"] != 0]
rows = []
for r in s.itertuples():
    rec = {"ticker": r.ticker.replace("KX", "").replace("15M", ""), "ml": r.minutes_left, "side": "YES" if r.side == 1 else "NO", "p_side": r.p if r.side == 1 else 1 - r.p,
           "candle_ask": r.ask_c if r.side == 1 else 1 - r.bid_c, "win": r.y if r.side == 1 else 1 - r.y}
    for lag in (0, 2, 4, 6, 10, 30):
        k = (r.ticker, int(r.end_period_ts + lag) // 2)
        if k in B.index:
            b = B.loc[k]
            a, sz = (b["ask"], b["ask_sz"]) if r.side == 1 else (1 - b["bid"], b["bid_sz"])
            rec[f"ask+{lag}"] = round(a, 3); rec[f"sz+{lag}"] = round(sz)
    rows.append(rec)
x = pd.DataFrame(rows)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(x.round(3).to_string(index=False))
for lag in (0, 2, 4, 6, 10, 30):
    c = f"ask+{lag}"
    if c in x:
        ok = x[c].notna() & (x[c] < 1) & (x[c] > 0)
        pnl = x.loc[ok, "win"] - x.loc[ok, c] - fee(x.loc[ok, c])
        print(f"buy at the displayed ask {lag:2d}s after the signal: n={ok.sum()} mean P&L {pnl.mean()*100:+.1f}c (se {pnl.std()/np.sqrt(max(ok.sum(),1))*100:.1f})  median displayed size {x.loc[ok, f'sz+{lag}'].median():.0f}  mean ask {x.loc[ok, c].mean()*100:.1f}c")
