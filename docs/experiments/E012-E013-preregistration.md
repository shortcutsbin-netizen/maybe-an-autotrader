# Pre-registration — E012 (frozen dislocation rule) and E013 (frozen weather maker rule) on unseen periods

Written and committed **before** any of the data below was pulled. Nothing here may be changed after the results are seen; any later variant is a new experiment with its own label.

## Why this exists

The user declined a multi-week forward paper test (2026-11-20) and asked for larger samples from recent history instead. The repository is now public, so GitHub Actions minutes are no longer a constraint. The two leads from round 2 are re-tested, unchanged, on periods neither was fitted, tuned or simulated on.

## E012 — dislocation rule (15-minute crypto)

**Rule (identical to E010, commit `9ac0a11`).** Logistic stack (`e003_s1_model.py` EXT + MKT features) fitted only on `full-001` days 2026-09-13 → 2026-10-11; at each minute end, buy the side whose model probability exceeds its ask plus the taker fee by more than 8c; hold to settlement. Code: `research/analysis/e012_frozen_new_periods.py` (its `fit_frozen` asserts the fit window).

**New periods.**

| Label | Markets closing | Source | Status before this commit |
|---|---|---|---|
| P (pre) | 2026-06-01 → 2026-09-12 | `/historical/*` endpoints, nine active coins | never pulled |
| Q (post) | 2026-11-13 → 2026-11-21 04:45Z | live endpoints | did not exist when E010 ran |

Signals in markets already used by the E010 test split are excluded from Q.

**Fill models (all reported; F1 is primary).**

- F1 — volume-weighted price of same-side taker prints in (t+1 s, t+6 s] at or below quote + 2c (E010's model).
- F2 — "last in line": the *highest* same-side print price in that window at or below the limit, and only when at least 20 contracts printed there.
- F3 — "slow": the first same-side print at or after t + 3 s (within 15 s), no price limit.

**Pass** (all must hold on P ∪ Q):

1. F1 mean P&L per contract > 0 with the day-bootstrap 95% CI lower bound > 0.
2. F2 mean > 0 and F3 mean > 0.
3. F1 mean > 0 in at least two-thirds of calendar months that have ≥ 100 F1 fills.

**Fail:** F1 CI includes zero, or criterion 2 fails. **Inconclusive:** passes overall but only because of one month or one coin (reported either way).

## E013 — weather favorite-side maker rule

**Rule W.** Every 30 minutes, for every daily-high bracket (7 cities) with a two-sided quote, until 30 minutes before close: if YES mid ≥ 0.90 rest a buy-YES order at the best bid for 30 minutes; if YES mid ≤ 0.20 rest a sell-YES order at the best ask for 30 minutes. No fee. Fill rules from `e008_maker_sim.simulate`; **"through" (a print strictly beyond our price) is primary**. Code: `research/analysis/e013_weather_maker_frozen.py`.

**Periods (by climate day).**

| Label | Days | Quotes previously used for | Maker simulation previously run? |
|---|---|---|---|
| A | 2026-05-01 → 2026-09-05 | E004/E004b calibration (seen) | no — trade prints never pulled |
| B | 2026-10-30 → 2026-11-12 | E004 data, but this is E008's unopened test split | no |
| C | 2026-11-13 → 2026-11-20 | never pulled | no |

**Pass:** combined (both legs) through-fill P&L per contract on B ∪ C > 0 with CI lower bound > 0, **and** both legs' through-fill means > 0 on A. **Fail** otherwise. Also reported: return on capital, worst day, drawdown, per city.

## Not pre-registered (exploratory, labelled as such when reported)

- E014: sports in-game Kalshi price vs ESPN's published win probability (user asked that sports be dropped only if absolutely not feasible).
- Any breakdown beyond those listed above.
