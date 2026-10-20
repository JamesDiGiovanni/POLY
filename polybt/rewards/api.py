"""Reward configurations from the CLOB. Field names vary between endpoint versions, so parsing is lenient."""
from __future__ import annotations

from ..api import CLOB_API, GAMMA_API, _as_list, _json_field

END_CURSOR = "LTE="


def _f(d: dict, *keys, default=0.0) -> float:
    for k in keys:
        if d.get(k) not in (None, ""):
            try:
                return float(d[k])
            except (TypeError, ValueError):
                pass
    return default


def parse_config(m: dict) -> dict:
    """One market's reward terms -> {condition_id, daily_rate, min_size, max_spread (price units), tokens...}."""
    r = m.get("rewards") if isinstance(m.get("rewards"), dict) else {}
    rates = (m.get("rewards_config") or r.get("rates") or m.get("rates") or [])
    daily = _f(m, "total_daily_rate", default=None)
    daily = daily if daily is not None else sum(_f(x, "rate_per_day", "rewards_daily_rate", "daily_rate") for x in rates if isinstance(x, dict))
    max_spread_c = _f(m, "rewards_max_spread", "max_spread") or _f(r, "max_spread")
    tokens = [t for t in m.get("tokens") or [] if isinstance(t, dict)]
    yes = next((t for t in tokens if str(t.get("outcome", "")).lower() == "yes"), tokens[0] if tokens else {})
    return {"condition_id": m.get("condition_id") or m.get("conditionId"),
            "question": m.get("question") or m.get("market_slug") or "",
            "daily_rate": daily,
            "min_size": _f(m, "rewards_min_size", "min_size") or _f(r, "min_size"),
            "max_spread": max_spread_c / 100.0,   # the API gives cents
            "sponsored": _f(m, "total_daily_rate") > _f(m, "native_daily_rate", default=_f(m, "total_daily_rate")),
            "yes_token": yes.get("token_id"),
            "no_token": next((t.get("token_id") for t in tokens if t is not yes), None),
            "tick": _f(m, "minimum_tick_size", default=0.01),
            "end": m.get("end_date_iso"),
            "yes_price": _f(yes, "price", default=None)}


class RewardsAPI:
    def __init__(self, client):
        self.client = client

    def current(self, max_pages: int = 50) -> list[dict]:
        out, cursor = [], ""
        for _ in range(max_pages):
            params = {"next_cursor": cursor} if cursor else {}
            body = self.client.get_json(CLOB_API, "/rewards/markets/current", params, cache=False)
            out += [parse_config(m) for m in _as_list(body, "data")]
            cursor = (body or {}).get("next_cursor") if isinstance(body, dict) else None
            if not cursor or cursor == END_CURSOR:
                break
        return out

    def market(self, condition_id: str) -> dict:
        return self.client.get_json(CLOB_API, f"/markets/{condition_id}", cache=False) or {}

    def taker_trades(self, condition_id: str, limit: int = 500) -> list[dict]:
        """The market's newest taker prints, both outcome tokens, newest first."""
        from ..api import DATA_API
        return _as_list(self.client.get_json(DATA_API, "/trades", {"market": condition_id, "limit": limit,
                                                                  "takerOnly": "true"}, cache=False))

    def holding_reward_markets(self, max_pages: int = 10) -> list[dict]:
        """Open Gamma markets flagged for holding rewards (4% a year on positions held)."""
        out = []
        for page in range(max_pages):
            rows = _as_list(self.client.get_json(GAMMA_API, "/markets", {"active": "true", "closed": "false",
                                                                         "limit": 100, "offset": page * 100,
                                                                         "order": "volume24hr", "ascending": "false"},
                                                 cache=False))
            out += [{"question": m.get("question"), "condition_id": m.get("conditionId"),
                     "prices": _json_field(m.get("outcomePrices")), "end": m.get("endDate")}
                    for m in rows if m.get("holdingRewardsEnabled")]
            if len(rows) < 100:
                break
        return out
