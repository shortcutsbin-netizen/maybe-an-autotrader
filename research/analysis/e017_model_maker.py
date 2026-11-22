#!/usr/bin/env python3
"""E017 - model-informed resting orders on the 15-minute alt-coin markets (zero maker fee).

E009 showed that quoting around the Kalshi mid loses to adverse selection (-1.1c per fill). The
question here is different: does the frozen S1-D model (fitted 2026-09-13..10-11, never refitted)
make *deep* resting orders profitable? At every minute end t, with model probability q:

  buy  YES limit at L = q - delta (rounded down to the tick), only if L < ask  (otherwise it is a taker trade)
  sell YES limit at U = q + delta (rounded up to the tick),  only if U > bid
  each order lives 60 s (cancelled at the next minute end); one contract; no fee (maker fee is zero here)

Fill rules from public prints in (t, t + 60]:
  through : a print by a taker selling YES strictly below L (or buying YES strictly above U)  [primary]
  touch   : at or through the price (optimistic: ignores the queue)
P&L per fill = outcome - L (buy) or U - outcome (sell); held to settlement.

Splits (14 UTC sample days, chosen before this analysis): train = Jun 10, 24, Jul 8, 22, Aug 5, 19;
validation = Sep 2, Oct 14, 28 (Sep 16 / 30 lie inside the model's fit window and are excluded);
test = Nov 11, 17, 19 (opened once, for the variant chosen on train+validation). CIs bootstrap 4-hour blocks.

usage: e017_model_maker.py build   <fit_run> <out_csv> <run> [<run> ...]   (q for every sample-day row)
       e017_model_maker.py sim     <q_csv> <trade_dirs_comma> [test]
"""
import glob
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e012_frozen_new_periods import ci, fit_frozen  # noqa: E402

LISTS = sorted(glob.glob(__file__.rsplit("/", 2)[0] + "/collect/requests/lists_sample_days_*.txt"))
FIT_DAYS = ("2026-09-13", "2026-10-11")
DELTAS = (0.02, 0.04, 0.06, 0.08, 0.12, 0.16)


def tick_down(p):
    t = np.where((p < 0.10) | (p > 0.90), 0.001, 0.01)
    return np.floor(p / t + 1e-9) * t


def tick_up(p):
    t = np.where((p < 0.10) | (p > 0.90), 0.001, 0.01)
    return np.ceil(p / t - 1e-9) * t


def split_of(day):
    if day <= "2026-08-31":
        return "train"
    if FIT_DAYS[0] <= day <= FIT_DAYS[1]:
        return "fitwindow"
    if day <= "2026-10-31":
        return "val"
    return "test"


def build(fit_run, out_csv, runs):
    tick = set()
    for f in LISTS:
        tick |= set(open(f).read().split())
    m, E = fit_frozen(fit_run)
    parts = []
    for r in runs:
        x = E.build(r).dropna(subset=E.EXT + E.MKT + ["y"])
        x = x[x["ticker"].isin(tick)].copy()
        if not len(x):
            continue
        x["q"] = m.predict_proba(x[E.EXT + E.MKT].values)[:, 1]
        parts.append(x[["ticker", "series", "day", "end_period_ts", "minutes_left", "q", "bid_c", "ask_c", "mid", "y"]])
        print(r, len(x), x["day"].min(), x["day"].max())
    q = pd.concat(parts).drop_duplicates(["ticker", "end_period_ts"])
    q.to_csv(out_csv, index=False)
    print("rows", len(q), "markets", q["ticker"].nunique(), "days", sorted(q["day"].unique()))


def window_extremes(q, trades_dirs):
    """min YES price sold by takers and max YES price bought by takers in (t, t+60] for each row."""
    tick = set(q["ticker"])
    parts = []
    for dd in trades_dirs.split(","):
        for f in sorted(glob.glob(f"{dd}/trades*.csv.gz")):
            t = pd.read_csv(f, usecols=["ticker", "created_time", "yes_price", "count", "taker_side"])
            parts.append(t[t["ticker"].isin(tick)])
    tr = pd.concat(parts, ignore_index=True).drop_duplicates()
    tr["ts"] = (pd.to_datetime(tr["created_time"], utc=True, format="ISO8601") - pd.Timestamp(0, tz="UTC")) / pd.Timedelta("1s")
    tr["yes_price"] = tr["yes_price"].astype(float)
    print("prints", len(tr), "markets with prints", tr["ticker"].nunique(), "of", len(tick))
    lo = np.full(len(q), np.nan)
    hi = np.full(len(q), np.nan)
    have = np.zeros(len(q), bool)
    q = q.reset_index(drop=True)
    g = dict(tuple(tr.sort_values("ts").groupby("ticker")))
    for tk, idx in q.groupby("ticker").groups.items():
        if tk not in g:
            continue
        have[idx] = True
        d = g[tk]
        ts, px, side = d["ts"].values, d["yes_price"].values, d["taker_side"].values
        t0 = q.loc[idx, "end_period_ts"].values.astype(float)
        a = np.searchsorted(ts, t0, side="right")
        b = np.searchsorted(ts, t0 + 60.0, side="right")
        for k, (i, j) in enumerate(zip(a, b)):
            if j > i:
                s, p = side[i:j], px[i:j]
                sell = p[s == "no"]           # taker sold YES (bought NO): hits resting YES bids
                buy = p[s == "yes"]           # taker bought YES: lifts resting YES asks
                if len(sell):
                    lo[idx[k]] = sell.min()
                if len(buy):
                    hi[idx[k]] = buy.max()
    q["lo"], q["hi"], q["has_prints"] = lo, hi, have
    return q


