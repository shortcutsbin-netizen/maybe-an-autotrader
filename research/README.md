# research/

Phase 2 research tooling. **Throwaway, read-only, never imported by production code. Nothing here can place orders.**

- `collect/kalshi_pull.py` — pulls Kalshi public market data (settled markets, 1-minute bid/ask candles) and Coinbase 1-minute candles. No credentials.
- `collect/requests/*.json` — one file per data pull. Committing a new request file to the `claude` branch triggers `.github/workflows/collect.yml`, which writes results to the `data` branch under `runs/<name>/`.
- Request files are a permanent record of what was pulled and when. Do not edit old ones; add new ones.

## Added 2026-11-13

- `collect/kalshi_events_pull.py`, `collect/ext_pull.py`, `collect/live_capture.py`, `collect/kalshi_trades_pull.py`, `collect/probe.py` — see the docstring at the top of each. All are read-only, credential-free GET clients.
- `analysis/e001 … e011` — one script per experiment; results and interpretation are in `docs/experiments/`.
- A request file selects its script with `"script": "<file>.py"` (default `kalshi_pull.py`).
- Trade pulls: keep `max_minutes` set and expect ~24 bytes per trade; GitHub rejects files over 100 MB, so output is split into parts.
