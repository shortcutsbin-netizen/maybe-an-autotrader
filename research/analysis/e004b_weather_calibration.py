#!/usr/bin/env python3
"""E004b — price-level calibration of daily-high markets (the E001/E002 test applied to weather).
One quote per market per 30 minutes; taker fee 0.07*p*(1-p); fill = ask 10 minutes later + 1 tick.
Usage: e004b_weather_calibration.py <kalshi_runs_comma_sep> <split: train|val>
"""
import glob, sys, warnings
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e004_weather import load_markets, fee, day_ci

kr, split = sys.argv[1], sys.argv[2]
mk = load_markets(kr)
cd = pd.concat([pd.read_csv(f) for r in kr.split(",") for f in glob.glob(f"{r}/candles/KXHIGH*.csv.gz")], ignore_index=True).dropna(subset=["bid_c", "ask_c"])
cd = cd.drop_duplicates(["ticker", "end_period_ts"]).sort_values(["ticker", "end_period_ts"])
cd["t"] = ((cd["end_period_ts"] + 599) // 600) * 600
cd = cd.drop_duplicates(["ticker", "t"], keep="last")
cd["ask_n"], cd["bid_n"] = cd.groupby("ticker")["ask_c"].shift(-1), cd.groupby("ticker")["bid_c"].shift(-1)
d = cd.merge(mk[["ticker", "city", "day", "d1", "y", "strike_type"]], on="ticker")
d = d[(d["t"] % 1800 == 0) & (d["bid_c"] > 0) & (d["ask_c"] < 1) & (d["ask_n"] < 1) & (d["bid_n"] > 0)]
days = sorted(d["day"].unique()); a, b = int(len(days) * .6), int(len(days) * .8)
d = d[d["day"].isin({"train": days[:a], "val": days[a:b]}[split])].copy()
d["mid"] = (d["bid_c"] + d["ask_c"]) / 2
d["h_left"] = (d["d1"] - d["t"]) / 3600
a2 = np.minimum(d["ask_n"] + .01, .99); n2 = np.minimum(1 - d["bid_n"] + .01, .99)
d["ev_yes"] = d["y"] - a2 - fee(a2); d["ev_no"] = (1 - d["y"]) - n2 - fee(n2); d["err"] = d["y"] - d["mid"]
d["pb"] = pd.cut(d["mid"], [0, .05, .1, .2, .35, .5, .65, .8, .9, .95, 1])
d["seg"] = pd.cut(d["h_left"], [-9, 5, 12, 24, 99], labels=["evening", "afternoon", "morning", "day-before"])
print(f"split={split} days={d['day'].min()}..{d['day'].max()} rows={len(d)} markets={d['ticker'].nunique()} mean spread={100*(d['ask_c']-d['bid_c']).mean():.2f}c  [cents; fills delayed 10 min + 1 tick]")
def show(by):
    for k, g in d.groupby(by, observed=True):
        e = day_ci(g, "err"); y_ = day_ci(g, "ev_yes"); n_ = day_ci(g, "ev_no")
        print(f"  {str(k):28s} n={len(g):6d} mid={g['mid'].mean()*100:5.1f} win={g['y'].mean()*100:5.1f} err={g['err'].mean()*100:+5.2f} [{e[0]*100:+.2f},{e[1]*100:+.2f}] | YES {g['ev_yes'].mean()*100:+5.2f} [{y_[0]*100:+.2f},{y_[1]*100:+.2f}] | NO {g['ev_no'].mean()*100:+5.2f} [{n_[0]*100:+.2f},{n_[1]*100:+.2f}]")
print("by price"); show(["pb"]); print("by time"); show(["seg"]); print("by city"); show(["city"]); print("by bracket type"); show(["strike_type"])
print("by time x price (tails)"); d2 = d; d = d[(d["mid"] <= .1) | (d["mid"] >= .9)]; show(["seg", "pb"])
