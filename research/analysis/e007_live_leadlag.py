#!/usr/bin/env python3
"""E007 — live order-book capture: depth at the touch, how fast Kalshi quotes
follow spot, and how the model-vs-quote edge decays with execution delay.

Input: a live_capture.py run directory (book.jsonl.gz, spot.jsonl.gz, markets.jsonl.gz).
Usage: e007_live_leadlag.py <run_dir>

Everything here uses only public data captured in real time, so quotes and
sizes are the ones a no-account observer actually saw, at ~2 s resolution.
Outcome of each 15-minute market = (next market's strike >= this market's
strike), because each strike is the previous window's settlement value.
"""
import gzip
import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

GRID = 2.0


def fee(p):
    return 0.07 * p * (1 - p)


def load(run):
    books, spots, mk = [], [], {}
    with gzip.open(f"{run}/markets.jsonl.gz", "rt") as f:
        for line in f:
            o = json.loads(line)
            for s, ms in o["markets"].items():
                if isinstance(ms, list):
                    for m in ms:
                        mk[m["ticker"]] = {"series": s, "open": pd.Timestamp(m["open_time"]).timestamp(),
                                           "close": pd.Timestamp(m["close_time"]).timestamp(), "strike": m.get("floor_strike")}
    with gzip.open(f"{run}/book.jsonl.gz", "rt") as f:
        for line in f:
            o = json.loads(line)
            if o["status"] != 200:
                continue
            try:
                ob = json.loads(o["body"]).get("orderbook_fp") or {}
                yes, no = ob.get("yes_dollars") or [], ob.get("no_dollars") or []
                yb, ybs = (float(yes[-1][0]), float(yes[-1][1])) if yes else (0.0, 0.0)
                nb, nbs = (float(no[-1][0]), float(no[-1][1])) if no else (0.0, 0.0)
                ya = 1 - nb if no else 1.0
                d_bid = sum(float(q) for p, q in yes if float(p) >= yb - 0.021)
                d_ask = sum(float(q) for p, q in no if float(p) >= nb - 0.021)
                books.append((o["t1"], o["series"], o["ticker"], yb, ybs, ya, nbs, d_bid, d_ask, o["t1"] - o["t0"]))
            except Exception:
                continue
    with gzip.open(f"{run}/spot.jsonl.gz", "rt") as f:
        for line in f:
            o = json.loads(line)
            if o["status"] != 200 or o["src"] != "coinbase":
                continue
            try:
                b = json.loads(o["body"])
                spots.append((o["t1"], o["key"], (float(b["bid"]) + float(b["ask"])) / 2, float(b["price"])))
            except Exception:
                continue
    B = pd.DataFrame(books, columns=["t", "series", "ticker", "bid", "bid_sz", "ask", "ask_sz", "depth_bid2c", "depth_ask2c", "lat"])
    S = pd.DataFrame(spots, columns=["t", "product", "smid", "last"])
    return B, S, mk


