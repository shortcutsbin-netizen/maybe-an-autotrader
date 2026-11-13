# Research Log

Append-only. Never delete entries; strike through and annotate if superseded.

Labels: **[V]** verified against primary source · **[S]** secondary source · **[E]** estimate · **[H]** hypothesis.

---

## Session 1 — 2026-11-12 (thread 1, Phase 1)

### Environment notes

- Repo `shortcutsbin-netizen/maybe-an-autotrader` was **completely empty** (no commits, no branches) at session start. `claude` branch created as the first branch.
- The Claude cloud workspace shell **cannot reach** `api.elections.kalshi.com` (proxy returns 403 on CONNECT). The WebFetch tool **can**, one URL at a time, returning model-summarized content. Bulk data pulls from this workspace are therefore not possible without another route (see PLANNING.md Q2 / enhancement E1).

### Primary-source observations (Kalshi live API, unauthenticated)

`GET /trade-api/v2/series/KXBTC15M` — 2026-11-12:

- `frequency: fifteen_min`, `category: Crypto`, `fee_type: quadratic`, `fee_multiplier: 1`
- `settlement_sources: CF Benchmarks`
- `contract_terms_url: https://assets.kalshi.com/contract_terms/CRYPTO.pdf`
- `contract_url: https://assets.kalshi.com/regulatory/product-certifications/CRYPTO.pdf`
- Prohibitions: source-agency employees; holders of MNPI on the underlying.
- Product note: 60 RTI prices collected in the last minute before expiration and averaged.

`GET /trade-api/v2/series?category=Crypto&tags=15 min` — 13 series, all `quadratic`, multiplier 1:
`KXBTC15M, KXETH15M, KXSOL15M, KXXRP15M, KXDOGE15M, KXBNB15M, KXADA15M, KXBCH15M, KXHYPE15M, KXNEAR15M, KXTON15M, KXZEC15M, KXCRYPTOLEAD15M`.

`GET /trade-api/v2/markets?series_ticker=KXBTC15M&status=open` — market `KXBTC15M-26NOV121730-30`:

- open 22:15:00Z, close 22:30:00Z, `expected_expiration_time` 22:35:00Z, `latest_expiration_time` +7 days
- `floor_strike: 71360.42`, `strike_type: greater_or_equal`, `can_close_early: true`
- yes bid 0.37 × 11,074.35 / yes ask 0.38 × 9,047.05
- `volume_fp: 1,275,244.91`, `open_interest_fp: 490,845.40` (caution: snapshot was labelled as just after open; volume figure may reflect a later cache state — re-measure properly in Phase 2)
- `price_level_structure: tapered_deci_cent`; steps 0.001 on [0, 0.10) and (0.90, 1.00], 0.01 on [0.10, 0.90]

`GET /trade-api/v2/markets?series_ticker=KXBTC15M&status=settled` — four consecutive windows on 2026-10-12:

| ticker | strike | expiration_value | result | volume | OI | settled |
|---|---|---|---|---|---|---|
| …OCT120345-45 | 84037.14 | 83884.37 | no | 1,419,940 | 555,754 | close + 3.67 s |
| …OCT120400-00 | 83884.37 | 83903.06 | yes | 1,690,865 | 547,516 | close + 3.67 s |
| …OCT120415-15 | 83903.06 | 83663.21 | no | 1,466,353 | 565,352 | close + 3.67 s |
| …OCT120430-30 | 83663.21 | 83585.98 | no | 1,312,276 | 455,562 | close + 3.66 s |

Confirms: each window's strike equals the previous window's `expiration_value`.

`GET /trade-api/v2/markets/trades?ticker=…` — returns trades with `created_time` (µs), `yes_price_dollars`, `no_price_dollars`, `count_fp`, `taker_side`, `taker_book_side`, `is_block_trade`, cursor pagination. Observed prints of NO at $0.001 within 0.25 s of close.

`GET /trade-api/v2/historical/cutoff` — `market_settled_ts` and `trades_created_ts` = 2026-09-12; `orders_updated_ts` = 2026-10-28.

### Primary-source observations (Kalshi docs, docs.kalshi.com)

- **Rate limits:** token buckets. Basic = 200 read / 100 write tokens per second; default request cost 10. Advanced = 300/300 via upgrade endpoint (criterion: ≥1 of last 100 orders via API). Higher tiers by volume share. 429 has no Retry-After and no penalty. WebSocket cap 200 connections at Basic. Balance endpoint 1/s.
- **Public endpoints:** series, markets, events, order book need no auth. **WebSockets need auth.**
- **Candlesticks:** `period_interval` ∈ {1, 60, 1440} minutes. Fields: `yes_bid` OHLC, `yes_ask` OHLC, `price` OHLC (+mean, previous), `volume_fp`, `open_interest_fp`.
- **Historical tier:** `/historical/{cutoff,markets,markets/{t}/candlesticks,trades,fills,orders,positions}`. No order-book history mentioned anywhere.
- **`cfbenchmarks_value` WebSocket:** auth required; ~1 tick/s; `index_ids` such as `BRTI`, `ETHUSD_RTI`; 21 coins; each message carries `avg_60s_data` and, in the final minute before each quarter-hour, `last_60s_windowed_average_15min`. Separate 5 Hz channel for BTC/ETH/SOL/XRP/DOGE.
- **CF Benchmarks REST passthrough:** `/cfbenchmarks/values`, `/cfbenchmarks/history/values?id=BRTI&timespan=HOUR&timestamp=…`; 50 tokens/request; requires account entitlement.
- **Fee rounding:** fee to $0.000001; balance precision $0.0001 (direct members) or $0.01 (non-direct); per-order accumulator rebates over-rounding.

