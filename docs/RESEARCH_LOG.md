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

---

## Session 2 — 2026-11-13 (thread 1, turns 2–3, Phase 2)

### Environment notes

- GitHub Actions runners reach Kalshi's public API, Coinbase, Kraken, Iowa Environmental Mesonet, Open-Meteo and ESPN without credentials. GDELT answers 429 to most requests from runner IPs (shared-IP rate limit of one request per 5 s).
- WebFetch from the Claude workspace needs user approval for any URL not already seen in the conversation; when the user is away those calls fail. Kalshi API URLs and URLs returned by WebSearch are fine. External source formats were therefore learned with `research/collect/probe.py` on a runner (`runs/probe-002/`).
- The Actions REST API is not reachable from the workspace; run status is inferred from the `data` branch.

### Verified this session [V]

- **Fee schedule PDF read directly** (kalshi.com/docs/kalshi-fee-schedule.pdf, effective 2026-07-07): taker `round up(M × 0.07 × C × P × (1−P))`; maker `round up(M × 0.0175 × C × P × (1−P))` with M = 0 unless listed; rounding such that fee + position cost is rounded to a centicent; no settlement or membership fee. Listed with maker fees (multiplier 1/1): KXMLBGAME, KXNCAAFGAME, KXNFLGAME, KXUCLGAME, KXWCGAME, KXWNBAGAME, KXATPMATCH, KXWTAMATCH, KXLALIGA (the API additionally flags KXNBAGAME, KXNHLGAME and others as `quadratic_with_maker_fees`). **No crypto 15-minute or weather series is listed → makers pay nothing there.** Combos (KXMVE) maker 2 / taker 1. This closes the Phase 1 to-do "read the fee PDF".
- **Series catalog** (16,341 series): `fee_type` counts — quadratic 16,178; quadratic_with_maker_fees 160; quadratic_with_combo_maker_fees 3. Lifetime volume by category: Sports 1.5e11 contracts, Crypto 5.0e10, Elections 4.7e9, Commodities 3.4e9, Politics 1.4e9, Economics 1.3e9, Climate and Weather 1.3e9.
- **Weather daily-high markets** (`KXHIGHNY`, `LAX`, `CHI`, `MIA`, `AUS`, `DEN`, `PHIL`): six brackets per city-day (four 2°F "between" brackets, one "less", one "greater"); open 14:00–15:00Z the day before; close at 1:00 am local clock time after the day; `expiration_value` holds the settled high. Rules text: maximum temperature at the named climate station (CLINYC, CLILAX, CLIMDW, CLIMIA, CLIAUS, CLIDEN, CLIPHL) "according to The Weather Company". Bracket mapping checked on 8,267 markets with 0 mismatches: between → [floor, cap]; greater → ≥ floor+1; less → ≤ cap−1.
- **Sports game markets**: two markets per game (one per team), ticker `SERIES-YYMONDD[HHMM]AWAYHOME-TEAM`; close when the game ends; ties resolve each side at $0.50 (NFL rule text); median volume above 1M contracts per market pre-game spread 1c.
- **Historical endpoints use different field names**: `/historical/markets/{t}/candlesticks` returns `yes_bid: {open, high, low, close}`, `volume`, `open_interest` (no `_dollars` / `_fp` suffixes). The first weather pull (`wx-001`) therefore has empty quotes before 2026-09-13; `wx-002` re-pulled that period correctly. Both are kept.
- **Public order book**: `GET /markets/{ticker}/orderbook?depth=10` needs no auth and returns `orderbook_fp: {yes_dollars: [[price, size], ...], no_dollars: [...]}` sorted ascending (best bid last). ~90 ms round trip from a runner.
- **Observed touch sizes** (2-minute smoke sample, 2026-11-13 17:50Z): BTC ~8,000 contracts each side; DOGE 100–200; BNB 50–100.
- **Settlement high vs station observations** (1,378 city-days): the settled high exceeds the maximum hourly METAR temperature by ≥1°F on 63% of days (≥2°F on 11%); it differs from the IEM 1-minute ASOS maximum by ≥1°F on 55% of days. Station feeds available to us do not pin the settlement value to the degree.

### Secondary sources [S]

