# E008 — Would resting orders have made money in weather markets?

| | |
|---|---|
| **Date** | 2026-11-13 |
| **Data** | Kalshi daily-high markets after the historical cutoff (`wx-001`, 2026-09-06 → 11-12, 7 cities) and all their trade prints (`wx-trades-002`, 2.65M trades, 2,562 markets) |
| **Split** | train 09-06 → 10-15 (40 days), validation 10-16 → 10-29 (14 days); test NOT opened |
| **Code** | `e008_maker_sim.py`; outputs `output/E008_weather_train.txt`, `output/E008_weather_val.txt` |
| **Status** | Complete on train and validation. **Second lead, weaker evidence than E010.** |

## Method

Every 30 minutes, for every bracket with a two-sided quote: one resting order to buy YES at the bid and one to sell YES at the ask, each alive 30 minutes. Zero maker fee on these series. Depth history does not exist, so three fill rules bracket the truth: *touch* (any opposing taker print at our price — optimistic), *through* (a print strictly beyond our price — conservative), *improve* (we quote one tick inside a spread of two ticks or more and are first in line).

## Results (cents per filled contract, 95% CI by day)

**Across everything** a resting order earns roughly nothing under *touch* and loses about 1c under *through*, in every city and time of day. Passive quoting in general is not an edge here either.

**By price** the favorite–longshot bias shows up clearly: orders on the favorite's side earn, orders on the longshot's side lose.

| Order | Rule | Train: fills / P&L | Validation: fills / P&L |
|---|---|---|---|
| Sell YES priced ≤ 10c (sell longshots) | touch | 11,186 / +0.84 [−0.82, +2.22] | 4,129 / +1.75 [−1.12, +3.77] |
| | through | 5,654 / +0.16 [−1.92, +2.05] | 1,691 / +1.34 [−2.06, +3.74] |
| | improve | 2,767 / +1.73 [−0.07, +3.25] | 841 / +1.22 [−1.55, +3.46] |
| Buy YES priced ≥ 90c (buy favorites) | touch | 600 / +2.52 [−1.02, +5.05] | 312 / +4.38 [+1.55, +6.26] |
| | through | 432 / +1.80 [−2.69, +5.14] | 189 / +4.01 [+0.22, +6.63] |
| | improve | 400 / +3.07 [+0.38, +5.09] | 182 / +3.62 [+0.34, +6.23] |
| Sell YES priced 10–20c | touch | 5,428 / +3.27 [+0.3, +6.0] | 1,974 / +5.51 [+1.6, +10.1] |
| Buy YES priced 10–20c | touch | 5,072 / −2.76 | 1,930 / −4.20 |

Signs agree across both periods and all three fill rules for the favorite-side orders; most intervals on train include zero. Win rates are 95–98%, so the payoff is many small gains and occasional losses of 90c+ — exactly the profile that looks better in a short sample than it is.

## Reading

- Consistent with the published finding that makers on the favorite side earn what longshot buyers lose.
- Capital-hungry: selling a 5c longshot ties up 95c to make ~1–2c.
- 54 days, one season, correlated brackets within a city-day. Needs a longer history (the pre-September pull did not publish — file-size limit, since fixed) and, ultimately, real resting orders, which need an account.
- Ranked below the E010 rule: smaller edge per dollar at risk, weaker statistics, and it cannot be paper-tested credibly without queue position.
