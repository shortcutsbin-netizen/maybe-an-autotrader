# research/

Phase 2 research tooling. **Throwaway, read-only, never imported by production code. Nothing here can place orders.**

- `collect/kalshi_pull.py` — pulls Kalshi public market data (settled markets, 1-minute bid/ask candles) and Coinbase 1-minute candles. No credentials.
- `collect/requests/*.json` — one file per data pull. Committing a new request file to the `claude` branch triggers `.github/workflows/collect.yml`, which writes results to the `data` branch under `runs/<name>/`.
- Request files are a permanent record of what was pulled and when. Do not edit old ones; add new ones.
