#!/usr/bin/env python3
"""E002 — symmetric favorite/underdog view of E001 for the up/down series only
(excludes KXCRYPTOLEAD15M, a 5-outcome market with ~8c spreads).

For every two-sided quote: favorite = side with mid > 0.5.
  ev_fav  = P(fav wins) - fav_ask - fee      (taker buys the favorite)
  ev_dog  = P(dog wins) - dog_ask - fee      (taker buys the underdog)
`_cons` = conservative fill (worse of this quote and next minute's open, plus one tick).
Usage: e002_favorite_side.py <run_dir> <split>
"""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e001_calibration import load, split_days, add_ev, day_boot_ci

run, split = sys.argv[1], sys.argv[2]
mk, df = load(run)
days = split_days(mk)[split]
df = df[df["day"].isin(days) & (df["series"] != "KXCRYPTOLEAD15M")]
d = add_ev(df)
fav_yes = d["mid"] > 0.5
d = d[d["mid"] != 0.5].copy(); fav_yes = d["mid"] > 0.5
d["fav_ask"] = np.where(fav_yes, d["ask_c"], 1 - d["bid_c"])
d["fav_win"] = np.where(fav_yes, d["y"], 1 - d["y"])
for s in ("", "_cons"):
    d["ev_fav" + s] = np.where(fav_yes, d["ev_yes" + s], d["ev_no" + s])
    d["ev_dog" + s] = np.where(fav_yes, d["ev_no" + s], d["ev_yes" + s])
d["abin"] = pd.cut(d["fav_ask"], [.5, .6, .7, .8, .9, .95, .97, .98, .99, 1.0])
d["tbin"] = pd.cut(d["minutes_left"], [0, 1, 2, 4, 7, 10, 14], labels=["1", "2", "3-4", "5-7", "8-10", "11-14"])

def table(by):
    rows = []
    for key, g in d.groupby(by, observed=True):
        lo, hi = day_boot_ci(g, "ev_fav_cons")
        lo2, hi2 = day_boot_ci(g, "ev_dog_cons")
        rows.append({"key": key, "n": len(g), "fav_ask": g["fav_ask"].mean() * 100, "fav_win%": g["fav_win"].mean() * 100,
                     "ev_fav": g["ev_fav"].mean() * 100, "ev_fav_cons": g["ev_fav_cons"].mean() * 100,
                     "fav_ci": f"[{lo*100:+.2f},{hi*100:+.2f}]",
                     "ev_dog": g["ev_dog"].mean() * 100, "ev_dog_cons": g["ev_dog_cons"].mean() * 100,
                     "dog_ci": f"[{lo2*100:+.2f},{hi2*100:+.2f}]"})
    return pd.DataFrame(rows).round(2)

pd.set_option("display.width", 220); pd.set_option("display.max_rows", 200)
print(f"split={split} days={days[0]}..{days[-1]} ({len(days)}) rows={len(d)}  [cents per contract]")
print("\n== by favorite ask"); print(table(["abin"]).to_string(index=False))
print("\n== by minutes left"); print(table(["tbin"]).to_string(index=False))
print("\n== minutes left x favorite ask (ask >= 0.90 only)")
t = table(["tbin", "abin"]); print(t[t["fav_ask"] >= 90].to_string(index=False))
print("\n== by series, favorite ask >= 0.95")
d = d[d["fav_ask"] >= 0.95]; print(table(["series"]).to_string(index=False))
