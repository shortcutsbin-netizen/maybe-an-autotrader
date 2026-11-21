# E012 — Frozen dislocation rule on two periods it has never seen

| | |
|---|---|
| **Date** | 2026-11-21 |
| **Pre-registration** | `E012-E013-preregistration.md`, commit `457f237`, made before any of this data was pulled. Signals were computed and committed (`e012_sig_P8.csv`, `e012_sig_Q.csv`) before their trade prints were pulled |
| **Code** | `research/analysis/e012_frozen_new_periods.py`, `e012b_placebo.py` |
| **Data** | P: `hist-{btc,eth,xrp,doge,bnb,hype,near,zec}-001` (history endpoints, markets closing 2026-06-01 → 09-12; NEAR and ZEC start ~07-01), prints `trades-p0/p1/p2` (5.6M). Q: `full-004` (11-13 → 11-21 04:45Z), prints `trades-006` (1.07M) |
| **Raw output** | `output/E012_P8.txt`, `output/E012_Q.txt`, `output/E012_pooled.txt`, `output/E012b_placebo.txt` |
| **Verdict** | **PASS on every pre-registered criterion.** |

**Nine coins, final (headline).** SOL's first history job did not publish; it was resubmitted (`hist-sol-002`), its signals were computed and committed before its prints were pulled (`trades-psol`), and it is included below. The eight-coin tables further down are what was first computed and are kept.

| Pre-registered test, all nine coins | Fills | F1 | F2 last-in-line | F3 slow | Days positive |
|---|---|---|---|---|---|
| **P ∪ Q** (113 days) | 3,729 | **+9.63c [+7.84, +11.36]** | +5.94c [+3.83, +8.03] | +8.07c [+6.48, +9.68] | 94/113 |
| All 145 out-of-fit days | 5,044 | +9.95c [+8.35, +11.53] | +6.05c [+4.27, +7.86] | +8.33c [+6.88, +9.74] | 123/145 |

Months with ≥ 100 fills: Jun +8.2c, Jul +10.9c, Aug +8.7c, Sep +12.9c, Nov +7.1c — 5 of 5 positive. SOL alone in P: +3.20c [−3.03, +9.06], 253 fills — weakest coin with BTC. All three criteria still hold. Output: `output/E012_P_sol.txt`, `output/E012_pooled_9coins.txt`.

**Eight-coin tables (as first computed):**

## Results

| Period | Days | Signals | F1 fills | F1 P&L per contract | 95% CI (by day) | F2 last-in-line | F3 slow | Days positive (F1) |
|---|---|---|---|---|---|---|---|---|
| P — Jun 1 → Sep 12 | 104 | 4,864 | 3,209 (66%) | **+10.35c** | [+8.41, +12.22] | +6.71c [+4.41, +9.02] | +8.70c [+6.97, +10.41] | 87/104 |
| Q — Nov 13 → Nov 21 | 9 | 328 | 267 (81%) | +7.08c | [−0.08, +13.43] | +3.94c | +5.57c | 6/9 |
| **P ∪ Q (the pre-registered test)** | 113 | 5,192 | 3,476 | **+10.10c** | **[+8.20, +11.92]** | **+6.46c** [+4.26, +8.47] | **+8.50c** [+6.84, +10.15] | 93/113 |

Pre-registered criteria: (1) F1 mean > 0 with CI lower bound > 0 — **yes**; (2) F2 and F3 means > 0 — **yes**; (3) F1 positive in at least two-thirds of months with ≥ 100 fills — **5 of 5** (Jun +8.8c, Jul +11.0c, Aug +9.4c, Sep +13.6c, Nov +7.1c).

**Everything the rule was never fitted on** (threshold days, validation, test, P, Q — 145 days, Jun → Nov): F1 +10.30c [+8.66, +11.97] on 4,791 fills, positive on 122 of 145 days. Restricted to periods never used for *any* choice (test, P, Q — 125 days): F1 +10.21c [+8.28, +12.07], F2 +6.65c, F3 +8.65c.

**By coin, all unseen periods (F1 fills, P&L):** BNB 1,548 / +14.6c, DOGE 752 / +12.3c, ETH 237 / +9.6c, HYPE 853 / +6.9c, NEAR 506 / +7.7c, ZEC 345 / +7.4c, XRP 409 / +4.6c, SOL 68 / +15.6c, BTC 73 / −0.5c. Positive on every coin except BTC, where signals are rare.

**By month, all unseen periods:** Jun +8.8, Jul +11.0, Aug +9.4, Sep +13.6, Oct +10.7, Nov +9.6c.

**Placebo** (random side at random non-signal minutes in the same markets, same F1 fill model): P −3.75c [−5.49, −2.17]; Q +1.63c [−0.30, +3.26]. The F1 limit rule flatters any trade a little (it keeps only prints at or below the limit), which shows up as Q's slightly positive placebo. F3 has no limit and no such selection, and still earns +8.5c.

**Fillable size.** Other takers bought a median 66 contracts (P) and 247 (Q) in the 5-second window at or below the limit; 25th percentile 20 and 68. Summer markets were thinner (66% of signals filled vs 75–81% in Oct–Nov).

**Illustration only** (10 contracts per F1 fill, about $4 of capital per trade): P averaged $32/day (median $24) with a worst day of −$57; Q averaged $21/day.

## What this settles and what it does not

Settled, as far as history can: the rule is not an artefact of one month or one sample. It held, frozen, from June to November across eight coins, under three fill models, with a placebo that behaves as it should.

Not settled, and history cannot settle it:
1. **Our own fills.** Every fill price here is what *other* takers paid. Our order would join that race; they act within half a second of the minute mark.
2. **Market impact and capacity.** Median fillable size is tens of contracts. At 10 contracts a trade the backtest is not capacity-bound; at 100 it would be.
3. **Live data path.** The rule needs minute-end Kalshi quotes and Coinbase prices within a second or two, which a polling bot must reproduce exactly.

These are what Phase 4 paper trading (real-time quotes, displayed size, simulated fills against the live book) is for.
