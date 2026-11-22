#!/usr/bin/env python3
"""E019 - hourly temperature markets (KXTEMPMIAH, KXTEMPNYCHS, KXTEMPCHIHS, KXTEMPLAXHS) vs the public
Kalshi Weather Index that settles them.

Each market asks whether the city's minute-resolution index at the hour is above a whole-degree-minus-0.01
strike. The index itself is published by Kalshi (GET /live_data/weather/{city}) with a short receipt delay.
Nowcast: at minute-end t (market open for the hour before close), the latest index value we would know is
v(t - lag); forecast v(close) = v(t - lag) + residual, with the residual distribution taken from the TRAIN
period conditional on lead time (minutes from t - lag to close) and the recent 10-minute slope bucket.

Compare Brier with the market mid; trade when model edge > theta after the taker fee; fills at the
minute-end quote (optimistic) and at the next minute's quote (one-minute delay). Chronological split by
day: first 60% train, next 20% validation, last 20% closed. Lags 2 and 5 minutes (index receipt delay).

usage: e019_hourly_temp.py <wxh_run> <windex_run> [lag_minutes]
"""
import glob
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e012_frozen_new_periods import ci  # noqa: E402

CITY = {"KXTEMPMIAH": "miami", "KXTEMPNYCHS": "nyc", "KXTEMPCHIHS": "chicago", "KXTEMPLAXHS": "la-coastal"}


def fee(p):
    return 0.07 * p * (1 - p)


