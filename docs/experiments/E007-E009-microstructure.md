# E007 / E007b / E009 — What the live order book says (15-minute crypto)

| | |
|---|---|
| **Date** | 2026-11-13 |
| **Data** | `live-001`: public Kalshi order books (10 levels) for nine coins plus Coinbase/Kraken tickers, every 2 s for 4h45m (2026-11-13 18:00 → 22:45Z; 180 markets; 76,815 book polls; 0 errors; 93 ms median request time). `trades-004`: every trade print in those markets (1.39M). `full-002`: 1-minute candles for the same window |
| **Code** | `e007_live_leadlag.py`, `e007b_candle_vs_book.py`, `e009_live_maker.py` |
| **Status** | Complete. Descriptive facts plus one **negative** result (naive market making). |

## A. How much size is at the touch

| Coin | Median spread | Median best-bid / best-ask size (contracts) | 10th percentile ask size | Depth within 2c (bid / ask) |
|---|---|---|---|---|
| BTC | 1.0c | 4,722 / 4,672 | 628 | 16,506 / 18,259 |
| ETH | 1.0c | 514 / 449 | 16 | 2,486 / 2,267 |
| XRP | 1.0c | 251 / 250 | 3 | 1,459 / 1,644 |
| SOL | 1.0c | 188 / 184 | 12 | 1,825 / 1,735 |
| HYPE | 1.4c | 70 / 57 | 5 | 607 / 583 |
| BNB | 1.0c | 62 / 50 | 3 | 441 / 381 |
| ZEC | 1.0c | 58 / 42 | 6 | 490 / 441 |
| DOGE | 1.0c | 47 / 50 | 5 | 1,126 / 890 |
| NEAR | 1.0c | 30 / 28 | 6 | 261 / 238 |

Outside BTC and ETH the books are a few dozen contracts deep at the best price. A few-hundred-dollar account fits; anything larger moves the price.

## B. How fast quotes follow spot

Regressing 2-second changes in the Kalshi mid on current and lagged 2-second Coinbase returns: 80–100% of the total response arrives within the same 2-second poll for every coin with enough data (BTC, ETH, DOGE, HYPE, NEAR). **Market makers reprice within about two seconds of a spot move.** There is no multi-second lag to exploit on average.

Quotes are also very jumpy: the mid moves on average 1.1–2.0c between polls two seconds apart and ~3c over ten seconds.

## C. Are the 1-minute candle quotes real? (E007b)

Candle bid/ask "close" values match the book actually captured at the minute end: mean mid difference 0.65c, exact match 51% (the rest within the 2-second sampling jitter). Sampling the book 10 s earlier gives 3.2c, 60 s earlier 9.2c. **Candle close quotes are the true book at the minute boundary**, so candle-based backtests are not built on stale quotes. Coinbase candle closes were checked the same way against the captured ticker (0.4 bps for BTC at the candle's end time).

## D. Would resting orders have made money? (E009) — **Negative**

Simulated 10-contract orders joined to the best bid and best ask every 10 s, alive for 30 s, filled only when taker volume at that price exceeded the displayed queue ahead plus our size, or a print went through the price. No maker fee.

| | Orders | Filled | Mid 10 s after fill vs our price | 60 s after | To settlement | Half-spread earned |
|---|---|---|---|---|---|---|
| Join best quote, all coins | 16,102 | 81% | **−1.11c** (se 0.06) | −1.02c (0.08) | −0.87c (0.15) | +0.52c |
| One tick inside the spread | 6,484 | 89% | −0.91c (0.07) | −0.83c (0.09) | −0.45c (0.16) | +0.16c |

Every coin and every price bucket is negative at the 10-second mark; the tails (below 10c, above 90c) lose least (−0.2 to −0.4c). A passive quoter earns half a cent of spread and gives back a cent and a half to better-informed takers. **Naive market making on these markets loses money; strategy S3 in its simple form is rejected.**

## E. Does the closed-form fair value beat the live quote?

Φ(z) against the real book: Brier 0.1425 vs 0.1422 for the Kalshi mid; trading its disagreements at the displayed ask gave −0.1 to −1.0c at every delay (standard errors 3–6c). No edge from the simple model on its own, consistent with E003.