- Crosier, "Prediction Markets Beat the Weather Forecast on Tomorrow's High Temperature", arXiv 2609.23969 (7,590 city-days, 2022 → Aug 2026): market-implied forecast RMSE 2.44 / 2.21 / 1.88°F at open / evening / morning-of vs NBM 2.70 / 2.45 / 2.12 (market ~10% better); no single public forecast beats the market at any horizon; the best out-of-sample forecast combination still trails by ~3%; advantage largest Nov–Jun and smallest in Miami. Does not test trading or fees.
- Kalshi changed the daily temperature settlement source from the NWS climate report to The Weather Company on 2026-08-14 (partnership announced 2026-08-27); several trackers report the underlying number is still the NWS climate report value.

### Free data sources confirmed usable (formats in `runs/probe-002/`)

| Source | What | Notes |
|---|---|---|
| IEM `asos.py` | METAR temperature, hourly + specials | whole °F in this feed |
| IEM `asos1min.py` | 1-minute ASOS temperature | available within days; real-time availability not verified |
| Open-Meteo previous-runs API | hourly forecasts as issued 1 and 2 days earlier, per model (GFS, ECMWF IFS 0.25, ICON, GEM, NBM) | `gfs_hrrr` returned values identical to `gfs_seamless` — dropped |
| ESPN site scoreboard + core odds | results; DraftKings open/close moneylines, spread, total | odds present for ~95% of completed games |
| Coinbase / Kraken public tickers | spot | Kraken multi-pair call fails if any pair is unknown |
| GDELT DOC timelines | news volume / tone | rate-limited from runners; partial |

### Negative findings added (details in `docs/experiments/`)

- 15-minute crypto: external-information-only models are worse forecasters than the market price (E003).
- Sports: Kalshi tracks the sportsbook closing line to under one point; no pre-game or in-game momentum edge after fees (E005).
- Weather: forecast + observation model is a much worse forecaster than the market; no taker edge (E004, E004b).

### Session 2 addendum (2026-11-13 late) — microstructure facts from the live capture [V]

- `live-001` (2026-11-13 18:00–22:45Z): 76,815 public order-book polls, 0 errors, 93 ms median round trip from a GitHub runner.
- Median contracts at the best bid/ask: BTC 4,722/4,672; ETH 514/449; XRP 251/250; SOL 188/184; HYPE 70/57; BNB 62/50; ZEC 58/42; DOGE 47/50; NEAR 30/28. Tenth-percentile ask size on the thin coins: 3–6 contracts.
- Kalshi mids incorporate a Coinbase move within the same 2-second poll (80–100% of the total response).
- One-minute candle close quotes equal the captured book at the minute end to 0.65c on average; Coinbase candle closes equal the captured last price at the candle's end to 0.4 bps (BTC).
- A 15-minute BTC market trades roughly 60,000 prints; mids can swing 30–40c within a minute when spot sits near the strike.
- Trades-per-market sizes made three pulls exceed GitHub's 100 MB file limit; they never published.

### Negative findings added

- Naive passive quoting on 15-minute crypto loses about 1c per filled contract to adverse selection (E009).
- Passive quoting in weather markets is roughly break-even to slightly negative overall; only favorite-side orders are positive (E008).

### Positive finding (unconfirmed on own fills)

- Frozen dislocation rule: +11.0c per contract on the untouched test split, 95% CI [+4.0, +18.4], 497 modelled fills over 12 days (E010).

---

## Session 3 — 2026-11-21 (thread 1, turn 4, Phase 2 round 3, Opus 5.5)

### Environment

- Repository public from ~2026-11-20 (user), so Actions minutes are unlimited. Twenty-one data jobs ran in parallel without errors except `hist-sol-001`, which never published.
- `/historical/markets` ignores close-time filters; `/historical/trades?ticker=` works.

### Verified [V]

- **CRYPTO contract terms** (assets.kalshi.com/contract_terms/CRYPTO.pdf, read directly): the underlying is the simple average of a CF Benchmarks index over the 60 seconds before the expiration time; if data is missing or incomplete, affected strikes resolve No; Kalshi may open a market outcome review before settlement; position accountability level $25,000 per strike per member; minimum tick $0.001. The document is a generic crypto template and does not mention 15-minute contracts specifically. Closes the Phase 1 to-do.
- Series history depth: seven 15-minute coins back to at least 2026-06-02; NEAR and ZEC from about 2026-07-01.
- ESPN win-probability endpoints and timing fields (see CLAUDE.md §11).

### Results (details in docs/experiments/)

