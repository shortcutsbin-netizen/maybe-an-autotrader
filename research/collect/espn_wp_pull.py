#!/usr/bin/env python3
"""Read-only puller for ESPN's published in-game win probability with play wall-clock times.

SAFETY: no credentials, HTTP GET only. Research tooling (E014).

Request: {"name": "...", "script": "espn_wp_pull.py", "games_csv_glob": "<path to games_<league>.csv.gz from ext_pull>",
          "leagues": {"nfl": "football/nfl", "ncaaf": "football/college-football", "nba": "basketball/nba"},
          "pause": 0.25, "max_minutes": 300}
games_csv_glob is resolved on the runner against a checkout of the data branch (the workflow does not
provide one), so instead the request carries the ESPN ids directly in "ids": {"nfl": [...], ...}.
Output: wp_<league>.csv.gz with espn_id, play_id, wallclock, home_wp, period, clock, home_score, away_score, source
"""
import argparse
import csv
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = "maybe-an-autotrader-research/0.1 (read-only public data)"
STATE = {"requests": 0, "errors": []}


def get(url, pause, tries=4):
    last = None
    for i in range(tries):
        time.sleep(pause)
        STATE["requests"] += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:150].decode('utf-8', 'replace')}"
            if e.code in (400, 404):
                return None, last
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (i + 1))
    return None, last


def plays_from_summary(s):
    """id -> (wallclock, period, clock, home_score, away_score) from either 'plays' (basketball) or 'drives' (football)."""
    out = {}
    plays = list(s.get("plays") or [])
    for d in ((s.get("drives") or {}).get("previous") or []):
        plays.extend(d.get("plays") or [])
    for p in plays:
        pid = str(p.get("id", ""))
        if not pid:
            continue
        out[pid] = (p.get("wallclock") or p.get("modified") or "",
                    (p.get("period") or {}).get("number", ""),
                    (p.get("clock") or {}).get("displayValue", ""),
                    p.get("homeScore", ""), p.get("awayScore", ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    req = json.load(open(a.request))
    os.makedirs(a.out, exist_ok=True)
    pause = float(req.get("pause", 0.25))
    deadline = time.time() + 60 * float(req.get("max_minutes", 300))
    man = {"request": {k: v for k, v in req.items() if k != "ids"}, "leagues": {}}
    for lg, path in req["leagues"].items():
        sport, league = path.split("/")
        ids = req["ids"].get(lg, [])
        n_games = n_rows = n_wp = 0
        with gzip.open(os.path.join(a.out, f"wp_{lg}.csv.gz"), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(["espn_id", "play_id", "wallclock", "home_wp", "period", "clock", "home_score", "away_score", "source"])
            for eid in ids:
                if time.time() > deadline:
                    STATE["errors"].append(f"deadline reached in {lg}")
                    break
                s, err = get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={eid}", pause)
                if err:
                    STATE["errors"].append(f"summary {lg} {eid}: {err}")
                    continue
                n_games += 1
                plays = plays_from_summary(s)
                wp = {str(x.get("playId")): x.get("homeWinPercentage") for x in (s.get("winprobability") or []) if x.get("playId")}
                src = "summary"
                if not wp and sport == "football":
                    src = "core"
                    page = 1
                    while True:
                        o, e2 = get(f"https://sports.core.api.espn.com/v2/sports/{path.replace('/', '/leagues/')}/events/{eid}/competitions/{eid}/probabilities?limit=1000&page={page}", pause)
                        if e2 or not o:
                            if e2:
                                STATE["errors"].append(f"probs {lg} {eid}: {e2}")
                            break
                        for it in o.get("items", []):
                            ref = (it.get("play") or {}).get("$ref", "")
                            pid = ref.split("/plays/")[-1].split("?")[0] if "/plays/" in ref else ""
                            if pid:
                                wp[pid] = it.get("homeWinPercentage")
                        if page >= int(o.get("pageCount", 1) or 1):
                            break
                        page += 1
                if wp:
                    n_wp += 1
                for pid, hw in wp.items():
                    pl = plays.get(pid, ("", "", "", "", ""))
                    w.writerow([eid, pid, pl[0], hw, pl[1], pl[2], pl[3], pl[4], src])
                    n_rows += 1
        man["leagues"][lg] = {"games_requested": len(ids), "games_fetched": n_games, "games_with_wp": n_wp, "rows": n_rows}
        print(lg, man["leagues"][lg], flush=True)
    man.update({"http_requests": STATE["requests"], "error_count": len(STATE["errors"]), "errors_first_50": STATE["errors"][:50]})
    json.dump(man, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
