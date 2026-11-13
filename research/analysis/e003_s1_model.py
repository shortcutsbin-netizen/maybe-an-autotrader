#!/usr/bin/env python3
"""E003 — multi-signal fair-value model for 15-minute crypto up/down markets.

Question: does information beyond the Kalshi price (spot path vs strike,
volatility, momentum, cross-coin moves, time of day, optional news volume)
let a model out-forecast the market, and does trading the disagreement pay
after the taker fee?

Honesty rules:
  * Features at decision time t use only data with timestamps <= t.
  * Chronological split by day (same as E001): train / val / test. Models are
    fit on the first 80% of train days; the trade threshold is chosen on the
    last 20% of train days; results are reported on val. Test is not read
    unless split == "test" is requested explicitly (once, at the end).
  * Three fill models: displayed quote at t; conservative (worse of quote at t
    and next minute's open, plus one tick); delayed (quote one minute later,
    plus one tick) — if an edge exists only without delay it is a latency
    edge this bot cannot capture.

Usage: e003_s1_model.py <run_dir> [eval_split=val] [news_csv]
"""
import glob
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e001_calibration import load, split_days, tick, fee  # noqa: E402

SPOT = {"KXBTC15M": "BTC-USD", "KXETH15M": "ETH-USD", "KXSOL15M": "SOL-USD", "KXXRP15M": "XRP-USD",
        "KXDOGE15M": "DOGE-USD", "KXBNB15M": "BNB-USD", "KXHYPE15M": "HYPE-USD",
        "KXNEAR15M": "NEAR-USD", "KXZEC15M": "ZEC-USD"}


def spot_grid(run, product):
    """Per-minute arrays indexed by minute END timestamp."""
    s = pd.read_csv(f"{run}/spot/{product}.csv.gz").drop_duplicates("time").set_index("time").sort_index()
    idx = np.arange(s.index.min(), s.index.max() + 60, 60)
    s = s.reindex(idx)
    s["traded"] = s["close"].notna().astype(int)
    s["close"] = s["close"].ffill()
    for c in ("open", "high", "low"):
        s[c] = s[c].fillna(s["close"])
    s["volume"] = s["volume"].fillna(0.0)
    g = pd.DataFrame(index=idx + 60)
    g["c"] = s["close"].values
    g["avg"] = ((s["open"] + s["high"] + s["low"] + s["close"]) / 4).values
    g["vol"] = s["volume"].values
    g["traded"] = s["traded"].values
    lr = np.log(g["c"]).diff()
    g["lr"] = lr
    g["rv15"] = lr.rolling(15, min_periods=10).std()
    g["rv60"] = lr.rolling(60, min_periods=30).std()
    g["rv1440"] = lr.rolling(1440, min_periods=300).std()
    g["mom1"] = lr
    g["mom3"] = lr.rolling(3).sum()
    g["mom5"] = lr.rolling(5).sum()
    g["mom15"] = lr.rolling(15).sum()
    g["volz"] = g["vol"] / g["vol"].rolling(1440, min_periods=300).mean()
    g["act60"] = g["traded"].rolling(60, min_periods=30).mean()
    return g


