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
| **Status** | **Round 4 (strategy-surface sweep, 2026-11-22) essentially complete: nothing new survives on its own; S1-D gains two validated options — a 4–8c secondary band (E016c) and maker entry (E016b). Recommendation unchanged: build S1-D only. Awaiting §7 answers.** Previous: **Testing round 3 complete (2026-11-21). Recommending Phase 2 close and a narrow Phase 3 build (dislocation rule only); awaiting user authorization** — see §7. E012 (pre-registered, 113 never-seen days, nine coins) PASSED: +9.6c/contract [+7.8, +11.4]. E013 weather maker FAILED; E014 in-game sports negative. Only S1-D survives. Time box: continue/stop decision by **2026-12-24**. |
| **Last thread** | Thread 1, turn 5 (2026-11-22 10:10Z → ~13:30Z+, resume chain), on Opus 5.5. Before that: turn 4 (2026-11-21 05:15Z → ~07:30Z), **on Opus 5.5** (moved from Fable 5.2; commit trailer now `Co-Authored-By: Claude Opus 5.5`) |
| **Code** | Research tooling only (`research/`). **No production code; none allowed until Phase 3 is authorized.** |
| **Data** | On the `data` branch under `runs/<request name>/` (written by GitHub Actions). |
| **Infrastructure** | One GitHub Actions workflow (`collect.yml`), read-only. **Repository is PUBLIC since ~2026-11-20 (user's choice, for unlimited Actions minutes).** Claude recommended on 2026-11-21 making it private again now; the user will do it. While public: never commit anything sensitive, and remember the rule details are visible. |

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

Added in testing round 2 (2026-11-13):

```
research/collect/kalshi_events_pull.py   ladders and game markets: settled markets + candles (live and /historical), resampling, lookback window
research/collect/ext_pull.py             IEM METAR / 1-min ASOS, Open-Meteo archived forecasts, ESPN results + sportsbook odds, GDELT timelines
research/collect/live_capture.py         public order books + Coinbase/Kraken tickers every ~2 s (no account)
research/collect/kalshi_trades_pull.py   public trade prints for a ticker list; split output; time-boxed
research/collect/probe.py                fetch arbitrary public URLs on a runner to learn response formats
research/collect/requests/lists_*.txt    ticker lists used by trade pulls
research/analysis/e002 … e011_*.py       one script per experiment (see §12)
docs/experiments/*.md                    E001-E002, E003, E004, E005, E006-E011 (dislocation), E007-E009 (microstructure), E008 (weather maker)
docs/experiments/output/                 raw text output of every run, frozen-rule signal lists
```

Data runs on the `data` branch (`runs/<name>/`): `full-001` (crypto candles+spot+catalog, 61 days), `full-002`/`full-003` (candles for the live window), `live-001` (order books), `wx-001`/`wx-002` (weather markets), `ext-wx-001` (obs+forecasts), `sp-001`, `ext-sp-001` (sports), `trades-003`/`-004`/`-005` (crypto prints), `wx-trades-002` (weather prints), `probe-002`, smoke runs. Local helper used in this workspace: `/home/claude/poll.sh <run>` waits for a run's manifest and checks out the data branch at `/home/claude/data/wt`.

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

~~Recommended market priority: alt-coin 15-minute series first, BTC as the benchmark, hourly ladders third, weather as the fallback pivot.~~ (superseded)

**Status after testing round 4 (2026-11-22) — authoritative:** S1-D primary (8c, alt coins, exclude BTC); **S1-D-4** (4–8c band, +6.3/+6.6c per fill post-hoc) and **S1-D-M** (maker entry, +6.1c/signal) as pre-registered Phase-4 secondaries; S1-D-L (BNB/DOGE ladder strikes) observe-only. Rejected in round 4: ladder box/monotone/relative-value arbitrage (E015), deep model-informed making (E017), 15-min commodities/FX/yields (E018; Pyth feed paid), hourly temperature vs Kalshi Weather Index (E019), Polymarket as input (E020), bucket-sum arbitrage, incentive farming (out of scope). Details: `docs/experiments/E015-E020-round4-strategy-surface.md`, PLANNING v5.

~~**Status after testing round 3 (2026-11-21) — authoritative:**~~ (superseded by round 4) only **S1-D** survives (E012 pass). S4-M rejected (E013 fail). Sports closed (E005, E014). The round-2 table below is kept for history; where it says "lead" for S4-M, read "rejected".

**Status after testing round 2 (2026-11-13):**

| ID | Strategy | Status |
|---|---|---|
| S1 | Fair-value model trading all disagreements | Rejected as a general strategy (E003, E007) |
| **S1-D** | **Dislocation rule** — frozen logistic stack (market + spot/vol/momentum/BTC features), trade only when edge > 8c, enter within seconds, hold to settlement | **LEAD.** E010 test split +11.0c/contract [+4.0, +18.4]; decays over 10–20 s; fills modelled from others' prints. Needs forward paper test on the real book |
| S3 | Passive quoting, 15-min crypto | **Rejected** (E009: −1.1c markout per fill on the real book) |
| S4 | Favorite/longshot as taker | Rejected (E002, E004b) |
| **S4-M** | Favorite-side resting orders in weather (buy YES ≥ 90c, sell YES ≤ 20c) | Secondary lead (E008); thin evidence |
| S5 | Flow fade | Subsumed by S1-D |
| S6, S7 | Momentum; spot book imbalance | No evidence / untested; quotes follow spot within 2 s |
| S8, S9 | Latency, cross-venue arbitrage | Rejected |
| S11 | Text news | Feed (GDELT) rate-limited; untested |
| — | **Sports** | **Dropped** (E005) |
| — | Weather as taker | Rejected (E004) |

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

| 2026-11-13 | Test split for the E003/E010 strategy family opened exactly once, on a rule frozen and committed beforehand (commit `9ac0a11`) | Claude | Result recorded in §12; do not re-tune that rule on test |
| 2026-11-13 | Sports dropped; weather taker strategies dropped; naive crypto market making dropped | Claude (recommendation, evidence in §12) | Pending user confirmation |
| 2026-11-13 | Trade puller now splits output files (<100 MB) and is time-boxed (`max_minutes`) | Claude (minor) | After three jobs failed to publish |

| 2026-11-21 | Pre-registered E012/E013 (commit `457f237`) before pulling data; signals committed before their trade prints | Claude | Keeps round 3 honest |
| 2026-11-21 | E013 failed → weather maker rejected; E014 negative → sports closed; S1-D the only surviving strategy | Claude (on evidence; consistent with user D16) | |
| 2026-11-21 | Recommend repo be made private again now | Claude (recommendation to user) | User performs it |

**User decisions 2026-11-20 (turn 4):** (1) **no** multi-week forward test before the build — for larger samples, pull recent history; (2) repo made **public** for Actions minutes, to be made private when Claude says it is no longer needed; (3) weather history re-pull approved; (4) drop sports / weather-taker / naive market making only if absolutely not feasible. Also: work moved to Opus 5.5. Auto-resume chaining was **not** requested this turn (it applies only when the user asks for it).

**User direction 2026-11-13 (turn 3):** bring in weather and sports; strategies must fuse all available information (market price, outside data, trends, news), not price level alone; no usage cap for that turn; **auto-resume chaining** — at the start of a long turn schedule `send_later` 315 minutes ahead with a resume prompt, cancel it (`delete_trigger`) when the work completes, and re-schedule each time a resume fires. If unsure how this works, ask before working.

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

**Open as of 2026-11-22 (re-asked at the end of turn 5; turn-4 versions below are superseded):**

1. **Authorize Phase 3 (mandatory).** Build the S1-D bot per PLANNING v4+v5: primary rule plus the S1-D-4 and S1-D-M paper variants and S1-D-L observe-only logging; background-friendly runtime (R-BG). Paper only; no live-order code.
2. **Phase 4 bar (mandatory).** v5: run ≥ 3 days and until ≥ 300 primary signals (≈ 4–7 days), background on the daily-use PC; pass = primary paper P&L > 0 with CI lower bound > 0, ≥ 50% fillable at 10 contracts, feature parity, R-BG met. Default: this.
3. **Make the repo private (recommendation, repeated).** Round-4 pulls are finished (except two late jobs).
4. **Read-only Kalshi key in Phase 4 (optional).** Default: no key.

**~~Open as of 2026-11-21 (asked at the end of turn 4):~~**

1. **Authorize Phase 3 (mandatory).** Build only the S1-D bot as scoped in `docs/PLANNING.md` v4: public-data feeds, frozen model, paper executor, risk gate, SQLite/JSONL, CLI, Windows Task Scheduler, tests. No live-order code.
2. **Phase 4 bar (mandatory, shapes Phase 4).** Short paper run: ≥ 300 signals (~7–10 days), pass if simulated-fill P&L > 0 with CI lower bound > 0, ≥ 50% fillable at 10 contracts, live-vs-rebuilt feature parity. Default: this bar.
3. **Make the repo private (recommendation).** Heavy pulls are done.
4. **Kalshi read-only key in Phase 4 (optional).** Faster WebSocket data and the real settlement index; contradicts "no account until live" unless the user agrees. Default: no key.

### ~~Open as of 2026-11-13~~ (answered 2026-11-20: 1 no; 2 repo public; 3 yes; 4 drop only if absolutely not feasible)


1. **Forward paper test (mandatory to progress).** Approve building a read-only observer/paper trader for the dislocation rule to run on the always-on PC for 2–4 weeks (no account, no orders)? This pulls a slice of Phases 3–4 forward for one strategy (enhancement E6). Default if declined: keep doing bounded captures on GitHub Actions, which is slow and limited by minutes.
2. **GitHub Actions minutes (mandatory).** This round likely used most of the month's free private-repo minutes. Options: (a) wait for the reset and stay frugal [default], (b) make the repo public (unlimited minutes; research becomes visible), (c) move collection to the PC (fits question 1).
3. **Weather maker lead (optional).** Spend ~90 Actions minutes re-pulling pre-September weather trades to triple the sample? Default: yes once minutes allow.
4. **Confirm drops (optional).** Sports, weather-as-taker and naive crypto market making removed from scope. Default: yes.

Thread-1 questions (all answered 2026-11-12) are kept below for the record.

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

## 7b. In-flight work (thread 1, turn 5 — round 4, started 2026-11-22 10:10Z) — READ THIS ON RESUME

**User instruction (2026-11-22, 04:10 local = UTC−6):** before building, expand and find **all valid strategies**; research extensively and take actions to maximize the strategy surface. Phase 4 test time: **a few days is ideal; longer is fine if the bot runs reliably in the background while the user uses the PC day to day** (→ design requirement: low CPU/RAM, no interference, unattended). **Auto-resume this turn:** first resume at 08:45 local = **14:45Z** (trigger `trig_011oFmtvqGy1NB68BPG4WXnh`); each later resume 5h15m after the previous one's fire time (20:00Z, 01:15Z, ...); cancel the pending one when the work is complete. §7 questions 1–4 remain open (Phase 3 not yet authorized; repo still public on 2026-11-22; no key).

**Round 4 plan (strategy surface):**

| Code | Idea | Data | Status |
|---|---|---|---|
| E015 | Cross-market: 15-min crypto vs hourly above/below ladders (KXBTCD, KXETHD, KXSOLD, KXXRPD, KXDOGED, KXHYPED, KXBNBD) that settle on the **same** 60-s CF average at the hour → (a) riskless two-leg box arbitrage, (b) relative-value mispricing, (c) within-ladder monotonicity arbitrage | `ladder-<coin>-002` (001 kept 0 markets: ladder strikes live in `custom_strike`) | **Alts+ETH done 11:30Z: negative.** No after-fee box/monotone arbitrage (≤3 quotes in 2 months per coin); 15-min mid beats ladder-implied; reverse rule noisy. E015b (frozen S1-D on ladder strikes, candle fills): ETH/SOL/XRP/HYPE ≤0; **BNB +12c next-minute fill (52 sig, both halves +), DOGE +13c (16, CI spans 0)**, ~10 contracts/min liquidity. BTC ladder pending |
| E016 | Dislocation entry with early exit (sell the rebound instead of holding) | existing prints | **Done.** Hold best (+10.0c early / +9.6c late); time exits lower EV, lower variance. **E016b maker entry** (rest 1 tick inside, 5–60 s): fills 67–83%, +7.9c/fill (through), +6.1c/signal, positive in all six sets. E016c (threshold 4c sensitivity): prints `trades-thr04-0..2` pending |
| E017 | Model-informed deep resting orders on 15-min crypto (zero maker fee) — catch dislocations as a maker | `trades-sample-*` (all markets on sample days); q in `/home/claude/e017_q.csv.gz` | **Val (group 2) negative:** −2…−3c per fill at every delta, model ≈ mid control. Groups 0,1 pending; test not to be opened if val negative |
| E018 | 15-min commodities / FX / index / yields (Pyth-settled) — calibration + dislocation analogue with Pyth 1-min history | `fin15-001`, `fin15-002` | **Negative / blocked.** Pyth history & Hermes need a paid key ($500/mo) since 2026-08-26; PAXG proxy too thin. Calibrated, taker EV < 0 everywhere; book-only + cross-market models no signals / negative |
| E019 | Hourly temp markets vs public **Kalshi Weather Index** (`/live_data/weather/{city}`, settles them exactly) | `wxh-001`, `windex-001` | **Negative.** Stack beats mid in-sample only; val trades −2…−9c at lags 1–5 min; ~10 contracts/min. Hypothesis kept: last-5-min nowcast at 1-min lag |
| E020 | Polymarket price as an extra signal | `poly-<coin>-001` (Jun 1–Nov 21, 9 jobs) | pending (puller works; ~2–3 h) |
| — | Literature / public-evidence sweep for further ideas | web | Done: Liquidity Incentive Program (public `/incentive_programs`) — 7k programs, none on 15-min crypto/hourly weather (long-dated markets only); Bürgi et al.; Pyth paywall. Also: bucket-sum arbitrage on daily weather brackets is rare (≤1c median); `ranges-001` pending |

## 7a. ~~In-flight work~~ (thread 1, turn 3) — COMPLETED 2026-11-13 ~23:45Z; kept for the record

**Nothing is in flight.** Jobs `trades-001`, `trades-002`, `wx-trades-001` and `ext-news-001` never published (first three: output file over GitHub's 100 MB limit; news: source rate-limited) and may still have been burning Actions minutes until their 350-minute timeouts (~01:20Z on 2026-11-14 at the latest). Their request files stay in the repo as a record. Do not wait for them.

### Original note

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

## 8. Next steps (current, as of 2026-11-22 turn 5)

Same as the 2026-11-21 list below, plus: (a) the paper executor runs three variants side by side on the same signals — taker F1-style (primary), maker entry (bid 1 tick inside the ask, 15 s), and the 4–8c band — all pre-registered in a Phase-4 pre-registration file committed before the run; (b) BTC excluded; (c) S1-D-L logs ladder strikes for BNB/DOGE only; (d) runtime requirement R-BG (PLANNING v5): < 2% CPU, < 300 MB RAM, logon start, sleep/network-loss tolerant, `status` command; (e) Phase 4 runs ≥ 3 days and until ≥ 300 primary signals.

## 8-old3. Next steps as of 2026-11-21 end of turn 4 (kept; still valid as the base list)

**Blocked on §7 question 1.** If Phase 3 is authorized:

1. New top-level package `bot/` (production; never imports `research/`). Export the frozen model: refit exactly as `e012_frozen_new_periods.fit_frozen` (full-001, 2026-09-13→10-11), dump scaler means/scales and logistic coefficients to `bot/model/frozen_s1d.json` with a hash; a unit test asserts the JSON model reproduces `predict_proba` on saved rows.
2. Feature engine must reproduce `e003_s1_model.build` exactly from live buffers (minute-end Kalshi quote, Kalshi per-minute volume, Coinbase minute closes/OHLC/volume, BTC cross-signal). Build a replay harness that feeds historical candles through the live code path and compares features to `build()` output row by row.
3. Paper executor: IOC at quote+2c against the displayed book at decision time + measured latency; record displayed size; later reconcile against public trade prints (F1/F2/F3 as in E012).
4. Risk gate, settlement via next strike, SQLite schema, JSONL logs with rotation, CLI, `doctor` (clock, connectivity, rate limits), Task Scheduler instructions, tests.
5. Then Phase 4 per the agreed bar.

~~SOL supplement~~ done: SOL added to E012 (nine-coin result in the report).

## 8-old2. Next steps as of 2026-11-13 end of turn 3 (superseded, kept)

**Blocked on the user's answers to §7 questions 1–2.** Then:

1. If the forward test is approved: write `observer/` (separate from `research/`, still no order code): poll public order books for the nine 15-min coins and Coinbase tickers at ~1 s; compute E003 features continuously (spot vs strike proxy, rolling vol from 1-minute closes, momentum, BTC z, Kalshi mid/spread/drift/volume from polled books and trades); apply the **frozen** logistic model (persist coefficients and scaler from `e010_dislocation_frozen.py` fit on `full-001`, 2026-09-13→10-11); on edge > 8c log the displayed ask and size at 0/1/2/3/5/10 s and the settlement outcome; SQLite + JSONL; Windows Task Scheduler. Success test: ≥ 500 signals, mean P&L at the +2 s displayed ask > 0 with CI lower bound above 0, and median displayed size ≥ 20 contracts.
2. Do not re-tune the rule on the test split. Any new variant needs fresh data (the forward test supplies it).
3. Weather maker (S4-M): re-pull pre-September trades in split files (`kalshi_trades_pull.py` handles `/historical/trades`; field names differ there) when minutes allow; re-run `e008_maker_sim.py weather` on a longer train/val; test split still unopened for weather.
4. Still owed from Phase 1: `CRYPTO.pdf` contract terms; rulebook conduct rules (relevant only if making); Bürgi/Becker crypto breakdowns. Fee PDF is done.
5. Untested ideas, low priority: 15-minute gold/WTI/silver and hourly index markets (same dislocation idea, needs a spot proxy); text-news feed.

## 8-old. Next steps as of the start of turn 3 (superseded, kept)

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

### Thread 1, turn 3 — 2026-11-13 17:40Z → 2026-11-13 ~23:45Z (testing round 2)

- User: add weather and sports, fuse all information sources, no usage cap, auto-resume chaining. Session was interrupted once (~19:55Z) and resumed by the scheduled trigger at 22:56Z; a second trigger was scheduled and cancelled at completion.
- Built collectors: `kalshi_events_pull.py` (ladders/games, live + historical), `ext_pull.py` (IEM obs, Open-Meteo archived forecasts, ESPN odds, GDELT), `live_capture.py` (public books + spot every 2 s), `kalshi_trades_pull.py`, `probe.py`.
- Ran E003–E011 (§12). Opened the crypto test split once for the frozen dislocation rule.
- Verified the fee schedule PDF directly; found the weather settlement-source change; verified candle and spot timestamps against the live capture.
- Mistakes worth remembering: three long trade pulls could never publish (file > 100 MB) and wasted Actions minutes; the first weather pull lost its history because historical endpoints use different field names.
- Wrote plan v3, six experiment reports, research-log session 2.

### Thread 1, turn 5 — 2026-11-22 10:10Z → (resume chain) (testing round 4, Opus 5.5)

- User: find all valid strategies before the build; Phase 4 a few days, longer if it runs in the background; schedule/resume across usage windows (first resume 14:45Z).
- Built `poly_pull.py`, `kalshi_windex_pull.py`; fixed ladder strike parsing; `spot_extra`, METAR report types.
- Ran E015, E015b, E016b, E016c, E017 (val), E018, E019, E020, bucket-sum checks, incentive/literature sweep. Wrote the round-4 report, PLANNING v5, research-log session 4.
- Pending at write time: `ladder-btc-002` (E015 BTC), `trades-sample-0/1` (E017 train).

### Thread 1, turn 4 — 2026-11-21 05:15Z → ~07:30Z (testing round 3, Opus 5.5)

- User declined the forward test, made the repo public, approved the weather re-pull, and asked that drops happen only if absolutely not feasible.
- Pre-registered E012/E013 (commit `457f237`) before pulling data. Pulled 104 days of crypto history for all nine coins (SOL needed a resubmit), 8 new days of crypto, weather trade prints May–Sep and Nov, ESPN win probability for 961 games.
- E012 **passed**; E013 **failed**; E014 negative; news-volume check null.
- Wrote E012, E013, E014 reports and the pre-registration; plan v4; this file; research-log session 3.

## 10. Feasibility assessment history

(2026-11-22, round 4: **Promising — one narrow strategy family**; P ≈ 40–50% informal; medium confidence; decision: continue, build S1-D only — see the row at the bottom.)

| Date | Outlook | P(sustainable net profit) | Confidence | Decision |
|---|---|---|---|---|
| 2026-11-12 | Uncertain, leaning Unpromising (BTC taker); Uncertain (alts, maker) | Informal 5–15%; not reliably quantifiable | Low–medium | Continue, narrowed scope |
| 2026-11-13 | **Unpromising** for price-only taker strategies on all 15-min crypto (own data); Uncertain for information-based (S1/S2/S5), maker, and non-crypto short-resolution markets | Informal 5–10% | Medium for the negative finding; low for the rest | Continue inside the time box: S1 model test next, then weather/financials calibration |
| 2026-11-21 (round 3) | **Promising — one narrow strategy** (E012 pre-registered pass on 113 unseen days); all else rejected | Informal 35–45% | Medium | Continue, narrowed: close Phase 2, build S1-D only, short Phase 4 paper run |
| 2026-11-22 (round 4) | **Promising — one narrow strategy family** (S1-D; round 4 found no independent second strategy but two validated S1-D options: lower threshold ~3× volume, maker entry) | Informal 40–50% | Medium | Continue, narrowed: build S1-D with variants; short background Phase 4 |
| 2026-11-13 (round 2) | **Uncertain — one narrow strategy Promising** (dislocation rule, +11c/contract on the test split with modelled fills); sports, weather-taker, general crypto forecasting and naive market making Unpromising/Not viable | Informal 20–30%, resting almost entirely on the forward test | Medium on the negatives; low–medium on the lead | Continue, narrowed: forward paper test of the dislocation rule; weather favorite-side making secondary |

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

| E006 | E003's large-disagreement signals checked against real trade prints: what did takers on the same side actually pay 0.5–45 s after each signal? `e006_signal_trades.py` | `trades-003` (thr+val signal markets), `trades-005` (test) | **Done** | **Positive.** Thr+val (1,092 signals): first same-side print at +1 s → +9.95c/contract, +2 s +9.07c, +5 s +7.62c, +10 s +6.36c, +30 s +3.45c. Test (636): +11.35c at 1 s [+4.9, +17.4], +8.73c at 5 s, +2.98c at 30 s. Median first print 0.2–0.5 s after the minute mark. Placebo (random side, non-signal minutes, same markets, same machinery): −1.24c. |
| E007 | Live order book, 4h45m, nine coins, 2 s cadence: touch size, quote speed, closed-form model on the real book. `e007_live_leadlag.py` | `live-001` | **Done** | Descriptive. Touch size: BTC ~4,700; ETH ~500; XRP ~250; SOL ~190; HYPE/BNB/ZEC/DOGE/NEAR 30–70 contracts. Quotes absorb a spot move within the same 2-second poll (80–100%). Φ(z) on the live book: no edge (−0.1…−1.0c, se 3–6c). |
| E007b | Candle close quotes vs the captured book. `e007b_candle_vs_book.py` | `full-002` + `live-001` | **Done** | Candle closes are the true book at the minute end (0.65c mean difference; 9c if compared 60 s earlier). |
| E008 | Maker simulation from trade prints, weather (touch / through / improve fill rules, 30-minute orders). `e008_maker_sim.py` | `wx-001` + `wx-trades-002` (post-cutoff only: train 09-06→10-15, val 10-16→10-29) | **Done train+val; test NOT opened** | **Secondary lead.** Passive quoting overall ≈ 0 to −1c. Favorite-side orders positive in both periods under all three rules: buy YES ≥ 90c +1.8…+3.1c train, +3.6…+4.4c val (val CIs exclude 0; 10–22 fills/day; win 96–98%); sell YES ≤ 10c +0.2…+1.7c train, +1.2…+1.8c val (CIs include 0); sell YES 10–20c +3.3c train, +5.5c val. Longshot-side orders lose. |
| E009 | Maker simulation on the live capture with real queue sizes (10-contract orders every 10 s, 30 s life). `e009_live_maker.py` | `live-001` + `trades-004` | **Done** | **Negative.** 81% of orders fill; mid 10 s after fill is 1.11c against us (se 0.06) vs 0.52c half-spread earned; every coin and price bucket negative. |
| E010 | **Frozen dislocation rule** (definition committed in `9ac0a11` before opening test): logistic stack fit 09-13→10-11; edge > 8c; IOC at quote + 2c; fill = same-side taker VWAP in (t+1 s, t+6 s]; hold to settlement. `e010_dislocation_frozen.py` | signals from `full-001`; prints `trades-003`, `trades-005` | **Done — TEST SPLIT OPENED ONCE (2026-11-13). Do not tune on it again.** | **Positive.** Threshold days +9.74c [+7.41, +12.68] (305 fills); validation +11.34c [+6.62, +16.34] (513); **test +11.01c [+3.97, +18.37] (497 fills, 10 of 12 days positive)**; one trade per market on test +10.26c [+4.45, +16.12]. ~53 signals/day; BNB and DOGE positive in all three periods. Fills are modelled from others' prints. |
| E011 | Frozen rule applied to the live-capture window, read against the real displayed book. `e011_frozen_on_live_book.py` | `full-003` + `live-001` | **Done** | 9 signals in 4h45m; buying the displayed ask 0–10 s later averaged +7.5…+10c with se ~19c (uninformative statistically); displayed size 13–390 contracts, occasionally 0–1. |

| E012 | **Frozen dislocation rule on never-seen periods (pre-registered, `457f237`)**: P = 2026-06-01→09-12 via history endpoints (nine coins; SOL via resubmitted `hist-sol-002` + `trades-psol`), Q = 11-13→11-21. Fill models F1 (VWAP 1–6 s ≤ quote+2c), F2 (worst price, ≥ 20 printed), F3 (first print after 3 s). `e012_frozen_new_periods.py`, `e012b_placebo.py` | `hist-*-001`, `trades-p0/p1/p2`, `full-004`, `trades-006` | **Done 2026-11-21 — PASS** | P ∪ Q, nine coins: F1 **+9.63c [+7.84, +11.36]** (3,729 fills, 94/113 days positive); F2 +5.94c; F3 +8.07c; months 5/5 positive (eight-coin first pass +10.10c). SOL alone in P +3.2c (CI spans 0). P alone (8 coins) +10.35c, (9 coins) +9.83c; Q alone +7.08c [−0.08, +13.43]. All 145 out-of-fit days (nine coins): +9.95c on 5,044 fills. Every coin positive except BTC (−0.5c, 73 fills). Placebo −3.75c (P), +1.63c (Q, CI spans 0). Median fillable size 66 (P) / 247 (Q) |
| E013 | **Frozen weather maker rule W (pre-registered)**: buy YES at bid when mid ≥ 0.90, sell YES at ask when mid ≤ 0.20, 30-min orders; primary "through" fills. `e013_weather_maker_frozen.py` | `wx-002`/`wx-001`/`wx-003`; prints `wx-trades-hist-a/b/c`, `wx-trades-002`, `wx-trades-005` | **Done — FAIL** | A (May→Sep 5): +0.91c [−0.09, +1.89] (buy-≥90 leg +2.54c); B ∪ C (Oct 30→Nov 20): **−3.11c** [−7.39, +1.07]. S4-M rejected |
| E014 | Exploratory: in-game sports, Kalshi vs ESPN win probability (30/60 s feed delay), NFL/NCAAF/NBA. `e014_sports_ingame_wp.py` | `sp-001`, `ext-sp-001`, `espn-wp-001` | **Done — negative** | Brier Kalshi 0.1555 vs ESPN 0.1595 (train), 0.1595 vs 0.1721 (val); trading ESPN gaps −2.8c (train), −13.1c (val). Sports closed |
| — | Exploratory: GDELT news volume in the prior hour vs E010 signal P&L | `ext-news-001` (partial, 27% coverage) | Done | No relationship (255 covered signals; +11.5c below median vs +8.1c above; corr −0.03) |

| E015 | 15-min vs hourly ladder (same settlement value): box arbitrage, within-ladder monotonicity, ladder-implied relative value, reverse rule. `e015_ladder_cross.py` | `ladder-<coin>-002` (6 alts+ETH; BTC pending), `full-001`, `full-004` | Done (BTC pending) | **Negative.** ≤3 after-fee box quotes per coin in 2 months, zero monotonicity violations; 15-min mid out-forecasts the ladder; both relative-value rules ≈ 0 or negative |
| E015b | Frozen S1-D on ladder strikes (last 15 min, candle fills). `e015b_s1d_on_ladders.py` | same | Done | ETH −1.3c, SOL −3.9c, XRP, HYPE ≤ 0; **BNB +12.2c [+2.7, +21.6] (52)**, DOGE +13.0c (16, CI spans 0); ~10–20 contracts/min |
| E016 | S1-D exit variants. `e016_dislocation_exit.py` | E012/E010 signals + prints | Done | Hold best (+10.0c / +9.6c); time exits lower EV, ~half the variance |
| E016b | S1-D **maker entry** (rest k ticks inside the ask, W s; touch/through fills; no fee). `e016b_dislocation_maker_entry.py` | 7,234 signals, six sets | Done | **through k=1 W=15 s: 76.5% filled, +7.93c [+6.32, +9.52] per fill, +6.07c per signal; all six sets positive** |
| E016c | S1-D threshold sensitivity, 4c (post-hoc, P∪Q). `e016c_threshold_sensitivity.py` | `trades-thr04-0..2` + earlier prints | Done | 4–6c +6.28c [+5.03, +7.34] (114/day), 6–8c +6.63c [+4.71, +8.38] (42/day), 8–12c +9.13c, >12c +10.42c; BTC negative in every band |
| E017 | Model-informed deep resting orders, all minutes, 8 alts, 14 sample days. `e017_model_maker.py` | `trades-sample-0..3` | Val done; train pending (groups 0, 1) | **Negative.** Val −1.7…−3.2c per fill (through), −1.0…−2.2c (touch), every δ; ≈ mid-quoting control. Test not opened |
| E018 | 15-min commodities/FX/yields/S&P: calibration + book-only/cross-market model; PAXG gold proxy. `e018_fin15.py` | `fin15-001`, `fin15-002` | Done | **Negative / blocked** (Pyth feed paid ≥ $500/mo). Calibrated; taker EV < 0 everywhere |
| E019 | Hourly temperature vs Kalshi Weather Index nowcast + stack, lags 1/2/5 min. `e019_hourly_temp.py` | `wxh-001`, `windex-001` | Done | **Negative** on validation (−0.3…−9c); index = settlement in 100% of hours |
| E020 | Polymarket 15-min price added to the S1-D stack. `poly_pull.py`, `e020_polymarket_signal.py` | `poly-<coin>-001` | Done (4 coins) | **Negative.** Poly Brier 0.158 vs Kalshi 0.140; augmented model no better out of fit |
| — | Bucket-sum arbitrage: hourly crypto ranges, daily weather brackets | `ranges-001`, `wx-002/003` | Done | None in ranges; weather 256/19,205 snapshots, median < 1c |

**Not run / failed:** `trades-001`, `trades-002`, `wx-trades-001` (never published — file-size limit), `ext-news-001` (GDELT rate limit). The crypto variant of E008 was therefore not run; E009 answers the same question with better data.

### Findings that change the plan

- "Alt-coins are less efficient" (S-priority hypothesis): **not supported** by price calibration. Do not prioritise alts on that basis.
- `KXCRYPTOLEAD15M`: 282 contracts median volume, 8¢ spread → **dropped**. `KXADA15M`, `KXBCH15M`, `KXTON15M`: zero markets in Sep–Nov 2026 → inactive.
- S4 (taker favorite/longshot): **rejected** on our own data. Maker version remains untested.
- Liquidity (median contracts per market): BTC 2.84M; ETH 163k; XRP 76k; SOL 61k; DOGE 37k; HYPE 24k; ZEC 21k; NEAR 18k; BNB 16k.

### Discovery pass (D8) — raw facts from `runs/full-001/catalog/` (16,341 series)

Series by frequency: fifteen_min 38 (Crypto 14, Financials 14, Commodities 9), hourly 80 (Financials 33, Crypto 25, Weather 14, Commodities 6), daily 401 (Weather 145, Economics 89, Financials 61, Crypto 22, ...).
Largest by lifetime volume — 15-min: BTC 3.4e10, ETH 2.0e9, **Gold 1.9e9**, XRP 8.9e8, SOL 7.8e8, **WTI 5.3e8**, DOGE 4.8e8, HYPE 4.5e8, **Silver 3.4e8**. Hourly: `KXBTCD` 9.4e9, `KXBTC` 4.9e8, `KXETHD` 3.9e8, `KXINXU` (S&P) 3.8e8, `KXNASDAQ100U` 2.0e8, `KXTEMPMIAH` (hourly Miami temp) 2.8e7. Daily: `KXHIGHLAX` 1.9e8, `KXHIGHNY` 1.5e8, `KXINX` 1.4e8, `KXHIGHCHI` 1.2e8, `KXWTI` 1.1e8, `KXNASDAQ100` 1.1e8, `KXHIGHMIA` 1.1e8, `KXRAIN` 8.7e7. All `quadratic`, multiplier 1 (no maker fee) among those listed.
**Next:** pull markets + candles for a shortlist (daily city highs, hourly S&P/Nasdaq, 15-min gold/WTI) and run E001-style calibration on each. The collector needs generalising: these are multi-strike ladders, not single up/down markets, and their windows are not 15 minutes (`pull_candles` groups by identical open/close, which still works; E001's `k`/`minutes_left` logic does not).
- **GitHub rejects any file over 100 MB**, and the workflow's publish step then fails without leaving a trace on `data`. Trade pulls must split output (done: `trades_partNN.csv.gz`, ~1.5M rows each) and be time-boxed (`max_minutes`). Rough sizes: ~24 bytes per trade gzipped; a BTC 15-minute market has ~60,000 trades, an alt-coin one ~1,700, a weather bracket ~1,000.
- **Actions minutes:** free private repos get 2,000 per month. Round 2 used roughly 550 on jobs that published plus up to ~1,400 on jobs that did not. The meter and job cancellation are not reachable from the workspace; the user can see and cancel runs in the repository's Actions tab.
- Jobs in the same push run sequentially in one runner; separate pushes run in parallel on separate runners. A push with several commits triggers one run that only sees request files changed in the last commit.
- `/historical/...` endpoints return bare field names (`yes_bid.close`, `volume`, `open_interest`, `yes_price`, `count`) where live endpoints return `*_dollars` / `*_fp`. `candle_row` and the trade puller handle both.
- Order book: `orderbook_fp.yes_dollars` / `no_dollars`, ascending; best YES bid is the last YES entry; best YES ask = 1 − last NO entry; its size is that NO entry's size.
- Each 15-minute strike equals the previous window's settlement value, so outcomes can be derived live from consecutive `floor_strike` values without waiting for results.
- 1-minute candle close quotes equal the real book at the minute end (checked against `live-001`); Coinbase candle `time` is the bucket start and `close` is the price at `time + 60`.
- Kalshi quotes on 15-minute markets move 1–2c every 2 seconds on average. Any fill assumption looser than a few seconds is fiction.
- WebFetch on new domains needs user approval and fails while the user is away; use `probe.py` on a runner to learn a source's format.
- pandas: read mixed ISO timestamps with `format="ISO8601"`.
- `/historical/markets` **ignores** `min_close_ts`/`max_close_ts`; page newest-first and stop by close time (the pullers do).
- History candles are one request per market: ~10,000 markets per coin per 104 days ≈ 50–60 minutes per coin on a runner. Run one coin per push so jobs run in parallel. One such job (`hist-sol-001`) silently never published; resubmit rather than wait.
- `/historical/trades?ticker=` works and returns the same `*_dollars` / `count_fp` names as live.
- 15-minute NEAR and ZEC markets start around 2026-07-01; the other seven coins go back to at least 2026-06-02.
- ESPN win probability: football via `sports.core.api.espn.com/v2/sports/football/leagues/<lg>/events/<id>/competitions/<id>/probabilities?limit=1000` (play id in `play.$ref`); basketball via the site `summary` endpoint's `winprobability` array (core API refuses basketball); play wall-clock times from `summary` → `drives.previous[].plays[]` (football) or `plays[]` (basketball). MLB summaries have WP but no wall-clock.
- GDELT DOC API: one request per 5 s per IP; runner IPs are shared, so most calls 429. Coverage of `ext-news-001` is about 27%.
- Ladder (`KX{COIN}D`) strikes are in `custom_strike.floor_strike`; `floor_strike` is null. `kalshi_events_pull.py` now reads it and keeps the nearest strikes per side (`nearest`, `band`).
- Historical cutoff for markets/trades moved to 2026-09-22 (2026-11-22 reading).
- Pyth Benchmarks / Hermes / TradingView shim: `unauthorized` without a paid key since 2026-08-26.
- Kalshi Weather Index: `GET /live_data/weather/{city}?from=<ms>&to=<ms>` — public, minute values, settles hourly temperature markets; puller `kalshi_windex_pull.py`.
- Kalshi incentives: `GET /incentive_programs?status=active&limit=10000`, `GET /incentive_schedules` — public.
- Polymarket: gamma `events?slug=<coin>-updown-15m-<start ts>` → `clobTokenIds`; CLOB `prices-history?market=<token>&startTs&endTs&fidelity=1`; ~4 requests/s from a runner without throttling.
- Workspace RAM is ~7 GB: load trade prints for at most ~1,500 markets at a time.
- Many parallel pushes queue on GitHub (≈ 20 concurrent jobs); expect late starts.
- When the repository is public, Actions minutes are unlimited; job time limit is still 6 h (workflow sets 350 min).
