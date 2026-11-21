#!/usr/bin/env python3
"""E012 — the frozen E010 dislocation rule on periods it has never seen.

Pre-registered in docs/experiments/E012-E013-preregistration.md (committed before
any of the new data was pulled). The model, threshold and primary fill model are
exactly E010's; nothing is re-fitted or re-tuned on the new periods.

  signals  <fit_run> <new_run> <out_csv> <out_tickers> [first_day] [last_day]
      Fits the frozen model on <fit_run> days 2026-09-13..2026-10-11 (identical to
      e010_dislocation_frozen.py) and writes every signal in <new_run>.
  evaluate <signals_csv> <trades_dirs_comma_separated>
      Fill models (all pre-registered):
        F1 primary  : VWAP of same-side taker prints in (t+1 s, t+6 s] at <= quote + 2c
        F2 last-in-line: the HIGHEST same-side print price in that window at <= limit,
                      and only if >= 20 contracts printed there (otherwise no trade)
        F3 slow     : the first same-side print at or after t + 3 s (within 15 s), no limit
      P&L per contract = outcome - price - 0.07 p (1 - p); hold to settlement.
"""
import glob
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
THR, LIM, W0, W1 = 0.08, 0.02, 1.0, 6.0


def fee(p):
    return 0.07 * p * (1 - p)


def fit_frozen(fit_run):
    import e003_s1_model as E
    from e001_calibration import load, split_days
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    d = E.build(fit_run)
    mk, _ = load(fit_run)
    tr = split_days(mk)["train"]
    d = d.dropna(subset=E.EXT + E.MKT + ["y"])
    fit = d[d["day"].isin(tr[:int(len(tr) * 0.8)])]
    assert fit["day"].min() == "2026-09-13" and fit["day"].max() == "2026-10-11", (fit["day"].min(), fit["day"].max())
    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300)).fit(fit[E.EXT + E.MKT].values, fit["y"].values)
    return m, E


def make_signals(fit_run, new_run, out_csv, out_list, first=None, last=None):
    m, E = fit_frozen(fit_run)
    x = E.build(new_run).dropna(subset=E.EXT + E.MKT + ["y"])
    if first:
        x = x[x["day"] >= first]
    if last:
        x = x[x["day"] <= last]
    x = x.copy()
    x["p"] = m.predict_proba(x[E.EXT + E.MKT].values)[:, 1]
    ask_y, ask_n = x["ask_c"], 1 - x["bid_c"]
    e_y, e_n = x["p"] - ask_y - fee(ask_y), (1 - x["p"]) - ask_n - fee(ask_n)
    x["side"] = np.where((e_y > THR) & (e_y >= e_n), 1, np.where(e_n > THR, -1, 0))
    print(f"rows={len(x)} days={x['day'].min()}..{x['day'].max()} ({x['day'].nunique()}) markets={x['ticker'].nunique()} "
          f"Brier model {np.mean((x['p']-x['y'])**2):.5f} vs Kalshi mid {np.mean((x['mid']-x['y'])**2):.5f}")
    s = x[x["side"] != 0][["ticker", "series", "day", "end_period_ts", "minutes_left", "side", "p", "bid_c", "ask_c", "y", "spread", "z", "mid"]]
    s.to_csv(out_csv, index=False)
    open(out_list, "w").write("\n".join(sorted(s["ticker"].unique())) + "\n")
    print(f"signals={len(s)} markets={s['ticker'].nunique()} by series={s['series'].value_counts().to_dict()}")


def ci(v, days, n=1000):
    df = pd.DataFrame({"v": v, "d": days}).dropna()
    g = df.groupby("d")["v"].agg(["sum", "count"])
    if len(g) < 4:
        return np.nan, np.nan
    rng = np.random.default_rng(4)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    mm = g["sum"].values[idx].sum(1) / np.maximum(g["count"].values[idx].sum(1), 1)
    return np.percentile(mm, 2.5), np.percentile(mm, 97.5)


def load_trades(dirs, tickers):
    parts = []
    for dd in dirs.split(","):
        for f in sorted(glob.glob(f"{dd}/trades*.csv.gz")):
            t = pd.read_csv(f, usecols=["ticker", "created_time", "yes_price", "no_price", "count", "taker_side"])
            parts.append(t[t["ticker"].isin(tickers)])
    tr = pd.concat(parts, ignore_index=True)
    tr["ts"] = (pd.to_datetime(tr["created_time"], utc=True, format="ISO8601") - pd.Timestamp(0, tz="UTC")) / pd.Timedelta("1s")
    tr = tr.drop_duplicates(["ticker", "created_time", "yes_price", "count", "taker_side"]).sort_values(["ticker", "ts"])
    return {k: g for k, g in tr.groupby("ticker")}


