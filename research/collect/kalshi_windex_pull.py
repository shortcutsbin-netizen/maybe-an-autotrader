"""Kalshi Weather Index history (public): the minute-resolution city temperature series that settles the
hourly temperature markets. GET /live_data/weather/{city}?from=<ms>&to=<ms> in 24-hour windows.

request: {"name": ..., "script": "kalshi_windex_pull.py", "cities": ["miami", ...], "start": ISO, "end": ISO,
          "pause": 0.2}
output: windex/<city>.csv.gz  (t_ms, v, status, contributors, receipt_basis, config_version)
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
from kalshi_pull import KALSHI, STATE, get_json, iso_to_ts, log, save_sample, ts_to_iso  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    req = json.load(open(a.request))
    out = a.out
    os.makedirs(os.path.join(out, "windex"), exist_ok=True)
    pause = float(req.get("pause", 0.2))
    t0, t1 = iso_to_ts(req["start"]), iso_to_ts(req["end"])
    man = {"request": req, "started_utc": ts_to_iso(int(time.time())), "cities": {}}
    for city in req["cities"]:
        rows, seen = [], set()
        for d in range(t0, t1, 86400):
            obj, err = get_json(f"{KALSHI}/live_data/weather/{city}?from={d * 1000}&to={(d + 86400) * 1000 - 1}", pause)
            if err:
                STATE["errors"].append(f"{city} {ts_to_iso(d)}: {err}")
                continue
            save_sample(out, f"windex_{city}", {k: (v[:3] if isinstance(v, list) else v) for k, v in obj.items()})
            cv = obj.get("config_version", "")
            for p in obj.get("timeseries", []):
                if p["t"] in seen:
                    continue
                seen.add(p["t"])
                rows.append([p["t"], p.get("v", ""), p.get("status", ""), p.get("contributors", ""), p.get("receipt_basis", ""), cv])
        rows.sort()
        with gzip.open(os.path.join(out, "windex", f"{city}.csv.gz"), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_ms", "v", "status", "contributors", "receipt_basis", "config_version"])
            w.writerows(rows)
        man["cities"][city] = {"points": len(rows), "first": ts_to_iso(rows[0][0] // 1000) if rows else None}
        log(f"{city}: {man['cities'][city]}")
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