def simulate(q, ref="q"):
    rows = []
    for d in DELTAS:
        L = tick_down(q[ref] - d)
        U = tick_up(q[ref] + d)
        okb = (L < q["ask_c"]) & (L > 0)
        oks = (U > q["bid_c"]) & (U < 1)
        for rule in ("through", "touch"):
            fb = okb & (q["lo"] < L if rule == "through" else q["lo"] <= L)
            fs = oks & (q["hi"] > U if rule == "through" else q["hi"] >= U)
            for side, f, pnl, deep in (("buy", fb, q["y"] - L, L < q["bid_c"]), ("sell", fs, U - q["y"], U > q["ask_c"])):
                x = q[f].assign(pnl=pnl[f], deep=deep[f], delta=d, rule=rule, side=side)
                rows.append(x[["ticker", "series", "day", "split", "minutes_left", "delta", "rule", "side", "deep", "pnl"]])
    return pd.concat(rows, ignore_index=True)


def report(f, label, splits):
    print(f"\n=== {label}")
    for rule in ("through", "touch"):
        for d in DELTAS:
            line = []
            for sp in splits:
                x = f[(f.rule == rule) & (f.delta == d) & (f.split == sp)]
                if len(x) < 10:
                    line.append(f"{sp}: n={len(x)}")
                    continue
                lo, hi = ci(x["pnl"].values, x["day"].values)
                nd = x["day"].nunique()
                line.append(f"{sp}: {len(x) / nd:5.1f} fills/4h {x.pnl.mean() * 100:+.2f}c [{lo * 100:+.2f},{hi * 100:+.2f}]")
            print(f"  {rule:7s} delta {d:.2f} | " + " | ".join(line))


def main():
    if sys.argv[1] == "build":
        return build(sys.argv[2], sys.argv[3], sys.argv[4:])
    q = pd.read_csv(sys.argv[2])
    q["split"] = q["day"].map(split_of)
    # the sample is 14 UTC days; bootstrap over 4-hour blocks so the validation and test CIs have enough clusters
    q["day"] = q["day"] + "T" + ((q["end_period_ts"] % 86400) // 14400).astype(str)
    q = q[q.split != "fitwindow"]
    test = len(sys.argv) > 4 and sys.argv[4] == "test"
    if not test:
        q = q[q.split != "test"]
    q = window_extremes(q, sys.argv[3])
    print("rows by split", q.groupby("split").size().to_dict(), "share of rows with any print in the next 60 s",
          round(float((q.lo.notna() | q.hi.notna()).mean()), 3))
    splits = ["train", "val"] + (["test"] if test else [])
    f = simulate(q, "q")
    report(f, "model-informed (q = frozen S1-D probability)", splits)
    report(f[f.deep], "model-informed, deep orders only (resting behind the touch)", splits)
    g = simulate(q.assign(qm=q["mid"]), "qm")
    report(g, "control: same rule around the Kalshi mid (E009 analogue)", splits)
    for sp in splits:
        x = f[(f.split == sp) & (f.rule == "through") & (f.delta == 0.08)]
        if len(x):
            print(f"\n{sp} through delta .08 by series:", x.groupby("series").pnl.agg(["count", "mean"]).round(4).to_dict("index"))
            print(f"{sp} through delta .08 by minutes left:",
                  x.groupby(pd.cut(x.minutes_left, [0, 2, 5, 10, 15])).pnl.agg(["count", "mean"]).round(4).to_dict("index"))
            print(f"{sp} through delta .08 by side:", x.groupby("side").pnl.agg(["count", "mean"]).round(4).to_dict("index"))


if __name__ == "__main__":
    main()
