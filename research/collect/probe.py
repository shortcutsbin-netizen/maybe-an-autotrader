#!/usr/bin/env python3
"""Fetch a list of public URLs and save the raw (truncated) responses.
Used to learn response formats of free data sources from a GitHub runner,
because the Claude workspace cannot reach them. Read-only GETs, no credentials.
Request: {"name": "...", "script": "probe.py", "urls": {"label": "https://..."}, "max_bytes": 200000}
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

UA = "maybe-an-autotrader-research/0.1 (read-only public data)"

def fetch(url, max_bytes):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read(max_bytes)
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000)
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}".encode()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--request", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); req = json.load(open(a.request)); os.makedirs(a.out, exist_ok=True)
    mb = int(req.get("max_bytes", 200000)); index = {}
    for label, url in req["urls"].items():
        status, body = fetch(url, mb)
        with open(os.path.join(a.out, label + ".txt"), "wb") as f:
            f.write(body)
        index[label] = {"url": url, "status": status, "bytes": len(body)}
        print(label, status, len(body), flush=True)
        time.sleep(1.0)
    # ESPN two-step: scoreboard -> first event id -> core odds
    for label, sb in (req.get("espn_odds") or {}).items():
        status, body = fetch(sb, 3_000_000)
        try:
            ev = json.loads(body)["events"][0]; eid = ev["id"]
            lg = sb.split("/sports/")[1].split("/scoreboard")[0]  # e.g. football/nfl
            sport, league = lg.split("/")
            u = f"https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{eid}/competitions/{eid}/odds"
            s2, b2 = fetch(u, mb)
            open(os.path.join(a.out, label + "_odds.txt"), "wb").write(b2)
            open(os.path.join(a.out, label + "_event.txt"), "w").write(json.dumps(ev)[:mb])
            index[label] = {"scoreboard": sb, "events": len(json.loads(body)["events"]), "odds_url": u, "odds_status": s2}
        except Exception as e:
            index[label] = {"scoreboard": sb, "status": status, "error": str(e)}
        print(label, index[label], flush=True)
    json.dump(index, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)

if __name__ == "__main__":
    sys.exit(main())
