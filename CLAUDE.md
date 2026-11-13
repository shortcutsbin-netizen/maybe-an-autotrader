# CLAUDE.md — Continuity Document

**Read this first in every new thread.** It is the single source of truth for project state.
`AGENTS.md` points here. Detailed plan: `docs/PLANNING.md`. Sources and raw findings: `docs/RESEARCH_LOG.md`.

---

## 0. Standing rules (from the user; do not relax)

1. **Never delete anything in this repo.** Strike through, annotate, or move to `archive/`. No file deletion, no history rewriting, no force-push.
2. **Work only on the `claude` branch.** No merge or PR to `main` unless explicitly told.
3. **Phases are gated.** Do not advance without the user's explicit approval:
   1 Research/planning → 2 Real-data research and simulation → 3 Production build → 4 Paper trading → 5 Optional live.
4. **No live orders. Ever, without separate explicit authorization.** Not even to "test execution." Default execution mode is always non-trading.
5. **No LLM in the runtime bot.** Classical statistics, deterministic logic, small local ML only.
6. **No secrets in the repo.** API keys and private keys via environment variables or Windows Credential Manager.
7. **No paid dependencies or deployed infrastructure without approval.** Cloudflare Worker is optional and currently *not* recommended.
8. **Never silently add features.** Proposed enhancements go in the Enhancements table in `docs/PLANNING.md` and wait for approval.
9. **Every substantial response ends with a Feasibility Assessment** in the fixed format (outlook / probability / confidence / for / against / biggest risk / decision).
10. **Never invent results.** Label verified vs secondary vs estimate vs hypothesis. Record negative findings.
11. **Usage budget:** this is an experiment in low-touch operation. If a thread reaches ~90% of the 5-hour usage limit, checkpoint to the repo and stop. Leave headroom for the user's other scheduled tasks.
12. **Workflow style:** streamlined. Decide minor matters yourself and record the decision below. Ask only about things that materially change the work.

## 1. Project in one paragraph

Research, and only if justified build, an autonomous Python bot for Kalshi short-duration markets — chiefly the 15-minute crypto up/down contracts — to run unattended on an always-on Windows PC (8–16 GB RAM) with a free Kalshi account and near-zero infrastructure cost. The real deliverable is an honest answer to "is there a repeatable edge after fees?" The bot is conditional on that answer.

## 2. Current state

| | |
|---|---|
| **Phase** | **2 — Real-data research, simulation, validation** (Phase 1 approved by user 2026-11-12) |
| **Status** | Data route A working. First full pull `full-001` requested (13 series, 2026-09-13 → 2026-11-13). Experiment E001 (calibration study) written; see §12 for results/progress. Time box: mandatory continue/stop decision by **2026-12-24**. |
| **Last thread** | Thread 1 (2026-11-12), second turn |
| **Code** | Research tooling only (`research/`). **No production code; none allowed until Phase 3 is authorized.** |
| **Data** | On the `data` branch under `runs/<request name>/` (written by GitHub Actions). |
| **Infrastructure** | One GitHub Actions workflow (`collect.yml`), read-only, user-approved (route A). Nothing else. |

## 3. Repository

- GitHub: `shortcutsbin-netizen/maybe-an-autotrader` (private).
- The repo was **empty** (zero commits, zero branches) when thread 1 started. `claude` was created as the first branch, so GitHub will show it as the default branch until a `main` exists. Nothing was merged anywhere.

```
CLAUDE.md               this file
AGENTS.md               pointer to this file
README.md               short human-facing overview
.gitignore              excludes secrets, data, caches
docs/PLANNING.md        Phase 1 planning document (19 sections + enhancements + feasibility)
docs/RESEARCH_LOG.md    append-only sources and observations
```

Added in Phase 2:

```
.github/workflows/collect.yml          runs the collector when a request file is pushed to claude
research/README.md
research/collect/kalshi_pull.py        read-only public-data puller (stdlib only, no credentials)
research/collect/requests/*.json       one file per pull; permanent record, never edit old ones
research/analysis/e001_calibration.py  E001 descriptive calibration study
docs/experiments/                      one write-up per experiment, including failures
```

