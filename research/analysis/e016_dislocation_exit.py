#!/usr/bin/env python3
"""E016 — dislocation rule with an early exit instead of holding to settlement.

E006 showed that after a signal the price on our side climbs ~7c within 30 s (the dislocation
reverts). Holding to settlement keeps the full binary risk; selling the rebound may keep most of
the edge with far less variance and free capital sooner.

Entry: exactly E012's F1 (VWAP of same-side taker prints in (t+1, t+6] at <= quote + 2c).
Exits (taker, paying the fee again on the exit price):
  hold            : to settlement
  time h          : first opposite-side print at or after t+h (h = 30, 60, 120, 300 s); hold if none before close-20 s
  target x        : first opposite-side print at or after t+6 s whose price >= entry + x; else hold
An opposite-side print is a taker trading the other way: for a YES position, a taker buying NO
(hitting YES bids) at yes_price; the YES we sell receives that yes_price.

Split (decided before running): choose on 'early' = P (Jun 1 - Sep 12) + threshold days + validation
(Oct 12-31); report on 'late' = E010 test split + Q (Nov 1-21) once.
Usage: e016_dislocation_exit.py <early|late>
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from e012_frozen_new_periods import load_trades, ci, fee  # noqa: E402

H = "/home/claude"
W = f"{H}/data/wt/runs"
SETS = {
    "early": [("e012_sig_P8_eval.csv", f"{W}/trades-p0,{W}/trades-p1,{W}/trades-p2"), ("e012_sig_P_sol_eval.csv", f"{W}/trades-psol"),
              ("e010_sig_thr_eval.csv", f"{W}/trades-003"), ("e010_sig_val_eval.csv", f"{W}/trades-003")],
    "late": [("e010_sig_test_eval.csv", f"{W}/trades-005"), ("e012_sig_Q_eval.csv", f"{W}/trades-006")],
}
SIG = {"e012_sig_P8_eval.csv": "e012_sig_P8.csv", "e012_sig_P_sol_eval.csv": "e012_sig_P_sol.csv", "e010_sig_thr_eval.csv": "e010_sig_thr.csv",
       "e010_sig_val_eval.csv": "e010_sig_val.csv", "e010_sig_test_eval.csv": "e010_sig_test.csv", "e012_sig_Q_eval.csv": "e012_sig_Q.csv"}


def main():
    which = sys.argv[1]
    rows = []
    for ev_name, tdirs in SETS[which]:
        ev = pd.read_csv(f"{H}/{ev_name}")
        sg = pd.read_csv(f"{H}/{SIG[ev_name]}")[["ticker", "end_period_ts", "side"]].rename(columns={"end_period_ts": "t"})
        ev = ev.merge(sg, on=["ticker", "t"], how="left").dropna(subset=["f1"])
        by = load_trades(tdirs, set(ev["ticker"]))
        for r in ev.itertuples():
            g = by.get(r.ticker)
            if g is None:
                continue
            close = r.t + 60 * r.ml
            opp = g[g["taker_side"] == ("no" if r.side == 1 else "yes")]
            ts = opp["ts"].values
            px = (opp["yes_price"] if r.side == 1 else opp["no_price"]).values.astype(float)   # price our side is sold at
            rec = {"day": r.day, "series": r.series, "entry": r.f1, "hold": r.win - r.f1 - fee(r.f1)}
            for h in (30, 60, 120, 300):
                j = np.searchsorted(ts, r.t + h)
                if j < len(ts) and ts[j] < close - 20:
                    x = px[j]
                    rec[f"t{h}"] = x - r.f1 - fee(r.f1) - fee(x)
                    rec[f"t{h}_secs"] = ts[j] - r.t
                else:
                    rec[f"t{h}"] = rec["hold"]
                    rec[f"t{h}_secs"] = close - r.t
            j0 = np.searchsorted(ts, r.t + 6)
            for tg in (0.03, 0.05, 0.10, 0.15):
                hit = np.nonzero((px[j0:] >= r.f1 + tg) & (ts[j0:] < close - 20))[0]
                if len(hit):
                    x = px[j0 + hit[0]]
                    rec[f"x{int(tg*100)}"] = x - r.f1 - fee(r.f1) - fee(x)
                    rec[f"x{int(tg*100)}_hit"] = 1
                    rec[f"x{int(tg*100)}_secs"] = ts[j0 + hit[0]] - r.t
                else:
                    rec[f"x{int(tg*100)}"] = rec["hold"]
                    rec[f"x{int(tg*100)}_hit"] = 0
                    rec[f"x{int(tg*100)}_secs"] = close - r.t
            rows.append(rec)
    x = pd.DataFrame(rows)
    print(f"set={which} fills={len(x)} days={x['day'].nunique()}  [cents per contract; 95% CI by day; sd = per-trade standard deviation]")
    for c in ["hold", "t30", "t60", "t120", "t300", "x3", "x5", "x10", "x15"]:
        lo, hi = ci(x[c].values, x["day"].values)
        extra = ""
        if c.startswith("x"):
            extra = f" target hit {x[c + '_hit'].mean()*100:.0f}%, median time to exit {x[c + '_secs'].median():.0f}s"
        elif c.startswith("t"):
            extra = f" median time in trade {x[c + '_secs'].median():.0f}s"
        daily = x.groupby("day")[c].sum()
        print(f"  {c:5s} mean {x[c].mean()*100:+6.2f} [{lo*100:+.2f},{hi*100:+.2f}] sd {x[c].std()*100:5.1f} win {np.mean(x[c] > 0)*100:4.0f}% "
              f"worst day (1 contract/fill) {daily.min()*100:+.0f}c  Sharpe-per-trade {x[c].mean()/x[c].std():.3f}{extra}")


if __name__ == "__main__":
    main()
