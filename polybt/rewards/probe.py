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


def books(client, cfg, n: int = 60) -> None:
    """Are the YES and NO books mirrors of one book, or separate? Compares the YES book with the NO book
    flipped (NO bid at p = YES ask at 1 - p) on the richest pools, and how the score changes if NO-book
    orders are added."""
    from ..api import PolymarketAPI
    from .scoring import book_score
    papi, rapi = PolymarketAPI(client, cfg), RewardsAPI(client)
    ms = sorted(rapi.current(), key=lambda m: -m["daily_rate"])[:n]
    same = differ = 0
    for m in ms:
        full = rapi.market(m["condition_id"])
        toks = {str(t.get("outcome", "")).lower(): t.get("token_id") for t in full.get("tokens") or []}
        if "yes" not in toks or "no" not in toks:
            continue
        y, no = papi.book(toks["yes"]), papi.book(toks["no"])
        flip_bids = sorted([(round(1 - p, 4), q) for p, q in no["asks"]], key=lambda lv: -lv[0])
        flip_asks = sorted([(round(1 - p, 4), q) for p, q in no["bids"]], key=lambda lv: lv[0])
        mirrored = y["bids"][:5] == flip_bids[:5] and y["asks"][:5] == flip_asks[:5]
        same += mirrored
        differ += not mirrored
        alone = book_score(y["bids"], y["asks"], m["max_spread"], m["min_size"])
        both = book_score(y["bids"] + flip_bids, y["asks"] + flip_asks, m["max_spread"], m["min_size"])
        print(f"{(full.get('question') or '')[:55]:55} pool {m['daily_rate']:6.0f} mirrored={mirrored} "
              f"yes bid/ask {y['bids'][0][0] if y['bids'] else None}/{y['asks'][0][0] if y['asks'] else None} "
              f"no-flipped {flip_bids[0][0] if flip_bids else None}/{flip_asks[0][0] if flip_asks else None} "
              f"score yes-only {alone and round(alone['q_min'])} with-no {both and round(both['q_min'])}")
        if differ == 1 and not mirrored:
            print("  yes book:", y["bids"][:4], y["asks"][:4], "\n  no book:", no["bids"][:4], no["asks"][:4])
    print(f"\nmirrored {same}, different {differ}")
