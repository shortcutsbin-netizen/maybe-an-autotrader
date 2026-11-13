#!/usr/bin/env python3
"""E001 — descriptive study: is the market's price calibrated, and does any
calibration error exceed the taker fee?

Read-only analysis of data pulled by research/collect/kalshi_pull.py.
Usage: e001_calibration.py <run_dir> <split: train|val|test|trainval|all> [out_json]

Chronological split by market close date (fixed before looking at results):
  train = first 60% of days, val = next 20%, test = last 20%.
The test split must not be opened during exploration.

Definitions (per market, per minute k = 1..14 after open; minutes_left = 15 - k):
  bid, ask   = YES bid/ask at the close of minute k
  mid        = (bid + ask) / 2
  y          = 1 if market resolved YES
  fee(p)     = 0.07 * p * (1 - p)          (taker, per contract, unrounded)
  ev_yes     = y - ask - fee(ask)           buy YES at the displayed ask
  ev_no      = (1 - y) - (1 - bid) - fee(1 - bid)   buy NO at the displayed NO ask
  *_cons     = same, but filled at the worse of this quote and the next
               minute's opening quote, plus one tick (conservative fill)
"""
import glob
import json
import sys

import numpy as np
import pandas as pd

FEE = 0.07


def fee(p):
    return FEE * p * (1 - p)


def tick(p):
    return np.where((p < 0.10) | (p > 0.90), 0.001, 0.01)


