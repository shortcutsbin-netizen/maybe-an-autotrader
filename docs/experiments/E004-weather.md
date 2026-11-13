# E004 / E004b — Daily high-temperature markets

| | |
|---|---|
| **Date** | 2026-11-13 |
| **Data** | Kalshi: `runs/wx-002/` (history to 2026-09-13) + `runs/wx-001/` (after), 7 cities (NY, LAX, CHI, MIA, AUS, DEN, PHIL), 1,378 city-days, 8,267 markets, 10-minute quotes over each market's 40-hour life. External: `runs/ext-wx-001/` — METAR and 1-minute ASOS temperatures (Iowa Environmental Mesonet), archived model forecasts as issued 1 and 2 days earlier (Open-Meteo: GFS, ECMWF, ICON, GEM, NBM) |
| **Split** | fit 2026-04-30→08-01; threshold days 08-02→08-25; **validation 08-26→10-03**; test (10-04→11-12) NOT opened |
| **Code** | `e004_weather.py`, `e004b_weather_calibration.py`; outputs `output/E004_val_metar.txt`, `output/E004b_train.txt`, `output/E004b_val.txt` |
| **Status** | Complete on validation. **Negative for taker strategies. One maker lead (longshot selling) → E008.** |

## What the model fuses

| Layer | Content |
|---|---|
| Forecast | Multi-model mean of the forecast daily maximum for the hours still to come. Only forecasts issued at least 24 h before the valid hour are used once inside that window (48 h before it otherwise) — older than what a live bot would have, so this understates the model |
| Observation | Running maximum of METAR temperatures so far in the climate day (10-minute reporting lag), current temperature, last-hour trend, and the current forecast error fed forward (weight chosen on fit days: 0.5) |
| Uncertainty | Empirical distribution of (settled high − point estimate) by city, hours left and whether the peak has probably passed; spread between models |
| Market | Mid (logit), spread, one-hour drift, volume |
| Combiner | Residual-distribution probability for each bracket → gradient boosting on external features; logistic and gradient boosting stacked with the market |

Point-estimate error (mean absolute, °F) falls from ~2.1 the day before to ~0.8 in the last hours.

## Results (validation, 273 city-days, 75,425 quote rows, mean spread 1.63c)

**Forecast skill (Brier)**

| Model | All | Day before | Morning | Afternoon | Evening |
|---|---|---|---|---|---|
| **Kalshi mid** | **0.1228** | 0.1206 | 0.1280 | 0.1149 | 0.0187 |
| Residual model (external only) | 0.1515 | 0.1413 | 0.1575 | 0.1953 | 0.3223 |
| Boosting, external only | 0.1475 | 0.1368 | 0.1554 | 0.1861 | 0.2659 |
| Logistic stack (model + market) | 0.1232 | 0.1205 | 0.1287 | 0.1177 | 0.0193 |
| Boosting, everything | 0.1239 | 0.1213 | 0.1290 | 0.1184 | 0.0677 |

The market is far ahead of the external model at every horizon, and the gap widens through the day — traders are evidently using better real-time observations than hourly METAR. Stacking adds nothing to the market price.

**Trading** (fills 10 minutes after the signal plus one tick; cents per contract)

| Model | Threshold | Per quote row | One trade per market-side |
|---|---|---|---|
| Residual model | 15c | −2.86 [−5.84, −0.05] n=19,533 | −3.46 [−4.95, −2.14] n=1,500 |
| Boosting, external | 15c | −3.09 [−6.07, +0.10] | −3.15 [−4.64, −1.70] n=1,390 |
| Logistic stack | 10c | +10.49 [−1.64, +19.33] n=488 | −3.33 [−12.80, +7.76] n=101 |
| Boosting, everything | 15c | +4.26 [−3.88, +11.47] n=462 | −0.23 [−7.88, +8.73] n=110 |

The positive per-row numbers for the stacked models come from a handful of markets counted many times; counted once per market they are zero or negative.

**Settlement noise.** The settled high exceeds the hourly METAR maximum by at least 1°F on 63% of days and differs from the 1-minute ASOS maximum by at least 1°F on 55%. With 2°F brackets, even a perfect reading of the feeds we can get leaves real uncertainty about the bracket.

**Price-level calibration (E004b)**

| YES price | Train: outcome − price (pts) | Val: outcome − price | Take YES (train / val) | Take NO (train / val) |
|---|---|---|---|---|
| 0–5c | −1.49 [−1.94, −1.01] | −0.95 [−1.74, +0.19] | −3.49 / −2.87 | +0.13 / −0.27 |
| 5–10c | −1.83 [−2.98, −0.78] | −0.99 [−2.81, +1.23] | −4.26 / −3.36 | −0.41 / −1.20 |
| 10–20c | −1.02 | −1.95 | −3.90 / −4.74 | −1.78 / −0.75 |
| 20–50c | +0.2 to +1.4 | +0.8 to +1.8 | −2.3 to −3.2 / −1.5 to −2.8 | −3.6 to −5.0 / −4.2 to −5.0 |
| 90–95c | +3.59 [+1.99, +4.95] | +3.61 [+0.36, +6.07] | +1.08 [−0.44, +2.39] / +0.62 [−2.60, +3.00] | −6.4 / −6.5 |
| 95–100c | +2.18 [+1.54, +2.67] | +0.34 [−3.10, +2.24] | +0.76 [+0.13, +1.26] / −1.11 [−4.50, +0.76] | −4.7 / −2.9 |

A favorite–longshot bias is present in both periods: cheap brackets are overpriced by 1–2 points and near-certain ones underpriced by 2–4. After the taker fee and a realistic fill it is not harvestable (the one positive train cell reverses on validation). A resting order pays no fee on these series and earns the spread instead of paying it, so the same bias could be worth 1–3c per contract to a maker — if fills are not dominated by better-informed traders. That is tested in E008.

## Outside evidence

Crosier (arXiv 2609.23969, 7,590 city-days) finds the Kalshi-implied forecast beats the National Blend of Models by ~10% RMSE at every horizon and the best out-of-sample combination of six public forecasts by ~3%. Our result is the same finding from the trading side.

## Variants tried

Nowcast weight {0, 0.5, 1.0} chosen on fit days; 4 models × 6 thresholds chosen on threshold days; observation feed fixed to METAR for the headline (1-minute ASOS variant not run for selection). E004b: 10 price buckets × 4 time segments × 7 cities × 3 bracket types, descriptive.