### Secondary sources — fees

Many independent pages citing Kalshi's fee schedule (dated 7 July 2026, still current 11 Nov 2026) agree: taker = `roundup(M × 0.07 × C × P × (1−P))`; maker = `0.0175` coefficient only on series flagged for maker fees (~157–160 series; 2 of 298 crypto series per one source); no settlement fee.
Sources: quantvps.com, rivo.markets, polykal.net, realize.tax, totalis.trade, oddsshopper.com.
**To do:** read the fee schedule PDF itself.

### Secondary sources — settlement

- predictionmarketspicks.com (several articles), botforkalshi.com, zeusportal.cc, turbinefi.com: consistent with the API rule text. Additional claims: missing index data → affected strikes resolve NO; one two-hour settlement delay on 2026-10-15; 8.8% of BTC windows over five weeks decided by < $10.
- kalshibacktest.com (240 days old) describes settlement as "BTC price at close" — **inconsistent with the current rule text; treated as outdated/inaccurate.**
- CF Benchmarks blog: BRTI consolidates order books of seven constituent exchanges; calculated every 200 ms since May 2026; venue excluded if its book is >10 s stale.

### Secondary sources — profitability evidence

| Source | Claim | Caveats |
|---|---|---|
| Bürgi, Deng, Whelan (UCD/CEPR/CESifo, 2025–26), "Makers and Takers" | >300k contracts; favorite–longshot bias; takers ≈ −32% average return, makers ≈ −10%; avg contract −20% pre-fee; makers buying ≥50¢ slightly positive | Data to Apr 2025; predates 15-min crypto and maker fees; exchange-wide |
| Becker, "The Microstructure of Wealth Transfer in Prediction Markets" (jbecker.dev) | 72.1M trades, $18.26B; takers −1.12% excess, makers +1.12%; at 50¢ ∓2.65/2.66%; 5¢ contracts win 4.18%; maker edge emerged after late-2024 volume surge; sports 72% / politics 13% / crypto 5% of volume; finance category near-efficient | Blog-published; data to 2025-11-25; dataset on GitHub |
| predictionmarketspicks.com, "Kalshi 15-minute bots" | 2,710 BTC windows, 29 Aug–27 Sep 2026. Late 95–99¢ favorites: 97.8% wins, −0.22¢/contract net. Own fair-value model: −1.36¢/contract net over 1,571 trades; Brier 0.1326 model vs 0.1269 market. Polymarket arb: 4 split settlements in 663 windows. Median spread 1¢ at 5 min left | Publisher sells subscriptions; own capture; 5 weeks |
| predictionmarketspicks.com, "12:30 rule" | 1,258 windows; final-minute favorites +1.9¢/contract | Same publisher; conflicts in spirit with the −0.22¢ result at 90 s — reconcile in Phase 2 |
| TurbineFi | 1,000 strategies, no costs: 69.5% profitable. 4,904 strategies with fees, liquidity caps, next-candle fills: 2.1% profitable, median −14.5%. Panic-fade 93/96 profitable; mean-reversion 0/432 | Vendor; one series; one 30-day window; no true OOS split |
| Finance Magnates, others | Polymarket 15-min latency-arb bot stories ($313 → $414k) | Anecdotal; different venue; Polymarket since added dynamic taker fees to these markets |
| layerx.xyz | Real-money Polymarket 15-min late-favorite strategy: −37.8% | Small, anecdotal, but real money |

### Secondary sources — competition and programs

- Susquehanna disclosed as Kalshi market maker (2024). Jump Trading reported (Bloomberg, Feb 2026) to take equity for liquidity; ~20 staff on prediction markets. Kalshi has an affiliated market maker (Kalshi Trading).
- Kalshi Liquidity Provider Program lists "Alt-Coin 15 Minute markets (ETH, HYPE, SOL, XRP, SHIB, BNB, DOGE)" with provider count 1.
- Liquidity Incentive Program published dates 2025-09-15 → 2026-09-01. Volume Incentive Program end moved up to Oct 13 (2026) amid CFTC review of incentive schemes.

### Cloudflare (developers.cloudflare.com) [V]

Workers Free: 100,000 requests/day, 10 ms CPU per invocation, 50 external subrequests per invocation; KV 100k reads/day, 1k writes/day.

### Negative findings / rejected ideas (keep)

- Latency arbitrage against spot: rejected for this hardware.
- Cross-venue arbitrage vs Polymarket: rejected (different settlement numbers; split settlements observed by third party).
- Cloudflare Worker: no current purpose.
- "Near-zero loss" objective: incompatible with positive EV on binaries; a 97.8%-win-rate strategy lost money in third-party testing.

### Unverified / to check

- Official fee schedule PDF; CRYPTO.pdf contract terms.
- CF Benchmarks passthrough entitlement on a free account.
- Read-only API key scopes.
- Alt-coin liquidity.
- 5-minute crypto contracts (one source, oddsreference.pages.dev; not in today's series list).
- Kalshi interest on cash/collateral (~3.25% APY per a forum comment).
- Request-signing clock tolerance (~5 s per pm.wiki).
