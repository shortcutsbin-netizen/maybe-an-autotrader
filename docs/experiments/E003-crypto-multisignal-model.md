# E003 — Multi-signal fair-value model for 15-minute crypto markets

| | |
|---|---|
| **Date** | 2026-11-13 |
| **Data** | `runs/full-001/` (Kalshi 1-minute candles, nine up/down coins, 2026-09-13→11-13; Coinbase 1-minute candles) |
| **Split** | Models fit 2026-09-13→10-11; trade threshold chosen 10-12→10-19; **reported on validation 10-20→10-31**. Test (11-01→11-13) NOT opened |
| **Code** | `research/analysis/e003_s1_model.py`; raw output `output/E003_val.txt` |
| **Status** | Complete on validation. **Forecasting: negative. Trading: one lead that depends on execution speed — see E006/E007.** |

## Question

Does information beyond the Kalshi price — where spot is relative to the strike, volatility, momentum, what Bitcoin is doing, time of day — let a model out-forecast the market, and can the disagreement be traded after fees?

## Signals used

| Group | Features |
|---|---|
| Settlement-aware fair value | `z` = log move of spot since the strike-setting minute ÷ (60-minute realized volatility × √time left), with ~40 s removed from time left for the 60-second settlement average; the same with 15-minute and 24-hour volatility |
| Trend | spot momentum over 1, 3, 5, 15 minutes in volatility units |
| Regime | short/long volatility ratios, spot volume vs its 24-hour mean, share of recent minutes with trades, hour of day, weekend |
| Cross-market | Bitcoin's own `z` for the same window |
| Market | Kalshi mid (logit), spread, mid drift over 1 and 3 minutes, Kalshi volume |
| News | placeholder column (GDELT volume) — source was rate-limited; not populated in this run |

Models: closed-form Φ(z); logistic regression and gradient boosting on external features only; logistic on market price only; logistic and gradient boosting on everything.

## Results (validation, 106,340 quote-minutes)

**Forecast skill (Brier, lower is better)**

| Model | All | 1–2 min left | 3–7 | 8–14 |
|---|---|---|---|---|
| Kalshi mid | **0.13562** | 0.06418 | 0.11911 | 0.18140 |
| Φ(z) closed form | 0.13900 | 0.07572 | 0.12241 | 0.18201 |
| Logistic, external only | 0.13839 | 0.07475 | 0.12137 | 0.18205 |
| Boosting, external only | 0.13931 | 0.07465 | 0.12201 | 0.18367 |
| Logistic, market only | 0.13562 | 0.06425 | 0.11905 | 0.18144 |
| **Logistic, everything** | **0.13509** | 0.06380 | 0.11849 | 0.18091 |
| Boosting, everything | 0.13615 | 0.06428 | 0.11950 | 0.18224 |

The market price is a better forecast than any model built from outside information alone. Adding outside information to the market price improves it by 0.0005 Brier — real but tiny.

**Trading the disagreement** (buy the side whose model probability exceeds ask + fee by more than the threshold; cents per contract; 95% CI by day bootstrap)

| Model | Threshold | Displayed quote | Conservative fill | Fill one minute later |
|---|---|---|---|---|
| Φ(z) | 8c | +2.72 [+1.28, +4.18] n=16,455 | +1.87 [+0.43, +3.34] | −0.21 [−1.58, +1.24] |
| Logistic, external | 8c | +3.03 [+1.52, +4.56] n=12,126 | +2.10 [+0.59, +3.62] | −0.90 [−2.10, +0.43] |
| Boosting, external | 8c | +1.71 n=14,719 | +0.77 [−0.34, +2.02] | −1.66 [−2.59, −0.62] |
| **Logistic, everything** | 8c | +11.73 [+6.22, +17.45] n=679 | **+10.64 [+5.11, +16.34]** | +1.79 [−1.88, +6.49] n=417 |
| Boosting, everything | 8c | −0.59 n=2,757 | −1.61 [−4.42, +1.27] | −4.12 [−6.38, −1.96] |

The combined logistic model on the threshold-selection days (not used for fitting): +7.49c [+5.78, +9.36] conservative, −1.49c with the one-minute delay.

**Where the combined-model trades are** (validation, 8c threshold): BNB 255 trades (+10.9c), HYPE 119 (+12.1c), DOGE 91 (+19.5c), NEAR 62 (−3.1c), ZEC 54 (+12.7c), XRP 46, SOL 27, ETH 14, BTC 11. Mean spread at signal 2.65c (vs ~1.2c typical). Both sides contribute equally. One trade per market gives the same picture (+11.9c, n=523).

## Reading

1. The signal is "spot has moved, the Kalshi quote on a thin coin has not yet". It is not a forecasting edge; it is a speed edge.
2. It is profitable at the quote shown at the end of the minute in two disjoint periods, and gone (indistinguishable from zero) one minute later. One-minute candles cannot say whether it lasts 1 second or 40.
3. Displayed size on those coins is small (50–200 contracts at the touch in a spot check).
4. A home bot polling public REST endpoints has a reaction time of a few hundred milliseconds to a couple of seconds. Whether that is fast enough is exactly what E006 (trade prints after each signal) and E007 (live 2-second order-book capture) measure.

## Variants tried (multiple-testing ledger)

5 models × 6 thresholds (0, 1, 2, 3, 5, 8c), threshold picked on held-back train days by conservative-fill EV with ≥300 trades. The diagnostic pass additionally looked at thresholds 3, 5, 8, 12c for the combined logistic on both periods. No feature selection was done after seeing validation results.

## Not done

Test split; maker version; sub-minute timing; news feature.
