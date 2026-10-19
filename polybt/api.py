"""Thin wrappers over Polymarket's public read-only APIs."""
from __future__ import annotations

import json
import logging
import time
from typing import Iterator

from .http import HttpClient, HttpError

log = logging.getLogger(__name__)

DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"


def _as_list(body, *keys) -> list:
    """Endpoints return either a bare list or a dict wrapping one."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in keys + ("data", "results"):
            if isinstance(body.get(k), list):
                return body[k]
    return []


def _json_field(v) -> list:
    """Gamma encodes some list fields as JSON strings."""
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return []
    return list(v) if isinstance(v, (list, tuple)) else []


class PolymarketAPI:
    def __init__(self, client: HttpClient, cfg: dict):
        self.client = client
        self.cfg = cfg
        http = cfg["http"]
        self.mutable_ttl = float(http["mutable_ttl_s"])
        self.page_size = int(http["activity_page_size"])
        self.offset_cap = int(http["activity_offset_cap"])

    # ---- Data API -------------------------------------------------------

    def leaderboard(self, path: str, query: dict, limit: int, offset: int) -> list[dict]:
        body = self.client.get_json(DATA_API, path, {**query, "limit": limit, "offset": offset},
                                    ttl=self.mutable_ttl)
        return _as_list(body, "leaderboard")

    def market_trades(self, condition_id: str, limit: int, offset: int = 0) -> list[dict]:
        body = self.client.get_json(DATA_API, "/trades",
                                    {"market": condition_id, "limit": limit, "offset": offset,
                                     "takerOnly": "false"}, ttl=self.mutable_ttl)
        return _as_list(body)

    def recent_activity(self, user: str, limit: int = 500) -> list[dict]:
        """The wallet's newest activity rows, newest first (one request)."""
        return _as_list(self.client.get_json(DATA_API, "/activity", {"user": user, "limit": limit, "sortBy": "TIMESTAMP",
                                                                     "sortDirection": "DESC"}, ttl=self.mutable_ttl))

    def activity(self, user: str, start: int, end: int | None = None, live: bool = False) -> Iterator[dict]:
        """All activity rows for a wallet with start <= timestamp (<= end), oldest first.

        Pages by offset until the API's offset cap, then restarts the window at the last
        timestamp seen. Rows at the boundary repeat; the caller dedupes on insert.
        """
        offset, last_seen = 0, start
        while True:
            params = {"user": user, "limit": self.page_size, "offset": offset, "start": start,
                      "end": end, "sortBy": "TIMESTAMP", "sortDirection": "ASC"}
            # A page that lies wholly in the past can't change; anything else may.
            ttl = None if end is not None and end < time.time() - 86400 else self.mutable_ttl
            try:
                rows = _as_list(self.client.get_json(DATA_API, "/activity", params, ttl=ttl, cache=not live))
            except HttpError as e:
                if e.status != 400 or offset == 0:
                    raise
                rows = None  # deep offset refused
            if rows is not None:
                yield from rows
                last_seen = max([last_seen] + [int(r.get("timestamp", 0)) for r in rows])
                if len(rows) < self.page_size:
                    return
                offset += self.page_size
            if rows is None or offset >= self.offset_cap:
                # Restart the window at the last timestamp seen. If one second holds more rows
                # than a whole window, step past it rather than loop forever.
                start = last_seen if last_seen > start else start + 1
                offset = 0

    # ---- Gamma ----------------------------------------------------------

    def markets_by_condition(self, condition_ids: list[str], live: bool = False) -> list[dict]:
        if not condition_ids:
            return []
        found: dict[str, dict] = {}
        for closed in (None, "true"):
            missing = [c for c in condition_ids if c not in found]
            if not missing:
                break
            body = self.client.get_json(GAMMA_API, "/markets",
                                        {"condition_ids": missing, "closed": closed,
                                         "limit": len(missing)}, ttl=self.mutable_ttl, cache=not live)
            for m in _as_list(body):
                if m.get("conditionId"):
                    found[m["conditionId"]] = m
        return list(found.values())

    def top_closed_markets(self, limit: int, end_date_min: str, end_date_max: str | None = None,
                           offset: int = 0) -> list[dict]:
        body = self.client.get_json(GAMMA_API, "/markets",
                                    {"closed": "true", "order": "volumeNum", "ascending": "false",
                                     "end_date_min": end_date_min, "end_date_max": end_date_max,
                                     "limit": limit, "offset": offset},
                                    ttl=self.mutable_ttl)
        return _as_list(body)

    # ---- CLOB -----------------------------------------------------------

    def clob_market_info(self, condition_id: str) -> dict | None:
        """CLOB market info, including fee details `fd: {r, e, to}`. None if the CLOB doesn't know it."""
        try:
            body = self.client.get_json(CLOB_API, f"/clob-markets/{condition_id}", ttl=self.mutable_ttl)
        except HttpError as e:
            if e.status in (400, 404):
                return None
            raise
        return body if isinstance(body, dict) else None

    def book(self, token_id: str) -> dict:
        """Live order book: {"bids": [(price, size)...] best first, "asks": [...] best first}."""
        body = self.client.get_json(CLOB_API, "/book", {"token_id": token_id}, cache=False)

        def side(rows, best_high):
            levels = [(float(r["price"]), float(r["size"])) for r in rows or [] if float(r.get("size", 0)) > 0]
            return sorted(levels, key=lambda lv: -lv[0] if best_high else lv[0])

        return {"bids": side(body.get("bids"), True), "asks": side(body.get("asks"), False),
                "timestamp": body.get("timestamp")}

    def prices_history(self, token_id: str, start_ts: int, end_ts: int, fidelity: int) -> list[tuple[int, float]]:
        ttl = None if end_ts < time.time() - 3600 else self.mutable_ttl
        body = self.client.get_json(CLOB_API, "/prices-history",
                                    {"market": token_id, "startTs": start_ts, "endTs": end_ts,
                                     "fidelity": fidelity}, ttl=ttl)
        return [(int(p["t"]), float(p["p"])) for p in _as_list(body, "history")]


