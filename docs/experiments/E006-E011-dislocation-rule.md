# E006 / E010 / E011 — The "dislocation" rule on thin 15-minute crypto markets

| | |
|---|---|
| **Date** | 2026-11-13 |
| **Status** | **First result that passes an untouched out-of-sample test.** Not yet proven tradeable: fills are modelled from other traders' prints, not from our own orders. |
| **Code** | `e003_s1_model.py` (model), `e006_signal_trades.py`, `e010_dislocation_frozen.py`, `e011_frozen_on_live_book.py` |
| **Data** | `full-001` (candles, spot), trade prints `trades-003` (threshold + validation signal markets) and `trades-005` (test signal markets), live book `live-001`, `full-003` |
| **Raw output** | `output/E006_signal_trades.txt`, `output/E006_test_first_print.txt`, `output/E010_frozen.txt`, `output/E011_live_book.txt`, signal lists `output/e010_sig_*.csv` |

## What the rule is (frozen in commit `9ac0a11`, before the test split was opened)

1. A logistic model combines the Kalshi price with outside information — where Coinbase spot sits relative to the strike in volatility units, momentum, Bitcoin's move, volatility regime, time left, recent Kalshi price drift. Fitted on 2026-09-13 → 10-11 only.
2. At the end of each minute of a 15-minute market: if the model's probability for a side exceeds that side's ask plus the taker fee by more than **8 cents**, buy that side and hold to settlement.
3. Fill model for evaluation: an immediate-or-cancel order at the quoted ask + 2c; the fill price is the volume-weighted price of what other takers actually paid on that side between 1 and 6 seconds later (at or below the limit). No such print → no trade.

In plain terms: on thin coins the Kalshi price sometimes lurches 10+ points away from what spot implies. The rule buys the side that got too cheap.

## Results

| Period | Role | Signals | Filled | P&L per contract | 95% CI (by day) | Win rate | Avg fill | Days positive |
|---|---|---|---|---|---|---|---|---|
| 10-12 → 10-19 | threshold chosen here | 413 | 305 (74%) | **+9.74c** | [+7.41, +12.68] | 51.5% | 40.3c | 8 of 8 |
| 10-20 → 10-31 | validation | 679 | 513 (76%) | **+11.34c** | [+6.62, +16.34] | 50.9% | 38.2c | 11 of 12 |
| **11-01 → 11-12** | **test — opened once** | 638 | 497 (78%) | **+11.01c** | **[+3.97, +18.37]** | 50.7% | 38.3c | 10 of 12 |

One trade per market on test: +10.26c [+4.45, +16.12], n=401. About 53 signals a day across nine coins.

**Stricter fill: the first same-side print at or after a delay, no price limit** (test split, 636 signals)

| Delay | Price paid vs quote | P&L per contract | 95% CI |
|---|---|---|---|
| 0.5 s | +0.0c | +11.97c | [+5.21, +18.54] |
| 1 s | +0.7c | +11.35c | [+4.90, +17.40] |
| 2 s | +1.7c | +10.49c | [+3.99, +16.51] |
| 3 s | +2.4c | +9.80c | [+3.79, +15.47] |
| 5 s | +3.4c | +8.73c | [+2.58, +14.45] |
| 10 s | +5.7c | +6.58c | [+0.47, +12.09] |
| 20 s | +8.6c | +3.82c | [−1.65, +9.05] |
| 30 s | +9.4c | +2.98c | [−2.07, +7.80] |

The same table on threshold + validation days: +9.95c at 1 s, +9.07c at 2 s, +7.62c at 5 s, +6.36c at 10 s, +3.45c at 30 s. The edge decays over roughly 10–20 seconds, not milliseconds. A bot that reacts within 1–3 seconds keeps most of it; one that takes 30 seconds keeps none.

**Where it comes from** (test, limit-fill model): BNB 174 fills (+22.1c), DOGE 71 (+12.6c), NEAR 57 (+13.6c), HYPE 54 (+4.6c), XRP 41 (−5.4c), ZEC 40 (−6.7c), SOL 24, BTC 19, ETH 17. BNB and DOGE are positive in all three periods; the others flip sign between periods (small samples).

**Size.** Other takers bought a median of 106–188 contracts in the 5-second fill window at or below the limit; 81–88% of filled signals had at least 20 contracts printed. In the live capture the displayed size at the signal was 13–390 contracts (median ~70), sometimes 0–1 two seconds later.

**Shape of the event** (threshold + validation): same-side prints 30–60 s before the signal were on average 5c *above* the quote; in the 30 s after they climb 7c. A dip and a rebound — a flow-driven dislocation rather than a slow reaction to spot.

**On the real book (E011).** The frozen model produced 9 signals in the 4h45m live capture. Buying the ask actually displayed 0–10 seconds later averaged +7.5 to +10c per contract, with a standard error of ~19c — far too few to prove anything, but the displayed quotes were where the candles said they were.

## Why this might not survive contact with reality

| Risk | Detail |
|---|---|
| Fills are borrowed, not ours | We assume we would have paid what other takers paid seconds later. Those takers exist (first print lands a median 0.2–0.5 s after the minute mark), so there is a race for a small amount of resting size. Our own order would move the price |
| Tiny capacity | ~50 signals/day, tens of contracts each. Fine for a few-hundred-dollar account; it does not scale |
| One regime | 32 days of October–November 2026 |
| High variance | ~51% win rate at ~39c. At 10 contracts per fill the test period's worst day was −$45 and best +$124 |
| Proxy data | Spot is Coinbase, not the settlement index; BNB (thin on Coinbase) contributes most |
| Selection inside the family | Five model variants and six thresholds were looked at on validation before freezing. The test split was run once, on one frozen rule |
| Needs speed and an account | Reaction within a few seconds, continuous polling, and — to trade — a Kalshi account |

## Against the Phase 2 → 3 gate (PLANNING §1)

| Criterion | Status |
|---|---|
| Out-of-sample net EV > 0 with CI lower bound above zero on ≥ 1,000 trades | Test alone: 497–636 trades, lower bound +4c. Validation + test (neither used for fitting): 1,010 fills. **Met only if validation is counted; not met on the test split alone** |
| Survives multiple-testing correction | Test opened once on a frozen rule → no correction needed for the test figure |
| Survives +1 tick and a 1-second delay | **Yes** (+11.4c at 1 s, +8.7c at 5 s). Fails at 20–30 s |
| Paper-traded confirmation (Phase 4 gate) | **Not done.** This is the missing piece |

## What would settle it

A read-only observer that evaluates the model every second on live public data and records the real displayed ask and size at decision time and 1–3 seconds later, for two to four weeks. No Kalshi account is needed for that. GitHub's free minutes cannot host it; an always-on PC can.
