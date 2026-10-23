"""Resolved Polymarket markets and their price paths into the last weeks before the scheduled end."""
from __future__ import annotations

import datetime as dt
import logging
from concurrent.futures import ThreadPoolExecutor

from ..api import PolymarketAPI, _json_field, parse_market
from ..db import insert_many
from ..ingest import fee_category

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS ls_markets (
    condition_id VARCHAR PRIMARY KEY, question VARCHAR, event_id VARCHAR, neg_risk BOOLEAN,
    yes_token VARCHAR, yes_won DOUBLE, scheduled_end BIGINT, closed_ts BIGINT, volume DOUBLE,
    fee_category VARCHAR);
CREATE TABLE IF NOT EXISTS ls_prices (token VARCHAR, ts BIGINT, price DOUBLE, PRIMARY KEY (token, ts));
CREATE TABLE IF NOT EXISTS ls_fetched (token VARCHAR PRIMARY KEY, n INTEGER);
"""


def _ts(s) -> int | None:
    try:
        return int(dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()) if s else None
    except ValueError:
        return None


def market_row(m: dict, cfg) -> tuple | None:
    """A resolved two-outcome market -> ls_markets row; None for anything else (50/50s, unresolved)."""
    p = parse_market(m)
    if not p["resolved"] or len(p["token_ids"]) != 2 or p["resolved_outcome"] is None:
        return None
    outcomes = [o.lower() for o in p["outcomes"]]
    yes_i = outcomes.index("yes") if "yes" in outcomes else 0
    yes = p["token_ids"][yes_i]
    events = m.get("events") or []
    event_id = str((events[0] or {}).get("id") or "") if events and isinstance(events[0], dict) else ""
    return (p["condition_id"], p["question"], event_id or p["condition_id"], bool(m.get("negRisk")), yes,
            1.0 if p["resolved_outcome"] == yes else 0.0, _ts(m.get("endDate")), _ts(m.get("closedTime")),
            p["volume"], fee_category(p, cfg))


def ingest_markets(con, api: PolymarketAPI, cfg) -> int:
    """Walk closed markets by end-date window (Gamma stops paging near 1,000), highest volume first,
    down to min_volume."""
    c = cfg["longshot"]
    con.execute(SCHEMA)
    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=int(c["lookback_days"]))
    step = dt.timedelta(days=int(c["window_days"]))
    total = 0
    t = start
    while t < now:
        lo, hi = t.strftime("%Y-%m-%dT%H:%M:%SZ"), min(t + step, now).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows, offset = [], 0
        while offset < int(c["max_per_window"]):
            page = api.top_closed_markets(100, lo, hi, offset)
            rows += [r for r in (market_row(m, cfg) for m in page) if r]
            vols = [float(m.get("volumeNum") or 0) for m in page]
            if len(page) < 100 or (vols and min(vols) < float(c["min_volume"])):
                break
            offset += 100
        rows = [r for r in rows if (r[8] or 0) >= float(c["min_volume"])]
        if rows:
            insert_many(con, "ls_markets", rows, "INSERT OR REPLACE")
        total += len(rows)
        log.info("markets ending %s..%s: %d (total %d)", lo[:10], hi[:10], len(rows), total)
        t += step
    return total


def ingest_prices(con, api: PolymarketAPI, cfg) -> int:
    """Hourly YES prices in the day before each decision time (the CLOB rejects long spans). Decision
    times after the market already closed are skipped: there is nothing left to bet on."""
    c = cfg["longshot"]
    con.execute(SCHEMA)
    age = int(c["max_price_age_h"]) * 3600
    todo = con.execute("""SELECT yes_token, scheduled_end, closed_ts FROM ls_markets
                          WHERE scheduled_end IS NOT NULL AND yes_token NOT IN (SELECT token FROM ls_fetched)""").fetchall()
    log.info("price paths to fetch: %d markets", len(todo))

    def one(item):
        token, end, closed = item
        pts = []
        for h in c["horizons_days"]:
            ts = int(end) - int(h) * 86400
            if closed and closed <= ts:
                continue
            try:
                pts += api.prices_history(token, ts - age, ts, int(c["fidelity_min"]))
            except Exception as e:
                log.warning("prices %s: %s", token[:12], str(e)[:120])
                return token, None
        return token, pts

    done = 0
    with ThreadPoolExecutor(int(cfg["price_history"]["workers"])) as pool:
        for token, pts in pool.map(one, todo):
            if pts is None:
                continue
            if pts:
                insert_many(con, "ls_prices", sorted(set((token, t, p) for t, p in pts)), "INSERT OR REPLACE")
            con.execute("INSERT OR REPLACE INTO ls_fetched VALUES (?, ?)", [token, len(pts)])
            done += 1
            if done % 2000 == 0:
                log.info("prices: %d / %d", done, len(todo))
    return done
