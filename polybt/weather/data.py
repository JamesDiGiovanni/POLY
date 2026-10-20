"""Weather data: Polymarket temperature markets, station metadata, observed highs, issued forecasts, prices."""
from __future__ import annotations

import csv
import datetime as dt
import io
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from ..api import GAMMA_API, PolymarketAPI, _as_list, parse_market
from ..db import insert_many
from ..http import HttpClient, HttpError
from .parse import market_date, parse_question, parse_station

log = logging.getLogger(__name__)

AVWX = "https://aviationweather.gov"
IEM = "https://mesonet.agron.iastate.edu"
OPEN_METEO_PREVIOUS = "https://previous-runs-api.open-meteo.com"


def _iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- markets ---------------------------------------------------------------

def gamma_temperature_events(client: HttpClient, wcfg: dict, since_ts: int) -> list[dict]:
    """Closed temperature events since since_ts, for each configured tag.

    Gamma stops paging after roughly 1,000 results, and there are ~50 city-days a day, so the range
    is walked in windows of end dates small enough to page through completely.
    """
    events: dict[str, dict] = {}
    step = int(wcfg.get("discovery_window_days", 7)) * 86400
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    for tag in wcfg["gamma_tags"]:
        n_tag = 0
        for lo in range(since_ts, now, step):
            for offset in range(0, int(wcfg.get("max_events_per_window", 1000)), 100):
                try:
                    page = _as_list(client.get_json(GAMMA_API, "/events", {
                        "tag_slug": tag, "closed": "true", "limit": 100, "offset": offset,
                        "end_date_min": _iso(lo), "end_date_max": _iso(lo + step),
                        "order": "endDate", "ascending": "true"}, cache=False))
                except HttpError as e:
                    log.warning("events for tag %s at %s failed: %s", tag, _iso(lo), e)
                    break
                for ev in page:
                    title = f"{ev.get('title', '')} {ev.get('slug', '')}".lower()
                    if "temperature" in title and ev.get("id") is not None and str(ev["id"]) not in events:
                        events[str(ev["id"])] = ev
                        n_tag += 1
                if len(page) < 100:
                    break
                if offset + 100 >= int(wcfg.get("max_events_per_window", 1000)):
                    log.warning("tag %s window %s hit the page cap; shorten discovery_window_days", tag, _iso(lo))
        log.info("gamma tag %r: %d temperature events", tag, n_tag)
    return list(events.values())


def market_rows(events: list[dict]) -> tuple[list[tuple], list[str]]:
    """wx_markets rows from Gamma events, plus the questions that didn't parse (for the inventory)."""
    rows, unparsed = [], []
    for ev in events:
        ev_station = parse_station(ev.get("description") or "") or parse_station(ev.get("resolutionSource") or "")
        for raw in ev.get("markets") or []:
            if not raw.get("conditionId"):
                continue
            b = parse_question(raw.get("question") or "")
            if b is None:
                unparsed.append(raw.get("question") or "")
                continue
            m = parse_market(raw)
            date = market_date(b, m["end_time"])
            yes_idx = next((i for i, o in enumerate(m["outcomes"]) if o.lower() == "yes"), 0)
            if not date or yes_idx >= len(m["token_ids"]):
                unparsed.append(raw.get("question") or "")
                continue
            station = (parse_station(raw.get("description") or "") or parse_station(raw.get("resolutionSource") or "")
                       or ev_station)
            yes_won = (m["payouts"][yes_idx] > 0.5) if m["resolved"] and m["payouts"] else None
            rows.append((m["condition_id"], f"{b.city.lower()}|{date.isoformat()}", raw.get("question"),
                         m["token_ids"][yes_idx], b.city, station, b.unit, b.lo, b.hi, date, m["end_time"],
                         m["resolved"], yes_won, m["volume"], None))  # fee rate filled from the CLOB later
    return rows, unparsed


def ingest_markets(con, client: HttpClient, cfg) -> dict:
    w = cfg["weather"]
    since = int(dt.datetime.fromisoformat(str(w["data_start"])).replace(tzinfo=dt.timezone.utc).timestamp())
    events = gamma_temperature_events(client, w, since)
    rows, unparsed = market_rows(events)
    insert_many(con, "wx_markets", rows, "INSERT OR REPLACE")
    # Fill any missing station from the city's most common station (rules sometimes omit the link).
    con.execute("""
        UPDATE wx_markets m SET station = s.station FROM (
            SELECT city, mode(station) AS station FROM wx_markets WHERE station IS NOT NULL GROUP BY city) s
        WHERE m.station IS NULL AND m.city = s.city""")
    log.info("weather markets: %d events, %d markets stored, %d questions unparsed", len(events), len(rows), len(unparsed))
    return {"events": len(events), "markets": len(rows), "unparsed": unparsed}


