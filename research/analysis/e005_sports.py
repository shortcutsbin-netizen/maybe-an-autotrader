#!/usr/bin/env python3
"""E005 — sports game-winner markets: Kalshi price vs sportsbook line vs outcome,
plus in-game price-trend (over/under-reaction) tests.

Inputs: Kalshi run dir (kalshi_events_pull.py output: markets/, candles/) and
external run dir (ext_pull.py output: sports/games_<league>.csv.gz).

Usage: e005_sports.py <kalshi_run> <ext_run> <split: train|val|trainval|test|all>

Taker fee on these series: 0.07*p*(1-p). (Makers pay 0.0175*p*(1-p) on the
big sports series — not modelled; all trades here are taker trades.)
Split: chronological by game date, 60/20/20, fixed in advance.
"""
import glob
import re
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

LEAGUE = {"KXNFLGAME": "nfl", "KXNBAGAME": "nba", "KXNHLGAME": "nhl", "KXNCAAFGAME": "ncaaf", "KXMLBGAME": "mlb"}
MON = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
# Kalshi code -> ESPN abbreviation where they differ (extended empirically from the unmatched list)
ALIAS = {
    "nba": {"WAS": "WSH", "NOP": "NO", "UTA": "UTAH", "GSW": "GS", "SAS": "SA", "NYK": "NY", "PHO": "PHX"},
    "nfl": {"WAS": "WSH", "LA": "LAR", "JAC": "JAX"},
    "nhl": {"LA": "LA", "TB": "TB", "NJ": "NJ", "SJ": "SJ", "WAS": "WSH", "MON": "MTL", "CLB": "CBJ", "NAS": "NSH", "CAL": "CGY", "WIN": "WPG", "VEG": "VGK"},
    "mlb": {"WAS": "WSH", "CWS": "CHW", "AZ": "ARI", "KC": "KC", "SD": "SD", "SF": "SF", "TB": "TB", "ATH": "ATH", "OAK": "ATH"},
    "ncaaf": {},
}


def fee(p):
    return 0.07 * p * (1 - p)


def american_to_prob(x):
    try:
        v = float(str(x).replace("+", "").replace("EVEN", "100"))
    except ValueError:
        return np.nan
    if v == 0:
        return np.nan
    return 100 / (v + 100) if v > 0 else -v / (-v + 100)


