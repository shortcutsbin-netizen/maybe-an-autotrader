#!/usr/bin/env python3
"""Read-only puller for Kalshi PUBLIC market data (Phase 2 research).

SAFETY: this script uses no credentials, sends only HTTP GET requests, and
cannot place, modify or cancel orders. It is research tooling and must never
be imported by production code.

Reads a request JSON, e.g.
  {"name": "smoke-001", "series": ["KXBTC15M"], "days": 1,
   "end": "2026-11-12T00:00:00Z", "candles": true, "spot": true}

Writes under --out:
  markets/<series>.csv.gz      one row per settled market
  candles/<YYYY-MM-DD>.csv.gz  1-minute candles (bid/ask/trade OHLC)
  spot/<product>.csv.gz        Coinbase 1-minute candles (index proxy)
  samples/*.json               first raw response of each kind (provenance)
  manifest.json                parameters, counts, errors, file hashes
Standard library only.
"""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
COINBASE = "https://api.exchange.coinbase.com"
UA = "maybe-an-autotrader-research/0.1 (read-only public data)"

SPOT_PRODUCTS = {
    "KXBTC15M": "BTC-USD", "KXETH15M": "ETH-USD", "KXSOL15M": "SOL-USD",
    "KXXRP15M": "XRP-USD", "KXDOGE15M": "DOGE-USD", "KXADA15M": "ADA-USD",
    "KXBCH15M": "BCH-USD", "KXNEAR15M": "NEAR-USD", "KXZEC15M": "ZEC-USD",
    "KXHYPE15M": "HYPE-USD", "KXTON15M": "TON-USD", "KXBNB15M": "BNB-USD",
}

STATE = {"requests": 0, "retries": 0, "errors": [], "t0": time.time()}


def log(msg):
    print(f"[{time.time() - STATE['t0']:8.1f}s] {msg}", flush=True)


def get_json(url, pause, tries=6):
    """GET with polite pacing and exponential backoff. Returns (obj, err)."""
    last = None
    for i in range(tries):
        time.sleep(pause)
        STATE["requests"] += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            last = f"HTTP {e.code}: {body}"
            if e.code in (400, 401, 403, 404):
                return None, last
        except Exception as e:  # network, timeout, JSON
            last = f"{type(e).__name__}: {e}"
        STATE["retries"] += 1
        time.sleep(min(30, 1.5 ** i))
    return None, last


