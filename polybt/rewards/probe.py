"""One request per rewards endpoint; prints the shapes so the parser can be checked."""
from __future__ import annotations

import json

from ..api import CLOB_API, _as_list
from .api import RewardsAPI, parse_config


def run(client) -> list[tuple[str, bool]]:
    results, state = [], {}

    def check(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {str(e)[:300]}"
        results.append((name, ok))
        print(f"\n== {name}: {'OK' if ok else 'FAIL'}\n{detail}")

    def current():
        body = client.get_json(CLOB_API, "/rewards/markets/current", cache=False)
        rows = _as_list(body, "data")
        m = rows[0] if rows else {}
        state["cid"] = m.get("condition_id")
        top = {k: v for k, v in (body or {}).items() if k != "data"} if isinstance(body, dict) else {}
        return bool(rows), (f"{len(rows)} rows; envelope: {json.dumps(top)}\nkeys: {sorted(m)}\n"
                            f"sample: {json.dumps(m)[:1200]}\nparsed: {parse_config(m)}")
    check("rewards/markets/current", current)

    def market():
        body = RewardsAPI(client).market(state["cid"])
        return bool(body), f"keys: {sorted(body)}\nrewards: {json.dumps(body.get('rewards'))}\ntokens: {json.dumps(body.get('tokens'))[:400]}\nparsed: {parse_config(body)}"
    check("clob markets/{condition_id}", market)

    def total():
        ms = RewardsAPI(client).current()
        return bool(ms), (f"{len(ms)} markets, ${sum(m['daily_rate'] for m in ms):,.0f}/day; with token: "
                          f"{sum(bool(m['yes_token']) for m in ms)}; max_spread range "
                          f"{min((m['max_spread'] for m in ms), default=0)}-{max((m['max_spread'] for m in ms), default=0)}; "
                          f"min_size range {min((m['min_size'] for m in ms), default=0)}-{max((m['min_size'] for m in ms), default=0)}")
    check("all pages", total)
    return results
