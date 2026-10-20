"""Kalshi public market data (trade-api v2, no login) and Kalshi's taker fee.

Prices come back either in cents (`yes_bid: 42`) or in dollars (`yes_bid_dollars: "0.42"`) depending
on API version; `_dollars` normalises both. The order book lists *bids* for YES and NO only: the best
YES ask is 1 - best NO bid, and vice versa.
"""
from __future__ import annotations

import math
from typing import Iterator

from ..api import _as_list
from ..http import HttpClient

KALSHI = "https://api.elections.kalshi.com"
BASE = "/trade-api/v2"


def _dollars(obj: dict, key: str) -> float | None:
    """A price field as dollars, from `<key>_dollars` (string/float dollars) or `<key>` (int cents)."""
    v = obj.get(f"{key}_dollars")
    if v not in (None, ""):
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    v = obj.get(key)
    if v in (None, ""):
        return None
    try:
        return float(v) / 100   # plain fields are integer cents
    except (TypeError, ValueError):
        return None


def taker_fee(contracts: float, price: float, multiplier: float = 1.0, rate: float = 0.07) -> float:
    """Kalshi taker fee in dollars for one order: rate x M x C x P x (1 - P), rounded up to the cent."""
    if contracts <= 0 or not 0 < price < 1:
        return 0.0
    return math.ceil(round(rate * multiplier * contracts * price * (1 - price) * 100, 9)) / 100


class Kalshi:
    def __init__(self, client: HttpClient):
        self.client = client

    def _get(self, path: str, params: dict | None = None):
        return self.client.get_json(KALSHI, BASE + path, params, cache=False)

    def events(self, status: str = "open", page_size: int = 200, max_pages: int = 200) -> Iterator[dict]:
        """Events with their markets nested."""
        cursor = None
        for _ in range(max_pages):
            body = self._get("/events", {"status": status, "limit": page_size, "with_nested_markets": "true",
                                         "cursor": cursor})
            yield from _as_list(body, "events")
            cursor = (body or {}).get("cursor") if isinstance(body, dict) else None
            if not cursor:
                return

    def series(self, ticker: str) -> dict:
        body = self._get(f"/series/{ticker}")
        return (body or {}).get("series") or {}

    def orderbook(self, ticker: str, depth: int = 10) -> dict:
        """{"yes_bids": [(price, qty)...] best first, "no_bids": [...]} in dollars."""
        body = self._get(f"/markets/{ticker}/orderbook", {"depth": depth})
        ob = (body or {}).get("orderbook") or (body or {}).get("orderbook_fp") or {}

        def side(name):
            in_dollars = bool(ob.get(f"{name}_dollars"))
            rows = ob.get(f"{name}_dollars") or ob.get(name) or []
            out = []
            for r in rows:
                try:
                    p, q = float(r[0]), float(r[1])
                except (TypeError, ValueError, IndexError):
                    continue
                out.append((p if in_dollars else p / 100, q))
            return sorted(out, key=lambda x: -x[0])

        return {"yes_bids": side("yes"), "no_bids": side("no")}


def asks_from_bids(opposite_bids: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """YES asks implied by NO bids (and vice versa): buying YES at 1 - p matches a NO bid at p."""
    return sorted(((round(1 - p, 6), q) for p, q in opposite_bids), key=lambda x: x[0])