def iso_to_ts(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def ts_to_iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_sample(out, name, obj):
    p = os.path.join(out, "samples", name + ".json")
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump(obj, f)


MARKET_FIELDS = ["ticker", "event_ticker", "open_time", "close_time", "status", "result",
                 "floor_strike", "cap_strike", "strike_type", "expiration_value",
                 "volume_fp", "open_interest_fp", "settlement_ts", "settlement_value_dollars",
                 "last_price_dollars", "can_close_early"]


def pull_markets(series, t_min, t_max, out, pause, use_historical):
    """Return list of market dicts closing in [t_min, t_max]."""
    found = {}

    def page(endpoint, params, source, stop_before=None):
        cursor, pages = "", 0
        while True:
            q = dict(params)
            if cursor:
                q["cursor"] = cursor
            obj, err = get_json(f"{KALSHI}{endpoint}?{urllib.parse.urlencode(q)}", pause)
            if err:
                return err
            save_sample(out, f"markets_{source}", {"markets": obj.get("markets", [])[:2]})
            ms = obj.get("markets", [])
            pages += 1
            oldest = None
            for m in ms:
                try:
                    ct = iso_to_ts(m["close_time"])
                except Exception:
                    continue
                oldest = ct if oldest is None else min(oldest, ct)
                if t_min <= ct <= t_max and m.get("ticker") not in found:
                    m["_source"] = source
                    found[m["ticker"]] = m
            cursor = obj.get("cursor") or ""
            if not cursor or not ms:
                return None
            if stop_before is not None and oldest is not None and oldest < stop_before:
                return None
            if pages > 2000:
                return "page cap hit"

    base = {"series_ticker": series, "limit": 1000}
    err = page("/markets", {**base, "min_close_ts": t_min, "max_close_ts": t_max}, "live")
    if err:
        STATE["errors"].append(f"{series} live markets (ts filter): {err}")
        err = page("/markets", {**base, "status": "settled"}, "live", stop_before=t_min)
        if err:
            STATE["errors"].append(f"{series} live markets (fallback): {err}")
    if use_historical:
        err = page("/historical/markets", base, "hist", stop_before=t_min)
        if err:
            STATE["errors"].append(f"{series} historical markets: {err}")

    rows = sorted(found.values(), key=lambda m: m["close_time"])
    os.makedirs(os.path.join(out, "markets"), exist_ok=True)
    with gzip.open(os.path.join(out, "markets", f"{series}.csv.gz"), "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "source"] + MARKET_FIELDS)
        for m in rows:
            w.writerow([series, m["_source"]] + [m.get(k, "") for k in MARKET_FIELDS])
    log(f"{series}: {len(rows)} markets")
    return rows


CANDLE_COLS = ["ticker", "end_period_ts",
               "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c",
               "px_o", "px_h", "px_l", "px_c", "px_mean", "volume", "oi"]


def candle_row(ticker, c):
    # live endpoints use "<k>_dollars"/"volume_fp"; /historical/ endpoints use bare "<k>"/"volume"
    def g(group, k):
        o = c.get(group) or {}
        v = o.get(k + "_dollars")
        return v if v is not None else o.get(k, "")
    vol = c.get("volume_fp", c.get("volume", ""))
    oi = c.get("open_interest_fp", c.get("open_interest", ""))
    return ([ticker, c.get("end_period_ts", "")]
            + [g("yes_bid", k) for k in ("open", "high", "low", "close")]
            + [g("yes_ask", k) for k in ("open", "high", "low", "close")]
            + [g("price", k) for k in ("open", "high", "low", "close", "mean")]
            + [vol, oi])


def pull_candles(markets, out, pause):
    """Batch by identical (open, close) window across series; write per close-date files."""
    groups = {}
    for m in markets:
        if not m.get("open_time") or not m.get("close_time"):
            continue
        groups.setdefault((m["_source"], m["open_time"], m["close_time"]), []).append(m)
    by_day, n_rows, n_empty = {}, 0, 0
    keys = sorted(groups, key=lambda k: k[2])
    for i, key in enumerate(keys):
        source, o, c = key
        ms = groups[key]
        start, end = iso_to_ts(o), iso_to_ts(c)
        results = []
        if source == "live":
            for j in range(0, len(ms), 100):
                chunk = ms[j:j + 100]
                q = urllib.parse.urlencode({"market_tickers": ",".join(m["ticker"] for m in chunk),
                                            "start_ts": start, "end_ts": end, "period_interval": 1})
                obj, err = get_json(f"{KALSHI}/markets/candlesticks?{q}", pause)
                if err:
                    STATE["errors"].append(f"candles batch {o}: {err}")
                    continue
                save_sample(out, "candles_batch", obj)
                for mk in obj.get("markets", []):
                    results.append((mk.get("market_ticker"), mk.get("candlesticks") or []))
        else:
            for m in ms:
                q = urllib.parse.urlencode({"start_ts": start, "end_ts": end, "period_interval": 1})
                obj, err = get_json(f"{KALSHI}/historical/markets/{m['ticker']}/candlesticks?{q}", pause)
                if err:
                    STATE["errors"].append(f"candles hist {m['ticker']}: {err}")
                    continue
                save_sample(out, "candles_hist", obj)
                results.append((m["ticker"], obj.get("candlesticks") or []))
        day = c[:10]
        for ticker, cs in results:
            if not cs:
                n_empty += 1
            for cd in cs:
                by_day.setdefault(day, []).append(candle_row(ticker, cd))
                n_rows += 1
        if i % 200 == 0:
            log(f"candles: window {i + 1}/{len(keys)} rows={n_rows} errors={len(STATE['errors'])}")
        if len(STATE["errors"]) > 500:
            log("too many errors; aborting candle pull")
            break
    os.makedirs(os.path.join(out, "candles"), exist_ok=True)
    for day, rows in by_day.items():
        with gzip.open(os.path.join(out, "candles", f"{day}.csv.gz"), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(CANDLE_COLS)
            w.writerows(rows)
    return n_rows, n_empty


def pull_spot(product, t_min, t_max, out, pause):
    rows, t = {}, t_min
    step = 300 * 60
    while t < t_max:
        q = urllib.parse.urlencode({"granularity": 60, "start": ts_to_iso(t), "end": ts_to_iso(min(t + step, t_max))})
        obj, err = get_json(f"{COINBASE}/products/{product}/candles?{q}", pause)
        if err:
            STATE["errors"].append(f"spot {product} {ts_to_iso(t)}: {err}")
            if "404" in err or "400" in err:
                break
        elif isinstance(obj, list):
            save_sample(out, "spot", obj[:3])
            for r in obj:
                if isinstance(r, list) and len(r) >= 6:
                    rows[r[0]] = r[:6]
        t += step
    if rows:
        os.makedirs(os.path.join(out, "spot"), exist_ok=True)
        with gzip.open(os.path.join(out, "spot", f"{product}.csv.gz"), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", "low", "high", "open", "close", "volume"])
            for k in sorted(rows):
                w.writerow(rows[k])
    log(f"spot {product}: {len(rows)} candles")
    return len(rows)


def pull_series_catalog(out, pause):
    """Market-discovery pass: every series with frequency, category, fees and (if offered) volume."""
    obj, err = get_json(f"{KALSHI}/series?include_volume=true", pause)
    if err:
        STATE["errors"].append(f"series catalog (with volume): {err}")
        obj, err = get_json(f"{KALSHI}/series", pause)
        if err:
            STATE["errors"].append(f"series catalog: {err}")
            return 0
    ss = obj.get("series") or []
    save_sample(out, "series_catalog", {"series": ss[:3]})
    os.makedirs(os.path.join(out, "catalog"), exist_ok=True)
    with gzip.open(os.path.join(out, "catalog", "series_raw.json.gz"), "wt") as f:
        json.dump(obj, f)
    cols = ["ticker", "title", "category", "frequency", "fee_type", "fee_multiplier", "volume_fp", "volume", "tags"]
    with gzip.open(os.path.join(out, "catalog", "series.csv.gz"), "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for x in ss:
            w.writerow([json.dumps(x.get(k)) if isinstance(x.get(k), (list, dict)) else x.get(k, "") for k in cols])
    log(f"series catalog: {len(ss)}")
    return len(ss)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.request) as f:
        req = json.load(f)
    out = a.out
    os.makedirs(out, exist_ok=True)
    pause = float(req.get("pause", 0.2))
    t_max = iso_to_ts(req["end"]) if req.get("end") else int(time.time()) - 600
    t_min = t_max - int(float(req.get("days", 1)) * 86400)
    series = req["series"]
    manifest = {"request": req, "t_min": ts_to_iso(t_min), "t_max": ts_to_iso(t_max),
                "started_utc": ts_to_iso(int(time.time())), "source": KALSHI, "counts": {}}

    cutoff, err = get_json(f"{KALSHI}/historical/cutoff", pause)
    manifest["historical_cutoff"] = cutoff if not err else err
    log(f"cutoff: {manifest['historical_cutoff']}")

    if req.get("discover", False):
        manifest["series_catalog"] = pull_series_catalog(out, pause)

    all_markets = []
    for s in series:
        ms = pull_markets(s, t_min, t_max, out, pause, bool(req.get("historical", False)))
        manifest["counts"][s] = len(ms)
        all_markets.extend(ms)

    if req.get("candles", True) and all_markets:
        n, empty = pull_candles(all_markets, out, pause)
        manifest["candle_rows"], manifest["markets_without_candles"] = n, empty

    if req.get("spot", True):
        manifest["spot"] = {}
        for s in series:
            p = SPOT_PRODUCTS.get(s)
            if p:
                manifest["spot"][p] = pull_spot(p, t_min - 3600, t_max, out, max(pause, 0.15))
        # extra Coinbase products named in the request (e.g. PAXG-USD as a free gold proxy)
        for p in req.get("spot_extra", []):
            manifest["spot"][p] = pull_spot(p, t_min - 3600, t_max, out, max(pause, 0.15))

    hashes = {}
    for root, _, files in os.walk(out):
        for fn in files:
            p = os.path.join(root, fn)
            with open(p, "rb") as fh:
                hashes[os.path.relpath(p, out)] = hashlib.sha256(fh.read()).hexdigest()
    manifest.update({"finished_utc": ts_to_iso(int(time.time())), "http_requests": STATE["requests"],
                     "retries": STATE["retries"], "error_count": len(STATE["errors"]),
                     "errors_first_50": STATE["errors"][:50], "sha256": hashes})
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    log(f"done: requests={STATE['requests']} errors={len(STATE['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
