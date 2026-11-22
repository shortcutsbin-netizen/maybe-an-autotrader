#!/usr/bin/env python3
"""E015b - the frozen S1-D model applied to hourly above/below ladder strikes in their last 15 minutes.

The ladder strike K settles on the same 60-second CF average as the 15-minute market closing on the hour.
In the last 15 minutes a ladder market is economically a 15-minute up/down contract with strike K instead of
K15. We feed the ladder's own quotes through the frozen model (fitted 2026-09-13..10-11 on 15-minute markets,
no refit), with the spot-vs-strike features recomputed against K (r = ln(spot / K)).

Ladders have no public print data in our pulls, so fills are read from candles only:
  now  = the minute-end quote (optimistic)
  next = the next minute's close quote (one-minute delay; E003 found that this removes most of the edge on
         15-minute markets, so a positive 'next' would be strong evidence)
Threshold 8c as E010 (no tuning). One trade per ladder market (first signal).

usage: e015b_s1d_on_ladders.py <fit_run> <ladder_run> <work_dir> <15m_run> [<15m_run> ...]
"""
import glob
import os
import shutil
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e012_frozen_new_periods import ci, fit_frozen  # noqa: E402

THR = 0.08


def fee(p):
    return 0.07 * p * (1 - p)


def make_pseudo_run(ladder_run, runs15, work):
    if os.path.exists(work):
        shutil.rmtree(work)
    for d in ("markets", "candles", "spot"):
        os.makedirs(os.path.join(work, d))
    kept = glob.glob(os.path.join(ladder_run, "markets", "*_kept.csv.gz"))[0]
    s15 = [os.path.basename(f).replace(".csv.gz", "") for f in glob.glob(os.path.join(ladder_run, "markets", "*15M.csv.gz"))][0]
    lm = pd.read_csv(kept)
    lm["series"] = s15                                   # so the spot mapping of the 15-minute series applies
    ct = pd.to_datetime(lm.close_time, utc=True)
    lm["open_time"] = (ct - pd.Timedelta("15min")).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    lm.to_csv(os.path.join(work, "markets", f"{s15}.csv.gz"), index=False)
    # BTC 15-minute market rows are needed only for its spot grid; build() reads spot files, not BTC markets
    for f in glob.glob(os.path.join(ladder_run, "candles", "*.csv.gz")):
        shutil.copy(f, os.path.join(work, "candles", "ladder_" + os.path.basename(f)))
    # concatenate spot files across the 15-minute runs (same product names)
    prods = {}
    for r in runs15:
        for f in glob.glob(os.path.join(r, "spot", "*.csv.gz")):
            prods.setdefault(os.path.basename(f), []).append(pd.read_csv(f))
    for name, parts in prods.items():
        p = pd.concat(parts).drop_duplicates(subset=[parts[0].columns[0]]).sort_values(parts[0].columns[0])
        p.to_csv(os.path.join(work, "spot", name), index=False)
    return s15


def main():
    fit_run, ladder_run, work, runs15 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
    s15 = make_pseudo_run(ladder_run, runs15, work)
    m, E = fit_frozen(fit_run)
    d = E.build(work)
    # recompute the spot-vs-strike features against the ladder strike K
    tau = d["minutes_left"] - 40.0 / 60.0
    sig = d["rv60"].clip(lower=1e-6)
    d["r"] = np.log(d["c"] / d["floor_strike"].astype(float))
    d["z"] = d["r"] / (sig * np.sqrt(tau))
    d["z15"] = d["r"] / (d["rv15"].clip(lower=1e-6) * np.sqrt(tau))
    d["z_day"] = d["r"] / (d["rv1440"].clip(lower=1e-6) * np.sqrt(tau))
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=E.EXT + E.MKT + ["y"])
    d["p"] = m.predict_proba(d[E.EXT + E.MKT].values)[:, 1]
    d["pbase"] = norm.cdf(d["z"])
    print(f"{s15} ladder strikes: rows {len(d)}, markets {d.ticker.nunique()}, days {d.day.min()}..{d.day.max()}; "
          f"Brier ladder mid {np.mean((d.mid - d.y) ** 2):.4f} model {np.mean((d.p - d.y) ** 2):.4f} closed-form {np.mean((d.pbase - d.y) ** 2):.4f}; "
          f"median spread {d.spread.median() * 100:.1f}c, median volume/min {d.volume.median():.0f}")
    ey = d.p - d.ask_c - fee(d.ask_c)
    en = (1 - d.p) - (1 - d.bid_c) - fee(1 - d.bid_c)
    d["side"] = np.where((ey > THR) & (ey >= en), 1, np.where(en > THR, -1, 0))
    S = d[d.side != 0].sort_values("end_period_ts").groupby("ticker").head(1).copy()
    if not len(S):
        print("  no signals")
        return
    out = S.y.where(S.side == 1, 1 - S.y)
    for nm, a, b in (("now", "ask_c", "bid_c"), ("next", "ask_c_next", "bid_c_next")):
        pa = np.where(S.side == 1, S[a], 1 - S[b])
        S["pnl_" + nm] = out - pa - fee(pa)
    for nm in ("now", "next"):
        v = S.dropna(subset=["pnl_" + nm])
        lo, hi = ci(v["pnl_" + nm].values, v["day"].values)
        print(f"  signals {len(v)} ({len(v) / v.day.nunique():.1f}/day): fill {nm}: {v['pnl_' + nm].mean() * 100:+.2f}c [{lo * 100:+.2f},{hi * 100:+.2f}]"
              f"  median volume in signal minute {v.volume.median():.0f}")
    S["half"] = np.where(S.day < sorted(d.day.unique())[len(d.day.unique()) // 2], "H1", "H2")
    print("  by half (next):", S.dropna(subset=["pnl_next"]).groupby("half").pnl_next.agg(["count", "mean"]).round(4).to_dict("index"))
    print("  by |K/spot-1| (next):", S.dropna(subset=["pnl_next"]).groupby(pd.cut(S.r.abs(), [0, .001, .003, .01, 1])).pnl_next.agg(["count", "mean"]).round(4).to_dict("index"))


if __name__ == "__main__":
    main()
