#!/usr/bin/env python3
"""Read-only puller for Kalshi PUBLIC data on event-style series (weather
ladders, sports games): settled markets + 1-minute candles, optionally
resampled, over a lookback window before each market's close.

SAFETY: no credentials, HTTP GET only, cannot place orders. Research tooling.

Request example:
 {"name": "wx-001", "script": "kalshi_events_pull.py",
  "series": ["KXHIGHNY"], "start": "2026-09-13T00:00:00Z", "end": "2026-11-13T00:00:00Z",
  "historical": true, "lookback_hours": 40, "resample_min": 10, "pause": 0.2}
`lookback_hours`: candles are pulled for [max(open, close - lookback), close].
`resample_min`: keep the last 1-minute candle of each N-minute bucket (volume summed).
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kalshi_pull import KALSHI, STATE, get_json, iso_to_ts, log, save_sample, ts_to_iso, candle_row, CANDLE_COLS  # noqa: E402

FIELDS = ["ticker", "event_ticker", "title", "yes_sub_title", "open_time", "close_time",
          "expected_expiration_time", "status", "result", "strike_type", "floor_strike", "cap_strike",
          "expiration_value", "volume_fp", "open_interest_fp", "settlement_ts", "settlement_value_dollars"]


def pull_markets(series, t_min, t_max, out, pause, use_hist):
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
            ms = obj.get("markets", [])
            save_sample(out, f"markets_{source}_{series}", {"markets": ms[:2]})
            pages += 1
            oldest = None
            for m in ms:
                try:
                    ct = iso_to_ts(m["close_time"])
                except Exception:
                    continue
                oldest = ct if oldest is None else min(oldest, ct)
                if t_min <= ct <= t_max and m.get("result") in ("yes", "no") and m["ticker"] not in found:
                    m["_source"] = source
                    found[m["ticker"]] = m
            cursor = obj.get("cursor") or ""
            if not cursor or not ms:
                return None
            if stop_before is not None and oldest is not None and oldest < stop_before:
                return None
            if pages > 3000:
                return "page cap"

    base = {"series_ticker": series, "limit": 1000}
    err = page("/markets", {**base, "min_close_ts": t_min, "max_close_ts": t_max}, "live")
    if err:
        STATE["errors"].append(f"{series} live markets: {err}")
    if use_hist:
        err = page("/historical/markets", base, "hist", stop_before=t_min)
        if err:
            STATE["errors"].append(f"{series} hist markets: {err}")
    rows = sorted(found.values(), key=lambda m: m["close_time"])
    os.makedirs(os.path.join(out, "markets"), exist_ok=True)
    with gzip.open(os.path.join(out, "markets", f"{series}.csv.gz"), "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "source"] + FIELDS)
        for m in rows:
            w.writerow([series, m["_source"]] + [m.get(k, "") for k in FIELDS])
    log(f"{series}: {len(rows)} markets ({sum(1 for m in rows if m['_source'] == 'hist')} hist)")
    return rows


def resample(cs, n):
    """Keep last candle per n-minute bucket; sum volume."""
    if n <= 1:
        return cs
    out, vol, last_bucket, last = [], 0.0, None, None
    for c in sorted(cs, key=lambda x: x.get("end_period_ts", 0)):
        b = (c["end_period_ts"] - 1) // (n * 60)
        if last_bucket is not None and b != last_bucket:
            last = dict(last)
            last["volume_fp"] = f"{vol:.2f}"
            last.pop("volume", None)
            out.append(last)
            vol = 0.0
        try:
            vol += float(c.get("volume_fp") or c.get("volume") or 0)
        except ValueError:
            pass
        last_bucket, last = b, c
    if last is not None:
        last = dict(last)
        last["volume_fp"] = f"{vol:.2f}"
        out.append(last)
    return out


def pull_candles(series, markets, out, pause, lookback_h, resample_min):
    events = {}
    for m in markets:
        events.setdefault((m["_source"], m["event_ticker"]), []).append(m)
    os.makedirs(os.path.join(out, "candles"), exist_ok=True)
    path = os.path.join(out, "candles", f"{series}.csv.gz")
    n_rows = n_empty = 0
    with gzip.open(path, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(CANDLE_COLS)
        keys = sorted(events)
        for i, key in enumerate(keys):
            source, _ = key
            ms = events[key]
            end = max(iso_to_ts(m["close_time"]) for m in ms)
            start = max(min(iso_to_ts(m["open_time"]) for m in ms), end - int(lookback_h * 3600))
            minutes = max(1, (end - start) // 60)
            results = []
            if source == "live":
                per = max(1, min(100, 9000 // minutes))
                for j in range(0, len(ms), per):
                    chunk = ms[j:j + per]
                    q = urllib.parse.urlencode({"market_tickers": ",".join(m["ticker"] for m in chunk),
                                                "start_ts": start, "end_ts": end, "period_interval": 1})
                    obj, err = get_json(f"{KALSHI}/markets/candlesticks?{q}", pause)
                    if err:
                        # fall back to single-market calls
                        for m in chunk:
                            q1 = urllib.parse.urlencode({"start_ts": start, "end_ts": end, "period_interval": 1})
                            o1, e1 = get_json(f"{KALSHI}/series/{series}/markets/{m['ticker']}/candlesticks?{q1}", pause)
                            if e1:
                                STATE["errors"].append(f"candles {m['ticker']}: {err} / {e1}")
                            else:
                                results.append((m["ticker"], o1.get("candlesticks") or []))
                        continue
                    save_sample(out, f"candles_batch_{series}", {"markets": [{"market_ticker": x.get("market_ticker"), "candlesticks": (x.get("candlesticks") or [])[:2]} for x in obj.get("markets", [])[:2]]})
                    for mk in obj.get("markets", []):
                        results.append((mk.get("market_ticker"), mk.get("candlesticks") or []))
            else:
                for m in ms:
                    q1 = urllib.parse.urlencode({"start_ts": start, "end_ts": end, "period_interval": 1})
                    o1, e1 = get_json(f"{KALSHI}/historical/markets/{m['ticker']}/candlesticks?{q1}", pause)
                    if e1:
                        STATE["errors"].append(f"hist candles {m['ticker']}: {e1}")
                    else:
                        save_sample(out, f"candles_hist_{series}", {"candlesticks": (o1.get("candlesticks") or [])[:2]})
                        results.append((m["ticker"], o1.get("candlesticks") or []))
            for ticker, cs in results:
                cs = resample(cs, resample_min)
                if not cs:
                    n_empty += 1
                for c in cs:
                    w.writerow(candle_row(ticker, c))
                    n_rows += 1
            if i % 100 == 0:
                log(f"{series} candles: event {i + 1}/{len(keys)} rows={n_rows} errors={len(STATE['errors'])}")
            if len(STATE["errors"]) > 2000:
                log("too many errors; stopping")
                break
    return n_rows, n_empty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    req = json.load(open(a.request))
    out = a.out
    os.makedirs(out, exist_ok=True)
    pause = float(req.get("pause", 0.2))
    t_min, t_max = iso_to_ts(req["start"]), iso_to_ts(req["end"])
    man = {"request": req, "started_utc": ts_to_iso(int(time.time())), "source": KALSHI, "series": {}}
    cutoff, err = get_json(f"{KALSHI}/historical/cutoff", pause)
    man["historical_cutoff"] = cutoff if not err else err
    ref = {}
    if req.get("ref_15m_series"):
        # strike of the 15-minute market closing at each time (known 15 minutes before that close; no look-ahead)
        for m in pull_markets(req["ref_15m_series"], t_min, t_max, out, pause, bool(req.get("historical", False))):
            try:
                ref[iso_to_ts(m["close_time"])] = float(m["floor_strike"])
            except Exception:
                pass
        man["ref_15m_closes"] = len(ref)
    band = float(req.get("band", 0.015))
    nearest = int(req.get("nearest", 2))

    def strike_of(m):
        # ladders ("custom" strike type) carry the threshold in custom_strike.floor_strike, e.g. 0.2349999 = "$0.235 or above"
        cs = m.get("custom_strike") or {}
        for v in (cs.get("floor_strike"), cs.get("cap_strike"), m.get("floor_strike"), m.get("cap_strike")):
            try:
                if v not in (None, ""):
                    return float(v)
            except Exception:
                pass
        t = m.get("ticker", "")
        if "-T" in t:
            try:
                return float(t.rsplit("-T", 1)[1])
            except Exception:
                pass
        return None

    for s in req["series"]:
        ms = pull_markets(s, t_min, t_max, out, pause, bool(req.get("historical", False)))
        if ref:
            # keep, per close time, every strike within `band` of the 15-min strike plus the `nearest` strikes on each side
            by_close = {}
            for m in ms:
                st = strike_of(m)
                if st is None:
                    continue
                m["floor_strike"] = st
                by_close.setdefault(iso_to_ts(m["close_time"]), []).append((st, m))
            keep = []
            for ct, lst in by_close.items():
                k = ref.get(ct)
                if not k:
                    continue
                lst.sort(key=lambda x: x[0])
                above = [x for x in lst if x[0] >= k][:nearest]
                below = [x for x in lst if x[0] < k][-nearest:]
                chosen = {id(x[1]): x[1] for x in above + below}
                for st, m in lst:
                    if abs(st / k - 1) <= band:
                        chosen[id(m)] = m
                keep.extend(chosen.values())
            log(f"{s}: kept {len(keep)} of {len(ms)} markets within {band:.1%} of the 15-min strike")
            ms = keep
            with gzip.open(os.path.join(out, "markets", f"{s}_kept.csv.gz"), "wt", newline="") as f:
                w = csv.writer(f)
                w.writerow(["series", "source"] + FIELDS)
                for m in ms:
                    w.writerow([s, m["_source"]] + [m.get(k, "") for k in FIELDS])
        n = e = 0
        if ms and req.get("candles", True):
            n, e = pull_candles(s, ms, out, pause, float(req.get("lookback_hours", 40)), int(req.get("resample_min", 1)))
        man["series"][s] = {"markets": len(ms), "candle_rows": n, "markets_without_candles": e}
        log(f"{s}: done {man['series'][s]}")
    hashes = {}
    for root, _, files in os.walk(out):
        for fn in files:
            p = os.path.join(root, fn)
            hashes[os.path.relpath(p, out)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    man.update({"finished_utc": ts_to_iso(int(time.time())), "http_requests": STATE["requests"], "retries": STATE["retries"],
                "error_count": len(STATE["errors"]), "errors_first_50": STATE["errors"][:50], "sha256": hashes})
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    log(f"done requests={STATE['requests']} errors={len(STATE['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
