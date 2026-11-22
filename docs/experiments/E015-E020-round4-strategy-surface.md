# Testing round 4 — widening the strategy surface (E015–E020)

Thread 1, turn 5, started 2026-11-22 10:10Z. User request: before the build, find **all** valid strategies.
Everything here is exploratory unless stated; the only pre-registered rule remains S1-D (E010/E012).
Labels: **verified** = computed here from Kalshi/public data; **secondary** = third-party source; **hypothesis** = untested.

Status: DRAFT — sections marked *pending* are filled as data lands.

## Summary table

| ID | Idea | Result | Verdict |
|---|---|---|---|
| E015 | 15-min vs hourly ladder (same settlement number): box arbitrage, ladder monotonicity, relative value | No after-fee arbitrage worth the name (≤3 quotes in two months per coin, tiny size); 15-min mid beats the ladder as a forecaster | **Rejected** (BTC pending) |
| E015b | Frozen S1-D model on ladder strikes, last 15 minutes | ETH/SOL/XRP/HYPE ≤ 0; **BNB +12.2c** next-minute fill (52 signals, CI [+2.7,+21.6], both halves +); DOGE +13c (16, CI spans 0); ~10–20 contracts/min of liquidity | **Small add-on candidate** (BNB/DOGE ladders), needs forward evidence |
| E016 | S1-D early exit | Holding is best (+10.0c / +9.6c); time exits trade EV for lower variance | Hold remains primary |
| E016b | S1-D **maker entry** (rest 1–3 ticks inside the ask for 5–60 s, zero fee) | Fills 59–87%; +7.4…+10.2c per fill; **+4.6…+8.2c per signal; positive in all six signal sets** | **Valid alternative execution** for S1-D |
| E016c | S1-D threshold sensitivity (post-hoc, same test periods) | 4–6c band +6.28c [+5.03, +7.34] per F1 fill, 6–8c +6.63c [+4.71, +8.38]; ~156 extra signals/day (vs ~49 at ≥ 8c); maker entry +3.0…+3.3c per signal in those bands; BTC negative in every band | **Secondary rule for Phase 4** (must be confirmed forward) |
| E017 | Model-informed deep resting orders (all minutes, zero fee) | Validation −2…−3c per fill at every distance (4–16c from fair); model barely better than quoting around the mid | **Rejected** (train *pending*) |
| E018 | 15-min commodities / FX / yields / S&P | Calibrated; taker EV < 0 everywhere; no settlement feed (Pyth now paid, ≥$500/month); book-only and cross-market models produce no edge | **Rejected / blocked** |
| E019 | Hourly temperature vs the public Kalshi Weather Index (the exact settlement series) | Index matches every settlement; nowcast+market stack beats the mid in-sample only; validation trades −2…−9c; ~10 contracts/min | **Rejected** (one hypothesis kept) |
| E020 | Polymarket 15-min price as an S1-D feature | *pending* | — |
| — | Bucket-sum arbitrage (daily weather brackets; hourly crypto ranges) | Weather: 256 of 19,205 10-min snapshots, median edge 0.3–0.9c; crypto ranges *pending* | Monitor only |
| — | Kalshi Liquidity Incentive Program | Public API lists ~7,200 programs; none on 15-min crypto, hourly/daily weather or other short markets | Out of scope (long-dated) |

## E015 — 15-minute vs hourly ladder

**Mechanics (verified).** `KX{COIN}D` hourly ladders ("price above K at the hour") settle on the same 60-second
CF Benchmarks average as the 15-minute market closing on the hour: the ladder `expiration_value` equals the
15-minute one in 100% of 1,409 common hours for every coin. Ladder strikes are in `custom_strike.floor_strike`
(`floor_strike` is null; the first pull kept 0 markets for that reason). Spacing: ETH ≈0.2%, SOL ≈0.24%,
HYPE ≈0.3%, BNB ≈0.7%, XRP ≈1.3%, DOGE ≈5% of price.

**Box arbitrage.** Buy YES15 + NO ladder at K ≥ K15 (or NO15 + YES ladder at K < K15) pays ≥ $1 in every state.
At minute-end quotes over the last 15 minutes of 1,409 hours: cost < $1 before fees in 0.02–0.7% of
quotes; after taker fees, 0–3 quotes per coin in two months, median edge < 1c except two ETH/SOL quotes
(3–7c) with ladder volume of 18–300 contracts in that minute. **Within-ladder monotonicity:** zero after-fee
violations in 1,000–15,800 snapshots per coin. Conclusion: Kalshi keeps these consistent; nothing to harvest.

**Relative value.** Ladder-implied P(S ≥ K15) (linear between bracketing strikes) forecasts worse than the
15-minute mid in every coin (e.g. ETH Brier 0.1868 vs 0.1796). Trading the 15-minute market toward the ladder:
−6…+2c, CIs span zero or are negative. Reverse (trade the ladder strike nearest K15 toward the 15-minute mid):
noisy, no consistent sign. Output: `output/E015_ladders.txt`.