def evaluate(sig_csv, dirs):
    sig = pd.read_csv(sig_csv)
    by = load_trades(dirs, set(sig["ticker"]))
    rows = []
    for r in sig.itertuples():
        q = r.ask_c if r.side == 1 else 1 - r.bid_c
        win = r.y if r.side == 1 else 1 - r.y
        rec = {"ticker": r.ticker, "day": r.day, "month": r.day[:7], "series": r.series, "t": r.end_period_ts, "ml": r.minutes_left,
               "q": q, "win": win, "f1": np.nan, "f2": np.nan, "f3": np.nan, "vol": 0.0, "has_trades": r.ticker in by}
        g = by.get(r.ticker)
        if g is not None:
            own = g[g["taker_side"] == ("yes" if r.side == 1 else "no")]
            t_, c_ = own["ts"].values, own["count"].values.astype(float)
            p_ = (own["yes_price"] if r.side == 1 else own["no_price"]).values.astype(float)
            m = (t_ > r.end_period_ts + W0) & (t_ <= r.end_period_ts + W1) & (p_ <= q + LIM + 1e-9)
            if m.any():
                rec["vol"] = c_[m].sum()
                rec["f1"] = (p_[m] * c_[m]).sum() / c_[m].sum()
                if rec["vol"] >= 20:
                    rec["f2"] = p_[m].max()
            j = np.searchsorted(t_, r.end_period_ts + 3.0)
            if j < len(t_) and t_[j] <= r.end_period_ts + 18.0:
                rec["f3"] = p_[j]
        rows.append(rec)
    x = pd.DataFrame(rows)
    for k in ("f1", "f2", "f3"):
        x[f"pnl_{k}"] = x["win"] - x[k] - fee(x[k])
    print(f"signals={len(x)} in {x['ticker'].nunique()} markets over {x['day'].nunique()} days ({len(x)/max(x['day'].nunique(),1):.0f}/day); "
          f"signals whose market has trade data: {x['has_trades'].mean()*100:.1f}%")
    names = {"f1": "F1 primary (VWAP 1-6 s, limit quote+2c)", "f2": "F2 last-in-line (worst price, >=20 printed)", "f3": "F3 slow (first print after 3 s, no limit)"}
    for k, nm in names.items():
        f = x.dropna(subset=[k])
        if len(f) < 10:
            print(f"  {nm}: too few fills ({len(f)})")
            continue
        lo, hi = ci(f[f"pnl_{k}"].values, f["day"].values)
        pos = (f.groupby("day")[f"pnl_{k}"].mean() > 0)
        print(f"  {nm}: fills={len(f)} ({len(f)/len(x)*100:.0f}%) P&L {f[f'pnl_{k}'].mean()*100:+.2f}c 95% CI [{lo*100:+.2f},{hi*100:+.2f}] "
              f"win {f['win'].mean()*100:.1f}% avg price {f[k].mean()*100:.1f}c (quote {f['q'].mean()*100:.1f}c) days positive {pos.sum()}/{len(pos)}")
    f = x.dropna(subset=["f1"])
    print("  F1 by month:", {k: (len(g), round(g['pnl_f1'].mean() * 100, 2)) for k, g in f.groupby("month")})
    print("  F1 by series:", {k[2:-3]: (len(g), round(g['pnl_f1'].mean() * 100, 1)) for k, g in f.groupby("series")})
    print("  F1 by minutes left:", {int(k): (len(g), round(g['pnl_f1'].mean() * 100, 1)) for k, g in f.groupby("ml")})
    one = f.sort_values("t").groupby("ticker").head(1)
    lo, hi = ci(one["pnl_f1"].values, one["day"].values)
    print(f"  F1 one trade per market: n={len(one)} P&L {one['pnl_f1'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}]")
    print(f"  F1 median volume printed in window: {f['vol'].median():.0f}; 25th pct {f['vol'].quantile(.25):.0f}")
    daily = f.groupby("day")["pnl_f1"].sum() * 10
    cum = daily.cumsum()
    print(f"  illustration, 10 contracts per F1 fill: mean ${daily.mean():.2f}/day, median ${daily.median():.2f}, worst ${daily.min():.2f}, best ${daily.max():.2f}, "
          f"max drawdown ${float((cum.cummax() - cum).max()):.2f}, capital per trade ~${f['f1'].mean()*10:.2f}")
    x.to_csv(sig_csv.replace(".csv", "_eval.csv"), index=False)


if __name__ == "__main__":
    if sys.argv[1] == "signals":
        make_signals(*sys.argv[2:])
    else:
        evaluate(sys.argv[2], sys.argv[3])
