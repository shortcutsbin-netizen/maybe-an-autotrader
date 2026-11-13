#!/usr/bin/env python3
"""Read-only puller for Kalshi PUBLIC trade prints of listed markets.
SAFETY: no credentials, HTTP GET only. Research tooling.
Request: {"name": "...", "script": "kalshi_trades_pull.py", "tickers_file": "research/collect/requests/<file>.txt", "pause": 0.15}
Output: trades.csv.gz (ticker, created_time, yes_price, no_price, count, taker_side), manifest.json
"""
import argparse, csv, gzip, json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kalshi_pull import KALSHI, STATE, get_json, log, save_sample  # noqa: E402

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--request", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); req = json.load(open(a.request)); os.makedirs(a.out, exist_ok=True)
    tickers = [x.strip() for x in open(req["tickers_file"]) if x.strip()]
    pause = float(req.get("pause", 0.15)); n = 0
    endpoints = ["/markets/trades"] + (["/historical/trades"] if req.get("historical") else [])
    max_pages = int(req.get("max_pages", 200))

    def f_(x, *keys):          # live endpoints use *_dollars / *_fp, historical ones bare names
        for k in keys:
            if x.get(k) is not None:
                return x.get(k)
        return ""
    with gzip.open(os.path.join(a.out, "trades.csv.gz"), "wt", newline="") as f:
        w = csv.writer(f); w.writerow(["ticker", "created_time", "yes_price", "no_price", "count", "taker_side", "trade_id", "src"])
        deadline = time.time() + 60 * float(req.get("max_minutes", 120))      # always stop early enough to publish
        done_tickers = 0
        for i, t in enumerate(tickers):
            if time.time() > deadline:
                STATE["errors"].append(f"deadline reached after {i} of {len(tickers)} tickers")
                break
            done_tickers = i + 1
            for ep in endpoints:
                cursor = ""
                for _ in range(max_pages):
                    q = {"ticker": t, "limit": 1000}
                    if cursor: q["cursor"] = cursor
                    obj, err = get_json(f"{KALSHI}{ep}?{urllib.parse.urlencode(q)}", pause)
                    if err:
                        STATE["errors"].append(f"{t} {ep}: {err}"); break
                    tr = obj.get("trades", [])
                    if tr:
                        save_sample(a.out, "trades_" + ep.strip("/").replace("/", "_"), {"trades": tr[:2]})
                    for x in tr:
                        w.writerow([t, x.get("created_time"), f_(x, "yes_price_dollars", "yes_price"), f_(x, "no_price_dollars", "no_price"),
                                    f_(x, "count_fp", "count"), x.get("taker_side"), x.get("trade_id", ""), ep[1:5]]); n += 1
                    cursor = obj.get("cursor") or ""
                    if not cursor or not tr: break
            if i % 200 == 0: log(f"{i}/{len(tickers)} trades={n} errors={len(STATE['errors'])}")
    json.dump({"request": req, "tickers": len(tickers), "tickers_done": done_tickers, "trades": n, "http_requests": STATE["requests"], "error_count": len(STATE["errors"]),
               "errors_first_50": STATE["errors"][:50]}, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)
    log(f"done trades={n}")

if __name__ == "__main__":
    sys.exit(main())
