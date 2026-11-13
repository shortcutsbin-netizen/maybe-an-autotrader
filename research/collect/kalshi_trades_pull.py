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
    with gzip.open(os.path.join(a.out, "trades.csv.gz"), "wt", newline="") as f:
        w = csv.writer(f); w.writerow(["ticker", "created_time", "yes_price", "no_price", "count", "taker_side"])
        for i, t in enumerate(tickers):
            cursor = ""
            for _ in range(200):
                q = {"ticker": t, "limit": 1000}
                if cursor: q["cursor"] = cursor
                obj, err = get_json(f"{KALSHI}/markets/trades?{urllib.parse.urlencode(q)}", pause)
                if err:
                    STATE["errors"].append(f"{t}: {err}"); break
                tr = obj.get("trades", [])
                save_sample(a.out, "trades", {"trades": tr[:2]})
                for x in tr:
                    w.writerow([t, x.get("created_time"), x.get("yes_price_dollars"), x.get("no_price_dollars"), x.get("count_fp"), x.get("taker_side")]); n += 1
                cursor = obj.get("cursor") or ""
                if not cursor or not tr: break
            if i % 200 == 0: log(f"{i}/{len(tickers)} trades={n} errors={len(STATE['errors'])}")
    json.dump({"request": req, "tickers": len(tickers), "trades": n, "http_requests": STATE["requests"], "error_count": len(STATE["errors"]),
               "errors_first_50": STATE["errors"][:50]}, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)
    log(f"done trades={n}")

if __name__ == "__main__":
    sys.exit(main())
