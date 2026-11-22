# Kalshi Short-Duration Trading Bot — Phase 1 Planning Document

| | |
|---|---|
| **Status** | **v5 (2026-11-22) — Phase 2 testing round 4 (strategy-surface sweep) complete. Recommendation unchanged in kind: close Phase 2, build one strategy family (S1-D) with the execution and threshold options found in round 4; awaiting user authorization.** (v4 2026-11-21; v3 2026-11-13; Phase 1 approved 2026-11-12.) |
| **Date** | 2026-11-12 |
| **Phase** | 2 — Real-data research, simulation and validation |
| **Author** | Claude (thread 1) |
| **Companion files** | `CLAUDE.md` (continuity), `docs/RESEARCH_LOG.md` (sources and raw findings) |

Labels used throughout:

- **[V]** Verified this session against a primary source (Kalshi docs or Kalshi's live public API).
- **[S]** Reported by a secondary source (blog, vendor, news). Treated as a lead, not a fact.
- **[E]** My estimate or calculation.
- **[H]** Hypothesis. Untested.

---

## v5 — testing round 4 (2026-11-22): the strategy-surface sweep

### User direction (2026-11-22)

| # | Direction | Effect |
|---|---|---|
| D17 | Before building, find **all** valid strategies; research extensively and act to maximize the surface | Round 4: E015–E020 plus desk research (below) |
| D18 | Phase 4 paper test: **a few days is ideal; longer is fine if the bot runs reliably in the background while the PC is in daily use** | New runtime requirement R-BG (below); Phase 4 bar revised |
| — | Schedule-and-resume across usage windows this turn | Resume chain scheduled from 14:45Z |

### What was tried in round 4 (details: `docs/experiments/E015-E020-round4-strategy-surface.md`)

| Area | Ideas tested | Verdict |
|---|---|---|
| Cross-market, same settlement number | 15-min vs hourly ladder box arbitrage; within-ladder monotonicity; ladder-implied relative value (both directions) | Rejected — Kalshi keeps them consistent after fees |
| S1-D on other books | Frozen model on hourly-ladder strikes (last 15 min) | BNB (+12c, n=52) and DOGE ladders positive with candle fills; others ≤ 0. Small add-on, needs forward evidence |
| S1-D execution | Early exit (E016); **maker entry** (E016b); **lower thresholds** (E016c) | Hold to settlement; **maker entry +6c/signal, positive in all six sets**; **4–8c signals +6.3…+6.6c per F1 fill (CIs > 0), ~3× the signal count** |
| Maker strategies | Model-informed deep resting orders everywhere (E017) | Rejected (−2…−3c per fill) |
| Other 15-min markets | Commodities, FX, yields, S&P (E018) | Rejected / blocked: settlement feed (Pyth) is paid, ≥ $500/month |
| Weather, hourly | Hourly temperature vs the public Kalshi Weather Index that settles it (E019) | Rejected on validation; one hypothesis kept for forward logging |
| Other venue as signal | Polymarket 15-min price in the S1-D stack (E020) | see report |
| Structural | Bucket-sum arbitrage (crypto ranges, weather brackets); Liquidity Incentive Program | Rejected / out of scope (incentives only on long-dated markets) |

Desk research also covered: Kalshi incentive programs (public `/incentive_programs`, `/incentive_schedules`); the
Kalshi Weather Index endpoint (`/live_data/weather/{city}`); Pyth's August 2026 paywall; third-party bots and
blogs (no repeatable hourly-book edge reported).

### Revised strategy set (authoritative)

| ID | Strategy | Status |
|---|---|---|
| **S1-D** | Dislocation rule, 15-min alt-coin markets, frozen model, edge > 8c, hold to settlement | **Primary** (E010/E012 pass) |
| S1-D-4 | Same model, edge 4–8c band | **Secondary, pre-register for Phase 4** (E016c post-hoc: +6.3c/+6.6c per fill) |
| S1-D-M | Maker entry for S1-D signals (bid 1 tick inside the ask, 15 s, else drop) | **Execution option to run in parallel in paper mode** (E016b) |
| S1-D-L | S1-D on hourly-ladder strikes (BNB, DOGE) | Observe-only in Phase 4 (thin; candle fills only) |
| — | BTC 15-min signals | Exclude (negative in every band, E012/E016c) |
| H-WX | Hourly-temperature nowcast in the last 5 minutes (E019) | Hypothesis; log only if cheap |
| everything else | see round 2–4 tables | Rejected |

### New runtime requirement R-BG (from D18)

The bot must coexist with daily use of the PC: one Python process, < 2% average CPU, < 300 MB RAM, no GPU, no
disk thrash (SQLite WAL, batched writes), network ~ 1–2 requests/s average (minute-end bursts of ~20 public
REST calls plus a Coinbase WebSocket), Task Scheduler start at logon with restart on failure, survives sleep /
network loss by stopping cleanly and resuming at the next quarter hour, and a `status` command. Paper-only.

### Revised Phase 4 bar (replaces v4's)

Run in the background until **both** (a) ≥ 3 calendar days and (b) ≥ 300 primary (8c) signals; longer only if
R-BG holds. At the observed rates (≈ 49 primary and ≈ 156 secondary signals per day on P∪Q) that is 4–7 days.
Pre-registered before the run: primary S1-D with taker paper fills against the displayed book; S1-D-4 and
S1-D-M reported alongside but not used for the pass/fail decision. Pass: primary paper P&L > 0 with CI lower
bound > 0; ≥ 50% of signals fillable at 10 contracts; live-vs-rebuilt feature parity; R-BG met.

---

## v4 — testing round 3 (2026-11-21): user decisions, results, recommendation

### User decisions (2026-11-20)

| # | Decision | Effect |
|---|---|---|
| D13 | No multi-week forward test before the build; for larger samples, pull recent history | Enhancement E6 (pre-build observer) **declined**. Both leads re-tested on recent history instead, with pre-registered rules |
| D14 | Repository made public (unlimited Actions minutes); to be made private again once not needed — Claude to recommend when | See the recommendation below |
| D15 | Weather history re-pull approved if it does not hit limits | Done (no limits on a public repo) |
| D16 | Drop sports / weather-taker / naive market making only if absolutely not feasible | One more sports test run (E014, in-game vs ESPN win probability); all three are now dropped on evidence |
| — | Work moved from Fable 5.2 to Opus 5.5 (commit attribution changed accordingly) | none |

### Round 3 results

| ID | Test | Verdict |
|---|---|---|
| E012 | Frozen dislocation rule on 113 never-seen days (Jun 1 → Sep 12, Nov 13 → 21), pre-registered | **PASS.** +9.63c per contract [+7.84, +11.36], 3,729 fills (nine coins; eight-coin first pass +10.10c); conservative fill models +5.9c and +8.1c; positive in every month and every coin except BTC (SOL weakest at +3.2c in the pre-period) |
| E013 | Frozen weather favorite-side maker rule on never-simulated periods, pre-registered | **FAIL.** Summer +0.9c; Oct 30 → Nov 20 −3.1c. S4-M rejected |
| E014 | In-game sports: Kalshi vs ESPN win probability (exploratory) | **Negative.** Kalshi out-forecasts ESPN; trading the gaps loses. Sports closed |
| — | News volume (GDELT, partial) vs dislocation P&L (exploratory) | No relationship (n = 255 covered signals) |

Across all 145 days the rule was not fitted on, it made +9.95c per contract on 5,044 modelled fills (nine coins), positive on 123 days.

### Where this leaves the strategy set

Exactly one strategy survives: **S1-D, the dislocation rule on 15-minute alt-coin markets** (BNB, DOGE, HYPE, NEAR, ZEC, XRP, ETH, SOL; BTC rarely signals). Everything else tested — sports (pre-game and in-game), weather (taker and maker), general crypto forecasting, crypto market making, favorite/longshot — is rejected with evidence recorded in `docs/experiments/`.

### Recommendation: close Phase 2; authorize a narrow Phase 3

Against the Phase 2 → 3 gate in §1: ≥ 1,000 out-of-sample trades with CI lower bound > 0 — **met** (3,729 on the pre-registered test alone); multiple-testing — **met** (frozen rule, pre-registered); +1 tick and 1-second delay — **met** (F2 and F3, and E006 at 1–5 s). The remaining Phase 4 gate (paper results inside the backtest's range) is what Phase 4 is for.

**Proposed Phase 3 scope (only this):**

| Component | Design |
|---|---|
| Market discovery | Each quarter hour, list open 15-minute markets for the active coins (public REST) |
| Kalshi data | Public order book for each active market about once a second; public trades for per-minute volume. No account needed |
| Spot data | Coinbase public WebSocket ticker (no account), REST fallback; minute bars built locally |
| Features and model | Re-implements the E003 features from live buffers; the frozen logistic model exported to JSON (no scikit-learn at runtime); a parity test checks live features against features rebuilt later from candles |
| Decision | At each minute end: edge > 8c → signal |
| Execution | **Paper executor only.** Simulates an immediate-or-cancel order at quote + 2c against the order book actually displayed when the order would arrive (measured latency added), records displayed size, then cross-checks against later trade prints. No live-order code is written until Phase 5 is separately authorized |
| Risk gate | Contracts per trade, per market, per coin, total open exposure, daily loss stop, stale-data and clock-skew stops |
| Settlement | Derived from the next window's strike, confirmed against the market result |
| Storage | SQLite (signals, decisions incl. no-trade, paper fills, settlements, daily P&L) and rotated JSONL event logs |
| Ops | CLI (`run --mode observe|paper`, duration or indefinite, coins, contracts, limits, log dir/level, profile; `report`; `doctor`), Windows Task Scheduler, NTP check, graceful shutdown, restart-safe state |
| Tests | Fee maths, feature parity, settlement derivation, risk gate, replay of a historical day end-to-end |

**Proposed Phase 4 bar** (short, given D13): run paper mode until **≥ 300 signals** (about 7–10 days at the observed rate). Pass if simulated-fill P&L is positive with its CI lower bound above zero, at least half of signals are fillable at 10 contracts on the displayed book, and live features match the later candle rebuild. Fail or stop otherwise.

### Repository visibility

Recommend making the repository **private again now**. The heavy data pulls are finished; Phase 3–4 work is code and local runs. The exact rule is currently public, and its edge is small-capacity and easy to copy. Anything already published may have been cloned, so making it private limits further exposure but cannot undo it.

---

## v3 — testing round 2 (2026-11-13): user direction, what was tested, where it leaves the plan

### User direction (2026-11-13)

| # | Direction | How it was applied |
|---|---|---|
| D10 | Bring in weather and sports markets for testing | Daily-high weather (7 cities) and game-winner markets (5 leagues) pulled and tested |
| D11 | Strategies must use every available source — market price, outside fundamentals, trends, news — not price level alone | Every domain now runs the same three-layer design (below) |
| D12 | No usage cap this round; auto-resume chaining every 5h15m until done | Followed |

### The information-fusion design used in every domain

| Layer | Crypto 15-minute | Weather daily high | Sports game winner |
|---|---|---|---|
| 1. Outside-information model | Spot vs strike in volatility units (settlement-average aware), momentum, volatility regime, Bitcoin cross-signal, time of day | Multi-model forecast of the remaining maximum, running observed maximum, nowcast error, empirical error distribution | De-vigged sportsbook closing line; opening line |
| 2. Market model | Kalshi mid, spread, recent drift, volume | Mid, spread, one-hour drift, volume | Mid, spread, in-game 5-minute moves |
| 3. Combiner and decision | Logistic / gradient-boosting stack; trade only when stacked probability beats ask + fee by a threshold; fills stressed by delay | Same | Same |

"News" enters as structured feeds a deterministic bot can use: forecast revisions, sportsbook lines, spot prices. A text-news volume/tone feed (GDELT) was wired in but the source rate-limited the collector; it is unpopulated and remains a to-do. No LLM is involved anywhere.

### What the round found

| Domain | Does outside information beat the market price as a forecast? | Taker result after fees | Maker result |
|---|---|---|---|
| Sports | No — Kalshi and the sportsbook agree to under one point | Negative | Not tested (these series charge maker fees) |
| Weather | No — market Brier 0.123 vs 0.148–0.152 for the model; matches a published study | Negative | Favorite-side resting orders +2 to +4c per fill in simulation; evidence thin (E008) |
| Crypto 15-min, in general | No — market 0.1356 vs 0.138–0.139; the stack is better by 0.0005 | Negative on average | Naive quoting loses ~1c per fill to adverse selection on the real book (E009) |
| **Crypto 15-min, large model-vs-quote gaps on thin coins** | n/a — a rare-event rule, ~53 signals a day | **+11.0c per contract on the untouched test split, 95% CI [+4.0, +18.4], if filled within a few seconds (E010)** | — |

### Strategy status after round 2

| ID | Strategy | Status |
|---|---|---|
| S1 | Fair-value model, taker, trading all disagreements | Rejected as a general strategy (E003, E007) |
| **S1-D** | **Dislocation rule: trade only gaps > 8c between the stacked model and the quote; fill within seconds** | **Lead. Passed the frozen out-of-sample test with modelled fills. Needs forward paper test on the real book** |
| S2 | Volatility-regime mispricing | Folded into S1 features; no separate edge seen |
| S3 | Passive quoting on 15-min crypto | **Rejected** (E009) |
| S4 | Favorite/longshot, taker | Rejected (E002, E004b) |
| **S4-M** | **Favorite-side resting orders in weather** | **Secondary lead** (E008); needs longer history and, eventually, real orders |
| S5 | Flow-overreaction fade | Subsumed by S1-D (the signals are dip-and-rebound events) |
| S6 | Momentum | No evidence (E003 features, E005 in-game) |
| S7 | Spot order-book imbalance | Not tested; quotes follow spot within 2 s (E007) |
| S8, S9 | Latency and cross-venue arbitrage | Rejected (Phase 1) |
| S11 | Text news | Feed unavailable; untested |
| — | Sports of any kind | **Dropped** (E005) |

### Proposed next step (needs your approval — it is a phase step)

**A read-only observer and paper trader for S1-D on the always-on PC.** It polls Kalshi's public order books and Coinbase about once a second, evaluates the frozen model continuously, and records for every signal the displayed ask and size at decision time and 1, 2, 3, 5 seconds later, plus the outcome. No Kalshi account, no orders. Two to four weeks of this either confirms or kills the lead with real quotes. It is a small slice of Phases 3–4 pulled forward for one strategy, so it is listed as enhancement E6 below and not started.

### Infrastructure note: GitHub Actions minutes

Three large trade pulls ran for hours and then failed to publish (single output file over GitHub's 100 MB limit — since fixed by splitting files and time-boxing jobs). Together with the 4h45m live capture, this round probably used most of a free private repository's 2,000 monthly Actions minutes. I cannot read the meter or cancel jobs from here. Options are in the open questions.

---

## v2 changes — user decisions of 2026-11-12 (authoritative where they differ from v1 text below)

| # | Decision | Effect on the plan |
|---|---|---|
| D1 | Empty `main` created with a placeholder README | Done. `claude` remains the working branch |
| D2 | Data route **A** (GitHub Actions) to start | Collector and workflow added under `research/collect/` and `.github/workflows/` |
| D3 | **No Kalshi account will be connected during development.** Only when ready for real trading, unless it is a hard blocker for test mode | No WebSocket access (it requires auth). Therefore: no `cfbenchmarks_value` settlement feed, no order-book delta stream, no CF Benchmarks history. Substitutes: public REST polling for books and trades; Coinbase/Kraken as index proxy; settlement values every 15 minutes from market records. **Not a hard blocker for Phase 2 or for taker paper trading.** It does weaken final-minute strategies (the true running average is unobservable) and maker evaluation (no delta stream). Will be raised again only if it becomes blocking |
| D4 | Starting bankroll: a few hundred dollars, more if results are good | Capacity is irrelevant. Absolute returns are small even with a real edge — see §20 |
| D5 | All 13 fifteen-minute crypto series in scope; testing decides priority | Supersedes the v1 recommendation to rank alt-coins first *a priori* |
| D6 | Taker vs maker: whichever is most effective | Both researched; taker first because it can be tested on history |
| D7 | Reuse applicable lessons from the earlier bot; no code import | As planned |
| D8 | **Short-term weather and any other quick-resolution market are also main targets.** Avoid long-dated positions; prefer contracts with a soon-measurable outcome | Scope widened: a market-discovery pass over all short-resolution series is added to Phase 2 (§3a) |
| D9 | Success criteria (§1), kill criteria and six-week time box (§17) accepted | Time box started 2026-11-12; mandatory continue/stop decision by 2026-12-24 |

### 3a. Scope rule (v2)

Eligible: any Kalshi market whose outcome is known within roughly 24 hours of entry, has a public, rules-defined settlement source, and has enough liquidity to enter at a few hundred dollars. Priority order is **not** fixed in advance; it is an output of Phase 2. Known candidates: 15-minute crypto (13 series), hourly/daily crypto ladders, daily weather highs/lows and hourly weather, short-dated index/commodity/FX ranges. A discovery pass will enumerate every series by `frequency` and rank by volume, spread and settlement transparency before any are modelled.

---

## 0. Executive summary

1. **The target market is real, liquid, and cheap to observe.** Kalshi lists 13 fifteen-minute crypto series. The BTC series (`KXBTC15M`) showed a 1¢ spread, roughly 9,000–11,000 contracts at each touch, and 1.2–1.7 million contracts traded per window in the samples pulled this session [V].
2. **That liquidity is the problem.** A 1¢ spread with five-figure touch size on a 15-minute contract means professional market makers are pricing it. Susquehanna is a disclosed Kalshi market maker and Jump Trading reportedly has about 20 people on prediction markets [S].
3. **The fee is the hurdle.** A taker pays `0.07 × P × (1 − P)` per contract — 1.75¢ at 50¢ [V formula, S coefficients; see §2.4]. Adding half the spread, a taker at mid-range prices needs its probability estimate to beat the market's by more than ~2.3 percentage points just to break even [E].
4. **Independent tests of the obvious strategies are negative.** One five-week study of 2,710 BTC windows found late-favorite buying lost 0.22¢/contract after fees and a fair-value model lost 1.36¢/contract; the market's Brier score beat the model's [S]. A vendor's 4,904-strategy backtest found 2.1% profitable once realistic fees and fills were applied [S].
5. **Makers pay no fee on these series** [V: `fee_type: quadratic`, not `quadratic_with_maker_fees`]. Exchange-wide studies show makers out-earning takers [S]. This is the most structurally plausible route to an edge, and also the hardest to validate without real orders.
6. **Historical data is sufficient for a real Phase 2**, with one gap: 1-minute bid/ask candles and full trade prints (with taker side) are available; historical order-book depth is not [V].
7. **Recommendation: continue to Phase 2 with a narrow scope and hard kill criteria.** Phase 2 costs no capital. It is the cheapest possible way to find out whether anything survives fees. My prior that this project reaches sustainable net profitability is low (§20).

---

## 1. Project purpose and measurable success criteria

**Purpose.** Determine, with evidence, whether an autonomous, LLM-free Python bot on a home Windows machine can earn a repeatable, positive, risk-adjusted return on Kalshi short-duration markets — and build it only if the evidence says yes.

**The stated goals conflict, and the plan resolves the conflict explicitly.** "Near-zero losing trades" and "maximize return" are incompatible on a binary contract. A bot that buys 97¢ favorites wins ~97% of the time and can still lose money (the study in §6 shows exactly this). Expected value after costs is the primary objective. Win rate is reported, never optimized.

**Proposed success criteria** (to be confirmed — see Q9):

| Gate | Criterion | Rationale |
|---|---|---|
| Phase 2 → 3 | At least one strategy with out-of-sample net EV > 0 after fees and conservative fill assumptions, with a 95% bootstrap confidence interval lower bound above zero, on ≥ 1,000 out-of-sample trades | A point estimate above zero is not enough at these margins |
| Phase 2 → 3 | Result survives a deflated-Sharpe / multiple-testing correction for every variant tried | Thousands of variants guarantee false positives |
| Phase 2 → 3 | Result survives +1 tick adverse slippage and a 1-second decision-to-fill delay | The bot will not be the fastest participant |
| Phase 4 → 5 | Paper-traded net EV within the Phase 2 confidence interval over ≥ 4 weeks and ≥ 1,000 trades | Forward data is the only real out-of-sample |
| Phase 5 | Realized net return beats the interest Kalshi pays on idle cash [S: ~3.25% APY, unverified] by a margin worth the operational effort | Otherwise holding cash dominates |

---

## 2. Kalshi market and API research

### 2.1 Contract mechanics — 15-minute crypto up/down

| Item | Finding | Label |
|---|---|---|
| Series | 13 fifteen-minute crypto series: BTC, ETH, SOL, XRP, DOGE, BNB, ADA, BCH, HYPE, NEAR, TON, ZEC, plus `KXCRYPTOLEAD15M` ("Coin Race") | V |
| Cadence | New market every quarter hour, 24/7 (96/day per coin) | V (open/close times), S (24/7) |
| Question | "BTC price up in next 15 mins?" | V |
| Settlement rule | YES if the 60-second simple average of CF Benchmarks' Real-Time Index (BRTI for BTC) before the close is **≥** the same average before the open | V (`rules_primary`, `strike_type: greater_or_equal`) |
| Strike | `floor_strike` on the market record = the previous window's settlement value. Verified: consecutive markets chain (`83663.21` expiry → next strike) | V |
| Tie | Resolves YES | V |
| Payout | $1 per winning contract, $0 otherwise | V (`notional_value_dollars: 1.0000`) |
| Tick size | 0.1¢ below 10¢ and above 90¢; 1¢ between | V (`price_ranges`) |
| Contract size | Fractional contracts supported (sizes reported to 2 decimals) | V |
| Settlement speed | ~3.7 seconds after close in four sampled markets | V |
| Settlement delay risk | Terms allow review and later expiration; one reported two-hour delay | S |
| Missing index data | Affected strikes reportedly resolve NO | S — **read CRYPTO.pdf contract terms in Phase 2** |
| Early close | `can_close_early: true` | V |

**Consequence of the averaging rule [E].** The outcome is not "spot at close vs spot at open." Both ends are 60-second averages. For a random walk, averaging the final 60 one-second prints removes roughly 40 seconds of terminal variance, and inside the final minute the outcome becomes progressively locked in. Any fair-value model that ignores this is mispriced in exactly the window where latecomers like to trade.

**BRTI itself [S, CF Benchmarks].** BRTI is computed from the consolidated order books of constituent exchanges (reported as seven), not from trades, and since May 2026 is reportedly calculated every 200 ms. A single exchange's price is a proxy for it, not the thing itself.

### 2.2 Other series considered

| Category | Why it matters | Status |
|---|---|---|
| Hourly/daily crypto (`KXBTCD` etc.) | Same index, strike ladders, slower | Secondary; possible cross-market consistency checks |
| 15-minute metals/energy/FX | Settle on Pyth, not CF Benchmarks | S — not yet researched |
| Weather (daily highs) | No latency race; model skill matters; no maker fee | Fallback pivot candidate (§3) |
| Sports, politics | 72% and 13% of volume; not short-duration in the relevant sense | Out of scope |

### 2.3 API capabilities

| Capability | Finding | Label |
|---|---|---|
| Base URL | `https://api.elections.kalshi.com/trade-api/v2` (also `external-api.kalshi.com`) | V |
| Demo environment | `https://demo-api.kalshi.co/trade-api/v2` | V |
| Auth | RSA-PSS signed headers (`KALSHI-ACCESS-KEY`, `-SIGNATURE`, `-TIMESTAMP`); sign the full path including `/trade-api/v2`, without query string | V (docs) + prior project experience |
| Public (no auth) REST | Series, markets, events, order book — documented as public. Trades and historical cutoff also returned data to an unauthenticated fetch this session | V |
| WebSocket | **Requires authentication** even for market data. Channels: `orderbook_delta`, `ticker`, `trade`, `cfbenchmarks_value`, 5 Hz CF Benchmarks variant, Pyth | V |
| Settlement-index feed | `cfbenchmarks_value` streams BRTI ~1/s with a trailing 60-second average, and during the final minute of each quarter hour the running settlement-window average. A 5 Hz channel exists for BTC, ETH, SOL, XRP, DOGE | V |
| CF Benchmarks REST passthrough | Historical index ticks via Kalshi credentials; 50 tokens/request; **requires an account entitlement** | V — entitlement status for a free account unknown |
| Rate limits (Basic) | 200 read tokens/s, 100 write tokens/s; default cost 10 → 20 reads/s, 10 writes/s. 429 with no cooldown penalty | V |
| Advanced tier | 300/300; obtained by calling an upgrade endpoint once at least one of the last 100 orders was placed via API | V |
| WebSocket connections | 200 concurrent at Basic | V |
| API key scopes | Read vs write scopes reportedly supported | S — verify; if true, Phases 2–4 use a **read-only key** |

### 2.4 Fees

| Item | Finding | Label |
|---|---|---|
| Taker fee | `ceil(M × 0.07 × C × P × (1 − P))`; `M = 1` for all 13 fifteen-minute crypto series | V (`fee_type`, `fee_multiplier`), S (0.07 coefficient, consistent across many sources citing the July 2026 fee schedule) |
| Maker fee | **None** on these series (`fee_type: quadratic`) | V |
| Settlement fee | None | S (consistent) |
| Rounding | Fees computed to $0.000001; direct members' balances move in $0.0001 steps with an order-level rounding accumulator. Rounding is negligible for a direct account | V |
| Membership/API fee | None | S |

Taker cost per contract [E]:

| Price | Fee | Fee + ½ of a 1¢ spread | As % of stake |
|---|---|---|---|
| 50¢ | 1.75¢ | 2.25¢ | 4.5% |
| 30¢ / 70¢ | 1.47¢ | 1.97¢ | 6.6% / 2.8% |
| 10¢ / 90¢ | 0.63¢ | 1.13¢ (0.68¢ on the 0.1¢ tick) | 11% / 1.3% |
| 5¢ / 95¢ | 0.33¢ | ~0.38¢ | 7.6% / 0.4% |
| 1¢ / 99¢ | 0.07¢ | ~0.12¢ | 12% / 0.1% |

**Action for Phase 2:** read the official fee schedule PDF directly. The coefficient is the single most important number in the project and I have it only through secondary citations.

### 2.5 Liquidity snapshot (single observations, not a study)

| Observation | Value | Label |
|---|---|---|
| `KXBTC15M` top of book, just after open | 37¢ bid × 11,074 / 38¢ ask × 9,047 | V |
| Volume per BTC window | 1.28M–1.69M contracts (5 windows sampled, incl. 03:45–04:30 ET) | V |
| Open interest per BTC window | 456k–565k contracts | V |
| Last-second prints | NO traded at 0.1¢ within 0.25 s of close | V |
| Median BTC spread with 5 min left | 1¢ | S |
| Alt-coin liquidity | **Not yet measured.** Kalshi runs a designated-liquidity-provider program for alt-coin 15-minute markets with a provider count of 1 | S (Kalshi help page) |

For a small account, capacity is not a constraint on BTC. Efficiency is.

### 2.6 Historical data availability

| Data | Availability | Label |
|---|---|---|
| Settled markets with `floor_strike`, `expiration_value`, `result` | Yes, live and `/historical/markets` | V |
| Trade prints with price, size, taker side, microsecond timestamp | Yes, live and `/historical/trades` | V |
| 1-minute candlesticks with **yes-bid and yes-ask OHLC**, trade OHLC, volume, OI | Yes | V |
| Live/historical boundary | 2026-09-12 for markets and trades at time of check; moves forward | V |
| Historical order-book depth or snapshots | **Not available** | V (absent from docs) |
| Historical BRTI ticks | Via CF Benchmarks passthrough, if entitled | V (exists), unknown (access) |
| Third-party trade dataset | Becker dataset, 72.1M trades to Nov 2025, on GitHub | S — check coverage of 15M series |

One-minute bid/ask candles allow honest "could I have crossed the spread at this minute" backtests for taker strategies. They do **not** allow honest maker backtests (no queue position, no depth) or sub-minute timing. Those need prospective collection.

### 2.7 Regulatory and platform restrictions

- Kalshi is a CFTC-regulated designated contract market [S]. Automated trading via API is supported and documented [V].
- Series-level prohibitions: employees of the source agency, and anyone holding material non-public information on the underlying, may not trade [V].
- Incentive programs are in flux: Kalshi ended its volume rewards program early amid CFTC scrutiny; a liquidity incentive program's published end date was Sept 2026 [S]. **No strategy in this plan may depend on incentive payments.**
- Not yet researched: the full Kalshi rulebook sections on self-trading, order-to-trade ratios, and quote-stuffing; state-level availability of crypto contracts for the user's state; tax treatment. See §16.

---

## 3. Target market categories and prioritization

| Priority | Target | Reason |
|---|---|---|
| 1 | **Alt-coin 15-minute series** (SOL, XRP, DOGE, ETH, others) | Same mechanics and data as BTC; probably fewer and less attentive market makers; a small account does not need depth [H] |
| 2 | **BTC 15-minute** | Best data, deepest book, strongest competition. Serves as the efficiency benchmark and the place to validate the fair-value model |
| 3 | Hourly crypto ladders | Cross-market consistency with the 15-minute contract |
| Fallback | Daily weather or other model-driven, non-latency markets | If Phase 2 kills the 15-minute thesis, this is where a home bot's disadvantages matter least |

This is a change from the brief's emphasis on BTC. I recommend treating BTC as the hardest version of the problem, not the primary target (Q5).

---

## 4–6. Candidate strategies, hypotheses, and evidence

| # | Strategy | Hypothesis for edge | Evidence for | Evidence against | Testable with historical data? | Prior |
|---|---|---|---|---|---|---|
| S1 | **Settlement-aware fair value (taker).** Price each contract as a digital on the 60-second-average index using realized short-horizon volatility; trade when market deviates by more than cost | Some participants price off spot or off a naive last-tick model; averaging effects are mispriced near open and close | Mechanism is real and specific; final-minute favorites netted +1.9¢ in one vendor sample [S] | A comparable model lost 1.36¢/contract and had a worse Brier score than the market over 2,710 windows [S] | Yes (1-min candles + spot history) | Low on BTC; unknown on alts |
| S2 | **Volatility-regime mispricing (taker).** Trade only when the market's implied volatility is far from a forecast (time of day, weekend, post-news) | Market makers widen or misprice in thin hours | Liquidity reportedly thins overnight and weekends [S] | No direct evidence | Yes | Low–medium |
| S3 | **Passive quoting (maker).** Rest bids/offers around model fair value; earn the spread with zero fee | Makers earn what takers lose; zero maker fee here | Becker: takers −1.12% vs makers +1.12% excess return exchange-wide, ±2.66% at 50¢ [S]; Bürgi et al.: makers lose much less than takers [S] | Those are exchange-wide averages dominated by sports; on crypto the makers are professionals and a slow maker is adversely selected when spot moves; 1¢ spread already | **No** — needs forward collection with order-book deltas, and paper fills are estimates | Medium, low confidence |
| S4 | **Longshot selling (maker or taker).** Sell 1–10¢ lottery tickets / buy 90–99¢ favorites | Favorite–longshot bias: cheap contracts win less often than priced | Bias documented on Kalshi in two independent studies [S]; 0.1¢-priced prints in the last second [V] | Taker version tested: 97.8% win rate, −0.22¢/contract after fees [S]. Classic negative-skew payoff | Taker: yes. Maker: partly | Low (taker), unknown (maker) |
| S5 | **Flow overreaction fade ("panic-fade").** When the contract price moves sharply without a matching index move, take the other side | Retail order flow overshoots | 93 of 96 variants profitable in one vendor run [S] | One series, one 30-day window, vendor with a product to sell; 0 of 432 mean-reversion variants profitable in the same study | Yes (trades + candles + spot) | Low–medium |
| S6 | **Short-horizon momentum.** Direction of last N minutes of spot predicts the window | Microstructure momentum | One publisher runs a rule of this type [S, self-reported, 68 trades] | Tiny sample; standard result is that 15-minute crypto direction is close to a coin flip | Yes | Low |
| S7 | **Order-book imbalance on spot exchanges** | Imbalance predicts the next seconds of index movement | Well documented in equity/crypto microstructure generally | Predictive horizon is seconds; the bot's latency and the taker fee consume it | Forward only | Low |
| S8 | **Latency arbitrage vs spot** | Kalshi quotes lag exchange prices | Reported large wins on Polymarket in 2025 [S] | Windows reportedly compressed to seconds and dominated by sub-100 ms bots; home PC cannot compete | — | **Rejected** |
| S9 | **Cross-venue arbitrage vs Polymarket** | Same event, different price | — | Venues settle on different numbers; four opposite settlements in 663 windows [S]; second account and venue needed | — | **Rejected** |
| S10 | **Intra-Kalshi structural arbitrage** (YES+NO < $1, ladder violations) | Mechanical | Worked in thin demo-era markets | 1¢ spreads and fees leave nothing; fastest bots take what appears | Cheap to monitor | Monitor only |
| S11 | **News/event-driven** | Scheduled macro releases move BTC | — | No LLM allowed; reaction is a latency race | Calendar filter only | Use as a **no-trade filter**, not a signal |
| S12 | **Regime detection / selective no-trade** | Most windows have no edge; skip them | Consistent with every negative result above | Not a strategy by itself | Yes | Required component of any survivor |

**What the evidence says overall.** Every piece of independent evidence on 15-minute BTC points the same way: the market's own price is a better forecast than simple models, and the fee converts small errors into steady losses. The exchange-wide maker advantage is the one robust positive finding, and it comes from a setting (retail sports flow) unlike this one.

---

## 7. Required external data sources

| Need | Source | Cost | Notes |
|---|---|---|---|
| Settlement index, live | Kalshi `cfbenchmarks_value` WebSocket | Free with account | The actual settlement input. Removes most need for third-party price feeds |
| Settlement index, history | Kalshi CF Benchmarks REST passthrough | Free if entitled | Unknown entitlement; fallback below |
| Spot proxy, history and live | Coinbase and Kraken public APIs (both reported BRTI constituents) | Free | 1-minute candles historically; WebSocket live. US-accessible |
| Kalshi market data | Kalshi REST (public) + WebSocket (auth) | Free | |
| Economic calendar | Static schedule file (FOMC, CPI, payrolls) | Free | No-trade filter only |
| News | None planned | — | No evidence it helps at this horizon without an LLM |

**Cloudflare Worker: not recommended at this time.** The bot can reach every source above directly. Free-plan limits (100,000 requests/day, 10 ms CPU per invocation) [V, Cloudflare docs] could not carry a per-second feed anyway. Revisit only if a specific source needs it.

---

## 8. Proposed system architecture (for Phase 3; design only)

```
collectors ──► normalizer/clock ──► feature store (SQLite + Parquet)
   │                                      │
   │                              strategy engine ──► risk gate ──► execution interface
   │                                      │                              ├─ PaperExecutor (default)
   └── health/monitor ◄── event log ◄─────┘                              └─ LiveExecutor (Phase 5, off)
                                          │
                                  performance memory ──► offline evaluator (promotion gate)
```

- Single asyncio process; one WebSocket to Kalshi, one or two to spot exchanges.
- Every component writes to an append-only structured event log; all state is reconstructible from it.
- `ExecutionInterface` has two implementations. The live one is not built until Phase 5 is authorized, and is never the default.
- Strategy code is identical in backtest, paper, and live. Only the data source and executor change.

## 9. Data collection and storage

| Store | Contents | Format |
|---|---|---|
| Raw capture | Every WebSocket message and REST response, with local receive timestamp | Compressed JSONL, daily files |
| Research tables | Markets, trades, 1-min candles, index ticks, book snapshots | Parquet |
| Operational state | Positions, orders, balances, config versions | SQLite (WAL mode) |
| Performance memory | One row per decision (§12) | SQLite |

Estimated volume [E]: order-book deltas for 13 series plus 1 Hz index for 5 coins is on the order of 1–3 GB/month compressed. Comfortable on the target machine.

## 10. Trade selection and risk management concepts

- Trade only when `|model probability − executable price| − fee − slippage allowance > threshold`, with the threshold set from out-of-sample calibration error, not chosen by hand.
- Fractional Kelly sizing (≤ ¼ Kelly) capped by a fixed per-trade dollar limit; binary payoffs make full Kelly ruinous under calibration error.
- Hard limits, enforced in the risk gate and not overridable by strategy code: per-trade, per-window, per-coin, total exposure, daily loss, drawdown halt.
- Correlation: 12 coins' windows are one bet on crypto direction. Exposure is netted across coins.
- No-trade conditions: stale index feed (> 2 s), clock skew, book crossed or empty, scheduled macro release within the window, settlement delay in progress, final N seconds unless the strategy is explicitly a final-minute strategy.

## 11. Testing, simulation, and validation methodology

1. **Data first.** Pull settled markets, trades, and 1-min candles for all 13 series back to launch; pull spot history. Record provenance and hashes.
2. **Descriptive study before any strategy.** Calibration curve of market price vs outcome by time-to-expiry and coin; spread and depth by hour; realized vs implied volatility. If the market is well calibrated everywhere, most strategies die here cheaply.
3. **Chronological split.** Oldest 60% train, next 20% validation, most recent 20% untouched test — opened once per strategy family.
4. **Execution model for taker tests.** Enter at the *worst* of the next minute's ask range; add one tick; apply the fee formula exactly; cap size at a fraction of that minute's traded volume.
5. **Baselines.** No trade; random side at the same times; always-follow-market-favorite; buy at mid with zero costs (upper bound).
6. **Uncertainty.** Block bootstrap by day; report confidence intervals, not point estimates.
7. **Multiple testing.** Log every variant tried in a registry; apply deflated Sharpe ratio / White's reality check to the family's best result.
8. **Maker strategies.** Not backtested on candles. Evaluated only on prospectively captured order-book deltas with a conservative queue model (fill only when the price trades *through* the quote), and reported as estimates.
9. **Negative results** are written to `docs/experiments/` and never deleted.

## 12. Learning and performance-memory architecture

- One immutable row per decision, including decisions not to trade: market, coin, time-to-expiry, book state, index value and running average, model probability, features, strategy and config hash, action, simulated or real fill, outcome, P&L.
- **Learning is offline and gated.** A nightly job recomputes calibration (isotonic or Platt) and per-regime performance. It proposes parameter changes to a *candidate* config. A candidate is promoted only if it beats production on a held-out recent period by a pre-set margin, and promotions are logged and reversible.
- No in-loop adaptation after wins or losses. That is the feedback loop the brief warns about.
- Drift detection: CUSUM on calibration error and on realized-vs-expected P&L; a breach halts the strategy, it does not re-tune it.
- Candidate models limited to things that fit the hardware trivially: logistic regression, gradient-boosted trees. Adopted only if they beat the closed-form model out of sample.

## 13. Runtime and operational requirements

- Python 3.12+, Windows 10/11, runs as a console process; background operation via **Task Scheduler** ("run whether user is logged on or not", restart on failure) as the default, NSSM service as the alternative. To be finalized in Phase 3.
- Clock: request signing fails with a few seconds of skew, and the strategy is timing-sensitive. Require NTP sync checks at startup and hourly; refuse to trade if offset > 250 ms.
- Proposed CLI (illustrative): `kbot run --mode {observe,paper,live} --duration 8h|forever --series KXBTC15M,KXSOL15M --strategy s1 --profile conservative --max-exposure 50 --log-dir ... --log-level ...`, plus `kbot report`, `kbot doctor`, `kbot replay`.
- `--mode live` additionally requires an environment variable and an interactive confirmation; absent both, the process refuses.
- Secrets: API key ID and private key path from environment variables or Windows Credential Manager. Never in the repo; `.gitignore` already excludes key material.

## 14. Costs

| Item | Cost |
|---|---|
| Kalshi account and API | $0 |
| Market data | $0 |
| Cloudflare | $0 (not used) |
| Hardware/electricity | Existing machine |
| Phase 2–4 capital at risk | $0 |
| Realistic paid upgrade if latency ever matters | A US-East VPS at roughly $10–40/month — **not proposed**; listed so the option is visible |

## 15. Major risks

| Risk | Type | Severity | Mitigation |
|---|---|---|---|
| No edge exists after fees | Financial | **Highest** | Phase 2 kill criteria (§17) |
| Backtest overfitting across many variants | Statistical | High | Variant registry, deflated statistics, single-use test set |
| Paper fills flatter reality, especially for makers | Statistical | High | Trade-through fill rule; label estimates; small live pilot only with separate approval |
| Adverse selection against a slow participant | Financial | High | Prefer strategies whose edge lasts minutes, not milliseconds |
| Fee schedule or contract rule changes | Platform | Medium | Poll series fee-change endpoints; halt on change |
| Settlement anomalies (delays, missing index data → NO) | Platform | Medium | Read contract terms; cap exposure per window |
| Negative skew (favorite-buying) hides tail risk in short samples | Statistical | Medium | Report tail metrics; require long samples for high-win-rate strategies |
| Home internet/power outage with open positions | Operational | Low–medium | Positions self-liquidate at settlement within 15 minutes; exposure caps |
| Key compromise | Security | Medium | Read-only key until Phase 5; secrets outside repo |

## 16. Areas requiring further research

1. Official fee schedule PDF and `CRYPTO.pdf` contract terms, read directly.
2. Whether a free account is entitled to the CF Benchmarks REST passthrough.
3. Alt-coin 15-minute spreads, depth, and volume by hour.
4. Launch dates and total history length for each 15-minute series.
5. Kalshi rulebook on self-match prevention, messaging limits, and conduct rules relevant to quoting.
6. Whether API keys can be scoped read-only.
7. The Bürgi/Deng/Whelan and Becker papers in full, specifically any crypto-category breakdown.
8. Round-trip latency from the user's machine to Kalshi.
9. Reports of 5-minute crypto contracts [S, one unverified source; not present in the series list pulled today].

## 17. Success, failure, and termination criteria

**Stop the 15-minute crypto thesis if, at the end of Phase 2:**

- the descriptive study shows the market is calibrated to within the fee at every time-to-expiry bucket on every coin with usable liquidity, **and**
- no taker strategy family clears the Phase 2 → 3 gate in §1, **and**
- four weeks of forward order-book capture shows simulated maker fills with non-positive net EV under the trade-through rule.

**Then** either pivot to the fallback category (one further research round) or terminate. I will recommend termination plainly if that is what the data says.

**Time box proposed:** three testing rounds or six calendar weeks of Phase 2, whichever comes first, before a mandatory continue/stop decision (Q9).

## 18. Outstanding questions

See the numbered list in the chat message accompanying this version, mirrored in `CLAUDE.md` § Open Questions.

## 19. Recommended next steps

1. User answers the open questions.
2. I revise this document and resolve §16 items 1, 5, 6, 7 (desk research, no data pull needed).
3. On Phase 1 approval: stand up read-only data collection (method per Q2) and run the descriptive study in §11 step 2 **before** writing any strategy code.

---

## Proposed enhancements (not in scope until approved)

| # | Feature | Why it might help | Evidence | Cost | Risk | Recommend? |
|---|---|---|---|---|---|---|
| E1 | GitHub Actions scheduled collector for public Kalshi REST data | Lets research proceed without the user's machine; reproducible | None needed; plumbing | Free-tier minutes; a workflow file | Runner IPs may be throttled; adds infra | **Yes**, for Phase 2 (Q2) |
| E2 | Forward order-book recorder on the user's PC from day one of Phase 2 | Only way to ever evaluate maker strategies; history cannot be bought back | §2.6 gap | Small script, needs API key | Read-only; low | **Yes** |
| E3 | Small-size live pilot ("execution probe") before full Phase 5 | Only way to measure real maker fills | Paper fills are estimates | Capital at risk, small | Violates "no live orders to test" unless separately approved | Not now; flag for Phase 4 discussion |
| E4 | US-East VPS | Cuts latency from ~50–100 ms to single digits | Latency matters for S3/S7 | $10–40/mo | Cost; still not co-located | No |
| E5 | Machine-learned probability model | May capture nonlinearities | None on this market | Moderate | Overfitting | Only if closed-form model shows promise |
| E6 | **Read-only observer / paper trader for the dislocation rule (S1-D)** on the user's PC: ~1 s polling of public order books and spot, frozen model, logs displayed price and size at 0–5 s after each signal | The only way to learn whether the E010 edge is fillable | E006/E010/E011: +11c per contract out of sample with modelled fills; decays over 10–20 s | A few hundred lines of Python; runs unattended; no account | Pulls a slice of Phases 3–4 forward; result may be negative | **Yes — awaiting approval** |
| E7 | Longer weather history for the maker test (re-pull pre-September trades in split files) | Triples the sample behind S4-M | E008 | ~60–90 Actions minutes | Minutes budget | Yes, after the minutes question is settled |
| E8 | Text-news feed with a rate-limit-friendly source (GDELT from the PC, or RSS headline counts) | Completes the "use everything" brief for crypto | None yet | Small | Likely no incremental value at this horizon | Low priority |
| ~~E6~~ | ~~Pre-build observer / paper trader~~ | — | — | — | — | **Declined by user 2026-11-20 (D13)** |
| E9 | Apply the dislocation idea to 15-minute gold / WTI / silver markets | Same mechanism may exist | None; needs a free 1-minute spot proxy for each, which has not been found | Moderate | Proxy quality | Not now |
| E11 | S1-D-4: also trade the 4–8c edge band | ~3× signals at +6c per fill (E016c, post-hoc) | E016c | none | Post-hoc on the test periods; must be confirmed forward | **Yes, as a pre-registered secondary in Phase 4** |
| E12 | S1-D-M: maker entry (rest 1 tick inside the ask, 15 s) | No taker fee; far less latency-sensitive | E016b, all six sets positive | small | Lower fill rate; adverse selection | **Yes, in parallel in paper mode** |
| E13 | S1-D-L: hourly ladder strikes for BNB/DOGE | Extra signals | E015b (n=52, candle fills) | small | Thin books; weak evidence | Observe-only |
| E14 | Pyth Pro subscription to test the dislocation idea on 15-min gold/WTI | Same mechanism may exist | none (feed unavailable) | ≥ $500/month | Paid dependency, unproven | **No** |
| E10 | Kalshi read-only API key during Phase 4 (WebSocket order books, CF Benchmarks settlement index) | Faster data, exact settlement input | E006: edge decays over 10–20 s, so speed matters | Small | Contradicts "no account until live" unless the user agrees | Optional — user's call |

---

## 20. Feasibility assessment (v1)

| | |
|---|---|
| **Current outlook** | **Uncertain, leaning Unpromising** for taker strategies on BTC; **Uncertain** for alt-coins and maker strategies |
| **Probability of sustainable net profitability** | Not reliably quantifiable yet. Informal prior, stated so it can be held to account: roughly **5–15%** for the project as scoped. Basis: negative third-party tests, a 2.1% survival rate in a large vendor backtest, professional market makers, a 1.75¢ fee against a 1¢ spread |
| **Confidence** | **Low–medium.** Mechanics and fees are verified against primary sources. All profitability evidence is secondary and partly from vendors. Nothing has been tested by us |
| **Supporting continued development** | Zero maker fee; deep free data including the settlement index itself; 1-minute bid/ask history exists; alt-coin markets unexamined; documented behavioral biases on the exchange; Phase 2 risks no capital |
| **Against** | Market price out-forecast a model on BTC; late-favorite and model strategies lost after fees; latency arbitrage is closed to this hardware; maker edge cannot be validated historically; the "near-zero losses" goal is not achievable alongside positive EV |
| **Biggest unresolved assumption** | That any mispricing on these contracts is larger than ~2¢ and lasts longer than the bot's reaction time — or that a slow maker can avoid adverse selection |
| **Recommended decision** | **Continue, with narrowed scope:** Phase 2 as a time-boxed, data-only test with the kill criteria in §17 |

Distinctions the brief asks for:

| Claim | Assessment |
|---|---|
| Technically buildable | Yes, high confidence |
| Operationally reliable on Windows | Yes, with ordinary engineering |
| Occasionally profitable | Yes — and meaningless |
| Statistically credible, repeatable edge | **Unproven; evidence to date is against it on BTC** |
| Meaningful returns after costs and risk | Unproven, and bounded by account size even if an edge exists |


---

## 21. Feasibility assessment (v3, 2026-11-13)

| | |
|---|---|
| **Current outlook** | **Uncertain — one narrow strategy is now Promising; everything else tested is Unpromising or Not viable** |
| **Probability of sustainable net profitability** | Still not reliably quantifiable. Informal estimate moves from 5–10% to roughly **20–30%**, almost all of it resting on the dislocation rule surviving a forward test |
| **Confidence** | **Medium** that broad forecasting edges do not exist in sports, weather or 15-minute crypto (three domains, consistent, agrees with published work). **Low–medium** on the dislocation rule: it passed an untouched test split, but with fills inferred from other traders' prints |
| **Supporting continued development** | E010: +11.0c per contract on the test split (CI lower bound +4.0c), positive on 29 of 32 out-of-fit days, survives a 1–5 s delay, placebo trades through the same machinery lose the fee as they should; candle and spot timestamps verified against a live capture; position sizes fit a few-hundred-dollar account |
| **Against** | Fills are not our own; a visible race (other takers act within half a second); tiny capacity; 32 days of one regime; BNB carries most of it; naive market making loses; outside information does not beat the market as a forecaster anywhere |
| **Biggest unresolved risk** | That our own order, arriving 1–3 s after a dislocation, finds the cheap quote gone or filled only when the trade is wrong |
| **Recommended decision** | **Continue, narrowed further:** forward paper-test the dislocation rule on the real book (E6). Keep weather favorite-side making as a secondary line. Drop sports. Do not build anything else yet |

| Claim | Assessment |
|---|---|
| Technically buildable | Yes |
| Operationally reliable | Yes; the rule needs ~1 s polling of nine books, well inside public rate limits |
| Occasionally profitable | Yes — meaningless |
| Statistically credible, repeatable edge | **One candidate with out-of-sample support; unconfirmed on real fills** |
| Meaningful returns after costs and risk | Unknown. The backtest's dollar figures (tens of dollars a day at 10 contracts per trade) should not be believed until a forward test reproduces them; capacity caps the upside regardless |


---

## 22. Feasibility assessment (v4, 2026-11-21)

| | |
|---|---|
| **Current outlook** | **Promising — for one narrow strategy.** Everything else tested is Unpromising or Not viable |
| **Probability of sustainable net profitability** | Informal **35–45%**, up from 20–30%. The historical edge is now robust; the probability is held down by the untested step from others' fills to our own, and by the small capacity |
| **Confidence** | **Medium.** 145 out-of-fit days, a pre-registered test passed on 113 never-seen days across nine coins, three fill models, placebo as expected. Not yet a single real or paper fill of our own |
| **Supporting continued development** | E012 pass; consistent across six months and eight of nine coins (BTC signals rarely; SOL weakest); survives last-in-line and slow fill models; needs only public data and a home PC; fits a few-hundred-dollar bankroll |
| **Against** | Competing takers act within half a second; median fillable size is tens of contracts; the edge could decay as more bots find it, especially now that it has been public; returns are small in dollars even if real |
| **Biggest unresolved risk** | That our own orders, arriving a second or two after the minute mark, fill materially worse than the prints we measured |
| **Recommended decision** | **Continue, narrowed:** close Phase 2, build Phase 3 for S1-D only, prove it in a short Phase 4 paper run |

| Claim | Assessment |
|---|---|
| Technically buildable | Yes |
| Operationally reliable | Yes, with ordinary engineering; about 10 public requests per second |
| Occasionally profitable | Yes — meaningless on its own |
| Statistically credible, repeatable edge | **Yes in history, on modelled fills** (E010, E012) |
| Meaningful returns after costs and risk | Unproven. Backtest illustration at 10 contracts per trade: roughly $20–45 a day before any real-fill haircut |
