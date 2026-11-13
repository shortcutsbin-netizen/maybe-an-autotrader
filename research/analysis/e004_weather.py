#!/usr/bin/env python3
"""E004 — daily-high temperature markets: does a model fusing archived weather
forecasts, live station observations and the market price beat the market, and
does trading the disagreement pay after fees?

Inputs: Kalshi run (kalshi_events_pull.py: markets/, candles/ for KXHIGH*),
        external run (ext_pull.py: weather/metar_*, asos1min_*, fcst_*).
Usage:  e004_weather.py <kalshi_run> <ext_run> [eval_split=val] [obs=metar|asos1min]

Information set at decision time t (honest and deliberately conservative):
  * Observations: METAR reports with valid time <= t - 10 min (obs=metar), or
    1-minute ASOS <= t - 5 min (obs=asos1min; real-time availability of this
    feed is NOT verified — treat as an upper bound).
  * Forecasts: Open-Meteo "previous runs" — for valid hour v we use the forecast
    that was current 24 h before v when t >= v - 24h, otherwise the one current
    48 h before v. A live bot would have fresher runs; this understates it.
  * Market: 10-minute candle close quotes.
Split: chronological by climate day, 60/20/20 (fixed in advance). Models fit on
the first 80% of train days; trade threshold chosen on the last 20% of train
days; reported on eval split. Fills: displayed ask at t; "delay" = ask one
candle (10 min) later plus one tick.
"""
import glob
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CITY = {"KXHIGHNY": ("NY", 5), "KXHIGHPHIL": ("PHIL", 5), "KXHIGHMIA": ("MIA", 5), "KXHIGHCHI": ("CHI", 6),
        "KXHIGHAUS": ("AUS", 6), "KXHIGHDEN": ("DEN", 7), "KXHIGHLAX": ("LAX", 8)}
MON = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
HB = [0, 3, 5, 7, 9, 11, 14, 18, 24, 30, 99]


def fee(p):
    return 0.07 * p * (1 - p)


