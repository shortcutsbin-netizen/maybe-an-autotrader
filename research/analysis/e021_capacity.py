#!/usr/bin/env python3
"""E021 - capacity and return on capital of S1-D (post-hoc, from E016c evaluation chunks).

For each filled signal (F1 model, BTC excluded), our size = min(X, share * printed fillable volume).
P&L per day and peak capital open in any 15-minute window, for X contracts per signal and a share of
printed volume we would actually win (1.0, 0.5, 0.25). Inputs: /tmp/e016c_chunk_*.csv and *_eval.csv
written by e016c_threshold_sensitivity.py.
"""
import glob

import numpy as np
import pandas as pd

fee = lambda p: 0.07 * p * (1 - p)
rows = []
for f in sorted(glob.glob('/tmp/e016c_chunk_*_eval.csv')):
    s = pd.read_csv(f.replace('_eval.csv', '.csv')); e = pd.read_csv(f)
    ay, an = s.ask_c, 1 - s.bid_c
    e['edge'] = np.where(s.side == 1, s.p - ay - fee(ay), (1 - s.p) - an - fee(an))
    e['open_ts'] = (e.t // 900) * 900
    rows.append(e)
d = pd.concat(rows); d = d[d.series != 'KXBTC15M']
days = d.day.nunique()
f = d.dropna(subset=['f1']).copy(); f['cost'] = f.f1 + fee(f.f1)
for name, m in (('primary >=8c', f.edge > 0.08), ('all >=4c', f.edge > 0.04)):
    g = f[m]
    print(f'{name}: {len(g)} fills ({len(g)/days:.1f}/day), {g.pnl_f1.mean()*100:.2f}c/contract on {g.cost.mean()*100:.1f}c '
          f'({g.pnl_f1.mean()/g.cost.mean()*100:.1f}% per trade); median fillable volume {g.vol.median():.0f}')
    for share in (1.0, 0.5, 0.25):
        out = []
        for X in (1, 5, 10, 25, 50, 100, 250):
            q = np.minimum(X, share * g.vol)
            pnl = (q * g.pnl_f1).groupby(g.day).sum()
            cap = (q * g.cost).groupby([g.day, g.open_ts]).sum().groupby(level=0).max()
            out.append(f'X={X}: ${pnl.mean():.2f}/day cap ${cap.mean():.0f} days+ {np.mean(pnl > 0):.0%}')
        print(f'  share {share}: ' + ' | '.join(out))
    print('  by month:', g.groupby(g.day.str[:7]).pnl_f1.agg(['count', 'mean']).round(4).to_dict('index'))