## E015b — frozen S1-D on ladder strikes

Ladder markets in their last 15 minutes are 15-minute up/down contracts with strike K. Fed through the frozen
model (no refit) with spot features recomputed against K. No ladder prints were pulled, so fills come from
candles: the minute-end quote ("now", optimistic) and the next minute's quote ("next", a one-minute delay that
removed most of the 15-minute edge in E003). One trade per market, 8c threshold.

| Coin | signals (next) | now | next [CI] | liquidity |
|---|---|---|---|---|
| ETH | 120 | −0.5c | −1.3c [−7.2, +5.0] | median 131 contracts/min |
| SOL | 53 | −1.2c | −3.9c [−14.2, +8.1] | 10/min |
| XRP | 11 | −6.4c | −4.5c | 10/min |
| HYPE | 104 | +1.1c | −3.4c [−11.9, +4.6] | 0/min (median) |
| **BNB** | **52** | **+17.5c** | **+12.2c [+2.7, +21.6]** | 0/min median; 12 in signal minutes |
| DOGE | 16 | +13.1c | +13.0c [−7.0, +28.4] | 244 in signal minutes |

BNB and DOGE are the two coins where S1-D is strongest on the 15-minute markets, which makes the result
plausible rather than a fluke of six tries — but the sample is small, fills are candle-based, and size is a
few tens of contracts. Capacity estimate (estimate): ~1.5 signals/day × ~10 contracts × ~10c ≈ $1–2/day.
Output: `output/E015b_s1d_ladders.txt`.

## E016 / E016b / E016c — S1-D execution variants

E016 (early exit) is reported in `output/E016_early.txt` / `E016_late.txt`: holding to settlement has the
best EV; time exits at 30–120 s keep +3.5…+5c with roughly half the per-trade standard deviation.

**E016b — maker entry.** Instead of an IOC at quote + 2c, rest a bid k ticks inside the ask (k = 1, 2, 3; never
below the bid) for W seconds; filled only if a taker on the other side prints at or through our price
("touch") or strictly through it ("through", conservative — the queue at our price must have been exhausted).
No fee. All 7,234 signals from E010/E012 (P8, P_sol, threshold days, validation, test, Q):

| variant (through) | fill rate | per fill | per signal |
|---|---|---|---|
| k=1, W=5 s | 66.8% | +7.93c [+6.17, +9.63] | +5.30c |
| k=1, W=15 s | 76.5% | +7.93c [+6.32, +9.52] | +6.07c |
| k=1, W=60 s | 82.9% | +7.69c [+6.05, +9.29] | +6.38c |
| k=3, W=30 s | 75.6% | +7.68c [+6.03, +9.34] | +5.81c |

Every signal set is positive (through, k=1, W=15 s): test +7.3c/signal, validation +7.8c, P8 +6.1c, Q +5.0c,
threshold days +4.7c, SOL +2.3c. For comparison the taker rule F1 earned +9.6c per fill on P∪Q.
Interpretation: the dislocation usually persists long enough for a passive bid one tick inside the ask to be
hit, and saving the 1.5–1.75c taker fee offsets most of the adverse selection. This matters for a home PC:
the maker version is far less sensitive to the 1–6 s latency the taker version needs. Output:
`output/E016b_maker_entry.txt`.

**E016c — threshold sensitivity (post-hoc).** The frozen model at a 4c threshold on the same periods as the
pre-registered test (P = Jun 1–Sep 12, Q = Nov 13–21): 23,184 signals on 113 days; prints for 97% of their
markets (8,944 extra markets pulled in `trades-thr04-0..2`). Split by edge at signal time:

| edge band | signals/day | F1 fill | F1 P&L per fill [CI] | maker entry: fill, per fill [CI], per signal |
|---|---|---|---|---|
| 4–6c | 114 | 64% | +6.28c [+5.03, +7.34] | 64%, +4.74c [+3.54, +5.80], +3.05c |
| 6–8c | 42 | 64% | +6.63c [+4.71, +8.38] | 67%, +4.89c [+2.84, +6.72], +3.28c |
| 8–12c | 30 | 67% | +9.13c [+6.91, +11.46] | 74%, +7.18c [+5.04, +9.39], +5.32c |
| > 12c | 18 | 69% | +10.42c [+7.96, +12.90] | 81%, +8.24c [+5.80, +10.97], +6.64c |

P&L rises with the model's edge, as a calibrated model should. Every alt coin is positive in the 4–6c band
(ETH +2.5c and SOL +3.4c weakest; NEAR +11.2c, ZEC +8.9c, BNB +7.8c strongest); BTC is negative in all four
bands (−2…−13c) and should be excluded. Q alone, 4–8c: +7.44c. Because these bands were examined on data that
had already been used to confirm the 8c rule, this is evidence for a pre-registered secondary rule in Phase 4,
not a re-tuning of the primary. Output: `output/E016c_threshold.txt`.

