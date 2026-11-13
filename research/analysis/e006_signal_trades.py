#!/usr/bin/env python3
"""E006 — can the E003 signals actually be filled a few seconds later?

E003 found that when the combined model disagrees strongly with the Kalshi
quote, taking the displayed quote is profitable, but the edge is gone if the
fill is delayed by a full minute. One-minute candles cannot say what happens
in between. Public trade prints can: every taker print on our side shows the
price that was actually available at that microsecond.

For each signal (market, minute-end time t, side) we look at taker prints on
the same side after t:
  price_at(delay) = price of the first same-side taker print in [t+delay, t+delay+W]
  P&L(delay)      = outcome - price - fee(price)
Signals with no such print in the window are reported separately ("no print"):
for them we cannot tell what was available.

Usage: e006_signal_trades.py <signals.csv.gz> <trades_run_dir> [min_threshold=0.08]
Signals come from thr-days + validation only (never the test split).
"""
import sys

import numpy as np
import pandas as pd


def fee(p):
    return 0.07 * p * (1 - p)


def main():
    sig = pd.read_csv(sys.argv[1])
    import glob
    tr = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{sys.argv[2]}/trades*.csv.gz"))], ignore_index=True)
    thr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.08
    tr["ts"] = (pd.to_datetime(tr["created_time"], utc=True, format="ISO8601") - pd.Timestamp(0, tz="UTC")) / pd.Timedelta("1s")
    tr = tr.sort_values(["ticker", "ts"])
    by = {k: g for k, g in tr.groupby("ticker")}
    ask = np.where(sig["side"] == 1, sig["ask_c"], 1 - sig["bid_c"])
    edge = np.where(sig["side"] == 1, sig["p"], 1 - sig["p"]) - ask - fee(ask)
    sig = sig.assign(q_ask=ask, edge=edge, win=np.where(sig["side"] == 1, sig["y"], 1 - sig["y"]))
    sig = sig[sig["edge"] > thr].copy()
    print(f"signals with model edge > {thr:.2f}: {len(sig)} in {sig['ticker'].nunique()} markets, {sig['day'].nunique()} days; "
          f"markets with trade data: {sig['ticker'].isin(by).mean()*100:.0f}%")
    delays, W = [0.5, 1, 2, 3, 5, 10, 20, 30, 45], 15.0
    rows = []
    for r in sig.itertuples():
        g = by.get(r.ticker)
        rec = {"day": r.day, "series": r.series, "q_ask": r.q_ask, "win": r.win, "ml": r.minutes_left}
        if g is None:
            rows.append(rec)
            continue
        own = g[g["taker_side"] == ("yes" if r.side == 1 else "no")]
        t_, p_, c_ = own["ts"].values, (own["yes_price"].values if r.side == 1 else own["no_price"].values), own["count"].values
        t = float(r.end_period_ts)
        j0 = np.searchsorted(t_, t)
        rec["last_before"] = p_[j0 - 1] if j0 > 0 and t - t_[j0 - 1] < 30 else np.nan
        k = np.searchsorted(t_, t + 60)
        rec["n_prints_60s"] = int(k - j0)
        rec["vol_60s_at_or_below_quote"] = float(c_[j0:k][p_[j0:k] <= r.q_ask + 1e-9].sum())
        rec["t_first"] = (t_[j0] - t) if j0 < len(t_) and t_[j0] - t < 60 else np.nan
        rec["p_first"] = p_[j0] if j0 < len(t_) and t_[j0] - t < 60 else np.nan
        for d in delays:
            j = np.searchsorted(t_, t + d)
            rec[f"p_{d}"] = p_[j] if j < len(t_) and t_[j] <= t + d + W else np.nan
        rows.append(rec)
    x = pd.DataFrame(rows)
    x["pnl_quote"] = x["win"] - x["q_ask"] - fee(x["q_ask"])
    print(f"displayed-quote P&L (what E003 measured): {x['pnl_quote'].mean()*100:+.2f}c  win rate {x['win'].mean()*100:.0f}%  mean quoted ask {x['q_ask'].mean()*100:.1f}c")
    print(f"signals followed by a same-side taker print within 60 s: {x['t_first'].notna().mean()*100:.0f}%; median time to first print {x['t_first'].median():.1f}s")
    print(f"median contracts printed within 60 s at or below the quoted ask: {x['vol_60s_at_or_below_quote'].median():.0f} (mean {x['vol_60s_at_or_below_quote'].mean():.0f}); share of signals with zero: {(x['vol_60s_at_or_below_quote'].fillna(0) == 0).mean()*100:.0f}%")

    def ci(v, days, n=600):
        df = pd.DataFrame({"v": v, "d": days}).dropna()
        g = df.groupby("d")["v"].agg(["sum", "count"])
        if len(g) < 4:
            return (np.nan, np.nan)
        rng = np.random.default_rng(1)
        idx = rng.integers(0, len(g), size=(n, len(g)))
        m = g["sum"].values[idx].sum(1) / np.maximum(g["count"].values[idx].sum(1), 1)
        return np.percentile(m, 2.5), np.percentile(m, 97.5)

    print("\nfill at the first same-side taker print at or after t+delay (within 15 s of it):")
    print(f"{'delay':>6s} {'n':>6s} {'share':>6s} {'price':>7s} {'slip vs quote':>14s} {'P&L':>8s} {'95% CI':>18s} {'P&L same signals at quote':>26s}")
    for d in delays:
        c = f"p_{d}"
        m = x[c].notna()
        if m.sum() < 20:
            continue
        pnl = x.loc[m, "win"] - x.loc[m, c] - fee(x.loc[m, c])
        lo, hi = ci(pnl.values, x.loc[m, "day"].values)
        print(f"{d:6.1f} {m.sum():6d} {m.mean()*100:5.0f}% {x.loc[m, c].mean()*100:6.1f}c {(x.loc[m, c] - x.loc[m, 'q_ask']).mean()*100:+13.2f}c {pnl.mean()*100:+7.2f}c [{lo*100:+.2f},{hi*100:+.2f}] {x.loc[m, 'pnl_quote'].mean()*100:+25.2f}c")
    print("\nby series, delay 2 s:")
    m = x["p_2"].notna()
    for s, g in x[m].groupby("series"):
        pnl = g["win"] - g["p_2"] - fee(g["p_2"])
        print(f"  {s:10s} n={len(g):5d} P&L {pnl.mean()*100:+6.2f}c  slip {(g['p_2']-g['q_ask']).mean()*100:+5.2f}c")
    print("\nsignals with NO same-side print within 60 s (availability unknown):")
    nm = x["t_first"].isna()
    print(f"  n={nm.sum()} ({nm.mean()*100:.0f}%), displayed-quote P&L on these {x.loc[nm, 'pnl_quote'].mean()*100:+.2f}c vs {x.loc[~nm, 'pnl_quote'].mean()*100:+.2f}c on signals with prints")


if __name__ == "__main__":
    main()
