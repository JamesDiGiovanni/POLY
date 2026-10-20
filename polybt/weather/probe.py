"""One request per weather data source; prints what came back so the parsers can be checked."""
from __future__ import annotations

import json

from ..api import GAMMA_API, _as_list
from .data import AVWX, IEM, OPEN_METEO_PREVIOUS, market_rows
from .parse import parse_question, parse_station


def run(client, cfg) -> list[tuple[str, bool]]:
    results = []

    def check(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {str(e)[:300]}"
        results.append((name, ok))
        print(f"\n== {name}: {'OK' if ok else 'FAIL'}\n{detail}")

    def gamma(tag):
        def fn():
            page = _as_list(client.get_json(GAMMA_API, "/events", {"tag_slug": tag, "closed": "true", "limit": 100,
                                                                  "order": "endDate", "ascending": "false"}, cache=False))
            temp = [e for e in page if "temperature" in f"{e.get('title', '')} {e.get('slug', '')}".lower()]
            lines = [f"{len(page)} events, {len(temp)} temperature events"]
            if temp:
                ev = temp[0]
                rows, unparsed = market_rows(temp)
                ms = ev.get("markets") or []
                lines += [f"title: {ev.get('title')}", f"slug: {ev.get('slug')}", f"markets: {len(ms)}",
                          f"parsed rows from page: {len(rows)}, unparsed: {len(unparsed)} {unparsed[:3]}"]
                if ms:
                    m = ms[0]
                    lines += [f"question: {m.get('question')}", f"parsed: {parse_question(m.get('question') or '')}",
                              f"station: {parse_station(m.get('description') or '') or parse_station(ev.get('description') or '')}",
                              f"description: {(m.get('description') or ev.get('description') or '')[:500]}",
                              f"keys: {sorted(m)[:60]}"]
            return bool(temp), "\n".join(lines)
        return fn

    for tag in cfg["weather"]["gamma_tags"]:
        check(f"gamma events tag={tag}", gamma(tag))
    check("aviationweather station info", lambda: (
        True, json.dumps(client.get_json(AVWX, "/api/data/stationinfo", {"ids": "KLGA,EGLC", "format": "json"}, cache=False))[:600]))

    def iem():
        text = client.get_text(IEM, "/cgi-bin/request/asos.py", {
            "station": "KLGA", "data": "tmpf", "tz": "Etc/UTC", "format": "onlycomma", "latlon": "no", "elev": "no",
            "missing": "M", "trace": "T", "direct": "no", "report_type": [3, 4],
            "year1": 2026, "month1": 6, "day1": 1, "year2": 2026, "month2": 6, "day2": 2})
        return text.count("\n") > 2, "\n".join(text.splitlines()[:6])
    check("IEM ASOS observations", iem)

    def om():
        w = cfg["weather"]
        body = client.get_json(OPEN_METEO_PREVIOUS, "/v1/forecast", {
            "latitude": 40.78, "longitude": -73.88, "timezone": "auto", "models": ",".join(w["models"]),
            "hourly": ",".join(f"temperature_2m_previous_day{l}" for l in w["leads"]),
            "start_date": "2026-06-01", "end_date": "2026-06-02"}, cache=False)
        h = body.get("hourly") or {}
        return bool(h.get("time")), f"timezone {body.get('timezone')}; keys {sorted(h)}; first values " + \
            json.dumps({k: v[:3] for k, v in h.items()})[:800]
    check("Open-Meteo previous runs", om)
    return results
