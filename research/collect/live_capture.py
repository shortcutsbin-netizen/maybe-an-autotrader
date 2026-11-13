#!/usr/bin/env python3
"""Forward capture of PUBLIC order books (Kalshi, no account) alongside spot
prices, at ~2 second cadence, to measure how long Kalshi quotes lag spot moves
and how much size sits at the touch.

SAFETY: no credentials, HTTP GET only, cannot place orders. Research tooling.

Request: {"name": "...", "script": "live_capture.py", "minutes": 270, "cycle_s": 2.0,
          "series": {"KXBTC15M": {"coinbase": "BTC-USD", "kraken": "XBTUSD"}, ...}}
Output (gz JSONL, one record per poll, raw response text preserved):
  book.jsonl.gz   {"t0","t1","series","ticker","status","body"}
  spot.jsonl.gz   {"t0","t1","src","key","status","body"}
  markets.jsonl.gz  market-list refreshes
"""
import argparse
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
UA = "maybe-an-autotrader-research/0.1 (read-only public data)"


def fetch(url, timeout=4):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return t0, time.time(), r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return t0, time.time(), e.code, e.read()[:200].decode("utf-8", "replace")
    except Exception as e:
        return t0, time.time(), -1, f"{type(e).__name__}: {e}"


def current_markets(series):
    """ticker of the market currently open for trading in each series."""
    out = {}
    for s in series:
        t0, t1, st, body = fetch(f"{KALSHI}/markets?series_ticker={s}&status=open&limit=5", timeout=8)
        try:
            ms = json.loads(body).get("markets", [])
            now = time.time()
            live = [m for m in ms if m.get("open_time") and m.get("close_time")]
            live.sort(key=lambda m: m["close_time"])
            out[s] = [{"ticker": m["ticker"], "open_time": m["open_time"], "close_time": m["close_time"],
                       "floor_strike": m.get("floor_strike")} for m in live][:2]
        except Exception as e:
            out[s] = []
            out[s + "_err"] = f"{st} {str(e)[:80]} {body[:80]}"
        time.sleep(0.15)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    req = json.load(open(a.request))
    os.makedirs(a.out, exist_ok=True)
    series = req["series"]
    cycle = float(req.get("cycle_s", 2.0))
    t_end = time.time() + float(req["minutes"]) * 60
    fb = gzip.open(os.path.join(a.out, "book.jsonl.gz"), "wt")
    fs = gzip.open(os.path.join(a.out, "spot.jsonl.gz"), "wt")
    fm = gzip.open(os.path.join(a.out, "markets.jsonl.gz"), "wt")
    kraken_pairs = ",".join(v["kraken"] for v in series.values() if v.get("kraken"))
    pool = ThreadPoolExecutor(max_workers=24)
    mk, next_refresh = {}, 0
    n = errs = 0
    while time.time() < t_end:
        c0 = time.time()
        # refresh the market list just after each quarter hour and every 5 minutes
        if c0 >= next_refresh:
            mk = current_markets(list(series))
            fm.write(json.dumps({"t": c0, "markets": mk}) + "\n")
            q = (int(c0) // 900 + 1) * 900
            next_refresh = min(q + 2, c0 + 300)
        jobs = []
        for s in series:
            for m in mk.get(s, [])[:1]:
                jobs.append(("book", s, m["ticker"], pool.submit(fetch, f"{KALSHI}/markets/{m['ticker']}/orderbook?depth=10")))
        for s, v in series.items():
            if v.get("coinbase"):
                jobs.append(("spot", "coinbase", v["coinbase"], pool.submit(fetch, f"https://api.exchange.coinbase.com/products/{v['coinbase']}/ticker")))
        if kraken_pairs:
            jobs.append(("spot", "kraken", "all", pool.submit(fetch, f"https://api.kraken.com/0/public/Ticker?pair={kraken_pairs}")))
        for kind, x, y, fut in jobs:
            t0, t1, st, body = fut.result()
            if st != 200:
                errs += 1
            if kind == "book":
                fb.write(json.dumps({"t0": round(t0, 3), "t1": round(t1, 3), "series": x, "ticker": y, "status": st, "body": body}) + "\n")
            else:
                fs.write(json.dumps({"t0": round(t0, 3), "t1": round(t1, 3), "src": x, "key": y, "status": st, "body": body}) + "\n")
        n += 1
        if n % 300 == 0:
            print(f"cycle {n} errs={errs} elapsed={time.time() - c0:.2f}s", flush=True)
            for f in (fb, fs, fm):
                f.flush()
        dt_ = cycle - (time.time() - c0)
        if dt_ > 0:
            time.sleep(dt_)
    for f in (fb, fs, fm):
        f.close()
    json.dump({"request": req, "cycles": n, "non200": errs, "finished": time.time()}, open(os.path.join(a.out, "manifest.json"), "w"))
    print(f"done cycles={n} errs={errs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