def main():
    run, wrun = sys.argv[1], sys.argv[2]
    lag = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    out = []
    for s, city in CITY.items():
        f = f"{run}/markets/{s}.csv.gz"
        w = f"{wrun}/windex/{city}.csv.gz"
        if not (glob.glob(f) and glob.glob(w)):
            print("missing", s, city)
            continue
        m = pd.read_csv(f)
        m = m[m.result.isin(["yes", "no"])]
        m["close_ts"] = (pd.to_datetime(m.close_time, utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
        m["y"] = (m.result == "yes").astype(int)
        c = pd.read_csv(f"{run}/candles/{s}.csv.gz", usecols=["ticker", "end_period_ts", "bid_c", "ask_c", "volume"])
        wi = pd.read_csv(w)
        wi = wi[wi.receipt_basis.isna() & wi.v.notna()]            # canonical (settlement-eligible) points only
        wi["ts"] = wi.t_ms // 1000
        idx = wi.set_index("ts")["v"].sort_index()
        # settlement check: index at the close minute vs the market's expiration value
        ev = m.drop_duplicates("event_ticker")[["close_ts", "expiration_value"]].copy()
        ev["idx_close"] = ev.close_ts.map(idx)
        ok = ev.dropna()
        print(f"{s}/{city}: {len(m)} markets, {m.event_ticker.nunique()} hours; index points {len(idx)}; "
              f"index@close == expiration value for {np.mean(np.isclose(ok.idx_close, ok.expiration_value, atol=0.006)):.1%} of {len(ok)} hours "
              f"(within 0.1F {np.mean(np.isclose(ok.idx_close, ok.expiration_value, atol=0.1)):.1%})")
        x = c.merge(m[["ticker", "event_ticker", "series", "close_ts", "floor_strike", "y"]], on="ticker")
        x = x[(x.end_period_ts < x.close_ts) & (x.bid_c > 0) & (x.ask_c < 1) & (x.ask_c > x.bid_c)].copy()
        x = x.sort_values(["ticker", "end_period_ts"])
        x["next_bid"] = x.groupby("ticker").bid_c.shift(-1)
        x["next_ask"] = x.groupby("ticker").ask_c.shift(-1)
        # latest index value known at t: the value for minute (t - lag*60) (index is minute-stamped)
        kt = x.end_period_ts - lag * 60
        x["v_known"] = kt.map(idx)
        x["v_10"] = (kt - 600).map(idx)
        x["v_close"] = x.close_ts.map(idx)
        x["lead"] = (x.close_ts - kt) / 60.0
        out.append(x.dropna(subset=["v_known", "v_close"]))
    x = pd.concat(out, ignore_index=True)
    x["slope"] = (x.v_known - x.v_10).fillna(0.0)
    x["dist"] = x.v_known - x.floor_strike
    x["mid"] = (x.bid_c + x.ask_c) / 2
    x["day"] = pd.to_datetime(x.end_period_ts, unit="s", utc=True).dt.strftime("%Y-%m-%d")
    days = sorted(x.day.unique())
    n = len(days)
    tr, va = set(days[: int(n * .6)]), set(days[int(n * .6): int(n * .8)])
    x["split"] = np.where(x.day.isin(tr), "train", np.where(x.day.isin(va), "val", "closed"))
    print(f"\nrows {len(x)}; days {days[0]}..{days[-1]}; lag {lag} min; train {min(tr)}..{max(tr)}, val {min(va)}..{max(va)}")
    # empirical residual model: resid = v_close - v_known, by series, lead bucket and slope sign, from train hours
    x["lb"] = pd.cut(x.lead, [0, 5, 10, 20, 30, 45, 70]).astype(str)
    x["sb"] = np.sign(x.slope).astype(int)
    T = x[x.split == "train"].drop_duplicates(["event_ticker", "end_period_ts"])
    T = T.assign(res=T.v_close - T.v_known)
    groups = {k: np.sort(g.res.values) for k, g in T.groupby(["series", "lb", "sb"])}
    groups2 = {k: np.sort(g.res.values) for k, g in T.groupby(["series", "lb"])}

    def prob(r):
        a = groups.get((r.series, r.lb, r.sb))
        if a is None or len(a) < 50:
            a = groups2.get((r.series, r.lb))
        if a is None or len(a) < 20:
            return np.nan
        # P(v_known + res > strike) = P(res > strike - v_known)
        return 1.0 - np.searchsorted(a, r.floor_strike - r.v_known, side="right") / len(a)
    x["q"] = x.apply(prob, axis=1)
    x = x.dropna(subset=["q"])
    x["q"] = x.q.clip(0.002, 0.998)
    # stacked logistic (market + index nowcast), fitted on train, like the S1-D stack
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    sd = T.assign(res=T.v_close - T.v_known).groupby(["series", "lb"]).res.std()
    x["sd"] = [sd.get((a, b), np.nan) for a, b in zip(x.series, x.lb)]
    x["zk"] = (x.dist / x.sd.clip(lower=0.05)).clip(-8, 8)
    x["lmid"] = np.log(x.mid.clip(.01, .99) / (1 - x.mid.clip(.01, .99)))
    x["lq"] = np.log(x.q.clip(.01, .99) / (1 - x.q.clip(.01, .99)))
    x = x.sort_values(["ticker", "end_period_ts"])
    x["dmid1"] = (x.mid - x.groupby("ticker").mid.shift(1)).fillna(0)
    F = ["lmid", "lq", "zk", "slope", "lead", "dmid1"]
    x = x.dropna(subset=F)
    tr_ = x[x.split == "train"]
    st = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500)).fit(tr_[F].values, tr_.y.values)
    print("  stack coefficients:", dict(zip(F, np.round(st[-1].coef_[0], 3))))
    x["q_nowcast"] = x.q
    x["q"] = st.predict_proba(x[F].values)[:, 1]
    for sp in ("train", "val"):
        d = x[x.split == sp]
        print(f"  {sp}: n={len(d)}  Brier market mid {np.mean((d.mid - d.y) ** 2):.4f}  stack {np.mean((d.q - d.y) ** 2):.4f}")
    for sp in ("train", "val"):
        d = x[x.split == sp]
        print(f"  {sp}: n={len(d)}  Brier market mid {np.mean((d.mid - d.y) ** 2):.4f}  nowcast {np.mean((d.q_nowcast - d.y) ** 2):.4f}  stack {np.mean((d.q - d.y) ** 2):.4f}")
        for lbk, g in d.groupby("lb"):
            print(f"     lead {lbk:10s} n={len(g):6d}  mid {np.mean((g.mid - g.y) ** 2):.4f}  nowcast {np.mean((g.q_nowcast - g.y) ** 2):.4f}  stack {np.mean((g.q - g.y) ** 2):.4f}")
    print("  trading (taker, one trade per market, first qualifying minute):")
    for th in (0.03, 0.05, 0.08, 0.12):
        line = []
        for sp in ("train", "val"):
            d = x[x.split == sp]
            ey = d.q - d.ask_c - fee(d.ask_c)
            en = (1 - d.q) - (1 - d.bid_c) - fee(1 - d.bid_c)
            side = np.where((ey > th) & (ey >= en), 1, np.where(en > th, -1, 0))
            S = d[side != 0].assign(side=side[side != 0]).groupby("ticker").head(1)
            res = []
            for col_b, col_a, nm in (("bid_c", "ask_c", "now"), ("next_bid", "next_ask", "next")):
                pa = np.where(S.side == 1, S[col_a], 1 - S[col_b])
                p = np.where(S.side == 1, S.y, 1 - S.y) - pa - fee(pa)
                v = pd.Series(p, index=S.index).dropna()
                if len(v) >= 10:
                    lo, hi = ci(v.values, S.loc[v.index, "day"].values)
                    res.append(f"{nm} {v.mean() * 100:+.2f}c [{lo * 100:+.1f},{hi * 100:+.1f}]")
            line.append(f"{sp} n={len(S)} ({len(S) / max(1, S.day.nunique()):.0f}/day) " + " ".join(res))
        print(f"    theta {th:.2f}: " + " | ".join(line))
    v = x[x.split == "val"]
    ey = v.q - v.ask_c - fee(v.ask_c)
    en = (1 - v.q) - (1 - v.bid_c) - fee(1 - v.bid_c)
    S = v[(ey > .05) | (en > .05)].groupby("ticker").head(1)
    print("  val theta .05 by series:", S.groupby("series").size().to_dict(), " median volume in signal minute", S.volume.median())


if __name__ == "__main__":
    main()
