#!/usr/bin/env python3
"""E009 — maker simulation on the live capture, with real queue sizes.

Uses the order book captured every 2 s (live_capture.py) and the public trade
prints for the same markets. Every `step` seconds, in every market, we imagine
two resting orders of `size` contracts that live `life` seconds:
  BUY  YES at the best bid  (joining the back of the displayed queue)
  SELL YES at the best ask  (same)
and, when the spread is at least two ticks, the "improve" variants one tick
inside the spread (front of the queue).
Fill rule (conservative: nobody ahead of us ever cancels): filled when a taker
print goes strictly through our price, or when taker volume printed at our
price after we posted exceeds queue-ahead + our size.
P&L per filled contract, no fee (maker fee is zero on these series):
  to settlement:  outcome - price (buy) / price - outcome (sell)
  markout:        mid some seconds after the fill vs our price (low-noise view of adverse selection)

Usage: e009_live_maker.py <live_run_dir> <trades_run_dir> [step=10] [life=30] [size=10]
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e007_live_leadlag import load  # noqa: E402


def main():
    lrun, trun = sys.argv[1], sys.argv[2]
    step = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
    life = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
    size = float(sys.argv[5]) if len(sys.argv) > 5 else 10.0
    B, S, mk = load(lrun)
    info = pd.DataFrame.from_dict(mk, orient="index").reset_index().rename(columns={"index": "ticker"}).sort_values(["series", "open"])
    info["next_strike"] = info.groupby("series")["strike"].shift(-1)
    info["next_open"] = info.groupby("series")["open"].shift(-1)
    info["y"] = np.where((info["next_open"] - info["close"]).abs() < 5, (info["next_strike"] >= info["strike"]).astype(float), np.nan)
    info = info.set_index("ticker")
    tr = pd.read_csv(f"{trun}/trades.csv.gz")
    tr["ts"] = (pd.to_datetime(tr["created_time"], utc=True, format="ISO8601") - pd.Timestamp(0, tz="UTC")) / pd.Timedelta("1s")
    tr = tr.drop_duplicates(["ticker", "created_time", "yes_price", "count", "taker_side"]).sort_values(["ticker", "ts"])
    trades = {k: (g["ts"].values, g["yes_price"].values.astype(float), (g["taker_side"] == "yes").values, g["count"].values.astype(float)) for k, g in tr.groupby("ticker")}
    print(f"markets with book={B['ticker'].nunique()} with trades={len(trades)}; trades={len(tr)}")
    rows = []
    for tk, g in B.groupby("ticker"):
        if tk not in trades or tk not in info.index or not np.isfinite(info.loc[tk, "y"]):
            continue
        y, close, opn = info.loc[tk, "y"], info.loc[tk, "close"], info.loc[tk, "open"]
        g = g.sort_values("t")
        bt, bbid, bask, bbs, bas = g["t"].values, g["bid"].values, g["ask"].values, g["bid_sz"].values, g["ask_sz"].values
        mid = (bbid + bask) / 2
        ts, px, isyes, cnt = trades[tk]
        t = opn + 30
        while t < close - 90:
            i = np.searchsorted(bt, t, side="right") - 1
            t += step
            if i < 0 or t - step - bt[i] > 4:
                continue
            b, a, qb, qa = bbid[i], bask[i], bbs[i], bas[i]
            if not (b > 0 and a < 1 and a > b):
                continue
            t0 = bt[i] + 0.5
            j0, j1 = np.searchsorted(ts, t0), np.searchsorted(ts, t0 + life)
            tick = 0.001 if (b < 0.10 or a > 0.90) else 0.01
            wide = (a - b) >= 2 * tick - 1e-9
            for side, price, queue, variant in (("buy", b, qb, "join"), ("sell", a, qa, "join"),
                                                ("buy", b + tick, 0.0, "improve"), ("sell", a - tick, 0.0, "improve")):
                if variant == "improve" and not wide:
                    continue
                fill_t = np.nan
                if j1 > j0:
                    p_, s_, c_, t_ = px[j0:j1], isyes[j0:j1], cnt[j0:j1], ts[j0:j1]
                    if side == "buy":            # filled by takers selling YES
                        m = ~s_
                        thru = m & (p_ < price - 1e-9)
                        at = m & (np.abs(p_ - price) < 1e-9)
                    else:                        # filled by takers buying YES
                        m = s_
                        thru = m & (p_ > price + 1e-9)
                        at = m & (np.abs(p_ - price) < 1e-9)
                    cum = np.cumsum(np.where(at, c_, 0.0))
                    hit = thru | (at & (cum >= queue + size))
                    if hit.any():
                        fill_t = t_[np.argmax(hit)]
                rec = {"ticker": tk, "series": info.loc[tk, "series"], "t": bt[i], "tau": close - bt[i], "side": side, "variant": variant,
                       "price": price, "mid0": (a + b) / 2, "spread": a - b, "queue": queue, "y": y, "filled": np.isfinite(fill_t)}
                if np.isfinite(fill_t):
                    sgn = 1 if side == "buy" else -1
                    rec["pnl_settle"] = sgn * (y - price)
                    for h in (10, 60):
                        k = np.searchsorted(bt, fill_t + h, side="right") - 1
                        ok = k >= 0 and (fill_t + h - bt[k]) < 6 and bbid[k] > 0 and bask[k] < 1
                        rec[f"mo{h}"] = sgn * (mid[k] - price) if ok else np.nan
                rows.append(rec)
    R = pd.DataFrame(rows)
    print(f"orders posted={len(R)} in {R['ticker'].nunique()} markets; order size {size:.0f}, life {life:.0f}s, every {step:.0f}s")

    def line(g):
        f = g[g["filled"]]
        if len(f) < 20:
            return f"posted={len(g):6d} fills={len(f):5d}"
        gm = f.groupby("ticker")["pnl_settle"].agg(["sum", "count"])
        se = np.sqrt(((gm["sum"] - gm["count"] * f["pnl_settle"].mean()) ** 2).sum()) / len(f)
        def mo(c):
            x = f.dropna(subset=[c])
            gm2 = x.groupby("ticker")[c].agg(["sum", "count"])
            se2 = np.sqrt(((gm2["sum"] - gm2["count"] * x[c].mean()) ** 2).sum()) / max(len(x), 1)
            return f"{x[c].mean()*100:+5.2f}c (se {se2*100:.2f})"
        return (f"posted={len(g):6d} fills={len(f):5d} ({len(f)/len(g)*100:4.1f}%) | markout 10s {mo('mo10')} | 60s {mo('mo60')} | "
                f"to settlement {f['pnl_settle'].mean()*100:+5.2f}c (se {se*100:.2f}) | half-spread earned vs mid {((f['mid0']-f['price'])*np.where(f['side']=='buy',1,-1)).mean()*100:+.2f}c")

    for variant in ("join", "improve"):
        V = R[R["variant"] == variant]
        print(f"\n== {variant.upper()} the best quote")
        print("  ALL          ", line(V))
        for s, g in V.groupby("series"):
            print(f"  {s:13s}", line(g))
        V = V.assign(pb=pd.cut(V["mid0"], [0, .1, .3, .7, .9, 1]), tb=pd.cut(V["tau"], [0, 240, 480, 900], labels=["<4 min left", "4-8", ">8"]))
        for k, g in V.groupby("pb", observed=True):
            print(f"  price {str(k):11s}", line(g))
        for k, g in V.groupby("tb", observed=True):
            print(f"  {str(k):13s}", line(g))
        for k, g in V.groupby("side"):
            print(f"  {k:13s}", line(g))


if __name__ == "__main__":
    main()
