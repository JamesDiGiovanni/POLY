"""One request to every endpoint the tool depends on; prints the response shape.

Run first against the real API to confirm the assumptions the code makes about field names.
"""
from __future__ import annotations

import json
import time

from .api import CLOB_API, DATA_API, GAMMA_API, _as_list


def _shape(v, depth=0):
    if isinstance(v, dict):
        return {k: _shape(x, depth + 1) if depth < 1 else type(x).__name__ for k, x in list(v.items())[:40]}
    if isinstance(v, list):
        return [f"list[{len(v)}]", _shape(v[0], depth) if v else None]
    return type(v).__name__


def run(api, cfg) -> list[tuple[str, bool, str]]:
    c, results = api.client, []

    def check(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {str(e)[:300]}"
        results.append((name, ok, detail))
        print(f"\n== {name}: {'OK' if ok else 'FAIL'}\n{detail}")
        return ok

    lb = cfg["discovery"]["leaderboard"]
    state = {}

    def leaderboard():
        rows = api.leaderboard(lb["path"], lb["queries"][0], 5, 0)
        state["wallet"] = next((r.get("proxyWallet") for r in rows if r.get("proxyWallet")), None)
        return bool(rows and state["wallet"]), json.dumps(_shape(rows), indent=1)[:1500]

    def activity():
        rows = list(api.client.get_json(DATA_API, "/activity", {"user": state["wallet"], "limit": 5,
                                                                "sortBy": "TIMESTAMP", "sortDirection": "DESC"}, cache=False))
        state["trade"] = next((r for r in rows if r.get("type") == "TRADE"), None)
        need = {"timestamp", "type", "side", "asset", "conditionId", "price", "size", "usdcSize", "transactionHash"}
        missing = need - set(state["trade"] or {})
        return bool(state["trade"]) and not missing, f"missing: {sorted(missing)}\n" + json.dumps(_shape(rows), indent=1)[:1500]

    def gamma():
        cid = (state.get("trade") or {}).get("conditionId")
        rows = api.markets_by_condition([cid], live=True)
        state["market"] = rows[0] if rows else None
        need = {"conditionId", "clobTokenIds", "outcomes", "outcomePrices", "closed", "endDate"}
        missing = need - set(state["market"] or {})
        return bool(rows) and not missing, f"missing: {sorted(missing)}\n" + json.dumps(_shape(rows), indent=1)[:2500]

    def clob_info():
        info = api.clob_market_info(state["market"]["conditionId"])
        return info is not None, f"fd = {(info or {}).get('fd')}\n" + json.dumps(_shape(info), indent=1)[:1500]

    def prices():
        token = state["trade"]["asset"]
        ts = int(state["trade"]["timestamp"])
        pts = api.client.get_json(CLOB_API, "/prices-history",
                                  {"market": token, "startTs": ts - 3600, "endTs": ts + 3600, "fidelity": 1}, cache=False)
        hist = _as_list(pts, "history")
        return bool(hist), f"{len(hist)} points around the trade; first: {hist[:2]}"

    def active_market():
        rows = api.client.get_json(GAMMA_API, "/markets", {"closed": "false", "active": "true", "order": "volume24hr",
                                                           "ascending": "false", "limit": 5}, cache=False)
        rows = [r for r in _as_list(rows) if r.get("enableOrderBook", True)]
        state["active"] = rows[0] if rows else None
        return bool(rows), "; ".join(str(r.get("question"))[:60] for r in rows)

    def active_fees():
        found = []
        for r in _as_list(api.client.get_json(GAMMA_API, "/markets", {"closed": "false", "active": "true",
                                                                      "order": "volume24hr", "ascending": "false",
                                                                      "limit": 20}, cache=False)):
            info = api.client.get_json(CLOB_API, f"/clob-markets/{r['conditionId']}", cache=False)
            found.append(f"{str(r.get('question'))[:50]!r}: fd={info.get('fd')} keys={sorted(info)}")
        with_fd = sum("fd={'" in f for f in found)
        return with_fd > 0, f"{with_fd}/{len(found)} active markets carry fd\n" + "\n".join(found)

    def active_book():
        tokens = state["active"]["clobTokenIds"]
        token = (json.loads(tokens) if isinstance(tokens, str) else tokens)[0]
        b = api.book(token)
        return bool(b["bids"] or b["asks"]), f"bids {len(b['bids'])} asks {len(b['asks'])} best {b['bids'][:2]} / {b['asks'][:2]}"

    def top_markets():
        rows = api.top_closed_markets(3, time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(time.time() - 30 * 86400)))
        return bool(rows), f"{len(rows)} markets: " + "; ".join(str(r.get("question"))[:60] for r in rows)

    if check("data-api leaderboard", leaderboard):
        if check("data-api activity", activity):
            if check("gamma markets by condition", gamma):
                check("clob market info (fees), traded market", clob_info)
            check("clob prices-history", prices)
    check("gamma top closed markets", top_markets)
    if check("gamma active markets", active_market):
        check("clob book, active market", active_book)
    check("clob fee details on active markets", active_fees)
    return results
