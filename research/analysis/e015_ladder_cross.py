"""E015 - 15-minute crypto vs hourly above/below ladder (same settlement number).

The 15-minute market that closes on the hour and every strike of the hourly "price above K" ladder
settle on the same 60-second CF Benchmarks average. So, at any minute in the last 15 minutes of the hour:

  Box A (ladder strike Kj >= K15):  buy YES15 + buy NO_j   -> pays >= $1 in every state
  Box B (ladder strike Kj <  K15):  buy NO15  + buy YES_j  -> pays >= $1 in every state
  Monotone (Ki < Kj, same ladder):  buy YES_i + buy NO_j   -> pays >= $1 in every state

If the cost of either leg pair (asks, plus taker fees) is below $1 the trade is riskless apart from
execution (both legs must fill) and the exchange's settlement mechanics. We count how often that
happens at minute-end quotes and how big it is.

Relative value: interpolate the ladder's mid-prices at K15 to get a ladder-implied P(S >= K15) and
compare with the 15-minute market's own mid: which forecasts the outcome better, and does trading the
15-minute market toward the ladder pay after fees (threshold picked on the first half, read on the second)?

usage: python e015_ladder_cross.py <ladder_run> <15m_run> [<15m_run> ...]
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

FEE = 0.07


def fee(p):
    return FEE * p * (1 - p)


def load_15m(runs, series):
    ms, cs = [], []
    for r in runs:
        f = os.path.join(r, "markets", f"{series}.csv.gz")
        if os.path.exists(f):
            ms.append(pd.read_csv(f))
        for c in sorted(glob.glob(os.path.join(r, "candles", "*.csv.gz"))):
            d = pd.read_csv(c, usecols=["ticker", "end_period_ts", "bid_c", "ask_c", "volume"])
            cs.append(d[d.ticker.str.startswith(series + "-")])
    m = pd.concat(ms).drop_duplicates("ticker")
    c = pd.concat(cs).drop_duplicates(["ticker", "end_period_ts"])
    return m, c


def main():
    lad_run, runs15 = sys.argv[1], sys.argv[2:]
    kept = glob.glob(os.path.join(lad_run, "markets", "*_kept.csv.gz"))
    assert kept, "no kept ladder markets"
    lser = os.path.basename(kept[0]).replace("_kept.csv.gz", "")
    s15 = [os.path.basename(f).replace(".csv.gz", "") for f in glob.glob(os.path.join(lad_run, "markets", "*15M.csv.gz"))][0]
    lm = pd.read_csv(kept[0])
    lm["K"] = lm.floor_strike.astype(float)
    lc = pd.concat(pd.read_csv(f, usecols=["ticker", "end_period_ts", "bid_c", "ask_c", "volume"])
                   for f in glob.glob(os.path.join(lad_run, "candles", "*.csv.gz")))
    m15, c15 = load_15m(runs15, s15)
    m15["close_ts"] = (pd.to_datetime(m15.close_time, utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
    lm["close_ts"] = (pd.to_datetime(lm.close_time, utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
    m15 = m15[m15.close_ts % 3600 == 0][["ticker", "close_ts", "floor_strike", "result", "expiration_value"]]
    m15 = m15.rename(columns={"ticker": "t15", "floor_strike": "K15", "result": "res15", "expiration_value": "S15"})
    lm = lm.merge(m15, on="close_ts", how="inner")
    # settlement-number check: the ladder's expiration value should equal the 15-minute one
    ev = lm.dropna(subset=["expiration_value", "S15"])
    rel = (ev.expiration_value.astype(float) / ev.S15.astype(float) - 1).abs()
    print(f"{lser} vs {s15}: {lm.close_ts.nunique()} common hours, {len(lm)} ladder markets kept")
    print(f"settlement value agreement: max rel diff {rel.max():.2e}, share > 1e-6: {(rel > 1e-6).mean():.3%}")
    # outcome consistency: ladder result vs S >= K
    lm["yes"] = (lm.result == "yes").astype(int)

    c15 = c15.rename(columns={"ticker": "t15", "bid_c": "b15", "ask_c": "a15", "volume": "v15"})
    lc = lc.rename(columns={"bid_c": "bj", "ask_c": "aj", "volume": "vj"})
    x = lm[["ticker", "t15", "close_ts", "K", "K15", "yes", "res15"]].merge(lc, on="ticker")
    x = x.merge(c15, on=["t15", "end_period_ts"], how="inner")
    x = x[(x.end_period_ts < x.close_ts) & (x.end_period_ts >= x.close_ts - 900)]
    x["sec_left"] = x.close_ts - x.end_period_ts
    two15 = (x.b15 > 0) & (x.a15 < 1) & (x.a15 > x.b15)
    twoj = (x.bj > 0) & (x.aj < 1) & (x.aj > x.bj)
    print(f"minute x strike rows: {len(x)}; with two-sided 15m quote: {two15.mean():.1%}; two-sided ladder quote: {twoj.mean():.1%}")
    x["day"] = pd.to_datetime(x.end_period_ts, unit="s", utc=True).dt.strftime("%Y-%m-%d")
    days = sorted(x.day.unique())
    half = days[len(days) // 2]
    x["half"] = np.where(x.day < half, "H1", "H2")

    # ---------------- boxes
    A = x[(x.K >= x.K15) & (x.a15 < 1) & (x.a15 > 0) & (x.bj > 0)].copy()
    A["cost"] = A.a15 + (1 - A.bj)
    A["fees"] = fee(A.a15) + fee(1 - A.bj)
    B = x[(x.K < x.K15) & (x.b15 > 0) & (x.aj < 1) & (x.aj > 0)].copy()
    B["cost"] = (1 - B.b15) + B.aj
    B["fees"] = fee(1 - B.b15) + fee(B.aj)
    for name, d in (("Box A (YES15 + NO ladder, K>=K15)", A), ("Box B (NO15 + YES ladder, K<K15)", B)):
        d["edge"] = 1 - d.cost - d.fees
        pos = d[d.edge > 0]
        print(f"\n{name}: {len(d)} minute-strike quotes")
        for h in ("H1", "H2"):
            dh = d[d.half == h]
            ph = dh[dh.edge > 0]
            print(f"  {h}: cost<1 before fees {(dh.cost < 1).mean():.2%}; after fees {len(ph)} quotes in "
                  f"{ph.close_ts.nunique()} hours; median edge {ph.edge.median() * 100 if len(ph) else float('nan'):.2f}c; "
                  f"mean 15m vol in minute {ph.v15.mean() if len(ph) else float('nan'):.0f}, ladder vol {ph.vj.mean() if len(ph) else float('nan'):.0f}")
        if len(pos):
            g = pos.sort_values("edge", ascending=False).groupby("close_ts").head(1)
            print(f"  best per hour: n={len(g)}, edge mean {g.edge.mean() * 100:.2f}c, p90 {g.edge.quantile(.9) * 100:.2f}c; "
                  f"|K-K15|/K15 median {((g.K - g.K15).abs() / g.K15).median():.4%}; sec_left median {g.sec_left.median():.0f}")
            print("  edge by seconds left:", pos.groupby(pd.cut(pos.sec_left, [0, 120, 300, 600, 900])).edge.agg(["count", "mean"]).round(4).to_dict("index"))

    # ---------------- within-ladder monotonicity at each minute
    q = x[twoj][["close_ts", "end_period_ts", "K", "bj", "aj", "half"]]
    viol, tot = [], 0
    for (ct, t), g in q.groupby(["close_ts", "end_period_ts"]):
        g = g.sort_values("K")
        if len(g) < 2:
            continue
        a = g.aj.values
        b = g.bj.values
        tot += 1
        # buy YES at lower strike i (ask a_i), buy NO at higher strike j (1 - b_j): cost a_i + 1 - b_j
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                e = b[j] - a[i] - fee(a[i]) - fee(1 - b[j])
                if e > 0:
                    viol.append((ct, t, g.K.values[i], g.K.values[j], e, g.half.values[0]))
    v = pd.DataFrame(viol, columns=["close_ts", "t", "Ki", "Kj", "edge", "half"])
    print(f"\nWithin-ladder monotonicity: {tot} minute snapshots with >=2 two-sided strikes; "
          f"{v.t.nunique() if len(v) else 0} snapshots with an after-fee violation; "
          f"median edge {v.edge.median() * 100 if len(v) else float('nan'):.2f}c")

    # ---------------- relative value: ladder-implied P(S >= K15) vs the 15-minute mid
    r = x[two15 & twoj].copy()
    r["mj"] = (r.bj + r.aj) / 2
    r["m15"] = (r.b15 + r.a15) / 2
    rows = []
    for (ct, t), g in r.groupby(["close_ts", "end_period_ts"]):
        g = g.sort_values("K")
        lo, hi = g[g.K < g.K15], g[g.K >= g.K15]
        if not len(lo) or not len(hi):
            continue
        l, h = lo.iloc[-1], hi.iloc[0]
        w = (l.K15 - l.K) / (h.K - l.K)
        imp = l.mj + w * (h.mj - l.mj)          # linear in strike between the bracketing strikes
        rows.append((ct, t, g.K15.iloc[0], l.K, h.K, imp, g.m15.iloc[0], g.b15.iloc[0], g.a15.iloc[0],
                     int(g.res15.iloc[0] == "yes"), g.sec_left.iloc[0], g.half.iloc[0], g.day.iloc[0]))
    rv = pd.DataFrame(rows, columns=["close_ts", "t", "K15", "Klo", "Khi", "imp", "m15", "b15", "a15", "y", "sec_left", "half", "day"])
    if not len(rv):
        print("\nRelative value: no minutes with bracketing two-sided strikes")
        return
    rv["gap"] = rv.imp - rv.m15
    print(f"\nRelative value: {len(rv)} minutes ({rv.close_ts.nunique()} hours) with bracketing two-sided strikes; "
          f"median bracket width {((rv.Khi - rv.Klo) / rv.K15).median():.3%}")
    for h in ("H1", "H2"):
        d = rv[rv.half == h]
        print(f"  {h}: n={len(d)}  Brier 15m mid {((d.m15 - d.y) ** 2).mean():.4f}  ladder-implied {((d.imp - d.y) ** 2).mean():.4f}  "
              f"blend {(((d.m15 + d.imp) / 2 - d.y) ** 2).mean():.4f};  |gap| mean {d.gap.abs().mean() * 100:.2f}c, p90 {d.gap.abs().quantile(.9) * 100:.2f}c")
    # trading rule: buy the 15-minute side the ladder favours when gap exceeds theta (taker at the 15m quote)
    def pnl(d, th):
        buy_yes = d.imp - d.a15 - fee(d.a15) > th
        buy_no = (1 - d.imp) - (1 - d.b15) - fee(1 - d.b15) > th
        p = np.where(buy_yes, d.y - d.a15 - fee(d.a15), np.where(buy_no, (1 - d.y) - (1 - d.b15) - fee(1 - d.b15), np.nan))
        out = d.assign(p=p).dropna(subset=["p"])
        return out.groupby("close_ts").head(1)    # one trade per hour
    print("  rule 'trade 15m toward ladder', one trade per hour:")
    for th in (0.0, 0.02, 0.04, 0.06, 0.08):
        s = []
        for h in ("H1", "H2"):
            o = pnl(rv[rv.half == h], th)
            if len(o) > 5:
                bs = [o.groupby("day").p.sum().sample(frac=1, replace=True, random_state=i).sum() /
                      o.groupby("day").p.count().sample(frac=1, replace=True, random_state=i).sum() for i in range(300)]
                s.append(f"{h} n={len(o)} {o.p.mean() * 100:+.2f}c [{np.percentile(bs, 2.5) * 100:+.1f},{np.percentile(bs, 97.5) * 100:+.1f}]")
            else:
                s.append(f"{h} n={len(o)}")
        print(f"    theta {th:.2f}: " + "; ".join(s))




def reverse_rule(argv):
    """Trade the LADDER strike nearest K15 toward the 15-minute mid (the 15-minute book is the better
    forecaster in every coin, so the stale side may be the ladder). One trade per hour, taker at the ladder quote."""
    lad_run, runs15 = argv[0], argv[1:]
    kept = glob.glob(os.path.join(lad_run, "markets", "*_kept.csv.gz"))
    s15 = [os.path.basename(f).replace(".csv.gz", "") for f in glob.glob(os.path.join(lad_run, "markets", "*15M.csv.gz"))][0]
    lm = pd.read_csv(kept[0])
    lm["K"] = lm.floor_strike.astype(float)
    lc = pd.concat(pd.read_csv(f, usecols=["ticker", "end_period_ts", "bid_c", "ask_c", "volume"])
                   for f in glob.glob(os.path.join(lad_run, "candles", "*.csv.gz")))
    m15, c15 = load_15m(runs15, s15)
    to_ts = lambda s: (pd.to_datetime(s, utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
    m15["close_ts"], lm["close_ts"] = to_ts(m15.close_time), to_ts(lm.close_time)
    m15 = m15[m15.close_ts % 3600 == 0][["ticker", "close_ts", "floor_strike"]].rename(columns={"ticker": "t15", "floor_strike": "K15"})
    lm = lm.merge(m15, on="close_ts")
    lm["rel"] = (lm.K - lm.K15).abs() / lm.K15
    lm = lm.sort_values("rel").groupby("close_ts").head(1)
    lm["yl"] = (lm.result == "yes").astype(int)
    c15 = c15.rename(columns={"ticker": "t15", "bid_c": "b15", "ask_c": "a15", "volume": "v15"})
    x = lm[["ticker", "t15", "close_ts", "K", "K15", "rel", "yl"]].merge(lc, on="ticker").merge(c15, on=["t15", "end_period_ts"])
    x = x[(x.end_period_ts < x.close_ts) & (x.end_period_ts >= x.close_ts - 900)]
    x = x[(x.b15 > 0) & (x.a15 < 1) & (x.bid_c > 0) & (x.ask_c < 1) & (x.ask_c > x.bid_c)]
    x["m15"] = (x.b15 + x.a15) / 2
    x["day"] = pd.to_datetime(x.end_period_ts, unit="s", utc=True).dt.strftime("%Y-%m-%d")
    days = sorted(x.day.unique())
    x["half"] = np.where(x.day < days[len(days) // 2], "H1", "H2")
    print(f"\nReverse rule (ladder strike nearest K15, rel dist <= cap): {len(x)} two-sided minutes, {x.close_ts.nunique()} hours; "
          f"median rel dist {x.rel.median():.4%}; median ladder spread {(x.ask_c - x.bid_c).median() * 100:.1f}c; "
          f"mean ladder volume per minute {x.volume.mean():.0f}")
    for cap in (0.0005, 0.002):
        for th in (0.02, 0.05, 0.08):
            s = []
            for h in ("H1", "H2"):
                d = x[(x.half == h) & (x.rel <= cap)]
                ey = d.m15 - d.ask_c - fee(d.ask_c)
                en = (1 - d.m15) - (1 - d.bid_c) - fee(1 - d.bid_c)
                p = np.where(ey > th, d.yl - d.ask_c - fee(d.ask_c), np.where(en > th, (1 - d.yl) - (1 - d.bid_c) - fee(1 - d.bid_c), np.nan))
                o = d.assign(p=p).dropna(subset=["p"]).groupby("close_ts").head(1)
                if len(o) >= 5:
                    lo, hi = _ci(o)
                    s.append(f"{h} n={len(o)} {o.p.mean() * 100:+.2f}c [{lo:+.1f},{hi:+.1f}] vol/min {o.volume.mean():.0f}")
                else:
                    s.append(f"{h} n={len(o)}")
            print(f"  cap {cap:.2%} theta {th:.2f}: " + "; ".join(s))


def _ci(o, n=500):
    g = o.groupby("day").p.agg(["sum", "count"])
    rng = np.random.default_rng(3)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    mm = g["sum"].values[idx].sum(1) / g["count"].values[idx].sum(1)
    return np.percentile(mm, 2.5) * 100, np.percentile(mm, 97.5) * 100


if __name__ == "__main__":
    if sys.argv[1] == "reverse":
        reverse_rule(sys.argv[2:])
    else:
        main()
