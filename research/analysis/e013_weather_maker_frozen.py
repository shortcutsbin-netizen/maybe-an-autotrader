#!/usr/bin/env python3
"""E013 — frozen weather favorite-side maker rule on periods it has not been simulated on.

Pre-registered in docs/experiments/E012-E013-preregistration.md before the new data was pulled.

Rule W (frozen): every 30 minutes, for every daily-high bracket with a two-sided quote,
until 30 minutes before the market closes:
  * YES mid >= 0.90 -> rest a BUY YES order at the best bid for 30 minutes
  * YES mid <= 0.20 -> rest a SELL YES order at the best ask for 30 minutes (= buy NO at 1 - ask)
No maker fee on these series. Fill rules from e008_maker_sim.simulate (through = primary,
touch = optimistic, improve = one tick inside a >= 2-tick spread).
P&L per filled contract, and per dollar of capital (price paid for the side bought).

Usage: e013_weather_maker_frozen.py <kalshi_runs_comma> <trades_dirs_comma> <first_day> <last_day>
"""
import glob
import sys
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e004_weather import load_markets  # noqa: E402
from e008_maker_sim import simulate  # noqa: E402


def load_trades(dirs, tickers):
    parts = []
    for dd in dirs.split(","):
        for f in sorted(glob.glob(f"{dd}/trades*.csv.gz")):
            t = pd.read_csv(f, usecols=["ticker", "created_time", "yes_price", "count", "taker_side"])
            parts.append(t[t["ticker"].isin(tickers)])
    tr = pd.concat(parts, ignore_index=True).dropna(subset=["yes_price", "taker_side"])
    tr["ts"] = (pd.to_datetime(tr["created_time"], utc=True, format="ISO8601") - pd.Timestamp(0, tz="UTC")) / pd.Timedelta("1s")
    tr = tr.drop_duplicates(["ticker", "created_time", "yes_price", "count", "taker_side"]).sort_values(["ticker", "ts"])
    return {k: (g["ts"].values, g["yes_price"].values.astype(float), (g["taker_side"] == "yes").values, g["count"].values.astype(float))
            for k, g in tr.groupby("ticker")}


def ci(df, col, n=1000):
    x = df.dropna(subset=[col])
    g = x.groupby("day")[col].agg(["sum", "count"])
    if len(g) < 4:
        return np.nan, np.nan
    rng = np.random.default_rng(2)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    m = g["sum"].values[idx].sum(1) / np.maximum(g["count"].values[idx].sum(1), 1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5)


def main():
    kr, tdirs, first, last = sys.argv[1:5]
    mk = load_markets(kr)
    mk = mk[(mk["day"] >= first) & (mk["day"] <= last)]
    cd = pd.concat([pd.read_csv(f) for r in kr.split(",") for f in glob.glob(f"{r}/candles/KXHIGH*.csv.gz")], ignore_index=True).dropna(subset=["bid_c", "ask_c"])
    cd = cd[cd["ticker"].isin(mk["ticker"])].drop_duplicates(["ticker", "end_period_ts"])
    cd["t"] = ((cd["end_period_ts"] + 599) // 600) * 600
    cd = cd.sort_values(["ticker", "end_period_ts"]).drop_duplicates(["ticker", "t"], keep="last")
    d = cd.merge(mk[["ticker", "city", "day", "d1", "y", "close_ts"]], on="ticker")
    d = d[(d["t"] % 1800 == 0) & (d["t"] < d["close_ts"] - 1800)]
    d["t"] = d["end_period_ts"]
    d = d.rename(columns={"bid_c": "bid", "ask_c": "ask"})
    d = d[(d["bid"] > 0) & (d["ask"] < 1) & (d["ask"] > d["bid"])]
    d["mid"] = (d["bid"] + d["ask"]) / 2
    d = d[(d["mid"] >= 0.90) | (d["mid"] <= 0.20)].copy()
    trades = load_trades(tdirs, set(d["ticker"]))
    cover = d["ticker"].isin(trades).mean()
    d = d[d["ticker"].isin(trades)]
    d = simulate(d, trades, 1800.0, lambda b, a: np.full(len(b), 0.01))
    print(f"period {first}..{last}: city-days={d.groupby(['city','day']).ngroups} markets={d['ticker'].nunique()} eligible quotes={len(d)} "
          f"(trade coverage of eligible quotes {cover*100:.0f}%) mean spread {100*(d['ask']-d['bid']).mean():.2f}c")
    fav = d[d["mid"] >= 0.90]
    lng = d[d["mid"] <= 0.20]
    out = []
    for name, g, side, cost in (("buy YES >= 90c", fav, "buy", lambda g, rule: g["bid"] + (0.01 if rule == "improve" else 0)),
                                ("sell YES <= 20c", lng, "sell", lambda g, rule: 1 - g["ask"] + (0.01 if rule == "improve" else 0))):
        for rule in ("through", "touch", "improve"):
            col = f"pnl_{side}_{rule}"
            f = g.dropna(subset=[col])
            if len(f) < 10:
                print(f"  {name:16s} {rule:8s} fills={len(f)}")
                continue
            lo, hi = ci(g, col)
            c = cost(f, rule)
            roc = (f[col] / c).mean()
            print(f"  {name:16s} {rule:8s} fills={len(f):6d} ({len(f)/max(g['day'].nunique(),1):.0f}/day) P&L/fill {f[col].mean()*100:+.2f}c "
                  f"[{lo*100:+.2f},{hi*100:+.2f}] win {np.mean(f[col] > 0)*100:.1f}% capital/fill {c.mean()*100:.0f}c return on capital {roc*100:+.2f}%  worst fill {f[col].min()*100:.0f}c")
            out.append(f.assign(rule=rule, leg=name, pnl=f[col], cost=c)[["day", "city", "ticker", "rule", "leg", "pnl", "cost", "mid"]])
    if out:
        o = pd.concat(out)
        th = o[o["rule"] == "through"]
        lo, hi = ci(th, "pnl")
        daily = th.groupby("day")["pnl"].sum()
        print(f"  COMBINED (through): fills={len(th)} P&L/fill {th['pnl'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] "
              f"days positive {(daily > 0).sum()}/{len(daily)}; per city: " +
              ", ".join(f"{c}:{len(g)}/{g['pnl'].mean()*100:+.1f}" for c, g in th.groupby("city")))
        print("  COMBINED (through) by month: " + ", ".join(f"{m}:{len(g)}/{g['pnl'].mean()*100:+.2f}c" for m, g in th.groupby(th['day'].str[:7])))
        print(f"  illustration, 10 contracts per through-fill: mean ${daily.mean()*10:.2f}/day, worst ${daily.min()*10:.2f}, best ${daily.max()*10:.2f}, "
              f"max drawdown ${float((daily.cumsum().cummax() - daily.cumsum()).max())*10:.2f}")


if __name__ == "__main__":
    main()
