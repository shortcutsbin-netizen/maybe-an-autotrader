#!/usr/bin/env python3
"""E010 — frozen "dislocation" rule from E003/E006, evaluated with real trade prints.

FROZEN DEFINITION (written before the test split was opened; do not tune on test):
  model   : logistic regression on EXT + MKT features of e003_s1_model.py, fitted on the
            first 80% of train days only (2026-09-13 .. 2026-10-11)
  signal  : at a minute end t (minutes 1..14 of a 15-minute market, two-sided quote),
            edge = model probability of a side - that side's ask - taker fee > 0.08
  entry   : immediate-or-cancel limit at (quoted ask + 2c); fill price = volume-weighted
            price of same-side taker prints in (t+1 s, t+6 s] at or below that limit;
            no such print -> no trade (we assume we get the average price others got)
  exit    : hold to settlement; taker fee 0.07*p*(1-p) on entry
Steps:
  signals  <run> <split> <out_csv> <out_ticker_list>   -> writes signals (no outcomes inspected)
  evaluate <signals_csv> <trades_run_dir>               -> prints the frozen evaluation
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
THR, LIM, W0, W1 = 0.08, 0.02, 1.0, 6.0


def fee(p):
    return 0.07 * p * (1 - p)


def make_signals(run, split, out_csv, out_list):
    import e003_s1_model as E
    from e001_calibration import load, split_days
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    d = E.build(run)
    mk, _ = load(run)
    sp = split_days(mk)
    d = d.dropna(subset=E.EXT + E.MKT + ["y"])
    tr = sp["train"]
    fit = d[d["day"].isin(tr[:int(len(tr) * 0.8)])]
    days = {"thr": tr[int(len(tr) * 0.8):], "val": sp["val"], "test": sp["test"]}[split]
    x = d[d["day"].isin(days)].copy()
    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300)).fit(fit[E.EXT + E.MKT].values, fit["y"].values)
    x["p"] = m.predict_proba(x[E.EXT + E.MKT].values)[:, 1]
    ask_y, ask_n = x["ask_c"], 1 - x["bid_c"]
    e_y, e_n = x["p"] - ask_y - fee(ask_y), (1 - x["p"]) - ask_n - fee(ask_n)
    x["side"] = np.where((e_y > THR) & (e_y >= e_n), 1, np.where(e_n > THR, -1, 0))
    s = x[x["side"] != 0][["ticker", "series", "day", "end_period_ts", "minutes_left", "side", "p", "bid_c", "ask_c", "y", "spread", "z", "mid"]]
    s.to_csv(out_csv, index=False)
    open(out_list, "w").write("\n".join(sorted(s["ticker"].unique())) + "\n")
    print(f"split={split} days={days[0]}..{days[-1]} signals={len(s)} markets={s['ticker'].nunique()} by series={s['series'].value_counts().to_dict()}")


def ci(v, days, n=1000):
    df = pd.DataFrame({"v": v, "d": days}).dropna()
    g = df.groupby("d")["v"].agg(["sum", "count"])
    rng = np.random.default_rng(4)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    m = g["sum"].values[idx].sum(1) / np.maximum(g["count"].values[idx].sum(1), 1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5)


def evaluate(sig_csv, trun):
    import glob
    sig = pd.read_csv(sig_csv)
    tr = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{trun}/trades*.csv.gz"))], ignore_index=True)
    tr["ts"] = (pd.to_datetime(tr["created_time"], utc=True, format="ISO8601") - pd.Timestamp(0, tz="UTC")) / pd.Timedelta("1s")
    tr = tr.drop_duplicates(["ticker", "created_time", "yes_price", "count", "taker_side"]).sort_values(["ticker", "ts"])
    by = {k: g for k, g in tr.groupby("ticker")}
    rows = []
    for r in sig.itertuples():
        q = r.ask_c if r.side == 1 else 1 - r.bid_c
        win = r.y if r.side == 1 else 1 - r.y
        rec = {"ticker": r.ticker, "day": r.day, "series": r.series, "t": r.end_period_ts, "ml": r.minutes_left, "q": q, "win": win, "px": np.nan, "vol": 0.0}
        g = by.get(r.ticker)
        if g is not None:
            own = g[g["taker_side"] == ("yes" if r.side == 1 else "no")]
            t_, c_ = own["ts"].values, own["count"].values.astype(float)
            p_ = (own["yes_price"] if r.side == 1 else own["no_price"]).values.astype(float)
            m = (t_ > r.end_period_ts + W0) & (t_ <= r.end_period_ts + W1) & (p_ <= q + LIM + 1e-9)
            if m.any():
                rec["vol"] = c_[m].sum()
                rec["px"] = (p_[m] * c_[m]).sum() / c_[m].sum()
        rows.append(rec)
    x = pd.DataFrame(rows)
    x["pnl"] = x["win"] - x["px"] - fee(x["px"])
    f = x.dropna(subset=["px"])
    lo, hi = ci(f["pnl"].values, f["day"].values)
    print(f"signals={len(x)} in {x['ticker'].nunique()} markets over {x['day'].nunique()} days ({len(x)/x['day'].nunique():.0f}/day)")
    print(f"filled={len(f)} ({len(f)/len(x)*100:.0f}%)  P&L per contract {f['pnl'].mean()*100:+.2f}c  95% CI [{lo*100:+.2f},{hi*100:+.2f}]  win rate {f['win'].mean()*100:.1f}%  avg fill {f['px'].mean()*100:.1f}c  avg quoted ask {f['q'].mean()*100:.1f}c")
    print(f"volume others took in the fill window: median {f['vol'].median():.0f}, 25th pct {f['vol'].quantile(.25):.0f}; fills with >=20 contracts: {(f['vol']>=20).mean()*100:.0f}%")
    one = f.sort_values("t").groupby("ticker").head(1)
    lo, hi = ci(one["pnl"].values, one["day"].values)
    print(f"one trade per market: n={len(one)} P&L {one['pnl'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}]")
    print("by series:", {k[2:-3]: (len(g), round(g['pnl'].mean() * 100, 1)) for k, g in f.groupby("series")})
    print("by day:", {k[5:]: (len(g), round(g['pnl'].mean() * 100, 1)) for k, g in f.groupby("day")})
    print("by minutes left:", {int(k): (len(g), round(g['pnl'].mean() * 100, 1)) for k, g in f.groupby("ml")})
    pos = (f.groupby("day")["pnl"].mean() > 0)
    print(f"days with positive mean P&L: {pos.sum()} of {len(pos)}")
    # simple bankroll illustration: fixed 10 contracts per fill
    daily = f.groupby("day")["pnl"].sum() * 10
    print(f"illustration at 10 contracts per fill: mean ${daily.mean():.2f}/day, worst day ${daily.min():.2f}, best ${daily.max():.2f}, capital per trade ~${f['px'].mean()*10:.2f}")


if __name__ == "__main__":
    if sys.argv[1] == "signals":
        make_signals(*sys.argv[2:6])
    else:
        evaluate(sys.argv[2], sys.argv[3])