def ts(s, fmt=None):
    return ((pd.to_datetime(s, utc=True, format=fmt) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")).astype("int64")


def load_markets(krun):
    mk = pd.concat([pd.read_csv(f) for f in glob.glob(f"{krun}/markets/KXHIGH*.csv.gz")], ignore_index=True)
    mk = mk[mk["series"].isin(CITY) & mk["result"].isin(["yes", "no"])].copy()
    d = mk["event_ticker"].str.split("-").str[1]
    mk["day"] = d.map(lambda s: f"20{s[0:2]}-{MON[s[2:5]]:02d}-{s[5:7]}")
    mk["city"] = mk["series"].map(lambda s: CITY[s][0])
    off = mk["series"].map(lambda s: CITY[s][1])
    mk["d0"] = ts(mk["day"]) + off * 3600
    mk["d1"] = mk["d0"] + 86400
    mk["H"] = pd.to_numeric(mk["expiration_value"], errors="coerce")
    fl, cp = pd.to_numeric(mk["floor_strike"], errors="coerce"), pd.to_numeric(mk["cap_strike"], errors="coerce")
    st = mk["strike_type"]
    mk["lo"] = np.where(st == "between", fl, np.where(st == "greater", fl + 1, -999))
    mk["hi"] = np.where(st == "between", cp, np.where(st == "less", cp - 1, 999))
    mk["y"] = (mk["result"] == "yes").astype(int)
    mk["open_ts"], mk["close_ts"] = ts(mk["open_time"], "ISO8601"), ts(mk["close_time"], "ISO8601")
    return mk.dropna(subset=["H"])


def load_obs(erun, city, kind):
    if kind == "asos1min":
        o = pd.read_csv(f"{erun}/weather/asos1min_{city}.csv.gz")
    else:
        o = pd.read_csv(f"{erun}/weather/metar_{city}.csv.gz")
    o["t"] = ts(o["valid"])
    o["tmpf"] = pd.to_numeric(o["tmpf"], errors="coerce")
    o = o.dropna(subset=["tmpf"]).drop_duplicates("t").sort_values("t")
    return o["t"].values, o["tmpf"].values


def load_fc(erun, city):
    f = pd.read_csv(f"{erun}/weather/fcst_{city}.csv.gz")
    f["t"] = ts(f["time"])
    c1 = [c for c in f.columns if "previous_day1" in c]
    c2 = [c for c in f.columns if "previous_day2" in c]
    f = f.sort_values("t")
    return f["t"].values, f[c1].values.astype(float), f[c2].values.astype(float)


def event_features(ev_times, d0, d1, obs, fc, lag):
    """Features per decision time for one city-day."""
    ot, ov = obs
    ft, f1, f2 = fc
    sel = (ft >= d0) & (ft < d1)
    hv, h1, h2 = ft[sel], f1[sel], f2[sel]
    if len(hv) < 20:
        return None
    m1, m2 = np.nanmean(h1, axis=1), np.nanmean(h2, axis=1)
    spread_models = float(np.nanstd(np.nanmax(h1, axis=0)))
    i0, i1 = np.searchsorted(ot, d0), np.searchsorted(ot, d1)
    day_t, day_v = ot[i0:i1], ov[i0:i1]
    cummax = np.maximum.accumulate(day_v) if len(day_v) else np.array([])
    rows = []
    for t in ev_times:
        ta = t - lag
        k = np.searchsorted(day_t, ta, side="right")
        M = cummax[k - 1] if k > 0 else np.nan
        j = np.searchsorted(ot, ta, side="right")
        cur = ov[j - 1] if j > 0 and ta - ot[j - 1] < 3 * 3600 else np.nan
        j1 = np.searchsorted(ot, ta - 3600, side="right")
        prev = ov[j1 - 1] if j1 > 0 and ta - 3600 - ot[j1 - 1] < 3 * 3600 else np.nan
        fcst = np.where(hv - 86400 <= t, m1, m2)          # forecast available at t for each valid hour
        rem = hv >= (t // 3600) * 3600
        F_rem = np.nanmax(fcst[rem]) if rem.any() else np.nan
        F_day = np.nanmax(fcst)
        # forecast for "now" (the hour containing t - lag); day-1 forecast is always available for it
        jn = np.searchsorted(ft, (ta // 3600) * 3600)
        fc_now = np.nanmean(f1[jn]) if jn < len(ft) and ft[jn] == (ta // 3600) * 3600 else np.nan
        rows.append((t, M, cur, prev, F_rem, F_day, fc_now, spread_models, (d1 - t) / 3600.0, max(0.0, (t - d0) / 3600.0)))
    return pd.DataFrame(rows, columns=["t", "M", "cur", "prev", "F_rem", "F_day", "fc_now", "mspread", "h_left", "h_in"])


def build(krun, erun, kind):
    mk = load_markets(krun)
    lag = 300 if kind == "asos1min" else 600
    cd = pd.concat([pd.read_csv(f) for f in glob.glob(f"{krun}/candles/KXHIGH*.csv.gz")], ignore_index=True)
    cd = cd.drop_duplicates(["ticker", "end_period_ts"]).sort_values(["ticker", "end_period_ts"])
    cd["t"] = ((cd["end_period_ts"] + 599) // 600) * 600           # snap to the 10-minute grid
    cd = cd.drop_duplicates(["ticker", "t"], keep="last")
    cd["ask_next"] = cd.groupby("ticker")["ask_c"].shift(-1)
    cd["bid_next"] = cd.groupby("ticker")["bid_c"].shift(-1)
    cd["t_next"] = cd.groupby("ticker")["t"].shift(-1)
    cd["mid_prev6"] = (cd.groupby("ticker")["bid_c"].shift(6) + cd.groupby("ticker")["ask_c"].shift(6)) / 2
    d = cd.merge(mk[["ticker", "event_ticker", "city", "series", "day", "d0", "d1", "H", "lo", "hi", "y", "strike_type", "close_ts"]], on="ticker")
    feats, checks = [], []
    for city in sorted(d["city"].unique()):
        obs, fc = load_obs(erun, city, kind), load_fc(erun, city)
        o1 = load_obs(erun, city, "asos1min")
        dc = d[d["city"] == city]
        for ev, g in dc.groupby("event_ticker"):
            d0, d1, H = int(g["d0"].iloc[0]), int(g["d1"].iloc[0]), float(g["H"].iloc[0])
            times = np.sort(g["t"].unique())
            times = times[times <= d1]
            f = event_features(times, d0, d1, obs, fc, lag)
            if f is None:
                continue
            f["event_ticker"] = ev
            feats.append(f)
            a, b = np.searchsorted(obs[0], d0), np.searchsorted(obs[0], d1)
            a1, b1 = np.searchsorted(o1[0], d0), np.searchsorted(o1[0], d1)
            checks.append((city, g["day"].iloc[0], H, obs[1][a:b].max() if b > a else np.nan, o1[1][a1:b1].max() if b1 > a1 else np.nan))
    F = pd.concat(feats, ignore_index=True)
    d = d.merge(F, on=["event_ticker", "t"], how="inner")
    chk = pd.DataFrame(checks, columns=["city", "day", "H", "metar_max", "asos1_max"])
    return mk, d, chk


def add_model_inputs(d, lam):
    d = d.copy()
    err = (d["cur"] - d["fc_now"]).fillna(0.0)
    decay = np.clip(d["h_left"] / 12.0, 0, 1) * 0 + 1.0
    d["G"] = d["F_rem"] + lam * err * decay
    d["mu"] = np.fmax(d["M"].fillna(-999), d["G"])
    d["passed"] = (d["M"].fillna(-999) >= d["G"]).astype(int)
    d["hb"] = pd.cut(d["h_left"], HB, labels=False, include_lowest=True)
    return d


def residual_probs(fit, d):
    """Empirical residual model: P(lo <= H <= hi) from fit-set residuals in the same (city, hours-left, passed) cell."""
    ev = fit.drop_duplicates(["event_ticker", "t"])
    ev = ev.assign(res=ev["H"] - ev["mu"])
    cells = {k: g["res"].values for k, g in ev.groupby(["city", "hb", "passed"])}
    pooled = {k: g["res"].values for k, g in ev.groupby(["hb", "passed"])}
    p = np.full(len(d), np.nan)
    key = list(zip(d["city"], d["hb"], d["passed"]))
    mu, lo, hi = d["mu"].values, d["lo"].values, d["hi"].values
    idx = {}
    for i, k in enumerate(key):
        idx.setdefault(k, []).append(i)
    for k, ii in idx.items():
        r = cells.get(k)
        if r is None or len(r) < 150:
            r = pooled.get((k[1], k[2]))
        if r is None or len(r) < 50:
            continue
        ii = np.array(ii)
        r = r[:: max(1, len(r) // 2000)]
        Hs = np.rint(mu[ii][:, None] + r[None, :])
        p[ii] = ((Hs >= lo[ii][:, None]) & (Hs <= hi[ii][:, None])).mean(1)
    return p


EXT = ["p_res", "lo_mu", "hi_mu", "lo_M", "hi_M", "h_left", "h_in", "passed", "fday_mu", "nowerr", "mspread", "trend1h", "width"]
MKT = ["logit_mid", "spread", "dmid1h", "lvol"]


def features(d):
    d = d.copy()
    cl = lambda x: np.clip(x, -30, 30)
    d["lo_mu"], d["hi_mu"] = cl(d["lo"] - d["mu"]), cl(d["hi"] - d["mu"])
    Mf = d["M"].fillna(d["mu"] - 15)
    d["lo_M"], d["hi_M"] = cl(d["lo"] - Mf), cl(d["hi"] - Mf)
    d["fday_mu"] = cl(d["F_day"] - d["mu"])
    d["nowerr"] = cl((d["cur"] - d["fc_now"]).fillna(0))
    d["trend1h"] = cl((d["cur"] - d["prev"]).fillna(0))
    d["width"] = np.clip(d["hi"] - d["lo"], 0, 5)
    d["mid"] = (d["bid_c"] + d["ask_c"]) / 2
    d["spread"] = d["ask_c"] - d["bid_c"]
    m = d["mid"].clip(0.005, 0.995)
    d["logit_mid"] = np.log(m / (1 - m))
    d["dmid1h"] = (d["mid"] - d["mid_prev6"]).fillna(0)
    d["lvol"] = np.log1p(d["volume"].fillna(0))
    return d


def brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def day_ci(df, col, n=600, seed=3):
    g = df.groupby("day")[col].agg(["sum", "count"])
    if len(g) < 4:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    m = g["sum"].values[idx].sum(1) / np.maximum(g["count"].values[idx].sum(1), 1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def trade(d, p, thr):
    ask, bid, y = d["ask_c"].values, d["bid_c"].values, d["y"].values
    na = 1 - bid
    e_yes, e_no = p - ask - fee(ask), (1 - p) - na - fee(na)
    side = np.where((e_yes > thr) & (e_yes >= e_no), 1, np.where(e_no > thr, -1, 0))
    disp = np.where(side == 1, y - ask - fee(ask), np.where(side == -1, (1 - y) - na - fee(na), np.nan))
    a2, b2 = d["ask_next"].values, d["bid_next"].values
    ok = np.isfinite(a2) & np.isfinite(b2) & (a2 < 1) & (b2 > 0) & ((d["t_next"].values - d["t"].values) <= 1800)
    a2 = np.minimum(np.where(ok, a2, .5) + 0.01, 0.99)
    n2 = np.minimum(1 - np.where(ok, b2, .5) + 0.01, 0.99)
    dly = np.where(~ok, np.nan, np.where(side == 1, y - a2 - fee(a2), np.where(side == -1, (1 - y) - n2 - fee(n2), np.nan)))
    return side, disp, dly


def main():
    krun, erun = sys.argv[1], sys.argv[2]
    eval_split = sys.argv[3] if len(sys.argv) > 3 else "val"
    kind = sys.argv[4] if len(sys.argv) > 4 else "metar"
    mk, d, chk = build(krun, erun, kind)
    print(f"markets={len(mk)} city-days={mk['event_ticker'].nunique()} rows={len(d)} obs={kind}")
    bad = mk[(mk["y"] == 1) != ((mk["H"] >= mk["lo"]) & (mk["H"] <= mk["hi"]))]
    print(f"bracket-rule check: {len(bad)} of {len(mk)} markets disagree with (lo<=H<=hi)")
    chk["dm"], chk["d1"] = chk["H"] - chk["metar_max"], chk["H"] - chk["asos1_max"]
    print("settlement high minus max of observations (deg F): METAR mean %.2f, P(=0) %.2f, P(>=1) %.2f, P(>=2) %.2f | 1-min ASOS mean %.2f, P(=0) %.2f, P(|d|>=1) %.2f" % (
        chk["dm"].mean(), (chk["dm"].round() == 0).mean(), (chk["dm"] >= 1).mean(), (chk["dm"] >= 2).mean(),
        chk["d1"].mean(), (chk["d1"].round() == 0).mean(), (chk["d1"].abs() >= 1).mean()))
    days = sorted(d["day"].unique())
    a, b = int(len(days) * 0.6), int(len(days) * 0.8)
    sp = {"train": days[:a], "val": days[a:b], "test": days[b:]}
    cut = int(len(sp["train"]) * 0.8)
    fit_days, thr_days, ev_days = sp["train"][:cut], sp["train"][cut:], sp[eval_split]
    print(f"days fit={fit_days[0]}..{fit_days[-1]} thr={thr_days[0]}..{thr_days[-1]} eval[{eval_split}]={ev_days[0]}..{ev_days[-1]}")
    d = d[(d["t"] % 1800 == 0)]                               # one decision per 30 minutes
    d = d[(d["bid_c"] > 0) & (d["ask_c"] < 1) & (d["ask_c"] >= d["bid_c"])]
    # choose nowcast weight on fit days (MAE of mu vs H, one row per city-day-time)
    best = None
    for lam in (0.0, 0.5, 1.0):
        x = add_model_inputs(d[d["day"].isin(fit_days)], lam).drop_duplicates(["event_ticker", "t"])
        mae = float(np.abs(x["H"] - x["mu"]).mean())
        if best is None or mae < best[1]:
            best = (lam, mae)
    lam = best[0]
    d = add_model_inputs(d, lam)
    x = d.drop_duplicates(["event_ticker", "t"])
    print(f"nowcast weight lambda={lam} (fit MAE {best[1]:.2f}F). MAE of point forecast by hours left in day (all days):",
          {int(k): round(float(np.abs(g['H'] - g['mu']).mean()), 2) for k, g in x.groupby('hb')})
    fit = d[d["day"].isin(fit_days)]
    d["p_res"] = residual_probs(fit, d)
    d = features(d).dropna(subset=["p_res"])
    fit, thr_df, ev = d[d["day"].isin(fit_days)], d[d["day"].isin(thr_days)], d[d["day"].isin(ev_days)].copy()
    print(f"rows fit={len(fit)} thr={len(thr_df)} eval={len(ev)}; eval city-days={ev['event_ticker'].nunique()} spread mean={ev['spread'].mean()*100:.2f}c")
    gb = lambda: HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=250, min_samples_leaf=300, l2_regularization=1.0, random_state=0)
    models = {"gb_ext": (gb(), EXT), "lr_all": (make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=400)), ["p_res_logit", "logit_mid"]),
              "gb_all": (gb(), EXT + MKT)}
    for x in (fit, thr_df, ev):
        pr = x["p_res"].clip(0.005, 0.995)
        x.insert(0, "p_res_logit", np.log(pr / (1 - pr)))
    pt, pe = {"mid": thr_df["mid"].values, "p_res": thr_df["p_res"].values}, {"mid": ev["mid"].values, "p_res": ev["p_res"].values}
    for name, (m, cols) in models.items():
        m.fit(fit[cols].values, fit["y"].values)
        pt[name], pe[name] = m.predict_proba(thr_df[cols].values)[:, 1], m.predict_proba(ev[cols].values)[:, 1]
    print("lr_all coefficients [model logit, market logit] (standardised):", np.round(models["lr_all"][0][-1].coef_[0], 3))
    y = ev["y"].values
    hl = ev["h_left"].values
    print("\n== forecast skill on eval (Brier, lower is better): all | day before (>24h left) | morning (12-24h) | afternoon (5-12h) | evening (<5h)")
    for name, p in pe.items():
        seg = [brier(p[(hl > a_) & (hl <= b_)], y[(hl > a_) & (hl <= b_)]) for a_, b_ in ((24, 99), (12, 24), (5, 12), (0, 5))]
        print(f"  {name:7s} {brier(p, y):.5f} | " + " | ".join(f"{s:.5f}" for s in seg))
    print("\n== trading the disagreement (cents/contract; threshold chosen on held-back train days using the delayed fill)")
    grid = [0.0, 0.02, 0.04, 0.06, 0.10, 0.15]
    for name in ("p_res", "gb_ext", "lr_all", "gb_all"):
        bestv, bth = -9, None
        for th in grid:
            s, disp, dly = trade(thr_df, pt[name], th)
            if np.isfinite(dly).sum() >= 200 and np.nanmean(dly) > bestv:
                bestv, bth = float(np.nanmean(dly)), th
        if bth is None:
            print(f"  {name}: no threshold with >=200 trades")
            continue
        s, disp, dly = trade(ev, pe[name], bth)
        t = ev.assign(pd_=disp, pl=dly, side=s)
        t1, t2 = t.dropna(subset=["pd_"]), t.dropna(subset=["pl"])
        lo, hi = day_ci(t1, "pd_")
        lo2, hi2 = day_ci(t2, "pl")
        print(f"  {name:7s} thr={bth:.2f} (thr-days delayed EV {bestv*100:+.2f}c) | eval displayed n={len(t1)} EV={t1['pd_'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] | delayed 10min n={len(t2)} EV={t2['pl'].mean()*100:+.2f}c [{lo2*100:+.2f},{hi2*100:+.2f}] win={np.mean(t2['pl']>0)*100:.0f}% days={t2['day'].nunique()}")
        if len(t2):
            first = t2.sort_values("t").groupby(["ticker", "side"]).head(1)
            lo3, hi3 = day_ci(first, "pl")
            print(f"           one trade per market-side: n={len(first)} EV={first['pl'].mean()*100:+.2f}c [{lo3*100:+.2f},{hi3*100:+.2f}] | by city: " +
                  ", ".join(f"{c}:{len(g)}/{g['pl'].mean()*100:+.1f}" for c, g in first.groupby("city")))
            first = first.assign(seg=pd.cut(first["h_left"], [0, 5, 12, 24, 99], labels=["evening", "afternoon", "morning", "day-before"]))
            print("           by time: " + ", ".join(f"{c}:{len(g)}/{g['pl'].mean()*100:+.1f}" for c, g in first.groupby("seg", observed=True)) +
                  " | by side: " + ", ".join(f"{'YES' if c==1 else 'NO'}:{len(g)}/{g['pl'].mean()*100:+.1f}" for c, g in first.groupby("side")))
    print("\n== every threshold on eval, gb_all and p_res (transparency only)")
    for name in ("p_res", "gb_all"):
        for th in grid:
            s, disp, dly = trade(ev, pe[name], th)
            t2 = ev.assign(pl=dly).dropna(subset=["pl"])
            if len(t2):
                lo2, hi2 = day_ci(t2, "pl")
                print(f"  {name:7s} thr={th:.2f} n={len(t2):6d} delayed EV={t2['pl'].mean()*100:+.2f}c [{lo2*100:+.2f},{hi2*100:+.2f}]")


if __name__ == "__main__":
    main()