def main():
    run = sys.argv[1]
    B, S, mk = load(run)
    man = json.load(open(f"{run}/manifest.json"))
    series_map = {s: v.get("coinbase") for s, v in man["request"]["series"].items()}
    print(f"book polls={len(B)} spot polls={len(S)} markets seen={B['ticker'].nunique()} span={(B['t'].max()-B['t'].min())/3600:.2f}h "
          f"median request latency={B['lat'].median()*1000:.0f}ms median poll gap={B.groupby('ticker')['t'].diff().median():.2f}s")
    B["g"] = (B["t"] / GRID).round().astype("int64")
    S["g"] = (S["t"] / GRID).round().astype("int64")
    B = B.drop_duplicates(["ticker", "g"], keep="last")
    S = S.drop_duplicates(["product", "g"], keep="last")
    two = B[(B["bid"] > 0) & (B["ask"] < 1)]
    print("\n== A. size at the touch (contracts), two-sided books only")
    for s, g in two.groupby("series"):
        print(f"  {s:10s} spread median {100*(g['ask']-g['bid']).median():.1f}c mean {100*(g['ask']-g['bid']).mean():.2f}c | best bid size median {g['bid_sz'].median():8.0f} | best ask size median {g['ask_sz'].median():8.0f} | "
              f"10th pct ask size {g['ask_sz'].quantile(.1):6.0f} | depth within 2c: bid {g['depth_bid2c'].median():8.0f} ask {g['depth_ask2c'].median():8.0f}")

    # outcomes via strike chain
    info = pd.DataFrame.from_dict(mk, orient="index").reset_index().rename(columns={"index": "ticker"})
    info = info.sort_values(["series", "open"])
    info["next_strike"] = info.groupby("series")["strike"].shift(-1)
    info["next_open"] = info.groupby("series")["open"].shift(-1)
    info["y"] = np.where((info["next_open"] - info["close"]).abs() < 5, (info["next_strike"] >= info["strike"]).astype(float), np.nan)
    B = B.merge(info[["ticker", "open", "close", "strike", "y"]], on="ticker", how="left")
    B["product"] = B["series"].map(series_map)
    D = B.merge(S[["product", "g", "smid"]], on=["product", "g"], how="left").sort_values(["series", "g"])
    D["smid"] = D.groupby("series")["smid"].ffill(limit=3)
    D["mid"] = (D["bid"] + D["ask"]) / 2
    D["tau"] = D["close"] - D["t"]

    print("\n== B. lead-lag: response of the Kalshi mid to a spot move (regression of 2 s Kalshi mid change on lagged 2 s spot returns, in the middle of the window, prices 20-80c)")
    for s, g in D.groupby("series"):
        g = g[(g["mid"] > 0.2) & (g["mid"] < 0.8) & (g["tau"] > 90) & (g["bid"] > 0) & (g["ask"] < 1)].copy()
        if len(g) < 2000:
            continue
        g = g.set_index("g")
        full = D[D["series"] == s].drop_duplicates("g").set_index("g")
        r = np.log(full["smid"]).diff()
        dm = g["mid"].shift(-1) - g["mid"]
        same = g["ticker"].shift(-1) == g["ticker"]
        X = pd.concat({f"L{k}": r.shift(k - 1).reindex(g.index) for k in range(0, 9)}, axis=1)   # L0: spot move over the same 2 s; L1: previous 2 s ...
        ok = same & dm.notna() & X.notna().all(axis=1)
        if ok.sum() < 1500:
            continue
        Xv, yv = X[ok].values, dm[ok].values
        scale = np.std(Xv[:, 1])
        beta = np.linalg.lstsq(np.c_[np.ones(len(Xv)), Xv / scale], yv, rcond=None)[0][1:]
        cum = np.cumsum(beta)
        tot = cum[-1] if abs(cum[-1]) > 1e-9 else np.nan
        print(f"  {s:10s} n={ok.sum():6d} share of total response arriving: same 2s {beta[0]/tot*100:5.1f}% | by +2s {cum[1]/tot*100:5.1f}% | +4s {cum[2]/tot*100:5.1f}% | +8s {cum[4]/tot*100:5.1f}% | +16s 100%  (total {tot*100:.2f}c per 1-sd 2s spot move)")

    print("\n== C. model-vs-quote edge and its decay with execution delay")
    out = []
    for s, g in D.groupby("series"):
        full = g.drop_duplicates("g").set_index("g").sort_index()
        lr = np.log(full["smid"]).diff()
        sig2s = lr.rolling(450, min_periods=150).std()                    # 15 min of 2 s returns
        sm = full["smid"]
        for tk, m in g.groupby("ticker"):
            if not np.isfinite(m["y"].iloc[0]) or not m["strike"].iloc[0]:
                continue
            o, c, K = m["open"].iloc[0], m["close"].iloc[0], float(m["strike"].iloc[0])
            pre = sm[(sm.index * GRID >= o - 60) & (sm.index * GRID < o)]
            if len(pre) < 15:
                continue
            basis = K / pre.mean()                                       # index-vs-Coinbase level adjustment at the strike-setting minute
            m = m[(m["tau"] > 75) & (m["t"] > o + 20)].copy()
            sg = sig2s.reindex(m["g"]).values
            tau_eff = np.maximum(m["tau"].values - 40.0, 1.0)
            z = np.log(m["smid"].values * basis / K) / (np.maximum(sg, 1e-7) * np.sqrt(tau_eff / GRID))
            m["p"] = norm.cdf(z)
            m = m[np.isfinite(m["p"])]
            fut = g[g["ticker"] == tk].set_index("g")
            for d in (0, 1, 2, 3, 5, 10, 15, 30):                         # delay in grid steps (x2 s)
                m[f"ask_{d}"] = fut["ask"].reindex(m["g"] + d).values
                m[f"bid_{d}"] = fut["bid"].reindex(m["g"] + d).values
                m[f"asz_{d}"] = fut["ask_sz"].reindex(m["g"] + d).values
                m[f"bsz_{d}"] = fut["bid_sz"].reindex(m["g"] + d).values
            out.append(m)
    if not out:
        print("  not enough data")
        return
    M = pd.concat(out, ignore_index=True)
    M = M[(M["bid"] > 0) & (M["ask"] < 1)]
    print(f"  model rows={len(M)} markets={M['ticker'].nunique()}  Brier: model {np.mean((M['p']-M['y'])**2):.4f} vs Kalshi mid {np.mean((M['mid']-M['y'])**2):.4f}")
    for th in (0.03, 0.05, 0.08, 0.12):
        e_yes = M["p"] - M["ask"] - fee(M["ask"])
        e_no = (1 - M["p"]) - (1 - M["bid"]) - fee(1 - M["bid"])
        side = np.where((e_yes > th) & (e_yes >= e_no), 1, np.where(e_no > th, -1, 0))
        X = M[side != 0].copy()
        sd = side[side != 0]
        if len(X) < 30:
            continue
        line = f"  thr={th:.2f} signals={len(X)} in {X['ticker'].nunique()} markets | "
        for d in (0, 1, 2, 3, 5, 10, 15, 30):
            a = np.where(sd == 1, X[f"ask_{d}"], 1 - X[f"bid_{d}"])
            sz = np.where(sd == 1, X[f"asz_{d}"], X[f"bsz_{d}"])
            ok = np.isfinite(a) & (a < 1) & (a > 0)
            win = np.where(sd == 1, X["y"], 1 - X["y"])
            pnl = win[ok] - a[ok] - fee(a[ok])
            # market-clustered standard error
            df = pd.DataFrame({"p": pnl, "k": X["ticker"].values[ok]})
            gm = df.groupby("k")["p"].agg(["sum", "count"])
            se = np.sqrt(((gm["sum"] - gm["count"] * df["p"].mean()) ** 2).sum()) / max(len(df), 1)
            line += f"+{int(d*GRID)}s: {pnl.mean()*100:+.1f}c(se {se*100:.1f}, sz {np.nanmedian(sz[ok]):.0f}) "
        print(line)
        if th == 0.05:
            print("     by series (delay +4s): " + ", ".join(
                f"{s[2:-3]}:{len(g)}/{((np.where(sd[X['series'].values==s]==1, g['y'], 1-g['y']) - np.where(sd[X['series'].values==s]==1, g['ask_2'], 1-g['bid_2']) )).mean()*100:+.1f}" for s, g in X.groupby("series")))


if __name__ == "__main__":
    main()