def parse_market(m: dict) -> dict:
    """Normalise a Gamma market into the columns of the markets table (category set later)."""
    import datetime as dt

    def ts(s):
        if not s:
            return None
        try:
            return int(dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp())
        except ValueError:
            return None

    tokens = [str(t) for t in _json_field(m.get("clobTokenIds"))]
    outcomes = [str(o) for o in _json_field(m.get("outcomes"))]
    try:
        payouts = [float(p) for p in _json_field(m.get("outcomePrices"))]
    except (TypeError, ValueError):
        payouts = []
    closed = bool(m.get("closed"))
    # Resolved means closed with final prices that are all 0, 0.5 or 1 (a 50/50 split is still final).
    resolved = (closed and len(payouts) == len(tokens) and len(tokens) > 0
                and all(min(abs(p), abs(p - 0.5), abs(p - 1)) < 1e-3 for p in payouts)
                and abs(sum(payouts) - 1) < 1e-2)
    winner = None
    if resolved:
        for t, p in zip(tokens, payouts):
            if p > 0.999:
                winner = t
    end_time = ts(m.get("endDate"))
    if closed:
        end_time = ts(m.get("closedTime")) or ts(m.get("umaEndDate")) or end_time
    volume = m.get("volumeNum", m.get("volume"))
    try:
        volume = float(volume) if volume is not None else None
    except (TypeError, ValueError):
        volume = None
    tags = [str(t.get("slug") or t.get("label") or "").lower()
            for ev in (m.get("events") or []) if isinstance(ev, dict) for t in (ev.get("tags") or []) if isinstance(t, dict)]
    tags += [str(t.get("slug") or t.get("label") or "").lower() for t in (m.get("tags") or []) if isinstance(t, dict)]
    return {
        "condition_id": m["conditionId"],
        "gamma_category": str(m.get("category") or "").lower(),
        "tags": [t for t in tags if t],
        "question": m.get("question") or "",
        "slug": m.get("slug") or "",
        "token_ids": tokens,
        "outcomes": outcomes,
        "payouts": payouts if resolved else [],
        "volume": volume,
        "end_time": end_time,
        "closed": closed,
        "resolved": resolved,
        "resolved_outcome": winner,
    }