- E012 (pre-registered) **pass**: frozen dislocation rule +10.1c per contract over 113 never-seen days.
- E013 (pre-registered) **fail**: weather favorite-side maker rule negative in Oct 30 → Nov 20.
- E014 negative: Kalshi in-game prices beat ESPN's win probability.
- GDELT news volume: no relationship with dislocation P&L (partial coverage).

### Negative findings added

- Weather maker (S4-M) — rejected.
- Sports in-game vs public win-probability model — rejected; sports closed.

## Session 4 — 2026-11-22 (thread 1, turn 5, Phase 2 round 4 — strategy-surface sweep, Opus 5.5)

Sources consulted (primary unless marked):
- Kalshi public API, via GitHub runners: `/incentive_programs?status=active|upcoming|all`, `/incentive_schedules`
  (probe-006) — ~7,200 liquidity programs, nearly all on long-dated/niche markets; none on 15-min crypto or
  hourly/daily weather. Reward units in the API are not documented on the page read (`period_reward` 950000 etc.).
- Kalshi docs `api-reference/live-data/get-weather-index.md`: `GET /live_data/weather/{city}` (from/to in ms,
  last_sec, detailed). Probe-007: 13 cities (miami, dfw, houston, phl-delaware-valley, puget-sound, sf-bay,
  greater-boston, southeast-michigan, kansas-city, minneapolis-st-paul, nyc, chicago, la-coastal); canonical
  points from 2026-10-08; Miami index uses 5 stations (e.g. KFLL1M, source `hf_asos`). Verified: index at the close
  minute equals the hourly-temperature market's expiration value in 100% of hours (E019).
- Kalshi series metadata (probe-004/005): gold 15-min settles on the Pyth 1-minute candle close at window end vs
  start; WTI/silver/natgas/copper/EURUSD/yields on Pyth; S&P 15-min on S&P DJI; KXGOLDH hourly ladder exists.
- Pyth docs and forum (secondary for pricing): Benchmarks, Hermes and the TradingView shim require an API key
  since 2026-08-26; Pyth blog: plans start at $500/month (free trial only). All four Pyth routes returned
  `unauthorized` from a runner (probe-005).
- Polymarket gamma/CLOB (probe-005, poly_pull): 15-min up/down markets for btc/eth/sol/xrp/doge/bnb/hype exist
  with slug `<coin>-updown-15m-<start ts>`; resolution = Chainlink 60-s TWAP stream; none for near/zec.
- Coinbase PAXG-USD and Kraken PAXGUSD / EURUSD 1-min OHLC are public (Kraken returns only the last 720 bars).
- Synoptic API requires a token (probe-005).
- Literature (secondary): Bürgi, Deng, Whelan "Makers and Takers" (makers earn, takers lose; favourite–longshot);
  Subramanian (IJFMD 2026, Kalshi efficiency); Le (arXiv 2602.19520, calibration decomposition); Mohanty &
  Krishnamachari (arXiv 2604.01431); Portnaya (arXiv 2606.19517, Polymarket vs options). None reports an edge
  in Kalshi 15-minute crypto. Vendor/blog posts on hourly books report no repeatable entry.

Observations (verified unless marked):
- Ladder markets (`KX{COIN}D`) carry the strike in `custom_strike.floor_strike`; `floor_strike` is null and
  `strike_type` is `custom` (`greater` inside custom_strike). Ladder `expiration_value` equals the 15-minute one.
- Hourly temperature: the single-station `KXTEMP…H` series (NYC, LAX, CHI, AUS, DC) listed no markets after
  2026-09-22; the index-settled ones are `KXTEMPMIAH`, `KXTEMPNYCHS`, `KXTEMPCHIHS`, `KXTEMPLAXHS`.
- Kalshi 15-min FX/yield/commodity markets: 61 days pulled; spreads 0.85c (gold) to 4c (yields, median);
  FX 2.6–5.2k contracts per market, yields 330–590.
- Hourly crypto range events have 49–300 buckets, most without offers.
- Polymarket 15-min XRP volume ~$1.1k per window; BTC ~$32k.
- Experiments E015–E020 and E016b/E016c: see `docs/experiments/E015-E020-round4-strategy-surface.md`.

Mistakes / lessons:
- `ladder-*-001` kept 0 markets (strike field) — fixed in the puller, resubmitted as `-002`.
- A 13k-market print load OOM-killed the analysis (7 GB workspace); evaluate in chunks of ~1,500 markets.
- Mixing a smoke run into a glob overwrote full data in a dict; concatenate per key instead.
