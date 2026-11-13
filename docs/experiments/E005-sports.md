# E005 — Sports game-winner markets vs the sportsbook line

| | |
|---|---|
| **Date** | 2026-11-13 |
| **Data** | Kalshi `runs/sp-001/`: NFL, NBA, NHL, college football, MLB game-winner markets, 2026-09-13→11-13, 1-minute quotes for the last 9 hours of each market (3,976 markets). External `runs/ext-sp-001/`: ESPN results and DraftKings opening/closing moneylines (1,609 games; odds for 1,524) |
| **Matched** | 1,325 games (2,654 markets). 656 college-football events unmatched (lower-division games outside the ESPN group pulled) |
| **Split** | By game date 60/20/20: train (37 days), validation; test NOT opened |
| **Code** | `e005_sports.py`; outputs `output/E005_train.txt`, `output/E005_val.txt` |
| **Status** | Complete on train and validation. **Negative.** |

## Tests

A. Pre-game (5 minutes before the scheduled start): Kalshi mid vs de-vigged DraftKings closing probability vs outcome.
B. Rule: buy the team on Kalshi when (book probability − Kalshi ask − taker fee) exceeds a threshold.
C. Does the book add information to the Kalshi price (logistic on both)?
D. In-game trend: after a 5-minute price move of a given size, is the outcome systematically above or below the new price (momentum or over-reaction)? Fade and follow rules, taker, held to settlement.

## Results

| | Train (742 games) | Validation (209 games) |
|---|---|---|
| Kalshi pre-game spread | 1.01c | 1.00c |
| Median contracts traded per market | 1,048,533 | — |
| Sportsbook margin | 4.33% | — |
| Brier, Kalshi mid | 0.20949 | 0.21882 |
| Brier, book close (de-vigged) | 0.20906 | 0.21901 |
| Mean absolute gap, Kalshi vs book | 0.90 pts (corr 0.998) | 0.77 pts |
| Stacked (Kalshi + book) Brier | 0.20834 (in-sample) | 0.21847 |
| Rule B, threshold 0 | 104 trades, −1.31c [−6.38, +7.31] | too few trades |

Calibration by price bucket is within sampling noise in both periods; taking either side costs about the fee.

**In-game** (train, 200,137 quote-minutes): outcome minus price is within ±0.6 points after moves of every size, with intervals spanning zero. Fading or following moves larger than 8 points loses 1–6c per contract in every league on train. On validation, following very large moves (>15 points) shows +2.3 points before costs (CI [+0.2, +5.1]) and +0.3c after fee (CI spans zero); the same cell was +0.6 [−0.8, +2.0] on train. Not a tradeable effect.

## Reading

Kalshi's game markets are tied to the sportsbook consensus to within a point, with a 1c spread and seven-figure volume per game. There is nothing for a slow taker here, and these series charge maker fees, which removes the zero-fee maker argument too. In-game speed strategies would compete with professional sports traders on latency. **Sports dropped from the taker shortlist.**

## Variants tried

Pre-game offset fixed at −5 minutes; thresholds 0–5c; in-game lags 5 minutes (2 and 15 computed, not reported or selected on); 7 move buckets; 5 leagues.
