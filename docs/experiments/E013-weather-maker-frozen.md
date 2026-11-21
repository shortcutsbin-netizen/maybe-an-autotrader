# E013 — Frozen weather favorite-side maker rule on unseen periods

| | |
|---|---|
| **Date** | 2026-11-21 |
| **Pre-registration** | `E012-E013-preregistration.md`, commit `457f237` (before any data below was pulled) |
| **Code** | `research/analysis/e013_weather_maker_frozen.py`; output `output/E013_weather_maker.txt` |
| **Data** | Quotes: `wx-002` (A), `wx-001` (B), `wx-003` (C). Trade prints: `wx-trades-hist-a/b/c` (A, 4.9M prints), `wx-trades-002` (B), `wx-trades-005` (C) |
| **Verdict** | **FAIL. The weather maker lead (S4-M) is rejected.** |

## Rule W (frozen)

Every 30 minutes, for each daily-high bracket with a two-sided quote: rest a buy-YES order at the bid when YES mid ≥ 0.90, or a sell-YES order at the ask when YES mid ≤ 0.20, for 30 minutes. No fee. Primary fill rule "through" (a print strictly beyond our price).

## Results (cents per filled contract, 95% CI by day)

| Period | Days | Buy YES ≥ 90c | Sell YES ≤ 20c | Combined | Days positive |
|---|---|---|---|---|---|
| A — 2026-05-01 → 09-05 | 128 | **+2.54** [+0.99, +3.94], 1,661 fills | +0.83 [−0.18, +1.84], 34,573 fills | +0.91 [−0.09, +1.89] | 83/128 |
| B — 10-30 → 11-12 (E008's unopened test split) | 14 | +0.35 [−8.47, +5.70] | −3.64 [−9.84, +2.00] | −3.31 [−9.57, +2.22] | 7/14 |
| C — 11-13 → 11-20 | 7 | −8.22 [−25.32, +5.61] | −2.35 [−9.48, +4.00] | −2.77 [−9.16, +3.81] | 3/7 |
| **B ∪ C (pass test)** | 21 | −2.53 [−11.21, +4.58] | −3.16 [−7.63, +1.05] | **−3.11 [−7.39, +1.07]** | 10/21 |

Pre-registered pass condition: combined B ∪ C mean > 0 with CI lower bound > 0, and both legs positive on A. B ∪ C is negative. **Fail.**

Period A by month (combined, through): May +0.76c, Jun +0.18c, Jul +1.30c, Aug +0.80c, Sep (5 days) +4.68c.

## Reading

- The favorite–longshot effect seen in E004b and E008 is real in the summer months but small: about +1c per filled contract on ~91c of capital (about 1% per fill), with worst days of −$744 and a $1,314 drawdown at 10 contracts per fill.
- In late October and November it turned negative. Whether that is the season (winter forecasts are harder and the market's advantage is largest then, per Crosier 2026) or noise, a rule that needs two weeks of data to tell whether it still works is not something to run with a few hundred dollars.
- Buying 90c+ favorites as a maker stayed positive in A (+2.5c, CI excludes zero), but it was negative over B ∪ C. Picking that leg out now would be post-hoc selection, so it is recorded here and not pursued.
