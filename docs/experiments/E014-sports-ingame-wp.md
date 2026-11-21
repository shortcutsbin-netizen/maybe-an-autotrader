# E014 (exploratory) — In-game sports: Kalshi vs ESPN's win probability

| | |
|---|---|
| **Date** | 2026-11-21 |
| **Why** | The user asked that sports be dropped only if absolutely not feasible. E005 tested pre-game prices against sportsbook lines and in-game momentum. The remaining free information source for in-game trading is ESPN's published play-by-play win probability |
| **Data** | `sp-001` (Kalshi game-winner markets, 1-minute quotes for the last 9 hours of each market), `ext-sp-001` (ESPN games), `espn-wp-001` (ESPN win probability for 961 NFL, college-football and NBA games, 249,138 play-level values with wall-clock times) |
| **Code** | `research/analysis/e014_sports_ingame_wp.py`; output `output/E014_sports_ingame.txt` |
| **Status** | Complete on train and validation. **Negative. Sports closed.** |

## Method

At each minute during play, read ESPN's win probability for the market's team from the latest play whose wall-clock time is at least 30 s (or 60 s) before the minute end — a feed delay a home bot would realistically face. Compare it with the Kalshi price; trade when ESPN's probability beats the ask plus fee by a threshold; fill at the ask one minute later plus 1c. Same chronological split as E005.

## Results

| | Train (33 days) | Validation |
|---|---|---|
| Quote-minutes | 121,234 | — |
| Brier, Kalshi mid | **0.1555** | **0.1595** |
| Brier, ESPN WP | 0.1595 | 0.1721 |
| Logistic weights (Kalshi, ESPN) | 0.91, 0.11 | — |
| Trade ESPN gaps > 8c (30 s delay) | −2.81c [−9.91, +4.62] | **−13.07c** [−25.37, +1.06] |
| Same, one trade per market | −2.17c | −7.86c [−17.96, −0.59] |

NBA looked positive on train (+3 to +6c) with ESPN matching Kalshi's Brier; on validation ESPN fell well behind (0.1707 vs 0.1586) and NBA trades lost about 10c. NFL trades lost 4–12c on train and ~45c on validation.

## Reading

Kalshi's in-game price is a better forecast than ESPN's model, and ESPN's model adds almost nothing to it. Before the game Kalshi tracks the sportsbook consensus (E005). The only remaining routes would be paid low-latency official data feeds, which are outside the project's budget and latency.
