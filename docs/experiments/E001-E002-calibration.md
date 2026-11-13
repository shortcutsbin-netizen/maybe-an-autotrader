# E001 / E002 — Is the 15-minute crypto market calibrated, and does naive taking pay?

| | |
|---|---|
| **Date** | 2026-11-13 |
| **Data** | `data` branch, `runs/full-001/` — pulled by GitHub Actions from Kalshi's public API (no auth). Manifest: 9,391 HTTP requests, 0 errors, sha256 per file |
| **Period** | Markets closing 2026-09-13 00:00Z → 2026-11-13 00:00Z (61 days) |
| **Series with data** | BTC, ETH, SOL, XRP, DOGE, BNB, HYPE, NEAR, ZEC (5,785 markets each); `KXCRYPTOLEAD15M` (28,825 markets, 5 outcomes per window). **ADA, BCH, TON returned 0 markets** — listed in the catalog but not trading in this period |
| **Rows** | 80,890 settled markets; 1,191,417 one-minute candles |
| **Split (fixed in advance)** | train 2026-09-13→10-18 (36 days), validation 10-19→10-31 (13 days), **test 11-01→11-12 — NOT OPENED** |
| **Code** | `research/analysis/e001_calibration.py`, `e002_favorite_side.py` |
| **Raw output** | `docs/experiments/output/E001_trainval.txt`, `E002_train.txt`, `E002_val.txt` |
| **Status** | Complete. **Negative result.** |

## Question

Before modelling anything: does the quoted price already equal the outcome frequency to within the taker fee? If so, any strategy that simply buys what looks cheap or dear by price level is dead on arrival.

## Method

For every market and every minute 1–14 after open, take the YES bid and ask at the minute's close (two-sided quotes only). Compare mid with the realized outcome. Compute the per-contract result of taking either side, net of the taker fee `0.07·p·(1−p)`:

- **Displayed fill:** buy at the quote shown at the minute's close. Optimistic.
- **Conservative fill:** the worse of that quote and the next minute's opening quote, plus one tick.

Confidence intervals: bootstrap resampling whole days (400 draws), because quotes within a market, and markets across coins in the same window, are strongly correlated.

Limits: one-minute resolution; a displayed quote is not a guaranteed fill; fee coefficient taken from secondary sources; rounding ignored.

## Results

All figures are cents per contract, train+validation unless stated.

**Liquidity (median per market)**

| Series | Volume (contracts) | Mean spread |
|---|---|---|
| BTC | 2,844,255 | 0.77¢ |
| ETH | 162,618 | 0.90¢ |
| XRP | 75,947 | 1.00¢ |
| SOL | 60,904 | 1.03¢ |
| DOGE | 36,651 | 1.16¢ |
| HYPE | 23,858 | 1.28¢ |
| ZEC | 21,449 | 1.76¢ |
| NEAR | 18,322 | 2.02¢ |
| BNB | 16,374 | 1.36¢ |
| Coin Race (LEAD) | 282 | 8.12¢ |

**Calibration by series** (outcome frequency minus mid, percentage points, with 95% CI)

| Series | Error | 95% CI | Take YES (cons.) | Take NO (cons.) |
|---|---|---|---|---|
| BTC | −0.44 | [−1.51, +0.38] | −2.69 | −1.81 |
| ETH | −0.09 | [−0.91, +0.80] | −2.34 | −2.16 |
| SOL | −0.49 | [−1.37, +0.52] | −2.79 | −1.81 |
| XRP | +0.03 | [−0.79, +0.88] | −2.25 | −2.31 |
| DOGE | −0.75 | [−1.44, −0.05] | −3.10 | −1.61 |
| BNB | +0.55 | [−0.36, +1.44] | −1.93 | −3.04 |
| HYPE | −0.40 | [−1.33, +0.45] | −2.82 | −2.01 |
| NEAR | −0.53 | [−1.54, +0.42] | −3.35 | −2.29 |
| ZEC | −1.32 | [−2.20, −0.45] | −3.99 | −1.34 |
| Coin Race | −0.71 | [−0.78, −0.64] | −6.59 | −4.68 |

Every series, both sides, negative. The largest calibration error on any up/down coin is 1.3 points; the round-trip cost of taking is 2–3¢.

**By minutes left (all series pooled):** taking either side loses 1.7–4.7¢ at every time-to-expiry bucket. Error shrinks toward expiry (−0.05 points with one minute left).

**Favorite–longshot check (E002, nine up/down coins, favorite = side priced above 50¢)**

| Favorite ask | Train: buy favorite (cons.) | 95% CI | Validation: buy favorite (cons.) | 95% CI |
|---|---|---|---|---|
| 50–60¢ | −3.77 | [−4.32, −3.24] | −3.51 | [−4.24, −2.73] |
| 60–70¢ | −3.99 | [−4.63, −3.35] | −3.99 | [−5.22, −2.74] |
| 70–80¢ | −2.92 | [−3.61, −2.25] | −4.08 | [−5.31, −3.06] |
| 80–90¢ | −1.82 | [−2.48, −1.10] | −3.23 | [−4.44, −2.18] |
| 90–95¢ | **+0.07** | [−0.58, +0.73] | −0.88 | [−1.50, −0.34] |
| 95–97¢ | **+0.20** | [−0.29, +0.70] | −0.30 | [−0.92, +0.29] |
| 97–98¢ | **+0.23** | [−0.14, +0.60] | −0.02 | [−0.50, +0.47] |
| 98–99¢ | **+0.12** | [−0.17, +0.41] | −0.25 | [−0.60, +0.13] |
| 99–100¢ | −0.01 | [−0.15, +0.09] | −0.08 | [−0.29, +0.10] |

Buying the underdog is negative in every bucket in both periods (−0.4 to −3.6¢).

On train, favorites priced 90–99¢ showed a small positive point estimate whose interval includes zero. **On validation it reversed sign in all four buckets.** Per-coin, the best train cell (DOGE favorites ≥95¢: +0.59¢, CI [+0.33, +0.81]) became −0.24¢ on validation. This is what a false positive from scanning many cells looks like.

## Conclusions

1. **The market is calibrated to within the fee on all nine up/down coins, at every price level and every time-to-expiry.** No price-level rule survives.
2. **Hypothesis "alt-coins are less efficiently priced" — not supported** at the level of price calibration. Their spreads are wider (1–2¢ vs 0.8¢) and their calibration is no worse.
3. **Favorite–longshot bias exists but is smaller than the fee.** Longshots under 5¢ win about 1 point less often than priced (pooled), consistent with published work; a taker cannot harvest it. A maker with zero fee might — untestable on this data.
4. **Coin Race (`KXCRYPTOLEAD15M`) is illiquid** (282 contracts median, 8¢ spread) — drop from scope.
5. Agrees with the third-party study logged in Phase 1 (late favorites −0.22¢/contract).

## What this does not test

- Any strategy using information beyond the Kalshi price itself (index distance to strike, volatility, flow). That is S1/S2/S5 — next.
- Maker fills.
- Sub-minute timing, final 60 seconds.

## Variants tried (for multiple-testing accounting)

E001: 12 price bins × 6 time bins × 10 series × 2 sides, 2 fill models — descriptive, no selection.
E002: 9 ask bins × 6 time bins × 9 series × 2 sides. One candidate family (favorites 90–99¢) inspected on train, failed on validation. **Test set untouched.**
