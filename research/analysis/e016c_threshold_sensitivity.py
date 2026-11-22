#!/usr/bin/env python3
"""E016c - sensitivity of S1-D to the entry threshold (post-hoc, NOT a re-tuning of the frozen rule).

Signals from the frozen model at a 4c threshold on P (Jun 1 - Sep 12) and Q (Nov 13 - 21), the same periods as
the pre-registered E012 test. Each signal is evaluated with E012's F1 fill (taker) and with E016b's maker entry
(rest 1 tick inside the ask for 15 s, 'through' fills), then split by edge band: 4-6c, 6-8c, 8-12c, >12c.
The 8c rule's result is already fixed (E012); this only shows what lower thresholds would add.

usage: e016c_threshold_sensitivity.py <sig_csv> <trade_dirs> [<sig_csv> <trade_dirs> ...]
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import e012_frozen_new_periods as E12  # noqa: E402
from e016b_dislocation_maker_entry import run as maker_run  # noqa: E402


def main():
    a = sys.argv[1:]
    parts = []
    for i in range(0, len(a), 2):
        sig_csv, dirs = a[i], a[i + 1]
        full = pd.read_csv(sig_csv)
        tk = sorted(full.ticker.unique())
        nch = max(1, len(tk) // 1500)                    # chunk by market so the print data fits in memory
        for j in range(nch):
            keep = set(tk[j::nch])
            s = full[full.ticker.isin(keep)].reset_index(drop=True)
            cf = f"/tmp/e016c_chunk_{i}_{j}.csv"
            s.to_csv(cf, index=False)
            E12.evaluate(cf, dirs)
            ev = pd.read_csv(cf.replace(".csv", "_eval.csv"))
            mk = maker_run(cf, dirs)
            ask_y, ask_n = s.ask_c, 1 - s.bid_c
            edge = np.where(s.side == 1, s.p - ask_y - E12.fee(ask_y), (1 - s.p) - ask_n - E12.fee(ask_n))
            parts.append(ev.assign(edge=edge, maker=mk["through_k1_w15"].values, period=sig_csv.rsplit("/", 1)[-1]))
    d = pd.concat(parts, ignore_index=True)
    d["band"] = pd.cut(d.edge, [0.04, 0.06, 0.08, 0.12, 1.0], labels=["4-6c", "6-8c", "8-12c", ">12c"])
    print(f"\n{len(d)} signals, {d.day.nunique()} days; trade data for {d.has_trades.mean():.1%}")
    print(f"{'band':6s} {'signals':>8s} {'/day':>6s} {'F1 fill%':>8s} {'F1 P&L':>8s} {'F1 CI':>16s} {'maker fill%':>11s} {'maker/fill':>10s} {'maker CI':>16s} {'maker/signal':>12s}")
    for b, g in d.groupby("band", observed=True):
        f = g.dropna(subset=["f1"])
        lo, hi = E12.ci(f.pnl_f1.values, f.day.values)
        m = g.dropna(subset=["maker"])
        mlo, mhi = E12.ci(m.maker.values, m.day.values)
        print(f"{b:6s} {len(g):8d} {len(g) / d.day.nunique():6.1f} {len(f) / len(g) * 100:8.1f} {f.pnl_f1.mean() * 100:+7.2f}c "
              f"[{lo * 100:+6.2f},{hi * 100:+6.2f}] {len(m) / len(g) * 100:11.1f} {m.maker.mean() * 100:+9.2f}c [{mlo * 100:+6.2f},{mhi * 100:+6.2f}] "
              f"{g.maker.fillna(0).mean() * 100:+11.2f}c")
    for b, g in d.groupby("band", observed=True):
        f = g.dropna(subset=["f1"])
        print(f"  {b} F1 by series:", {k[2:-3]: (len(x), round(x.pnl_f1.mean() * 100, 1)) for k, x in f.groupby("series")})
    for per, g in d.groupby("period"):
        g = g[g.edge <= 0.08]
        f = g.dropna(subset=["f1"])
        print(f"  {per}: 4-8c band only: F1 n={len(f)} {f.pnl_f1.mean() * 100:+.2f}c; maker per signal {g.maker.fillna(0).mean() * 100:+.2f}c")


if __name__ == "__main__":
    main()