def load(run):
    mk = pd.concat([pd.read_csv(f) for f in glob.glob(f"{run}/markets/*.csv.gz")], ignore_index=True)
    mk = mk[mk["result"].isin(["yes", "no"])].copy()
    mk["open_ts"] = (pd.to_datetime(mk["open_time"], utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
    mk["close_ts"] = (pd.to_datetime(mk["close_time"], utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
    mk["y"] = (mk["result"] == "yes").astype(int)
    mk["day"] = mk["close_time"].str[:10]
    cd = pd.concat([pd.read_csv(f) for f in glob.glob(f"{run}/candles/*.csv.gz")], ignore_index=True)
    cd = cd.drop_duplicates(["ticker", "end_period_ts"])
    df = cd.merge(mk[["ticker", "series", "open_ts", "close_ts", "y", "day", "floor_strike",
                      "expiration_value", "volume_fp"]], on="ticker", how="inner")
    df["k"] = ((df["end_period_ts"] - df["open_ts"]) // 60).astype(int)
    df["minutes_left"] = 15 - df["k"]
    df = df.sort_values(["ticker", "end_period_ts"])
    df["next_ask_o"] = df.groupby("ticker")["ask_o"].shift(-1)
    df["next_bid_o"] = df.groupby("ticker")["bid_o"].shift(-1)
    return mk, df


def split_days(mk):
    days = sorted(mk["day"].unique())
    n = len(days)
    a, b = int(n * 0.6), int(n * 0.8)
    return {"train": days[:a], "val": days[a:b], "test": days[b:],
            "trainval": days[:b], "all": days}


def add_ev(df):
    d = df[(df["k"] >= 1) & (df["k"] <= 14)].copy()
    # usable two-sided quote
    d = d[(d["bid_c"] > 0) & (d["ask_c"] < 1) & (d["ask_c"] > d["bid_c"] - 1e-9)]
    d["spread"] = d["ask_c"] - d["bid_c"]
    d["mid"] = (d["ask_c"] + d["bid_c"]) / 2
    d["ev_yes"] = d["y"] - d["ask_c"] - fee(d["ask_c"])
    no_ask = 1 - d["bid_c"]
    d["ev_no"] = (1 - d["y"]) - no_ask - fee(no_ask)
    a2 = np.maximum(d["ask_c"], d["next_ask_o"].fillna(d["ask_c"]))
    a2 = np.minimum(a2 + tick(a2), 0.999)
    d["ev_yes_cons"] = d["y"] - a2 - fee(a2)
    b2 = np.minimum(d["bid_c"], d["next_bid_o"].fillna(d["bid_c"]))
    n2 = np.minimum((1 - b2) + tick(1 - b2), 0.999)
    d["ev_no_cons"] = (1 - d["y"]) - n2 - fee(n2)
    return d


def day_boot_ci(d, col, n=400, seed=7):
    """95% CI of the mean of `col`, resampling whole days (handles cross-coin and intraday correlation)."""
    g = d.groupby("day")[col].agg(["sum", "count"])
    if len(g) < 5:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    s, c = g["sum"].values[idx].sum(1), g["count"].values[idx].sum(1)
    m = s / np.maximum(c, 1)
    return (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def summarize(d, by, col_list=("ev_yes", "ev_no", "ev_yes_cons", "ev_no_cons")):
    rows = []
    for key, g in d.groupby(by, observed=True):
        r = {"key": key if isinstance(key, tuple) else (key,), "n": int(len(g)),
             "mid": float(g["mid"].mean()), "yes_rate": float(g["y"].mean()),
             "calib_err": float(g["y"].mean() - g["mid"].mean()),
             "spread": float(g["spread"].mean())}
        r["calib_ci"] = day_boot_ci(g.assign(e=g["y"] - g["mid"]), "e")
        for c in col_list:
            r[c] = float(g[c].mean())
        r["ev_yes_cons_ci"] = day_boot_ci(g, "ev_yes_cons")
        r["ev_no_cons_ci"] = day_boot_ci(g, "ev_no_cons")
        rows.append(r)
    return rows


def main():
    run, split = sys.argv[1], sys.argv[2]
    mk, df = load(run)
    days = split_days(mk)[split]
    mk, df = mk[mk["day"].isin(days)], df[df["day"].isin(days)]
    d = add_ev(df)
    d["pbin"] = pd.cut(d["mid"], [0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, 1.0])
    d["tbin"] = pd.cut(d["minutes_left"], [0, 1, 2, 4, 7, 10, 14], labels=["1", "2", "3-4", "5-7", "8-10", "11-14"])
    out = {"run": run, "split": split, "days": [days[0], days[-1], len(days)],
           "markets": int(len(mk)), "quote_rows": int(len(d)),
           "base_yes_rate_by_series": mk.groupby("series")["y"].agg(["mean", "count"]).round(4).to_dict("index"),
           "volume_per_market_by_series": mk.groupby("series")["volume_fp"].median().round(0).to_dict(),
           "spread_by_series": d.groupby("series")["spread"].agg(["mean", "median"]).round(4).to_dict("index"),
           "pooled_by_price": summarize(d, ["pbin"]),
           "pooled_by_time": summarize(d, ["tbin"]),
           "by_time_price": summarize(d, ["tbin", "pbin"]),
           "by_series": summarize(d, ["series"]),
           "by_series_price": summarize(d, ["series", "pbin"])}
    path = sys.argv[3] if len(sys.argv) > 3 else None
    if path:
        with open(path, "w") as f:
            json.dump(out, f, indent=1, default=str)
    pd.set_option("display.width", 220)

    def show(title, rows, cols):
        print(f"\n== {title}")
        t = pd.DataFrame(rows)
        t["key"] = t["key"].map(lambda k: " | ".join(str(x) for x in k))
        for c in cols:
            if c.endswith("_ci"):
                t[c] = t[c].map(lambda x: f"[{x[0]*100:+.2f},{x[1]*100:+.2f}]")
            elif c not in ("key", "n"):
                t[c] = (t[c] * 100).round(2)
        print(t[cols].to_string(index=False))

    print(f"split={split} days={out['days']} markets={out['markets']} quote_rows={out['quote_rows']}")
    print("values in cents per contract (or percentage points)")
    print("base YES rate:", {k: round(v["mean"], 3) for k, v in out["base_yes_rate_by_series"].items()})
    print("median volume/market:", out["volume_per_market_by_series"])
    print("spread mean/median:", out["spread_by_series"])
    cols = ["key", "n", "mid", "yes_rate", "calib_err", "calib_ci", "spread", "ev_yes", "ev_no",
            "ev_yes_cons", "ev_yes_cons_ci", "ev_no_cons", "ev_no_cons_ci"]
    show("pooled by price", out["pooled_by_price"], cols)
    show("pooled by minutes left", out["pooled_by_time"], cols)
    show("by series", out["by_series"], cols)


if __name__ == "__main__":
    main()