## E017 — model-informed deep resting orders

Every minute end on 14 sample days (8 alt coins, all markets): rest a YES bid at q − δ and a YES offer at q + δ
(q = frozen S1-D probability), 60-second life, zero fee, one contract; fills from public prints.
Validation (Sep 2, Oct 14, Oct 28; Sep 16/30 excluded as inside the model's fit window):

| δ | through: fills/4 h, P&L per fill | touch |
|---|---|---|
| 0.02 | 1,283, −2.14c [−2.62, −1.72] | −1.25c |
| 0.08 | 722, −2.84c [−4.06, −1.80] | −2.12c |
| 0.16 | 321, −1.72c [−3.58, −0.07] | −0.95c |
| control (mid ± 0.08) | 742, −3.14c | −2.19c |

The model helps only marginally over quoting around the mid; deep orders get filled when the price moves
against them. Sells (−3.8c) are worse than buys (−1.9c). The test split was not opened.
*Train (groups 0, 1) pending.* Output: `output/E017_*.txt`.

## E018 — 15-minute commodity, FX, yield and index markets

**Settlement sources (verified from series metadata):** gold, silver, WTI, natural gas, copper, EUR/USD and the
Treasury yields settle on Pyth (gold: the 1-minute candle close at the window end vs at the window start, no
averaging); S&P 15-minute on S&P DJI. **Pyth Benchmarks and Hermes need an API key since 2026-08-26; plans start
at $500/month** (secondary: Pyth blog), so no settlement-feed history is available within the no-paid-dependency
rule. Coinbase PAXG-USD (tokenised gold) is too thin as a proxy (prints in ~42% of minutes).

Calibration on 61 days (E001 method): every series within ±2 points except palladium (−1.9, CI excludes 0);
taker EV after fee negative for every series and side. Liquidity: FX 2.6–5.2k contracts per market, yields
330–590, gold ~0.85c spread. A book-only logistic with cross-market moves (EUR/GBP/AUD vs JPY/CAD; metals;
energy; yields) produced no signals or negative P&L. Output: `output/E018_*.txt`.

## E019 — hourly temperature markets vs the Kalshi Weather Index

**New verified fact:** the hourly temperature markets (`KXTEMPMIAH`, `KXTEMPNYCHS`, `KXTEMPCHIHS`, `KXTEMPLAXHS`;
the older single-station `…H` series listed nothing after 2026-09-22) settle on Kalshi's own minute-resolution
city index, public at `GET /live_data/weather/{city}` (13 cities; history back to 2026-10-08; multi-station,
1-minute ASOS + METAR fallback). The index value at the close minute equals the market's expiration value in
100% of 1,040–1,064 hours per city.

Nowcast = latest index value known at t − lag plus an empirical residual by lead time and slope (train only),
stacked with the market mid in a logistic (train only). Brier, validation: mid 0.0887, stack 0.0884 (lag 1),
0.0889 (lag 2). Trading at 3–12c thresholds: train positive (in-sample), **validation −0.3…−9c**. Typical
volume in a signal minute ~10 contracts. **Kept as a hypothesis:** in the last 5 minutes with a 1-minute lag the
stack beat the mid on validation (0.0962 vs 0.1013) — chosen after seeing validation, so it needs fresh data.
Output: `output/E019_lag{1,2,5}.txt`.

## E020 — Polymarket as a signal *(pending)*

Polymarket lists 15-minute up/down markets for BTC, ETH, SOL, XRP, DOGE, BNB, HYPE (slug
`<coin>-updown-15m-<window start>`), resolving on Chainlink's 60-second TWAP stream — not CF Benchmarks, so they
cannot be an arbitrage leg (S9 stays rejected). BTC ~$32k volume per window. Price paths pulled Jun 1–Nov 21.

## Other checks

* **Bucket-sum arbitrage, daily weather brackets** (mutually exclusive buckets; buy all YES if Σasks + fees < 1,
  sell all if Σbids − fees > 1): 60 + 196 of 19,205 ten-minute snapshots (May–Sep), median edge 0.9c / 0.3c;
  largest 7c on 2026-05-03. Capital per box ~$5 for cents of edge. Monitor-only.
* **Liquidity Incentive Program**: public `GET /incentive_programs` and `/incentive_schedules`. ~7,200 active or
  upcoming programs, nearly all on long-dated or niche markets (elections, entertainment, economics); none on
  15-minute crypto, hourly or daily weather. Out of scope while the user wants short-duration positions.
* Third-party bots and blogs (secondary) report no repeatable edge on hourly books; consistent with E015.