def fetch_fee_rates(con, api: PolymarketAPI, workers: int = 16) -> None:
    """Each market's own taker fee rate from the CLOB (no `fd` = fee-free)."""
    ids = [r[0] for r in con.execute("SELECT condition_id FROM wx_markets WHERE fee_rate IS NULL").fetchall()]

    def one(cid):
        try:
            info = api.clob_market_info(cid)
        except Exception:
            return cid, None
        fd = (info or {}).get("fd") if info is not None else None
        return cid, (float(fd["r"]) if isinstance(fd, dict) and fd.get("r") is not None else (0.0 if info else None))

    with ThreadPoolExecutor(workers) as pool:
        for cid, rate in pool.map(one, ids):
            if rate is not None:
                con.execute("UPDATE wx_markets SET fee_rate = ? WHERE condition_id = ?", [rate, cid])


# ---- stations --------------------------------------------------------------

def ingest_stations(con, client: HttpClient) -> int:
    todo = [r[0] for r in con.execute("""
        SELECT DISTINCT station FROM wx_markets WHERE station IS NOT NULL
        AND station NOT IN (SELECT station FROM wx_stations)""").fetchall()]
    n = 0
    for i in range(0, len(todo), 20):
        ids = todo[i:i + 20]
        try:
            info = client.get_json(AVWX, "/api/data/stationinfo", {"ids": ",".join(ids), "format": "json"}, cache=False)
        except Exception as e:
            log.warning("station info %s failed: %s", ids, e)
            continue
        for s in _as_list(info):
            sid = s.get("icaoId") or s.get("id")
            if sid and s.get("lat") is not None and s.get("lon") is not None:
                con.execute("INSERT OR REPLACE INTO wx_stations VALUES (?, ?, ?, NULL)",
                            [sid, float(s["lat"]), float(s["lon"])])
                n += 1
    log.info("stations: %d located (%d requested)", n, len(todo))
    return n


# ---- observations ----------------------------------------------------------

