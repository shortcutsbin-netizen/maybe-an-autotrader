#!/usr/bin/env python3
"""E014 (exploratory) — in-game sports: Kalshi game-winner price vs ESPN's published win probability.

Question: during a game, does ESPN's play-by-play win-probability model, read with a realistic delay,
know something the Kalshi price does not — and is the gap tradeable after the taker fee?

Inputs: Kalshi run (sp-001: markets + 1-minute candles for each market's last 9 hours),
        external run (ext-sp-001: ESPN games), ESPN WP run (espn-wp-001: wp_<league>.csv.gz).
Usage: e014_sports_ingame_wp.py <kalshi_run> <ext_run> <wp_run> <split: train|val|trainval> [lag_s=30]

At each minute end t during play (start + 5 min .. close - 5 min):
  p_espn = ESPN home-win probability of the latest play with wall-clock time <= t - lag, for this market's team
  Kalshi mid/ask/bid from the 1-minute candle close at t
Fill for any trade: the ask one minute later plus one cent (in-game prices move fast; displayed quote at t is not assumed).
Same chronological 60/20/20 day split as E005; the test split is not read.
"""
import glob
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e005_sports import load, match, boot_ci, brier  # noqa: E402


def fee(p):
    return 0.07 * p * (1 - p)


def main():
    krun, erun, wrun, split = sys.argv[1:5]
    lag = float(sys.argv[5]) if len(sys.argv) > 5 else 30.0
    mk, g = load(krun, erun)
    m, _ = match(mk, g)
    m["espn_id"] = m["espn_id"].astype(str)
    wp = pd.concat([pd.read_csv(f, dtype={"espn_id": str, "play_id": str}) for f in glob.glob(f"{wrun}/wp_*.csv.gz")], ignore_index=True)
    wp = wp.dropna(subset=["wallclock", "home_wp"])
    wp["ts"] = (pd.to_datetime(wp["wallclock"], utc=True, format="ISO8601", errors="coerce") - pd.Timestamp(0, tz="UTC")) / pd.Timedelta("1s")
    wp = wp.dropna(subset=["ts"]).sort_values("ts")
    have = set(wp["espn_id"])
    m = m[m["espn_id"].isin(have)]
    print(f"ESPN WP rows={len(wp)} games with WP={len(have)}; Kalshi markets matched to a game with WP={len(m)} (games {m['espn_id'].nunique()}, leagues {m['league'].value_counts().to_dict()})")
    days = sorted(m["gdate"].unique())
    a, b = int(len(days) * 0.6), int(len(days) * 0.8)
    sp = {"train": days[:a], "val": days[a:b], "trainval": days[:b]}
    cd = pd.concat([pd.read_csv(f) for f in glob.glob(f"{krun}/candles/*.csv.gz")], ignore_index=True)
    cd = cd[cd["ticker"].isin(m["ticker"])].drop_duplicates(["ticker", "end_period_ts"]).sort_values(["ticker", "end_period_ts"])
    cd["ask_n"] = cd.groupby("ticker")["ask_c"].shift(-1)
    cd["bid_n"] = cd.groupby("ticker")["bid_c"].shift(-1)
    cd["t_n"] = cd.groupby("ticker")["end_period_ts"].shift(-1)
    d = cd.merge(m[["ticker", "espn_id", "is_home", "y", "start_ts", "close_ts", "gdate", "league", "p_book_close"]], on="ticker")
    d = d[(d["end_period_ts"] >= d["start_ts"] + 300) & (d["end_period_ts"] <= d["close_ts"] - 300)]
    d = d[(d["bid_c"] > 0) & (d["ask_c"] < 1) & (d["ask_c"] >= d["bid_c"]) & (d["t_n"] - d["end_period_ts"] <= 120)]
    d = d[(d["ask_n"] < 1) & (d["bid_n"] > 0)]
    d["tq"] = (d["end_period_ts"] - lag).astype(float)
    d = d.sort_values("tq")
    w = wp[["espn_id", "ts", "home_wp"]].rename(columns={"ts": "tq"}).sort_values("tq")
    d = pd.merge_asof(d, w, on="tq", by="espn_id", direction="backward", tolerance=1800)
    d = d.dropna(subset=["home_wp"])
    d["p_espn"] = np.where(d["is_home"] == 1, d["home_wp"], 1 - d["home_wp"]).clip(0.001, 0.999)
    d["mid"] = (d["bid_c"] + d["ask_c"]) / 2
    D = d[d["gdate"].isin(sp[split])].copy()
    T = d[d["gdate"].isin(sp["train"])]
    print(f"split={split} lag={lag:.0f}s quote-minutes={len(D)} markets={D['ticker'].nunique()} days={D['gdate'].nunique()}  mean spread {100*(D['ask_c']-D['bid_c']).mean():.2f}c")
    print(f"  Brier: Kalshi mid {brier(D['mid'], D['y']):.5f} | ESPN WP {brier(D['p_espn'], D['y']):.5f} | mean |Kalshi - ESPN| {np.abs(D['mid']-D['p_espn']).mean()*100:.2f} pts")
    for lg, x in D.groupby("league"):
        print(f"    {lg:6s} n={len(x):6d} Kalshi {brier(x['mid'], x['y']):.5f} ESPN {brier(x['p_espn'], x['y']):.5f} |diff| {np.abs(x['mid']-x['p_espn']).mean()*100:.2f}")
    lg_ = lambda p: np.log(np.clip(p, .005, .995) / (1 - np.clip(p, .005, .995)))
    lr = LogisticRegression(C=10.0).fit(np.c_[lg_(T["mid"]), lg_(T["p_espn"])], T["y"])
    D["p_comb"] = lr.predict_proba(np.c_[lg_(D["mid"]), lg_(D["p_espn"])])[:, 1]
    print(f"  logistic (fit on train) coef Kalshi={lr.coef_[0][0]:.3f} ESPN={lr.coef_[0][1]:.3f}; combined Brier on {split}: {brier(D['p_comb'], D['y']):.5f}")
    a2 = np.minimum(D["ask_n"] + 0.01, 0.99)
    n2 = np.minimum(1 - D["bid_n"] + 0.01, 0.99)
    for name in ("p_espn", "p_comb"):
        p = D[name]
        ey, en = p - D["ask_c"] - fee(D["ask_c"]), (1 - p) - (1 - D["bid_c"]) - fee(1 - D["bid_c"])
        for th in (0.03, 0.05, 0.08, 0.12, 0.20):
            side = np.where((ey > th) & (ey >= en), 1, np.where(en > th, -1, 0))
            pnl = np.where(side == 1, D["y"] - a2 - fee(a2), np.where(side == -1, (1 - D["y"]) - n2 - fee(n2), np.nan))
            t = D.assign(pnl=pnl, side=side).dropna(subset=["pnl"])
            if len(t) < 30:
                continue
            lo, hi = boot_ci(t, "pnl")
            one = t.sort_values("end_period_ts").groupby("ticker").head(1)
            lo1, hi1 = boot_ci(one, "pnl")
            print(f"  {name} edge>{th:.2f}: n={len(t):6d} P&L {t['pnl'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] win {t['pnl'].gt(0).mean()*100:.0f}% | "
                  f"first per market n={len(one)} {one['pnl'].mean()*100:+.2f}c [{lo1*100:+.2f},{hi1*100:+.2f}] | by league " +
                  ", ".join(f"{k}:{len(x)}/{x['pnl'].mean()*100:+.1f}" for k, x in t.groupby("league")))


if __name__ == "__main__":
    main()
