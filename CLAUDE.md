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
| **Phase** | 1 — Research and planning |
| **Status** | Planning document v1 delivered 2026-11-12. **Awaiting user review and answers to open questions.** Phase 1 NOT approved. |
| **Last thread** | Thread 1 (2026-11-12) |
| **Code** | None. No application code exists or should exist yet. |
| **Data** | None collected. |
| **Infrastructure** | None deployed. |

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

Planned, not yet created: `docs/experiments/` (one file per Phase 2 experiment, including failures), `research/` (throwaway Phase 2 scripts, never imported by production), `src/` (Phase 3), `archive/`.

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

**Approved by user:** nothing yet beyond the original brief.

## 7. Open questions for the user (asked in thread 1)

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

## 8. Next steps

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

## 10. Feasibility assessment history

| Date | Outlook | P(sustainable net profit) | Confidence | Decision |
|---|---|---|---|---|
| 2026-11-12 | Uncertain, leaning Unpromising (BTC taker); Uncertain (alts, maker) | Informal 5–15%; not reliably quantifiable | Low–medium | Continue, narrowed scope |

## 11. Technical gotchas carried forward

- Sign the **full** path including `/trade-api/v2`; exclude the query string; timestamp in milliseconds.
- The live API hostname contains "elections" but serves every market.
- Prices and sizes arrive as fixed-point strings (`*_dollars`, `*_fp`). Parse with `Decimal`, never float.
- Kalshi reportedly drops some 15-minute reads under heavy parallel load — throttle and retry.
- Live vs historical endpoints split at a moving cutoff (`GET /historical/cutoff`); a full pull must query both.
- A single exchange's BTC price is not BRTI. Use Kalshi's `cfbenchmarks_value` feed for anything settlement-critical.
- An older third-party page describes 15-minute settlement as "price at close." That is wrong for current contracts; the rule is 60-second average vs 60-second average.
