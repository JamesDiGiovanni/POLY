"""One request per endpoint the arbitrage work uses; prints the shapes so the parsers can be checked."""
from __future__ import annotations

import json

from ..api import GAMMA_API, _as_list
from .kalshi import BASE, KALSHI, Kalshi


def run(client) -> list[tuple[str, bool]]:
    results, state = [], {}

    def check(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {str(e)[:300]}"
        results.append((name, ok))
        print(f"\n== {name}: {'OK' if ok else 'FAIL'}\n{detail}")

    def events():
        body = client.get_json(KALSHI, BASE + "/events", {"status": "open", "limit": 50, "with_nested_markets": "true"},
                               cache=False)
        evs = _as_list(body, "events")
        ev = next((e for e in evs if e.get("markets")), evs[0] if evs else {})
        m = (ev.get("markets") or [{}])[0]
        markets = [mk for e in evs for mk in e.get("markets") or []]
        state["ticker"] = max(markets, key=lambda mk: float(mk.get("volume_24h") or mk.get("volume") or 0),
                              default={}).get("ticker")
        state["series"] = ev.get("series_ticker")
        return bool(evs), (f"{len(evs)} events; cursor={'yes' if (body or {}).get('cursor') else 'no'}\n"
                           f"event keys: {sorted(ev)}\nevent: {json.dumps({k: ev.get(k) for k in ('event_ticker', 'series_ticker', 'title', 'category')})}\n"
                           f"market keys: {sorted(m)}\nmarket sample: " +
                           json.dumps({k: m.get(k) for k in sorted(m) if k not in ('rules_primary', 'rules_secondary')})[:1500] +
                           f"\nrules_primary: {(m.get('rules_primary') or '')[:400]}")
    check("kalshi events + nested markets", events)

    def series():
        s = Kalshi(client).series(state["series"])
        return bool(s), f"keys: {sorted(s)}\n" + json.dumps(s)[:1200]
    check("kalshi series (settlement sources, fees)", series)

    def orderbook():
        body = client.get_json(KALSHI, BASE + f"/markets/{state['ticker']}/orderbook", {"depth": 5}, cache=False)
        parsed = Kalshi(client).orderbook(state["ticker"], 5)
        return bool(parsed["yes_bids"] or parsed["no_bids"]), f"ticker {state['ticker']}\nraw: {json.dumps(body)[:800]}\nparsed: {parsed}"
    check("kalshi orderbook", orderbook)

    def gamma():
        page = _as_list(client.get_json(GAMMA_API, "/markets", {"active": "true", "closed": "false", "order": "volume24hr",
                                                               "ascending": "false", "limit": 5}, cache=False))
        m = page[0] if page else {}
        ev = (m.get("events") or [{}])[0] if isinstance(m.get("events"), list) else {}
        return bool(page), (f"market keys: {sorted(m)[:80]}\nquestion: {m.get('question')}\noutcomes: {m.get('outcomes')}\n"
                            f"event keys: {sorted(ev)[:40]}\nevent title/category: {ev.get('title')} / {ev.get('category')}")
    check("polymarket open markets", gamma)
    return results
