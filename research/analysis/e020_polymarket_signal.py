#!/usr/bin/env python3
"""E020 - Polymarket's 15-minute up/down price as an extra input to the S1-D stack.

Polymarket windows start on the same quarter hours as Kalshi's 15-minute markets but resolve on Chainlink's
60-second TWAP stream (window-end TWAP vs price at the window start), so the two contracts are close cousins,
not identical. Polymarket price history (CLOB prices-history, ~1 point a minute) is aligned as-of each Kalshi
minute end t using only points stamped <= t - 5 s.

1. Forecast skill: Brier of the Kalshi mid, the Polymarket price, and a logistic blend (fitted on the S1-D fit
   window 2026-09-13..10-11), read on every other day.
2. Augmented S1-D: refit the S1-D logistic with the Polymarket logit added (same fit window, same C) and
   compare with the frozen model on out-of-fit days: Brier, number of > 8c signals, and F1 P&L where public
   prints exist (only markets that already had prints pulled).

usage: e020_polymarket_signal.py <fit_run> <poly_runs_comma> <trade_dirs_comma> <run> [<run> ...]
"""
import glob
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import e012_frozen_new_periods as E12  # noqa: E402

COIN = {"KXBTC15M": "btc", "KXETH15M": "eth", "KXSOL15M": "sol", "KXXRP15M": "xrp", "KXDOGE15M": "doge",
        "KXBNB15M": "bnb", "KXHYPE15M": "hype"}


def load_poly(runs):
    out = {}
    for r in runs.split(","):
        for f in glob.glob(f"{r}/poly/*_prices.csv.gz"):
            coin = f.rsplit("/", 1)[-1].split("_")[0]
            p = pd.read_csv(f).dropna()
            if len(p):
                out.setdefault(coin, []).append(p)
    return {k: pd.concat(v).drop_duplicates(["window_start", "t"]).sort_values("t") for k, v in out.items()}


def attach(d, poly):
    d = d.copy()
    d["poly"] = np.nan
    for s, coin in COIN.items():
        if coin not in poly:
            continue
        m = d["series"] == s
        if not m.any():
            continue
        p = poly[coin]
        sub = d.loc[m, ["end_period_ts", "open_ts"]].reset_index()
        sub["key"] = sub["end_period_ts"] - 5
        sub = sub.sort_values("key")
        pp = p.rename(columns={"t": "key"})[["key", "window_start", "p_up"]].sort_values("key")
        j = pd.merge_asof(sub, pp, on="key", direction="backward")
        j = j[j["window_start"] == j["open_ts"]]          # same window only
        d.loc[j["index"].values, "poly"] = j["p_up"].values
    return d


def main():
    fit_run, poly_runs, tdirs, runs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
    poly = load_poly(poly_runs)
    print("polymarket coins:", {k: len(v) for k, v in poly.items()})
    m, E = E12.fit_frozen(fit_run)
    frames = []
    for r in runs:
        x = E.build(r).dropna(subset=E.EXT + E.MKT + ["y"])
        x = attach(x, poly)
        frames.append(x)
        print(r, len(x), "with poly price", round(float(x.poly.notna().mean()), 3))
    d = pd.concat(frames, ignore_index=True).drop_duplicates(["ticker", "end_period_ts"])
    d = d[d.poly.notna()].copy()
    d["lpoly"] = np.log(d.poly.clip(.01, .99) / (1 - d.poly.clip(.01, .99)))
    d["gap"] = d.poly - d["mid"]
    d["p_frozen"] = m.predict_proba(d[E.EXT + E.MKT].values)[:, 1]
    fitm = (d.day >= "2026-09-13") & (d.day <= "2026-10-11")
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    F = E.EXT + E.MKT + ["lpoly"]
    aug = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300)).fit(d.loc[fitm, F].values, d.loc[fitm, "y"].values)
    bl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300)).fit(d.loc[fitm, ["logit_mid", "lpoly"]].values, d.loc[fitm, "y"].values)
    print("augmented-model coefficient on lpoly (standardised):", round(float(aug[-1].coef_[0][-1]), 3),
          "| blend coefficients [kalshi, poly]:", np.round(bl[-1].coef_[0], 3))
    d["p_aug"] = aug.predict_proba(d[F].values)[:, 1]
    d["p_blend"] = bl.predict_proba(d[["logit_mid", "lpoly"]].values)[:, 1]
    o = d[~fitm].copy()
    o["period"] = np.where(o.day < "2026-09-13", "P (Jun-Sep12)", np.where(o.day <= "2026-11-12", "Oct12-Nov12", "Q (Nov13-21)"))
    print(f"\nout-of-fit rows with a Polymarket price: {len(o)} ({o.day.nunique()} days)")
    for per, g in o.groupby("period"):
        b = lambda c: np.mean((g[c] - g.y) ** 2)
        print(f"  {per}: n={len(g)}  Brier kalshi mid {b('mid'):.5f}  poly {b('poly'):.5f}  blend {b('p_blend'):.5f}  "
              f"frozen S1-D {b('p_frozen'):.5f}  augmented {b('p_aug'):.5f};  |poly - mid| mean {g.gap.abs().mean() * 100:.2f}c")
    print("  by coin (all out-of-fit):")
    for s, g in o.groupby("series"):
        b = lambda c: np.mean((g[c] - g.y) ** 2)
        print(f"    {s}: n={len(g)} mid {b('mid'):.5f} poly {b('poly'):.5f} frozen {b('p_frozen'):.5f} aug {b('p_aug'):.5f}")
    # signals: frozen vs augmented, 8c threshold
    for nm in ("p_frozen", "p_aug"):
        ey = o[nm] - o.ask_c - E12.fee(o.ask_c)
        en = (1 - o[nm]) - (1 - o.bid_c) - E12.fee(1 - o.bid_c)
        o[f"side_{nm}"] = np.where((ey > .08) & (ey >= en), 1, np.where(en > .08, -1, 0))
    both = (o.side_p_frozen != 0) & (o.side_p_aug == o.side_p_frozen)
    only_f = (o.side_p_frozen != 0) & (o.side_p_aug != o.side_p_frozen)
    only_a = (o.side_p_aug != 0) & (o.side_p_aug != o.side_p_frozen)
    print(f"\n  >8c signals: frozen {int((o.side_p_frozen != 0).sum())}, augmented {int((o.side_p_aug != 0).sum())}; "
          f"agree {int(both.sum())}, frozen-only {int(only_f.sum())}, augmented-only {int(only_a.sum())}")
    for lab, msk, col in (("agree", both, "side_p_frozen"), ("frozen-only", only_f, "side_p_frozen"), ("augmented-only", only_a, "side_p_aug")):
        s = o[msk].copy()
        if not len(s):
            continue
        s["side"] = s[col]
        s["p"] = s["p_aug"] if col == "side_p_aug" else s["p_frozen"]
        f = "/tmp/e020_sig_" + lab + ".csv"
        s[["ticker", "series", "day", "end_period_ts", "minutes_left", "side", "p", "bid_c", "ask_c", "y", "spread", "z", "mid"]].to_csv(f, index=False)
        print(f"  --- {lab} ({len(s)} signals) F1 evaluation on markets with prints:")
        E12.evaluate(f, tdirs)


if __name__ == "__main__":
    main()