def build(run, news_csv=None):
    mk, df = load(run)
    df = df[df["series"].isin(SPOT)].copy()
    df = df[(df["k"] >= 1) & (df["k"] <= 14)]
    parts = []
    grids = {s: spot_grid(run, p) for s, p in SPOT.items()}
    btc = grids["KXBTC15M"]
    for s, g in grids.items():
        d = df[df["series"] == s].copy()
        t = d["end_period_ts"].values
        for c in ("c", "rv15", "rv60", "rv1440", "mom1", "mom3", "mom5", "mom15", "volz", "act60"):
            d[c] = g[c].reindex(t).values
        d["avg_open"] = g["avg"].reindex(d["open_ts"].values).values       # minute ending at open
        d["c_open"] = g["c"].reindex(d["open_ts"].values).values
        d["btc_c"] = btc["c"].reindex(t).values
        d["btc_avg_open"] = btc["avg"].reindex(d["open_ts"].values).values
        d["btc_rv60"] = btc["rv60"].reindex(t).values
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    d = d.sort_values(["ticker", "end_period_ts"])
    # delayed-fill quotes (one minute later)
    d["ask_c_next"] = d.groupby("ticker")["ask_c"].shift(-1)
    d["bid_c_next"] = d.groupby("ticker")["bid_c"].shift(-1)
    d["mid_prev1"] = d.groupby("ticker")["bid_c"].shift(1).add(d.groupby("ticker")["ask_c"].shift(1)) / 2
    d["mid_prev3"] = d.groupby("ticker")["bid_c"].shift(3).add(d.groupby("ticker")["ask_c"].shift(3)) / 2
    d = d[(d["bid_c"] > 0) & (d["ask_c"] < 1) & (d["ask_c"] >= d["bid_c"])].copy()
    d["mid"] = (d["bid_c"] + d["ask_c"]) / 2
    d["spread"] = d["ask_c"] - d["bid_c"]
    tau = d["minutes_left"] - 40.0 / 60.0                 # averaging removes ~40 s of terminal variance
    sig = d["rv60"].clip(lower=1e-6)
    d["r"] = np.log(d["c"] / d["avg_open"])              # move since the strike-setting minute
    d["z"] = d["r"] / (sig * np.sqrt(tau))
    d["p_base"] = norm.cdf(d["z"])
    d["z15"] = d["r"] / (d["rv15"].clip(lower=1e-6) * np.sqrt(tau))
    d["z_day"] = d["r"] / (d["rv1440"].clip(lower=1e-6) * np.sqrt(tau))
    d["btc_z"] = np.log(d["btc_c"] / d["btc_avg_open"]) / (d["btc_rv60"].clip(lower=1e-6) * np.sqrt(tau))
    for m in ("mom1", "mom3", "mom5", "mom15"):
        d[m + "_s"] = d[m] / sig
    d["volratio"] = np.log((d["rv15"].clip(lower=1e-6)) / sig)
    d["volratio_day"] = np.log(sig / d["rv1440"].clip(lower=1e-6))
    eps = 1e-3
    d["logit_mid"] = np.log(d["mid"].clip(eps, 1 - eps) / (1 - d["mid"].clip(eps, 1 - eps)))
    d["dmid1"] = d["mid"] - d["mid_prev1"]
    d["dmid3"] = d["mid"] - d["mid_prev3"]
    hr = (d["end_period_ts"] % 86400) / 3600.0
    d["hsin"], d["hcos"] = np.sin(2 * np.pi * hr / 24), np.cos(2 * np.pi * hr / 24)
    d["dow"] = ((d["end_period_ts"] // 86400) + 4) % 7
    d["weekend"] = d["dow"].isin([0, 6]).astype(int)
    d["lvol"] = np.log1p(d["volume"])
    d["lvolz"] = np.log(d["volz"].clip(lower=1e-3))
    d["news"] = 0.0
    if news_csv:
        nw = pd.read_csv(news_csv).set_index("ts")["z"]
        d["news"] = nw.reindex((d["end_period_ts"] // 900) * 900 - 900).fillna(0).values   # previous full 15-min bucket
    return d.replace([np.inf, -np.inf], np.nan)


EXT = ["z", "z15", "z_day", "btc_z", "mom1_s", "mom3_s", "mom5_s", "mom15_s", "volratio", "volratio_day",
       "minutes_left", "hsin", "hcos", "weekend", "lvolz", "act60", "news"]
MKT = ["logit_mid", "spread", "dmid1", "dmid3", "lvol"]


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def logloss(p, y):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def day_ci(df, col, n=500, seed=11):
    g = df.groupby("day")[col].agg(["sum", "count"])
    if len(g) < 4:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    m = g["sum"].values[idx].sum(1) / np.maximum(g["count"].values[idx].sum(1), 1)
    return (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def trade_pnl(d, p, thr):
    """Per-row P&L (dollars per contract) under three fill models; NaN where no trade."""
    out = {}
    ask, bid = d["ask_c"].values, d["bid_c"].values
    y = d["y"].values
    no_ask = 1 - bid
    e_yes = p - ask - fee(ask)
    e_no = (1 - p) - no_ask - fee(no_ask)
    side = np.where((e_yes > thr) & (e_yes >= e_no), 1, np.where(e_no > thr, -1, 0))
    # displayed
    out["disp"] = np.where(side == 1, y - ask - fee(ask), np.where(side == -1, (1 - y) - no_ask - fee(no_ask), np.nan))
    # conservative
    a2 = np.maximum(ask, np.nan_to_num(d["next_ask_o"].values, nan=0))
    a2 = np.minimum(a2 + tick(a2), 0.999)
    b2 = np.minimum(bid, np.nan_to_num(d["next_bid_o"].values, nan=1))
    n2 = np.minimum((1 - b2) + tick(1 - b2), 0.999)
    out["cons"] = np.where(side == 1, y - a2 - fee(a2), np.where(side == -1, (1 - y) - n2 - fee(n2), np.nan))
    # delayed one minute (no fill if the quote one minute later is missing/one-sided)
    a3, b3 = d["ask_c_next"].values, d["bid_c_next"].values
    ok = np.isfinite(a3) & np.isfinite(b3) & (a3 < 1) & (b3 > 0)
    a3 = np.minimum(np.where(ok, a3, 0.5) + tick(np.where(ok, a3, 0.5)), 0.999)
    n3 = np.minimum((1 - np.where(ok, b3, 0.5)) + tick(1 - np.where(ok, b3, 0.5)), 0.999)
    out["delay"] = np.where(~ok, np.nan, np.where(side == 1, y - a3 - fee(a3), np.where(side == -1, (1 - y) - n3 - fee(n3), np.nan)))
    return side, out


def main():
    run = sys.argv[1]
    eval_split = sys.argv[2] if len(sys.argv) > 2 else "val"
    news = sys.argv[3] if len(sys.argv) > 3 else None
    d = build(run, news)
    mk, _ = load(run)
    sp = split_days(mk)
    tr_days = sp["train"]
    cut = int(len(tr_days) * 0.8)
    fit_days, thr_days, ev_days = tr_days[:cut], tr_days[cut:], sp[eval_split]
    d = d.dropna(subset=EXT + MKT + ["y"])
    fit, thr_df, ev = d[d["day"].isin(fit_days)], d[d["day"].isin(thr_days)], d[d["day"].isin(ev_days)].copy()
    print(f"rows fit={len(fit)} thr={len(thr_df)} eval[{eval_split}]={len(ev)}  days fit={fit_days[0]}..{fit_days[-1]} "
          f"thr={thr_days[0]}..{thr_days[-1]} eval={ev_days[0]}..{ev_days[-1]}")

    models = {
        "lr_ext": (make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300)), EXT),
        "lr_mkt": (make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300)), ["logit_mid"]),
        "lr_all": (make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300)), EXT + MKT),
        "gb_ext": (HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=300, l2_regularization=1.0,
                                                  min_samples_leaf=500, random_state=0), EXT),
        "gb_all": (HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=300, l2_regularization=1.0,
                                                  min_samples_leaf=500, random_state=0), EXT + MKT),
    }
    preds_thr, preds_ev = {"mid": thr_df["mid"].values, "p_base": thr_df["p_base"].values}, \
                          {"mid": ev["mid"].values, "p_base": ev["p_base"].values}
    for name, (m, cols) in models.items():
        m.fit(fit[cols].values, fit["y"].values)
        preds_thr[name] = m.predict_proba(thr_df[cols].values)[:, 1]
        preds_ev[name] = m.predict_proba(ev[cols].values)[:, 1]

    print("\n== forecast skill on eval (lower is better)")
    print(f"{'model':8s} {'brier':>8s} {'logloss':>8s}   by minutes_left brier: 1-2 | 3-7 | 8-14")
    y = ev["y"].values
    ml = ev["minutes_left"].values
    for name, p in preds_ev.items():
        seg = [brier(p[(ml >= a) & (ml <= b)], y[(ml >= a) & (ml <= b)]) for a, b in ((1, 2), (3, 7), (8, 14))]
        print(f"{name:8s} {brier(p, y):8.5f} {logloss(p, y):8.5f}   {seg[0]:.5f} | {seg[1]:.5f} | {seg[2]:.5f}")
    print("per-series brier (mid / gb_all / gb_ext):")
    for s, g in ev.groupby("series"):
        i = (ev["series"] == s).values
        print(f"  {s:10s} {brier(preds_ev['mid'][i], y[i]):.5f} / {brier(preds_ev['gb_all'][i], y[i]):.5f} / {brier(preds_ev['gb_ext'][i], y[i]):.5f}")

    print("\n== trading the disagreement (cents per contract; threshold chosen on held-back train days, cons. fill)")
    grid = [0.0, 0.01, 0.02, 0.03, 0.05, 0.08]
    for name in ("p_base", "lr_ext", "gb_ext", "lr_all", "gb_all"):
        best, best_thr = -9, None
        for th in grid:
            side, o = trade_pnl(thr_df, preds_thr[name], th)
            n = int(np.isfinite(o["cons"]).sum())
            if n >= 300:
                m = float(np.nanmean(o["cons"]))
                if m > best:
                    best, best_thr = m, th
        if best_thr is None:
            print(f"{name:7s} no threshold with >=300 trades on threshold days")
            continue
        side, o = trade_pnl(ev, preds_ev[name], best_thr)
        line = f"{name:7s} thr={best_thr:.2f} (thr-days cons EV {best*100:+.2f}c) | eval: "
        for k in ("disp", "cons", "delay"):
            t = ev.assign(p=o[k]).dropna(subset=["p"])
            lo, hi = day_ci(t, "p")
            line += f"{k} n={len(t)} ev={t['p'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] win={np.mean(t['p']>0)*100:.0f}% | "
        print(line)
        if name == "gb_all":
            t = ev.assign(p=o["cons"], side=side).dropna(subset=["p"])
            print("   gb_all cons by series:", {s: (len(g), round(g['p'].mean() * 100, 2)) for s, g in t.groupby("series")})
            print("   gb_all cons by minutes_left:", {int(k): (len(g), round(g['p'].mean() * 100, 2)) for k, g in t.groupby("minutes_left")})
    # all thresholds on eval for transparency (not for selection)
    print("\n== gb_all, every threshold, eval split (shown for transparency; selection used thr-days only)")
    for th in grid:
        side, o = trade_pnl(ev, preds_ev["gb_all"], th)
        t = ev.assign(p=o["cons"], pd_=o["delay"])
        n = t["p"].notna().sum()
        if n:
            lo, hi = day_ci(t.dropna(subset=["p"]), "p")
            print(f"  thr={th:.2f} n={n} cons={t['p'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] delay={t['pd_'].mean()*100:+.2f}c")


if __name__ == "__main__":
    main()
