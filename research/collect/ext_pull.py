#!/usr/bin/env python3
"""Read-only puller for free external information sources (Phase 2 research).

SAFETY: no credentials, HTTP GET only. Research tooling, never imported by production.

Request: {"name": "...", "script": "ext_pull.py", "start": "2026-09-12", "end": "2026-11-13",
          "weather": {...optional...}, "sports": {...optional...}, "news": {...optional...}}

weather: {"stations": {"NY": {"iem": "NYC", "lat": 40.779, "lon": -73.969}, ...},
          "models": ["gfs_seamless", ...], "one_minute": true}
   -> weather/metar_<key>.csv.gz   IEM ASOS METAR reports (routine + specials), UTC
      weather/asos1min_<key>.csv.gz IEM 1-minute ASOS temperature, UTC
      weather/fcst_<key>.csv.gz    Open-Meteo "previous runs": forecasts as issued 1 and 2 days earlier
sports:  {"leagues": {"nfl": "football/nfl", ...}, "ncaaf_groups": "80"}
   -> sports/games_<league>.csv.gz one row per game with scores and sportsbook open/close moneylines (ESPN)
news:    {"queries": {"btc": "bitcoin", ...}}
   -> news/<label>.csv.gz          GDELT article-volume and tone timelines (15-minute buckets)
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

UA = "maybe-an-autotrader-research/0.1 (read-only public data)"
STATE = {"requests": 0, "errors": [], "t0": time.time()}


def log(m):
    print(f"[{time.time() - STATE['t0']:8.1f}s] {m}", flush=True)


def get(url, pause=0.3, tries=5, raw=False, backoff=2.0):
    last = None
    for i in range(tries):
        time.sleep(pause)
        STATE["requests"] += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=90) as r:
                b = r.read()
            return (b.decode("utf-8", "replace") if raw else json.loads(b.decode("utf-8"))), None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
            if e.code in (400, 404):
                return None, last
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(backoff * (i + 1))
    return None, last


def daterange(a, b, step):
    d = a
    while d <= b:
        e = min(d + dt.timedelta(days=step - 1), b)
        yield d, e
        d = e + dt.timedelta(days=1)


def gzcsv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------- weather
def pull_weather(cfg, d0, d1, out, man):
    models = cfg.get("models", ["gfs_seamless"])
    for key, st in cfg["stations"].items():
        info = {}
        # METAR (routine + specials)
        rows = []
        for a, b in daterange(d0, d1, 31):
            b2 = b + dt.timedelta(days=1)
            u = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?" +
                 f"station={st['iem']}&data=tmpf&data=dwpf&data=sknt&data=skyc1&year1={a.year}&month1={a.month}&day1={a.day}"
                 f"&year2={b2.year}&month2={b2.month}&day2={b2.day}&tz=Etc/UTC&format=onlycomma&latlon=no&missing=M&trace=T"
                 "&direct=no" + "".join(f"&report_type={r}" for r in cfg.get("metar_report_types", [3, 4])))
            txt, err = get(u, pause=1.0, raw=True)
            if err:
                STATE["errors"].append(f"metar {key} {a}: {err}")
                continue
            for line in txt.strip().split("\n")[1:]:
                p = line.split(",")
                if len(p) >= 3:
                    rows.append(p[:6])
        gzcsv(f"{out}/weather/metar_{key}.csv.gz", ["station", "valid", "tmpf", "dwpf", "sknt", "skyc1"], rows)
        info["metar_rows"] = len(rows)
        # 1-minute ASOS
        if cfg.get("one_minute", True):
            rows = []
            for a, b in daterange(d0, d1, 10):
                b2 = b + dt.timedelta(days=1)
                u = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?" +
                     f"station={st['iem']}&vars=tmpf&sts={a.isoformat()}T00:00Z&ets={b2.isoformat()}T00:00Z&sample=1min&what=download&delim=comma")
                txt, err = get(u, pause=1.0, raw=True)
                if err:
                    STATE["errors"].append(f"asos1min {key} {a}: {err}")
                    continue
                for line in txt.strip().split("\n")[1:]:
                    p = line.split(",")
                    if len(p) >= 4:
                        rows.append([p[2], p[3]])
            gzcsv(f"{out}/weather/asos1min_{key}.csv.gz", ["valid", "tmpf"], rows)
            info["asos1min_rows"] = len(rows)
        # forecasts as issued earlier
        cols, data = None, {}
        hourly = ",".join(["temperature_2m", "temperature_2m_previous_day1", "temperature_2m_previous_day2"])
        for a, b in daterange(d0, d1 + dt.timedelta(days=1), 31):
            u = ("https://previous-runs-api.open-meteo.com/v1/forecast?" +
                 f"latitude={st['lat']}&longitude={st['lon']}&hourly={hourly}&temperature_unit=fahrenheit&timezone=GMT"
                 f"&start_date={a.isoformat()}&end_date={b.isoformat()}&models={','.join(models)}")
            obj, err = get(u, pause=1.0)
            if err or "hourly" not in (obj or {}):
                STATE["errors"].append(f"fcst {key} {a}: {err or str(obj)[:150]}")
                continue
            h = obj["hourly"]
            c = [k for k in h if k != "time"]
            cols = cols or c
            for i, t in enumerate(h["time"]):
                data[t] = [h[k][i] if k in h else "" for k in cols]
        if cols:
            gzcsv(f"{out}/weather/fcst_{key}.csv.gz", ["time"] + cols, [[t] + ["" if v is None else v for v in data[t]] for t in sorted(data)])
        info["fcst_rows"] = len(data)
        man["weather"][key] = info
        log(f"weather {key}: {info}")


# ---------------------------------------------------------------- sports
def ml(o, which):
    try:
        v = o[which]["moneyLine"]
        return v.get("american") or v.get("alternateDisplayValue") or ""
    except Exception:
        return ""


def pull_sports(cfg, d0, d1, out, man):
    for lg, path in cfg["leagues"].items():
        sport, league = path.split("/")
        rows, n_odds = [], 0
        seen = set()
        d = d0
        while d <= d1:
            u = f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d.strftime('%Y%m%d')}&limit=300"
            if league == "college-football":
                u += f"&groups={cfg.get('ncaaf_groups', '80')}"
            if league == "mens-college-basketball":
                u += "&groups=50"
            obj, err = get(u, pause=0.25)
            d += dt.timedelta(days=1)
            if err:
                STATE["errors"].append(f"espn sb {lg} {d}: {err}")
                continue
            for ev in obj.get("events", []):
                if ev["id"] in seen:
                    continue
                seen.add(ev["id"])
                try:
                    c = ev["competitions"][0]
                    home = next(x for x in c["competitors"] if x["homeAway"] == "home")
                    away = next(x for x in c["competitors"] if x["homeAway"] == "away")
                    completed = c["status"]["type"].get("completed")
                except Exception as e:
                    STATE["errors"].append(f"espn parse {lg} {ev.get('id')}: {e}")
                    continue
                row = [lg, ev["id"], ev["date"], completed, c["status"]["type"].get("name", ""),
                       home["team"].get("abbreviation", ""), home["team"].get("location", ""), home["team"].get("displayName", ""), home.get("score", ""), home.get("winner", ""),
                       away["team"].get("abbreviation", ""), away["team"].get("location", ""), away["team"].get("displayName", ""), away.get("score", ""), away.get("winner", "")]
                odds = [""] * 9
                if completed:
                    ou = f"https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{ev['id']}/competitions/{ev['id']}/odds"
                    oo, e2 = get(ou, pause=0.15, tries=3)
                    if not e2 and oo.get("items"):
                        it = oo["items"][0]
                        h, a = it.get("homeTeamOdds", {}), it.get("awayTeamOdds", {})
                        odds = [it.get("provider", {}).get("name", ""), ml(h, "open"), ml(a, "open"), ml(h, "close"), ml(a, "close"),
                                h.get("moneyLine", ""), a.get("moneyLine", ""), it.get("spread", ""), it.get("overUnder", "")]
                        n_odds += 1
                rows.append(row + odds)
        gzcsv(f"{out}/sports/games_{lg}.csv.gz",
              ["league", "espn_id", "start", "completed", "status", "home_abbr", "home_loc", "home_name", "home_score", "home_win",
               "away_abbr", "away_loc", "away_name", "away_score", "away_win",
               "book", "ml_home_open", "ml_away_open", "ml_home_close", "ml_away_close", "ml_home_cur", "ml_away_cur", "spread", "total"], rows)
        man["sports"][lg] = {"games": len(rows), "with_odds": n_odds}
        log(f"sports {lg}: {man['sports'][lg]}")


# ---------------------------------------------------------------- news
def pull_news(cfg, d0, d1, out, man):
    for label, query in cfg["queries"].items():
        data = {}
        for mode in ("timelinevolraw", "timelinetone"):
            for a, b in daterange(d0, d1, 3):
                u = ("https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
                    {"query": query, "mode": mode, "format": "json",
                     "startdatetime": a.strftime("%Y%m%d000000"), "enddatetime": (b + dt.timedelta(days=1)).strftime("%Y%m%d000000")}))
                obj, err = get(u, pause=7.0, tries=6, backoff=10.0)
                if err:
                    STATE["errors"].append(f"gdelt {label} {mode} {a}: {err}")
                    continue
                try:
                    for pt in obj["timeline"][0]["data"]:
                        r = data.setdefault(pt["date"], {})
                        r[mode] = pt.get("value")
                        if "norm" in pt:
                            r["norm"] = pt["norm"]
                except Exception as e:
                    STATE["errors"].append(f"gdelt parse {label} {mode} {a}: {e} {str(obj)[:100]}")
        gzcsv(f"{out}/news/{label}.csv.gz", ["date", "articles", "all_articles", "tone"],
              [[k, v.get("timelinevolraw", ""), v.get("norm", ""), v.get("timelinetone", "")] for k, v in sorted(data.items())])
        man["news"][label] = len(data)
        log(f"news {label}: {len(data)} buckets")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    req = json.load(open(a.request))
    out = a.out
    os.makedirs(out, exist_ok=True)
    d0, d1 = dt.date.fromisoformat(req["start"]), dt.date.fromisoformat(req["end"])
    man = {"request": req, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "weather": {}, "sports": {}, "news": {}}
    for name, fn in (("weather", pull_weather), ("sports", pull_sports), ("news", pull_news)):
        if req.get(name):
            try:
                fn(req[name], d0, d1, out, man)
            except Exception as e:  # keep partial output
                STATE["errors"].append(f"{name} crashed: {type(e).__name__}: {e}")
                log(f"{name} crashed: {e}")
    hashes = {}
    for root, _, files in os.walk(out):
        for fn_ in files:
            p = os.path.join(root, fn_)
            hashes[os.path.relpath(p, out)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    man.update({"finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "http_requests": STATE["requests"],
                "error_count": len(STATE["errors"]), "errors_first_50": STATE["errors"][:50], "sha256": hashes})
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    log(f"done requests={STATE['requests']} errors={len(STATE['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