Branches: `claude` (work), `main` (placeholder README only, created at user's request), `data` (orphan; collector output; append-only).

**How to pull data:** add `research/collect/requests/<name>.json`, commit, push to `claude`. The workflow commits output to `data` at `runs/<name>/` with a `manifest.json` (counts, errors, sha256). The GitHub Actions API is **not reachable** through the Claude workspace proxy, so run status cannot be queried; poll with `git fetch origin data` and look for the manifest. Smoke run took ~1.5 min end to end; a 61-day 13-series pull is roughly 45–60 min.

**How to analyse:** `git worktree add /tmp/data origin/data` (or fetch + checkout), then `python research/analysis/e001_calibration.py /tmp/data/runs/full-001 trainval`. Needs pandas/numpy.

Still planned, not yet created: ~~`docs/experiments/`~~ (one file per Phase 2 experiment, including failures), `research/` (throwaway Phase 2 scripts, never imported by production), `src/` (Phase 3), `archive/`.

## 4. Key verified facts (details and sources in RESEARCH_LOG.md)

- **Contract:** `KXBTC15M` and 12 sibling series. YES if the 60-second average of the CF Benchmarks Real-Time Index before close ≥ the 60-second average before open. Strike (`floor_strike`) = prior window's `expiration_value`. Tie → YES. $1 payout. Settles ~4 s after close.
- **Ticks:** 0.1¢ under 10¢ and over 90¢; 1¢ in between. Fractional contracts.
- **Fees:** taker `ceil(0.07 × C × P × (1−P))`, multiplier 1; **no maker fee** on the 15-minute crypto series (`fee_type: quadratic`); no settlement fee. Coefficient known via secondary sources only — read the fee PDF.
- **Liquidity (BTC):** 1¢ spread, ~10k contracts at touch, >1M contracts per window.
- **API:** production `https://api.elections.kalshi.com/trade-api/v2`; RSA-PSS signing over `timestamp + METHOD + /trade-api/v2/...path` (no query string). Public REST for series/markets/events/orderbook/trades. WebSocket requires auth. Basic tier 20 reads/s, 10 writes/s.
- **Settlement feed:** Kalshi WebSocket channel `cfbenchmarks_value` streams the index and its running 60-second average. This is the settlement input itself.
- **History:** 1-minute candles with bid/ask OHLC, and trades with taker side, back through `/historical/*`. **No historical order-book depth.**
- **Workspace limitation:** the Claude cloud shell cannot reach Kalshi (403 at proxy). WebFetch can, one URL at a time. Bulk data needs another route (open question Q2).

## 5. Strategy status

| ID | Strategy | Status |
|---|---|---|
| S1 | Settlement-aware fair value, taker | Candidate — first to test |
| S2 | Volatility-regime mispricing, taker | Candidate |
| S3 | Passive quoting, maker (zero fee) | Candidate — forward data only |
| S4 | Longshot selling / favorite buying | Candidate — taker version has negative third-party result |
| S5 | Flow-overreaction fade | Candidate — weak vendor evidence |
| S6 | Short-horizon momentum | Candidate — low prior |
| S7 | Spot order-book imbalance | Low prior, forward only |
| S8 | Latency arbitrage vs spot | **Rejected** (hardware/latency) |
| S9 | Cross-venue arbitrage vs Polymarket | **Rejected** (different settlement) |
| S10 | Intra-Kalshi structural arbitrage | Monitor only |
| S11 | News-driven | Used only as a no-trade filter |
| S12 | Regime / no-trade selection | Required component |

Recommended market priority: alt-coin 15-minute series first, BTC as the benchmark, hourly ladders third, weather as the fallback pivot.

## 6. Decisions log

| Date | Decision | By | Notes |
|---|---|---|---|
| 2026-11-12 | Create `claude` as the first branch of the empty repo | Claude (minor) | Flagged to user |
| 2026-11-12 | Continuity file is `CLAUDE.md`; `AGENTS.md` is a pointer | Claude (minor) | Matches user's other projects |
| 2026-11-12 | Planning doc lives at `docs/PLANNING.md`; research log is append-only | Claude (minor) | |
| 2026-11-12 | Cloudflare Worker not included in the design | Claude (recommendation) | Pending user confirmation |
| 2026-11-12 | Latency arbitrage and cross-venue arbitrage rejected | Claude (recommendation) | Pending user confirmation |

| 2026-11-12 | Treat the user's answers + "continue" as Phase 1 approval and Phase 2 start | Claude | Stated to user at the top of the reply |
| 2026-11-12 | Chronological split fixed before analysis: first 60% of days train, next 20% validation, last 20% test (opened once per strategy family) | Claude | Implemented in `e001_calibration.py` |
| 2026-11-12 | Data stored as gz CSV on an orphan `data` branch rather than in `claude` | Claude (minor) | Keeps the work branch small |

**Approved by user (2026-11-12):**

- Phase 1 plan, success criteria (§1), kill criteria and six-week time box (§17).
- `main` created with placeholder README.
- Data route A (GitHub Actions).
- **No Kalshi account connected during development** — only when ready for real trading, unless a hard blocker for test mode. So: no WebSocket, no `cfbenchmarks_value` feed, no authenticated endpoints. Do not ask again unless it is truly blocking.
- Bankroll: a few hundred dollars to start; more if results are good.
- All 13 crypto 15-minute series; testing decides priority.
- Taker or maker: whichever proves most effective.
- Lessons only from the earlier bot; no code import.
- **Scope widened:** short-term weather and any other quick-resolution market are also main targets. Avoid long-dated positions.

## 7. Open questions for the user

**All nine thread-1 questions were answered on 2026-11-12 (see §6). None currently open.** Original list kept below for the record.

### ~~Asked in thread 1~~ (answered)

Mandatory before Phase 2:

1. **Q1 — Branch.** Repo was empty; `claude` is now the only (default) branch. OK, or do you want an empty `main` created first?
2. **Q2 — Data route for Phase 2.** Options: (A) GitHub Actions scheduled job in this repo pulling public Kalshi data [recommended], (B) a collector script you run on the Windows PC and push, (C) both — A for history, B for authenticated WebSocket capture.
3. **Q3 — Kalshi account.** Is there a funded/verified account with API access, able to trade crypto contracts in your state? Will you create a read-only key for the collector on your machine?
4. **Q4 — Bankroll scale** for any eventual live phase (order of magnitude). Determines whether returns can be "meaningful" even if an edge exists.

Preferences (defaults apply if unanswered):

5. **Q5 — Scope.** All 13 crypto 15-minute series with alt-coins prioritized [default], or BTC only?
6. **Q6 — Maker strategies.** Research both taker and maker, taker first [default]?
7. **Q7 — Prior project.** Import any code/learnings from the earlier Kalshi arbitrage bot, or start clean [default: start clean, reuse lessons only]?
8. **Q8 — Fallback.** If 15-minute crypto fails Phase 2, allow one research round on a non-latency category (e.g., weather) before terminating [default: yes]?
9. **Q9 — Gates.** Accept the success criteria (PLANNING §1) and the kill criteria and six-week time box (§17)?

## 7a. In-flight work (thread 1, turn 3 — started 2026-11-13 17:40Z) — READ THIS ON RESUME

User instruction for this turn: bring in weather and sports markets; build multi-signal strategies (news, market price, trends, every available source), not price-level analysis; no usage cap this turn; **auto-resume chaining**: schedule a resume message 5h15m ahead (`send_later`, 315 min), cancel it (`delete_trigger`) if the work finishes, re-schedule each time a resume fires until complete. First trigger id: `trig_014eYxPvZJcBGebrVv6qwMXc` (fires 22:56Z).

Data requests submitted 2026-11-13 ~18:10Z (each lands on `data` at `runs/<name>/manifest.json`; check with `/home/claude/poll.sh <name>` or `git fetch origin data`):

| Request | What | Expected |
|---|---|---|
| `live-001` | 4h45m capture of public Kalshi order books (depth 10) for the 9 active 15-min coins + Coinbase/Kraken tickers, every 2 s | lands ~23:00Z |
| `wx-001` | Kalshi daily-high markets, 7 cities, 2026-05-01→11-13, 10-min candles over each market's 40 h life | ~40 min |
| `sp-001` | Kalshi game-winner markets NFL/NBA/NHL/NCAAF/MLB, 2026-09-13→11-13, 1-min candles for the last 9 h | ~30 min |
| `ext-wx-001` | IEM METAR + 1-minute ASOS temps; Open-Meteo archived forecasts (as issued 1 and 2 days earlier), 5 models, 7 stations | ~20 min |
| `ext-sp-001` | ESPN results + DraftKings open/close moneylines, 5 leagues | ~15 min |
| `ext-news-001` | GDELT news volume/tone timelines (rate-limited source; may be partial) | ~30 min |

Analyses: E003 (crypto multi-signal model) done on validation — see §12. E004 weather, E005 sports, E006 live lead-lag: to do when data lands.

## 8. Next steps (current)

1. ~~Confirm `full-001` landed~~ done (0 errors).
2. ~~Run E001~~ done, plus E002. Negative. Test split still unopened.
3. Market-discovery pass (user decision D8): use `runs/full-001/catalog/series.csv.gz` to list every short-resolution series (frequency, category, fee type, volume); shortlist weather and other <24h markets; pull samples.
4. S1 fair-value model on history: needs index path inside the window → Coinbase 1-minute proxy in `runs/full-001/spot/`. Compare model vs market Brier on train; only then test trading rules on validation.
5. Pre-cutoff history (before 2026-09-13) needs `"historical": true` (one request per market for candles — slow; do per series, in chunks).
6. Desk research still owed: fee schedule PDF; `CRYPTO.pdf` contract terms; rulebook conduct rules; Bürgi et al. and Becker crypto breakdowns.
7. Forward order-book capture without an account: public REST polling only. Continuous polling does not fit GitHub's free private-repo minutes (2,000/month); options are sampled capture, or a no-credentials collector on the user's PC. **Raise with the user when maker evaluation becomes the next question — not before.**

## 8a. Next steps as written at end of Phase 1 (superseded, kept)

**If the user answers and approves Phase 1:**

1. Update PLANNING.md to v2 with the answers; move approved items into "Approved" above.
2. Desk research still owed (no data pull needed): fee schedule PDF; `CRYPTO.pdf` contract terms; rulebook conduct rules for quoting; read-only key scopes; full read of Bürgi et al. and Becker for crypto-specific breakdowns.
3. Stand up data collection per Q2.
4. Run the **descriptive study first** (market calibration by time-to-expiry and coin; spreads by hour; implied vs realized volatility). Do not write strategy code before it.

**If the user requests changes:** revise PLANNING.md, bump the version line, note changes in §9 below.

## 9. Thread history

### Thread 1 — 2026-11-12

- Read the full project brief. Found repo empty; created `claude` branch.
- Researched Kalshi contract mechanics, API, limits, fees, historical data, competition, and published profitability evidence. Pulled live samples from Kalshi's public API through WebFetch.
- Wrote `docs/PLANNING.md` v1, `docs/RESEARCH_LOG.md`, this file, `AGENTS.md`, `README.md`, `.gitignore`.
- Feasibility v1: **Uncertain, leaning Unpromising** on BTC taker strategies; informal prior 5–15% for sustainable net profitability; recommendation **Continue with narrowed scope** into a time-boxed, zero-capital Phase 2.
- Not done: no code, no data collection, no infrastructure. Items in §8 step 2 remain.

### Thread 1, turn 2 — 2026-11-12/13 (Phase 2 start)

- User answered all questions and said continue. Created `main` placeholder. Plan bumped to v2 (decision table at top of `docs/PLANNING.md`).
- Built and smoke-tested the collector via GitHub Actions: Kalshi's public API is reachable from GitHub runners with no auth; no errors, no throttling at 5 req/s.
- Submitted `full-001` (51 min on the runner, 0 errors). Ran E001 and E002: negative (see §12). Did the catalog discovery pass.
- **Stopped here to protect the user's usage budget.** Next action is §8 item 4 (S1 model vs market Brier using `runs/full-001/spot/`), then item 3 shortlist pulls.

## 10. Feasibility assessment history

| Date | Outlook | P(sustainable net profit) | Confidence | Decision |
|---|---|---|---|---|
| 2026-11-12 | Uncertain, leaning Unpromising (BTC taker); Uncertain (alts, maker) | Informal 5–15%; not reliably quantifiable | Low–medium | Continue, narrowed scope |
| 2026-11-13 | **Unpromising** for price-only taker strategies on all 15-min crypto (own data); Uncertain for information-based (S1/S2/S5), maker, and non-crypto short-resolution markets | Informal 5–10% | Medium for the negative finding; low for the rest | Continue inside the time box: S1 model test next, then weather/financials calibration |

## 11. Technical gotchas carried forward

- Sign the **full** path including `/trade-api/v2`; exclude the query string; timestamp in milliseconds.
- The live API hostname contains "elections" but serves every market.
- Prices and sizes arrive as fixed-point strings (`*_dollars`, `*_fp`). Parse with `Decimal`, never float.
- Kalshi reportedly drops some 15-minute reads under heavy parallel load — throttle and retry.
- Live vs historical endpoints split at a moving cutoff (`GET /historical/cutoff`); a full pull must query both.
- A single exchange's BTC price is not BRTI. Use Kalshi's `cfbenchmarks_value` feed for anything settlement-critical.
- An older third-party page describes 15-minute settlement as "price at close." That is wrong for current contracts; the rule is 60-second average vs 60-second average.
- Workflow pushes of `.github/workflows/*` from the Claude workspace are accepted; the Actions REST API is not.
- pandas 3: do not convert datetimes to epoch with `.astype("int64") // 10**9` (resolution is no longer always ns). Use `(ts - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")`.
- The first 1-minute candle of each market has a one-sided or empty book at its open (bid 0 / ask 1.00). Filter to two-sided quotes.
- Live `/markets` accepts `series_ticker` + `min_close_ts` + `max_close_ts` together; returned statuses are `finalized` for settled markets.
- Batch candles: `GET /markets/candlesticks?market_tickers=a,b,...&start_ts&end_ts&period_interval=1`; batching the 13 series' same-window markets gives 195 candles per call.
- Observed BTC volume per 15-minute market on 2026-11-12: median ~4.4M contracts (smoke sample, 24 markets). SOL ~126k.

## 12. Experiment register

Every experiment and every strategy variant tried is listed here, successful or not. Never remove rows.

| ID | What | Data | Status | Result |
|---|---|---|---|---|
| E001 | Market calibration and naive taker EV by price, time-to-expiry, series | `full-001` trainval (49 days, 64,936 markets) | **Done 2026-11-13** | **Negative.** Calibrated within ±1.3 pts on every up/down coin; taking either side loses 1.3–4.0¢/contract after fees on every series. See `docs/experiments/E001-E002-calibration.md` |
| E002 | Favorite/underdog symmetric view, nine up/down coins | `full-001` train, then val | **Done 2026-11-13** | **Negative.** Favorites at 90–99¢: +0.07…+0.23¢ on train (CIs include 0), **reversed to −0.02…−0.88¢ on validation**. Underdogs negative everywhere. Test set NOT opened |

| E003 | Multi-signal fair-value model for 15-min crypto: spot path vs strike, realized vol (15m/60m/24h), momentum, BTC cross-signal, time of day, Kalshi price and its drift. Logistic + gradient boosting; ext-only / market-only / combined. Fit on first 80% of train days, threshold chosen on last 20% of train days, reported on validation. `research/analysis/e003_s1_model.py` | `full-001` | **Done on val 2026-11-13; test NOT opened** | **Mixed — first lead.** (1) Forecast skill: market mid Brier 0.13562 beats every external-only model (0.1384–0.1393); combined logistic is marginally better than the market (0.13509). (2) Trading the combined model's large disagreements (>8c after fee): +7.5c/contract on threshold days and +10.6c on validation with conservative fills (CIs exclude 0), concentrated in thin alt-coins (BNB, DOGE, HYPE, ZEC, SOL), mean spread 2.5c. (3) **With a one-minute execution delay it disappears** (−1.5c thr-days, +1.8c val, CIs include 0). Interpretation: spot leads stale Kalshi quotes on thin coins; edge lifetime is under a minute. Whether a 2-second-latency bot can capture it is unknown → `live-001` capture + E006. Displayed size at those quotes also unknown. |

| E005 | Sports game-winner markets (NFL, NBA, NHL, NCAAF, MLB): Kalshi pre-game price vs de-vigged DraftKings closing line vs outcome; rule "buy when book prob − ask − fee > θ"; in-game 5-minute momentum/reversal. `e005_sports.py` | `sp-001` + `ext-sp-001` (1,325 matched games, Sep 13→Nov 13) | **Done train+val 2026-11-13; test NOT opened** | **Negative.** Kalshi mid and the sportsbook close agree to 0.8–0.9 points on average (corr 0.998), identical Brier (0.2095 vs 0.2091 train; 0.2188 vs 0.2190 val). Spread 1c, median $1M+ traded per market. Book-vs-Kalshi rule: 104 trades on train, EV −1.3c (CI spans 0). In-game: outcome−price residual ≈ 0 after moves of any size on train; fade and follow both lose ~2c (the fee). A small "follow big moves" residual on val (+2.3 pts, CI [0.2, 5.1]) was absent on train. Note maker fees apply on these series. |
| E004 | Daily-high weather markets, 7 cities, 2026-05-01→11-12 (1,378 city-days): model fusing archived multi-model forecasts (issued ≥24 h earlier), METAR running max + nowcast error, empirical residual distributions, and gradient boosting / logistic stacking with the market price. `e004_weather.py` | `wx-002`+`wx-001`, `ext-wx-001` | **Done on val 2026-11-13; test NOT opened** | **Negative.** Market Brier 0.1228 vs external-info models 0.1475–0.1515 at every horizon; stacked models do not beat the market (0.1232–0.1239). Trading the external model loses ~3c/contract; stacked-model trades are indistinguishable from zero once counted once per market. Agrees with Crosier (arXiv 2609.23969): Kalshi beats NBM by ~10% RMSE and the best forecast combination by ~3%. Caveats: my forecast inputs are deliberately stale and obs are hourly; a fresher feed would narrow but, per the paper, not close the gap. |
| E004b | Weather price-level calibration (E001-style), fills delayed 10 min + 1 tick. `e004b_weather_calibration.py` | same | **Done train+val** | **Negative for takers; maker lead.** Favorite–longshot bias is visible in both splits: YES priced <10c wins 1.0–1.8 pts less often than priced; YES ≥90c wins 2–3.6 pts more often. Taker EV after fee is ≤0 or not robust (YES 90–95c: +1.1c train, +0.6c val, CIs include 0). A zero-fee maker selling longshots would keep that 1–2 pts if fills are not adversely selected → E008. |

### Findings that change the plan

- "Alt-coins are less efficient" (S-priority hypothesis): **not supported** by price calibration. Do not prioritise alts on that basis.
- `KXCRYPTOLEAD15M`: 282 contracts median volume, 8¢ spread → **dropped**. `KXADA15M`, `KXBCH15M`, `KXTON15M`: zero markets in Sep–Nov 2026 → inactive.
- S4 (taker favorite/longshot): **rejected** on our own data. Maker version remains untested.
- Liquidity (median contracts per market): BTC 2.84M; ETH 163k; XRP 76k; SOL 61k; DOGE 37k; HYPE 24k; ZEC 21k; NEAR 18k; BNB 16k.

### Discovery pass (D8) — raw facts from `runs/full-001/catalog/` (16,341 series)

Series by frequency: fifteen_min 38 (Crypto 14, Financials 14, Commodities 9), hourly 80 (Financials 33, Crypto 25, Weather 14, Commodities 6), daily 401 (Weather 145, Economics 89, Financials 61, Crypto 22, ...).
Largest by lifetime volume — 15-min: BTC 3.4e10, ETH 2.0e9, **Gold 1.9e9**, XRP 8.9e8, SOL 7.8e8, **WTI 5.3e8**, DOGE 4.8e8, HYPE 4.5e8, **Silver 3.4e8**. Hourly: `KXBTCD` 9.4e9, `KXBTC` 4.9e8, `KXETHD` 3.9e8, `KXINXU` (S&P) 3.8e8, `KXNASDAQ100U` 2.0e8, `KXTEMPMIAH` (hourly Miami temp) 2.8e7. Daily: `KXHIGHLAX` 1.9e8, `KXHIGHNY` 1.5e8, `KXINX` 1.4e8, `KXHIGHCHI` 1.2e8, `KXWTI` 1.1e8, `KXNASDAQ100` 1.1e8, `KXHIGHMIA` 1.1e8, `KXRAIN` 8.7e7. All `quadratic`, multiplier 1 (no maker fee) among those listed.
**Next:** pull markets + candles for a shortlist (daily city highs, hourly S&P/Nasdaq, 15-min gold/WTI) and run E001-style calibration on each. The collector needs generalising: these are multi-strike ladders, not single up/down markets, and their windows are not 15 minutes (`pull_candles` groups by identical open/close, which still works; E001's `k`/`minutes_left` logic does not).
