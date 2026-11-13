#!/usr/bin/env python3
"""E008 — would resting (maker) orders have made money? Simulation from public
trade prints, for series with zero maker fee (weather ladders, 15-min crypto).

At each decision time t with a two-sided quote (bid b, ask a) we imagine two
independent resting orders that live for L seconds and are then cancelled:
  BUY  YES at b   -> P&L if filled = outcome - b
  SELL YES at a   -> P&L if filled = a - outcome      (same as buying NO at 1-a)
No fee (maker fee is zero on these series).

Historical depth is not available, so queue position is unknown. Three fill rules bracket it:
  touch   (optimistic)   a taker print on the other side at our price or better
  through (conservative) a taker print strictly through our price (we would certainly have filled)
  improve                only when the spread is >= 2 ticks: we quote one tick inside the
                         spread (so we are first in line); filled by the first opposing taker
                         print at our price or better
Adverse selection is inside the numbers: orders fill precisely when someone
with fresher information trades against them.

Usage: e008_maker_sim.py weather <kalshi_runs_comma> <trades_run> <split>
       e008_maker_sim.py crypto  <full_run>         <trades_run> <split>
Split: same chronological day split as the other experiments (train|val).
"""
import glob
import sys
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
sys.path.insert(0, __file__.rsplit("/", 1)[0])


def load_trades(run, tickers):
    tr = pd.concat([pd.read_csv(f, usecols=["ticker", "created_time", "yes_price", "count", "taker_side"]) for f in sorted(glob.glob(f"{run}/trades*.csv.gz"))], ignore_index=True)
    tr = tr[tr["ticker"].isin(tickers)].dropna(subset=["yes_price", "taker_side"])
    tr["ts"] = (pd.to_datetime(tr["created_time"], utc=True, format="ISO8601") - pd.Timestamp(0, tz="UTC")) / pd.Timedelta("1s")
    tr = tr.drop_duplicates(["ticker", "created_time", "yes_price", "count", "taker_side"]).sort_values(["ticker", "ts"])
    return {k: (g["ts"].values, g["yes_price"].values.astype(float), (g["taker_side"] == "yes").values, g["count"].values.astype(float))
            for k, g in tr.groupby("ticker")}


def simulate(d, trades, L, tick_fn):
    """d: rows with ticker, t, bid, ask, y. Adds fill flags and P&L columns."""
    n = len(d)
    out = {k: np.zeros(n, dtype=bool) for k in ("buy_touch", "buy_through", "buy_improve", "sell_touch", "sell_through", "sell_improve")}
    has = np.zeros(n, dtype=bool)
    tk, tt, bid, ask = d["ticker"].values, d["t"].values.astype(float), d["bid"].values, d["ask"].values
    tick = tick_fn(bid, ask)
    wide = (ask - bid) >= 2 * tick - 1e-9
    order = np.argsort(tk, kind="stable")
    i = 0
    while i < n:
        j = i
        while j < n and tk[order[j]] == tk[order[i]]:
            j += 1
        g = trades.get(tk[order[i]])
        if g is not None:
            ts, px, isyes, _ = g
            for r in order[i:j]:
                has[r] = True
                a0, a1 = np.searchsorted(ts, tt[r], side="right"), np.searchsorted(ts, tt[r] + L, side="right")
                if a1 <= a0:
                    continue
                p, s = px[a0:a1], isyes[a0:a1]
                sells, buys = p[~s], p[s]            # taker sold YES (hits bids) / taker bought YES (lifts asks)
                if len(sells):
                    mn = sells.min()
                    out["buy_touch"][r] = mn <= bid[r] + 1e-9
                    out["buy_through"][r] = mn < bid[r] - 1e-9
                    out["buy_improve"][r] = wide[r] and (mn <= bid[r] + tick[r] + 1e-9)
                if len(buys):
                    mx = buys.max()
                    out["sell_touch"][r] = mx >= ask[r] - 1e-9
                    out["sell_through"][r] = mx > ask[r] + 1e-9
                    out["sell_improve"][r] = wide[r] and (mx >= ask[r] - tick[r] - 1e-9)
        i = j
    d = d.assign(has_trades=has, tick=tick, wide=wide, **out)
    y = d["y"].values
    for rule in ("touch", "through"):
        d[f"pnl_buy_{rule}"] = np.where(d[f"buy_{rule}"], y - bid, np.nan)
        d[f"pnl_sell_{rule}"] = np.where(d[f"sell_{rule}"], ask - y, np.nan)
    d["pnl_buy_improve"] = np.where(d["buy_improve"], y - (bid + tick), np.nan)
    d["pnl_sell_improve"] = np.where(d["sell_improve"], (ask - tick) - y, np.nan)
    return d


def ci(df, col, n=500):
    x = df.dropna(subset=[col])
    g = x.groupby("day")[col].agg(["sum", "count"])
    if len(g) < 4:
        return np.nan, np.nan
    rng = np.random.default_rng(2)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    m = g["sum"].values[idx].sum(1) / np.maximum(g["count"].values[idx].sum(1), 1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5)


