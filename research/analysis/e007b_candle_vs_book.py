#!/usr/bin/env python3
"""E007b — are the 1-minute candle "close" quotes the real book at the minute end?

Compares Kalshi candle bid/ask close (from the candlestick endpoint) with the
order book actually captured every 2 s by live_capture.py over the same window.
If the candle quote lags the real book, any backtest that "trades" candle quotes
against a synchronous spot price manufactures a fake edge.
Usage: e007b_candle_vs_book.py <candle_run_dir> <live_run_dir>
"""
import glob, sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e007_live_leadlag import load

crun, lrun = sys.argv[1], sys.argv[2]
B, S, mk = load(lrun)
B["g"] = (B["t"] / 2).round().astype("int64")
B = B.drop_duplicates(["ticker", "g"], keep="last").set_index(["ticker", "g"])
cd = pd.concat([pd.read_csv(f) for f in glob.glob(f"{crun}/candles/*.csv.gz")], ignore_index=True)
cd = cd[cd["ticker"].isin(B.index.get_level_values(0).unique())]
cd = cd[(cd["bid_c"] > 0) & (cd["ask_c"] < 1)]
print(f"candles={len(cd)} markets={cd['ticker'].nunique()}")
res = {}
for lag in (-60, -30, -20, -10, -6, -4, -2, 0, 2, 4, 10):
    idx = pd.MultiIndex.from_arrays([cd["ticker"], (cd["end_period_ts"] + lag) // 2])
    bb, ba = B["bid"].reindex(idx).values, B["ask"].reindex(idx).values
    ok = np.isfinite(bb) & (bb > 0) & (ba < 1)
    dm = (cd["bid_c"].values + cd["ask_c"].values) / 2 - (bb + ba) / 2
    exact = (np.abs(cd["bid_c"].values - bb) < 1e-6) & (np.abs(cd["ask_c"].values - ba) < 1e-6)
    res[lag] = (ok.sum(), np.nanmean(np.abs(dm[ok])) * 100, exact[ok].mean() * 100, np.nanmean(np.abs(cd["ask_c"].values - ba)[ok]) * 100)
print("book sampled at (minute end + lag): n, mean |candle mid - book mid| (c), exact bid&ask match %, mean |ask diff| (c)")
for k, v in res.items():
    print(f"  lag {k:+4d}s  n={v[0]:5d}  |mid diff|={v[1]:5.2f}c  exact={v[2]:5.1f}%  |ask diff|={v[3]:5.2f}c")
cd["series"] = cd["ticker"].str.split("-").str[0]
idx = pd.MultiIndex.from_arrays([cd["ticker"], cd["end_period_ts"] // 2])
cd["book_bid"], cd["book_ask"] = B["bid"].reindex(idx).values, B["ask"].reindex(idx).values
x = cd.dropna(subset=["book_bid"]); x = x[(x["book_bid"] > 0) & (x["book_ask"] < 1)]
x = x.assign(d=((x["bid_c"] + x["ask_c"]) / 2 - (x["book_bid"] + x["book_ask"]) / 2).abs() * 100,
             cs=(x["ask_c"] - x["bid_c"]) * 100, bs=(x["book_ask"] - x["book_bid"]) * 100)
print("\nby series at lag 0: n, mean |mid diff| c, share with |diff| >= 3c, candle spread c, book spread c")
for s, g in x.groupby("series"):
    print(f"  {s:10s} n={len(g):5d} {g['d'].mean():5.2f}c  {np.mean(g['d'] >= 3)*100:5.1f}%  candle spread {g['cs'].mean():.2f}  book spread {g['bs'].mean():.2f}")