def to_ts(s):
    return (pd.to_datetime(s, utc=True, format="ISO8601") - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")


def load(krun, erun):
    mk = pd.concat([pd.read_csv(f) for f in glob.glob(f"{krun}/markets/*.csv.gz")], ignore_index=True)
    mk = mk[mk["series"].isin(LEAGUE)].copy()
    mk["league"] = mk["series"].map(LEAGUE)
    mk["code"] = mk["ticker"].str.rsplit("-", n=1).str[-1]
    part = mk["event_ticker"].str.split("-", n=1).str[1]
    mk["kdate"] = part.map(lambda s: f"20{s[0:2]}-{MON.get(s[2:5], 0):02d}-{s[5:7]}")
    mk["close_ts"] = to_ts(mk["close_time"])
    mk["y"] = (mk["result"] == "yes").astype(float)
    g = pd.concat([pd.read_csv(f, dtype=str) for f in glob.glob(f"{erun}/sports/games_*.csv.gz")], ignore_index=True)
    g = g[g["completed"] == "True"].copy()
    g["start_ts"] = to_ts(g["start"])
    # US date of the game (Eastern, approx: UTC-5) — Kalshi tickers use the local US date
    g["gdate"] = pd.to_datetime(g["start_ts"] - 5 * 3600, unit="s").dt.strftime("%Y-%m-%d")
    g["gdate_alt"] = pd.to_datetime(g["start_ts"] - 10 * 3600, unit="s").dt.strftime("%Y-%m-%d")
    for side in ("home", "away"):
        g[f"p_{side}_close_raw"] = g[f"ml_{side}_close"].map(american_to_prob)
        g[f"p_{side}_open_raw"] = g[f"ml_{side}_open"].map(american_to_prob)
    for k in ("close", "open"):
        tot = g[f"p_home_{k}_raw"] + g[f"p_away_{k}_raw"]
        g[f"p_home_{k}"] = g[f"p_home_{k}_raw"] / tot
        g[f"p_away_{k}"] = g[f"p_away_{k}_raw"] / tot
        g[f"vig_{k}"] = tot - 1
    return mk, g


def match(mk, g):
    """Attach ESPN game info to each Kalshi market. Returns market-level frame."""
    idx = {}
    for r in g.itertuples():
        for d in {r.gdate, r.gdate_alt}:
            idx.setdefault((r.league, d, frozenset((r.home_abbr.upper(), r.away_abbr.upper()))), r)
    rows, unmatched = [], {}
    for ev, grp in mk.groupby("event_ticker"):
        if len(grp) != 2:
            continue
        lg, d = grp["league"].iloc[0], grp["kdate"].iloc[0]
        codes = [ALIAS.get(lg, {}).get(c, c) for c in grp["code"]]
        r = idx.get((lg, d, frozenset(codes)))
        if r is None:
            unmatched[lg] = unmatched.get(lg, []) + ["/".join(sorted(grp["code"]))]
            continue
        for (_, m), c in zip(grp.iterrows(), codes):
            is_home = c == r.home_abbr.upper()
            rows.append({**m.to_dict(), "espn_id": r.espn_id, "start_ts": r.start_ts, "is_home": int(is_home),
                         "p_book_close": r.p_home_close if is_home else r.p_away_close,
                         "p_book_open": r.p_home_open if is_home else r.p_away_open,
                         "vig": r.vig_close, "gdate": r.gdate})
    return pd.DataFrame(rows), unmatched


def quotes_at(cd, tickers_ts, offset_s):
    """Last two-sided quote at or before (start_ts + offset) and within 10 minutes of it."""
    want = tickers_ts.assign(t=tickers_ts["start_ts"] + offset_s).sort_values("t")
    c = cd.sort_values("end_period_ts")
    out = pd.merge_asof(want, c, left_on="t", right_on="end_period_ts", by="ticker", direction="backward", tolerance=600)
    return out


def boot_ci(df, col, by="gdate", n=600, seed=5):
    g = df.groupby(by)[col].agg(["sum", "count"])
    if len(g) < 4:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    m = g["sum"].values[idx].sum(1) / np.maximum(g["count"].values[idx].sum(1), 1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def main():
    krun, erun, split = sys.argv[1], sys.argv[2], sys.argv[3]
    mk, g = load(krun, erun)
    m, unmatched = match(mk, g)
    print(f"kalshi events={mk['event_ticker'].nunique()} espn games={len(g)} matched markets={len(m)} (games={m['espn_id'].nunique() if len(m) else 0})")
    for lg, u in unmatched.items():
        print(f"  unmatched {lg}: {len(u)} e.g. {sorted(set(u))[:25]}")
    if not len(m):
        return
    days = sorted(m["gdate"].unique())
    a, b = int(len(days) * 0.6), int(len(days) * 0.8)
    sp = {"train": days[:a], "val": days[a:b], "test": days[b:], "trainval": days[:b], "all": days}
    cd = pd.concat([pd.read_csv(f) for f in glob.glob(f"{krun}/candles/*.csv.gz")], ignore_index=True)
    cd = cd[(cd["bid_c"] > 0) & (cd["ask_c"] < 1) & (cd["ask_c"] >= cd["bid_c"])]
    cd = cd[cd["ticker"].isin(m["ticker"])]

    # ---------- A/B: pre-game
    pre = quotes_at(cd, m, -300).dropna(subset=["bid_c", "ask_c"])
    pre["mid"] = (pre["bid_c"] + pre["ask_c"]) / 2
    pre["spread"] = pre["ask_c"] - pre["bid_c"]
    pre = pre.dropna(subset=["p_book_close"])
    pre["ev_yes"] = pre["y"] - pre["ask_c"] - fee(pre["ask_c"])
    pre["edge_book"] = pre["p_book_close"] - pre["ask_c"] - fee(pre["ask_c"])
    P = pre[pre["gdate"].isin(sp[split])]
    T = pre[pre["gdate"].isin(sp["train"])]
    print(f"\n== A. pre-game (5 min before start), split={split}: markets={len(P)} games={P['espn_id'].nunique()} days={P['gdate'].nunique()}")
    print(f"   mean spread {P['spread'].mean()*100:.2f}c; book vig {P['vig'].mean()*100:.2f}%; volume/market median {P['volume_fp'].median():,.0f}")
    print(f"   Brier: kalshi mid {brier(P['mid'], P['y']):.5f} | book close (de-vigged) {brier(P['p_book_close'], P['y']):.5f} | book open {brier(P['p_book_open'].fillna(P['p_book_close']), P['y']):.5f}")
    print(f"   mean |kalshi mid - book close| = {np.abs(P['mid']-P['p_book_close']).mean()*100:.2f} pts; corr {np.corrcoef(P['mid'], P['p_book_close'])[0,1]:.4f}")
    for lg, x in P.groupby("league"):
        print(f"   {lg:6s} n={len(x):5d} brier kalshi {brier(x['mid'], x['y']):.5f} book {brier(x['p_book_close'], x['y']):.5f} spread {x['spread'].mean()*100:.2f}c |diff| {np.abs(x['mid']-x['p_book_close']).mean()*100:.2f}")
    P = P.assign(pb=pd.cut(P["mid"], [0, .2, .35, .5, .65, .8, 1]))
    print("   calibration by Kalshi price:")
    for k, x in P.groupby("pb", observed=True):
        lo, hi = boot_ci(x.assign(e=x["y"] - x["mid"]), "e")
        lo2, hi2 = boot_ci(x, "ev_yes")
        print(f"     {str(k):12s} n={len(x):5d} mid={x['mid'].mean()*100:5.1f} win={x['y'].mean()*100:5.1f} err={100*(x['y'].mean()-x['mid'].mean()):+5.2f} [{lo*100:+.2f},{hi*100:+.2f}]  take-YES EV={x['ev_yes'].mean()*100:+.2f}c [{lo2*100:+.2f},{hi2*100:+.2f}]")
    if len(T) > 200:
        lg_ = lambda p: np.log(np.clip(p, .01, .99) / (1 - np.clip(p, .01, .99)))
        X = np.c_[lg_(T["mid"]), lg_(T["p_book_close"])]
        lr = LogisticRegression(C=10.0).fit(X, T["y"])
        print(f"   logistic on train: coef kalshi={lr.coef_[0][0]:.3f} book={lr.coef_[0][1]:.3f} (does the book add information beyond the Kalshi price?)")
        pc = lr.predict_proba(np.c_[lg_(P["mid"]), lg_(P["p_book_close"])])[:, 1]
        print(f"   combined-model Brier on {split}: {brier(pc, P['y']):.5f}")
    print("   B. rule: buy YES when (book prob - ask - fee) > threshold")
    for th in (0.0, 0.01, 0.02, 0.03, 0.05):
        x = P[P["edge_book"] > th]
        if len(x) >= 20:
            lo, hi = boot_ci(x, "ev_yes")
            print(f"     thr={th:.2f} n={len(x):5d} EV={x['ev_yes'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] win={x['y'].mean()*100:.0f}% avg ask={x['ask_c'].mean()*100:.0f}c")

    # ---------- D: in-game trend
    c = cd.merge(m[["ticker", "start_ts", "close_ts", "y", "gdate", "league", "p_book_close"]], on="ticker")
    c = c[(c["end_period_ts"] >= c["start_ts"] + 300) & (c["end_period_ts"] <= c["close_ts"] - 300)].sort_values(["ticker", "end_period_ts"])
    c["mid"] = (c["bid_c"] + c["ask_c"]) / 2
    grp = c.groupby("ticker")
    for lag in (2, 5, 15):
        prev = c[["ticker", "end_period_ts", "mid"]].rename(columns={"mid": f"mid_l{lag}"})
        prev["end_period_ts"] += lag * 60
        c = c.merge(prev, on=["ticker", "end_period_ts"], how="left")
        c[f"d{lag}"] = c["mid"] - c[f"mid_l{lag}"]
    c["ev_yes"] = c["y"] - c["ask_c"] - fee(c["ask_c"])
    no_ask = 1 - c["bid_c"]
    c["ev_no"] = (1 - c["y"]) - no_ask - fee(no_ask)
    c["resid"] = c["y"] - c["mid"]
    C = c[c["gdate"].isin(sp[split])].dropna(subset=["d5", "d15"])
    C = C[(C["mid"] > 0.05) & (C["mid"] < 0.95)]
    print(f"\n== D. in-game trend, split={split}: quote-minutes={len(C)} markets={C['ticker'].nunique()}")
    print("   mean (outcome - mid) by size of the last 5-minute move; negative after up-moves = overreaction")
    C = C.assign(db=pd.cut(C["d5"], [-1, -.15, -.08, -.03, .03, .08, .15, 1]))
    for k, x in C.groupby("db", observed=True):
        lo, hi = boot_ci(x, "resid")
        lo1, hi1 = boot_ci(x, "ev_yes")
        lo2, hi2 = boot_ci(x, "ev_no")
        print(f"     d5 {str(k):16s} n={len(x):7d} resid={x['resid'].mean()*100:+.2f} [{lo*100:+.2f},{hi*100:+.2f}] | take YES {x['ev_yes'].mean()*100:+.2f}c [{lo1*100:+.2f},{hi1*100:+.2f}] | take NO {x['ev_no'].mean()*100:+.2f}c [{lo2*100:+.2f},{hi2*100:+.2f}]")
    print("   by league, |d5| > 0.08: fade (take the side that just fell)")
    big = C[np.abs(C["d5"]) > 0.08].copy()
    big["fade"] = np.where(big["d5"] > 0, big["ev_no"], big["ev_yes"])
    big["follow"] = np.where(big["d5"] > 0, big["ev_yes"], big["ev_no"])
    for lg, x in big.groupby("league"):
        lo, hi = boot_ci(x, "fade")
        lo2, hi2 = boot_ci(x, "follow")
        print(f"     {lg:6s} n={len(x):6d} fade {x['fade'].mean()*100:+.2f}c [{lo*100:+.2f},{hi*100:+.2f}] | follow {x['follow'].mean()*100:+.2f}c [{lo2*100:+.2f},{hi2*100:+.2f}]")


if __name__ == "__main__":
    main()