def report(d, by, title):
    print(f"\n== {title}  [cents per filled contract; n = filled orders; fill% = share of posted orders filled]")
    for key, g in d.groupby(by, observed=True):
        line = f"  {str(key):26s} posted={len(g):6d} "
        for side in ("buy", "sell"):
            for rule in ("touch", "through", "improve"):
                c = f"pnl_{side}_{rule}"
                k = g[c].notna().sum()
                if k < 25:
                    line += f"| {side[0].upper()}-{rule[:3]} n={k:5d}            "
                    continue
                lo, hi = ci(g, c)
                line += f"| {side[0].upper()}-{rule[:3]} n={k:5d} {g[c].mean()*100:+5.2f} [{lo*100:+.1f},{hi*100:+.1f}] "
        print(line)


def main():
    domain, kr, trun, split = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    if domain == "weather":
        from e004_weather import load_markets
        mk = load_markets(kr)
        cd = pd.concat([pd.read_csv(f) for r in kr.split(",") for f in glob.glob(f"{r}/candles/KXHIGH*.csv.gz")], ignore_index=True).dropna(subset=["bid_c", "ask_c"])
        cd = cd.drop_duplicates(["ticker", "end_period_ts"])
        cd["t"] = ((cd["end_period_ts"] + 599) // 600) * 600
        cd = cd.sort_values(["ticker", "end_period_ts"]).drop_duplicates(["ticker", "t"], keep="last")
        d = cd.merge(mk[["ticker", "city", "day", "d1", "y", "close_ts"]], on="ticker")
        d = d[(d["t"] % 1800 == 0) & (d["t"] < d["close_ts"] - 1800)]
        d["grp"] = d["city"]
        d["seg"] = pd.cut((d["d1"] - d["t"]) / 3600, [-9, 5, 12, 24, 99], labels=["evening", "afternoon", "morning", "day-before"])
        L = 1800.0
        tick_fn = lambda b, a: np.full(len(b), 0.01)
        t_actual = d["end_period_ts"].values            # the quote was observed at the candle's own end time
        d["t"] = t_actual
        days = sorted(d["day"].unique())
    else:
        from e001_calibration import load, split_days
        mk, df = load(kr)
        d = df[(df["k"] >= 1) & (df["k"] <= 13) & (df["series"] != "KXCRYPTOLEAD15M")].copy()
        d["t"] = d["end_period_ts"]
        d["grp"] = d["series"]
        d["seg"] = pd.cut(d["minutes_left"], [0, 3, 7, 14], labels=["2-3 min left", "4-7", "8-14"])
        L = 60.0
        tick_fn = lambda b, a: np.where((b < 0.10) | (a > 0.90), 0.001, 0.01)
        days = None
    d = d.rename(columns={"bid_c": "bid", "ask_c": "ask"})
    d = d[(d["bid"] > 0) & (d["ask"] < 1) & (d["ask"] > d["bid"])]
    trades = load_trades(trun, set(d["ticker"]))
    d = d[d["ticker"].isin(trades)]
    if days is None:
        days = sorted(d["day"].unique())                # crypto: only sampled days have trades
    a, b = int(len(days) * 0.6), int(len(days) * 0.8)
    sel = {"train": days[:a], "val": days[a:b], "trainval": days[:b], "all": days}[split]
    d = d[d["day"].isin(sel)].copy()
    print(f"domain={domain} split={split} days={sel[0]}..{sel[-1]} ({len(sel)}) markets={d['ticker'].nunique()} posted order-pairs={len(d)} order life={L:.0f}s mean spread={100*(d['ask']-d['bid']).mean():.2f}c")
    d = simulate(d, trades, L, tick_fn)
    d["mid"] = (d["bid"] + d["ask"]) / 2
    d["pb"] = pd.cut(d["mid"], [0, .05, .1, .2, .35, .5, .65, .8, .9, .95, 1])
    for side in ("buy", "sell"):
        print(f"fill rates {side}: touch {d[f'{side}_touch'].mean()*100:.1f}%  through {d[f'{side}_through'].mean()*100:.1f}%  improve {d[f'{side}_improve'].mean()*100:.1f}% (spread>=2 ticks on {d['wide'].mean()*100:.0f}% of rows)")
    report(d, ["pb"], "by price of YES (B = buy YES at bid, S = sell YES at ask)")
    report(d, ["seg"], "by time")
    report(d, ["grp"], "by series/city")
    # the two classic maker ideas
    lo_ = d[d["mid"] <= 0.10]
    hi_ = d[d["mid"] >= 0.90]
    print("\n== focus: sell longshots (YES priced <= 10c) and buy favorites (YES >= 90c) as a maker")
    for name, g, c in (("sell YES<=10c", lo_, "sell"), ("buy YES>=90c", hi_, "buy")):
        for rule in ("touch", "through", "improve"):
            col = f"pnl_{c}_{rule}"
            k = g[col].notna().sum()
            if k >= 25:
                lo, hi = ci(g, col)
                per_day = k / max(len(sel), 1)
                print(f"  {name:14s} {rule:8s} fills={k:6d} ({per_day:.0f}/day) P&L/fill {g[col].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] win {np.mean(g[col].dropna()>0)*100:.1f}%")


if __name__ == "__main__":
    main()
