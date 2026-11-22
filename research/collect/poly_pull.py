"""Polymarket 15-minute up/down price history (public, read-only, no account).

For each 15-minute window start ts in [start, end): gamma `events?slug=<coin>-updown-15m-<ts>` gives the
market (outcomes, CLOB token ids, volume, result); CLOB `prices-history` gives the 1-minute price path of
the "Up" token. Output: poly/<coin>_windows.csv.gz and poly/<coin>_prices.csv.gz (split by month).

Polymarket resolves on Chainlink's 60-second TWAP stream (window-end TWAP vs price at window start), not on
CF Benchmarks, so this is only used as an information signal, never as an arbitrage leg.

request: {"name": ..., "script": "poly_pull.py", "coins": ["btc"], "start": ISO, "end": ISO,
          "pause": 0.12, "max_minutes": 330}
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kalshi_pull import STATE, get_json, iso_to_ts, log, save_sample, ts_to_iso  # noqa: E402

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    req = json.load(open(a.request))
    out = a.out
    os.makedirs(os.path.join(out, "poly"), exist_ok=True)
    os.makedirs(os.path.join(out, "samples"), exist_ok=True)
    pause = float(req.get("pause", 0.12))
    t0, t1 = iso_to_ts(req["start"]), iso_to_ts(req["end"])
    t0 -= t0 % 900
    deadline = time.time() + 60 * float(req.get("max_minutes", 330))
    man = {"request": req, "started_utc": ts_to_iso(int(time.time())), "coins": {}}
    for coin in req["coins"]:
        wrows, prows, missing, nohist = [], [], 0, 0
        for ws in range(t0, t1, 900):
            if time.time() > deadline:
                man["stopped_early_at"] = ts_to_iso(ws)
                break
            ev, err = get_json(f"{GAMMA}/events?slug={coin}-updown-15m-{ws}", pause)
            if err or not ev:
                missing += 1
                continue
            e = ev[0]
            if not e.get("markets"):
                missing += 1
                continue
            m = e["markets"][0]
            save_sample(out, f"gamma_{coin}", e)
            try:
                toks = json.loads(m.get("clobTokenIds") or "[]")
                outs = json.loads(m.get("outcomes") or "[]")
                prices = json.loads(m.get("outcomePrices") or "[]")
            except Exception:
                toks, outs, prices = [], [], []
            up = toks[outs.index("Up")] if "Up" in outs and len(toks) == len(outs) else (toks[0] if toks else "")
            res = ""
            if prices and "Up" in outs:
                res = prices[outs.index("Up")]
            wrows.append([coin, ws, m.get("slug", ""), m.get("volumeNum", m.get("volume", "")), res, m.get("umaResolutionStatus", ""), up])
            if not up:
                continue
            h, err = get_json(f"{CLOB}/prices-history?market={up}&startTs={ws - 300}&endTs={ws + 960}&fidelity=1", pause)
            if err or not h:
                nohist += 1
                STATE["errors"].append(f"hist {coin} {ws}: {err}")
                continue
            save_sample(out, f"hist_{coin}", h)
            for pt in h.get("history", []):
                prows.append([ws, pt.get("t"), pt.get("p")])
        with gzip.open(os.path.join(out, "poly", f"{coin}_windows.csv.gz"), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(["coin", "window_start", "slug", "volume", "up_final_price", "uma_status", "up_token"])
            w.writerows(wrows)
        with gzip.open(os.path.join(out, "poly", f"{coin}_prices.csv.gz"), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(["window_start", "t", "p_up"])
            w.writerows(prows)
        man["coins"][coin] = {"windows": len(wrows), "missing": missing, "no_history": nohist, "price_points": len(prows)}
        log(f"{coin}: {man['coins'][coin]}")
    hashes = {}
    for root, _, files in os.walk(out):
        for fn in files:
            p = os.path.join(root, fn)
            hashes[os.path.relpath(p, out)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    man.update({"finished_utc": ts_to_iso(int(time.time())), "http_requests": STATE["requests"], "retries": STATE["retries"],
                "error_count": len(STATE["errors"]), "errors_first_50": STATE["errors"][:50], "sha256": hashes})
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