def daily_max_from_csv(text: str, tz: str) -> dict[dt.date, tuple[float, int]]:
    """IEM ASOS CSV (station,valid,tmpf; UTC) -> {local date: (max °C, n observations)}."""
    zone = ZoneInfo(tz)
    best: dict[dt.date, list] = {}
    for row in csv.DictReader(io.StringIO("\n".join(l for l in text.splitlines() if not l.startswith("#")))):
        t = row.get("tmpf")
        if not t or t in ("M", ""):
            continue
        try:
            f = float(t)
            when = dt.datetime.strptime(row["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        except (ValueError, KeyError):
            continue
        day = when.astimezone(zone).date()
        c = (f - 32) * 5 / 9
        cur = best.setdefault(day, [c, 0])
        cur[0] = max(cur[0], c)
        cur[1] += 1
    return {d: (v[0], v[1]) for d, v in best.items()}


def ingest_obs(con, client: HttpClient, cfg) -> int:
    start = dt.date.fromisoformat(str(cfg["weather"]["data_start"]))
    end = dt.datetime.now(dt.timezone.utc).date()
    n = 0
    for station, tz in con.execute("SELECT station, tz FROM wx_stations WHERE tz IS NOT NULL").fetchall():
        last = con.execute("SELECT max(date) FROM wx_obs WHERE station = ?", [station]).fetchone()[0]
        frm = (last - dt.timedelta(days=2)) if last else start
        text = ""
        for sid in (station, station[1:] if station.startswith("K") else None):
            if not sid:
                continue
            try:
                text = client.get_text(IEM, "/cgi-bin/request/asos.py", {
                    "station": sid, "data": "tmpf", "tz": "Etc/UTC", "format": "onlycomma", "latlon": "no",
                    "elev": "no", "missing": "M", "trace": "T", "direct": "no", "report_type": [3, 4],
                    "year1": frm.year, "month1": frm.month, "day1": frm.day,
                    "year2": end.year, "month2": end.month, "day2": end.day})
            except Exception as e:
                log.warning("observations for %s failed: %s", sid, e)
                text = ""
            if text.count("\n") > 2:
                break
        days = daily_max_from_csv(text, tz)
        insert_many(con, "wx_obs", [(station, d, c, k) for d, (c, k) in days.items()], "INSERT OR REPLACE")
        n += len(days)
        log.info("observations %s: %d days", station, len(days))
    return n


# ---- forecasts -------------------------------------------------------------

def daily_max_forecasts(body: dict, models: list[str], leads: list[int], min_hours: int = 20):
    """Open-Meteo previous-runs hourly response -> [(model, lead, date, max °C)], plus its timezone."""
    hourly = body.get("hourly") or {}
    times = hourly.get("time") or []
    out = []
    for model in models:
        for lead in leads:
            key = f"temperature_2m_previous_day{lead}"
            # With several models each series is suffixed with the model name; with one, it isn't.
            series = hourly.get(f"{key}_{model}", hourly.get(key) if len(models) == 1 else None)
            if series is None:
                continue
            by_day: dict[str, list[float]] = defaultdict(list)
            for t, v in zip(times, series):
                if v is not None:
                    by_day[t[:10]].append(float(v))
            for d, vals in by_day.items():
                if len(vals) >= min_hours:
                    out.append((model, lead, dt.date.fromisoformat(d), max(vals)))
    return out, body.get("timezone")


def ingest_forecasts(con, client: HttpClient, cfg) -> int:
    w = cfg["weather"]
    models, leads = list(w["models"]), [int(x) for x in w["leads"]]
    start = dt.date.fromisoformat(str(w["data_start"]))
    end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    n = 0
    for station, lat, lon, tz in con.execute("SELECT station, lat, lon, tz FROM wx_stations").fetchall():
        last = con.execute("SELECT max(date) FROM wx_forecasts WHERE station = ?", [station]).fetchone()[0]
        frm = (last + dt.timedelta(days=1)) if last else start
        while frm <= end:
            to = min(end, frm + dt.timedelta(days=180))
            try:
                body = client.get_json(OPEN_METEO_PREVIOUS, "/v1/forecast", {
                    "latitude": lat, "longitude": lon, "timezone": "auto", "models": ",".join(models),
                    "hourly": ",".join(f"temperature_2m_previous_day{l}" for l in leads),
                    "start_date": frm.isoformat(), "end_date": to.isoformat()}, cache=False)
            except Exception as e:
                log.warning("forecasts %s %s..%s failed: %s", station, frm, to, e)
                break
            rows, zone = daily_max_forecasts(body, models, leads)
            if zone and not tz:
                tz = zone
                con.execute("UPDATE wx_stations SET tz = ? WHERE station = ?", [zone, station])
            insert_many(con, "wx_forecasts", [(station, m, l, d, v) for m, l, d, v in rows], "INSERT OR REPLACE")
            n += len(rows)
            frm = to + dt.timedelta(days=1)
        log.info("forecasts %s: done", station)
    return n


# ---- prices ----------------------------------------------------------------

def decision_ts(date: dt.date, lead: int, tz: str, hour: int) -> int:
    """When a lead-`lead` decision is made: `hour` local time, (lead - 1) days before the market's day.

    Open-Meteo's previous_day{lead} value for a valid hour is the forecast as it stood about `lead`
    days earlier, so the afternoon hours that set the day's high were published by the evening of
    D-lead. Midnight local on D-(lead-1) is therefore after publication for the hours that matter.
    """
    local = dt.datetime.combine(date - dt.timedelta(days=lead - 1), dt.time(hour), ZoneInfo(tz))
    return int(local.timestamp())


def ingest_prices(con, api: PolymarketAPI, cfg) -> int:
    """Each range's YES price history from a few days before its day until it closed."""
    w = cfg["weather"]
    todo = con.execute("""
        SELECT m.yes_token, m.date, m.end_time FROM wx_markets m
        WHERE m.resolved AND m.yes_token IS NOT NULL
          AND m.yes_token NOT IN (SELECT token_id FROM price_fetches WHERE start_ts = -1)""").fetchall()
    log.info("weather prices: %d tokens to fetch", len(todo))
    fid = int(w["price_fidelity_min"])

    def one(row):
        token, date, end_time = row
        start = int(dt.datetime.combine(date - dt.timedelta(days=int(w["price_days_before"])), dt.time(0),
                                        dt.timezone.utc).timestamp())
        end = (end_time or start + 5 * 86400) + 86400
        try:
            return token, api.prices_history(token, start, end, fid)
        except Exception as e:
            log.warning("prices %s failed: %s", token, e)
            return token, None

    n = 0
    with ThreadPoolExecutor(int(cfg["price_history"].get("workers", 16))) as pool:
        for i, (token, points) in enumerate(pool.map(one, todo)):
            if points is None:
                continue
            insert_many(con, "price_history", [(token, t, p) for t, p in points])
            con.execute("INSERT OR IGNORE INTO price_fetches VALUES (?, -1, -1)", [token])  # -1: full weather window
            n += len(points)
            if (i + 1) % 1000 == 0:
                log.info("  %d/%d tokens", i + 1, len(todo))
    return n


def run(con, cfg, steps=("markets", "stations", "forecasts", "obs", "prices")) -> None:
    h = cfg["http"]
    client = HttpClient(cfg["cache_dir"], {**h["requests_per_second"], **cfg["weather"]["requests_per_second"]},
                        h["timeout_s"], h["max_retries"], h["backoff_s"])
    api = PolymarketAPI(client, cfg)
    if "markets" in steps:
        ingest_markets(con, client, cfg)
        fetch_fee_rates(con, api)
    if "stations" in steps:
        ingest_stations(con, client)
    if "forecasts" in steps:
        ingest_forecasts(con, client, cfg)   # also sets each station's timezone
    if "obs" in steps:
        ingest_obs(con, client, cfg)
    if "prices" in steps:
        ingest_prices(con, api, cfg)
