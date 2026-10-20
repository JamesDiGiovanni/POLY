"""Phase 1: pull both venues, match, grade, take one live order-book snapshot of the pairs, report."""
from __future__ import annotations

import csv
import datetime as dt
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..api import PolymarketAPI
from ..http import HttpClient
from .kalshi import Kalshi, asks_from_bids
from .match import Pair, Ref, kalshi_refs, match, near_misses, polymarket_refs

log = logging.getLogger(__name__)


def walk_pair(yes_asks, no_asks, fee_yes, fee_no) -> dict:
    """Buy YES on one venue and NO on the other, level by level, while each pair of contracts still
    costs less than the $1 it is guaranteed to pay (fees included).

    yes_asks / no_asks: [(price, qty)] best first. fee_*: per-contract fee in dollars at a price.
    Returns the edge of the very first contract, and how many contracts / dollars of profit are
    available at a non-negative edge.
    """
    i = j = 0
    ry = yes_asks[0][1] if yes_asks else 0
    rn = no_asks[0][1] if no_asks else 0
    first, contracts, profit, cost = None, 0.0, 0.0, 0.0
    while i < len(yes_asks) and j < len(no_asks):
        py, pn = yes_asks[i][0], no_asks[j][0]
        edge = 1 - py - pn - fee_yes(py) - fee_no(pn)
        if first is None:
            first = edge
        if edge < 0:
            break
        q = min(ry, rn)
        contracts += q
        profit += q * edge
        cost += q * (py + pn)
        ry -= q
        rn -= q
        if ry <= 1e-9:
            i += 1
            ry = yes_asks[i][1] if i < len(yes_asks) else 0
        if rn <= 1e-9:
            j += 1
            rn = no_asks[j][1] if j < len(no_asks) else 0
    return {"first_edge": first, "contracts": contracts, "profit": profit, "cost": cost}


def snapshot(pair: Pair, papi: PolymarketAPI, kalshi: Kalshi, poly_fee_rate: float, kalshi_mult: float,
             kalshi_rate: float) -> dict:
    yes_p = papi.book(pair.poly.extra["yes_token"])["asks"]
    no_p = papi.book(pair.poly.extra["no_token"])["asks"]
    ob = kalshi.orderbook(pair.kalshi.id)
    yes_k, no_k = asks_from_bids(ob["no_bids"]), asks_from_bids(ob["yes_bids"])
    fp = lambda p: poly_fee_rate * p * (1 - p)
    fk = lambda p: kalshi_rate * kalshi_mult * p * (1 - p)   # per contract; whole-order rounding is < 1c
    a = walk_pair(yes_p, no_k, fp, fk)   # YES on Polymarket + NO on Kalshi
    b = walk_pair(yes_k, no_p, fk, fp)   # YES on Kalshi + NO on Polymarket
    best = max((("poly_yes+kalshi_no", a), ("kalshi_yes+poly_no", b)),
               key=lambda x: -9 if x[1]["first_edge"] is None else x[1]["first_edge"])
    top_depth = min(sum(p * q for p, q in yes_p[:1]), sum(p * q for p, q in no_k[:1]),
                    sum(p * q for p, q in yes_k[:1]), sum(p * q for p, q in no_p[:1])) if all(
        (yes_p, no_k, yes_k, no_p)) else 0.0
    return {"direction": best[0], **best[1], "top_depth_usd": top_depth,
            "poly_yes_ask": yes_p[0][0] if yes_p else None, "kalshi_yes_ask": yes_k[0][0] if yes_k else None}


def run(con, cfg, steps=("match", "snapshot")) -> str:
    a = cfg["arb"]
    h = cfg["http"]
    client = HttpClient(cfg["cache_dir"], {**h["requests_per_second"], **a["requests_per_second"]},
                        h["timeout_s"], h["max_retries"], h["backoff_s"])
    papi, kalshi = PolymarketAPI(client, cfg), Kalshi(client)
    polys, kalshis = polymarket_refs(client, cfg), kalshi_refs(kalshi, cfg)

    series_cache: dict[str, set] = {}
    fee_mult: dict[str, float] = {}

    def series_sources(k):
        t = k.extra.get("series_ticker")
        if not t:
            return set()
        if t not in series_cache:
            try:
                s = kalshi.series(t)
                text = " ".join(f"{x.get('name', '')} {x.get('url', '')}" for x in s.get("settlement_sources") or [])
                series_cache[t] = Ref("kalshi", t, "", None, rules=text).sources()
                fee_mult[t] = float(s.get("fee_multiplier") or 1.0)
            except Exception as e:
                log.warning("series %s failed: %s", t, e)
                series_cache[t] = set()
        return series_cache[t]

    pairs = match(polys, kalshis, cfg, series_sources)
    misses = near_misses(polys, kalshis, cfg)
    pairs.sort(key=lambda p: (p.grade, -(p.poly.extra.get("volume24h", 0) + p.kalshi.extra.get("volume24h", 0))))

    snaps: dict[int, dict] = {}
    if "snapshot" in steps:
        todo = list(enumerate(pairs[: int(a["snapshot_pairs"])]))

        def one(item):
            i, p = item
            try:
                info = papi.clob_market_info(p.poly.id.split("#")[0])
                rate = float(((info or {}).get("fd") or {}).get("r") or 0)  # no fd: fee-free
            except Exception:
                rate = float(a["poly_fee_fallback"])
            mult = fee_mult.get(p.kalshi.extra.get("series_ticker"), 1.0)
            try:
                return i, snapshot(p, papi, kalshi, rate, mult, float(a["kalshi_fee_rate"]))
            except Exception as e:
                return i, {"error": f"{type(e).__name__}: {str(e)[:100]}"}

        with ThreadPoolExecutor(8) as pool:
            snaps = dict(pool.map(one, todo))
    return write_report(cfg, polys, kalshis, pairs, snaps, misses)


def _days(p: Pair) -> str:
    if not p.kalshi.close_ts:
        return "–"
    return str(max(1, round((p.kalshi.close_ts - dt.datetime.now(dt.timezone.utc).timestamp()) / 86400)))


def annualised(edge: float | None, days: float) -> float | None:
    """Return per year on the capital locked in both legs until settlement (simple, not compounded)."""
    if edge is None or edge <= -1 or days <= 0:
        return None
    return edge / (1 - edge) * 365 / days


def _annual(p: Pair, s: dict) -> str:
    d = _days(p)
    a = annualised(s.get("first_edge"), float(d)) if d != "–" else None
    return "–" if a is None else f"{a * 100:+.0f}%"


def write_report(cfg, polys, kalshis, pairs: list[Pair], snaps: dict[int, dict], misses=()) -> str:
    a = cfg["arb"]
    out = Path(cfg["output_dir"]) / "arb"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "pairs.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["grade", "score", "poly_id", "poly_market", "poly_outcome", "kalshi_ticker", "kalshi_market",
                    "poly_close", "kalshi_close", "shared_sources", "grade_reasons", "snapshot"])
        day = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat() if ts else ""
        for i, p in enumerate(pairs):
            w.writerow([p.grade, f"{p.score:.2f}", p.poly.id, p.poly.extra.get("question"), p.poly.extra.get("outcome"),
                        p.kalshi.id, p.kalshi.text, day(p.poly.close_ts), day(p.kalshi.close_ts),
                        ";".join(sorted(p.shared_sources)), "; ".join(p.reasons), json.dumps(snaps.get(i, {}))])

    n_a = sum(p.grade == "A" for p in pairs)
    liquid_a = [i for i, p in enumerate(pairs) if p.grade == "A"
                and snaps.get(i, {}).get("top_depth_usd", 0) >= float(a["min_depth_usd"])]
    positive = [i for i, s in snaps.items() if (s.get("first_edge") or -1) > 0]
    gate = len(liquid_a) >= int(a["min_grade_a_pairs"])
    pct = lambda v: "–" if v is None else f"{v * 100:+.1f}¢"
    lines = [f"## Arbitrage phase 1: {'PASSED' if gate else 'FAILED'}", "",
             f"{len(polys)} Polymarket sides and {len(kalshis)} Kalshi markets open. {len(pairs)} matched pairs: "
             f"**{n_a} grade A** (same proposition and a shared resolution source), {len(pairs) - n_a} grade B "
             f"(plausible, but settlement may differ).", "",
             f"Gate: at least {a['min_grade_a_pairs']} grade-A pairs with ≥ ${a['min_depth_usd']} at the best price "
             f"on every leg. Found **{len(liquid_a)}**.", "",
             f"Snapshot of {len(snaps)} pairs: {len(positive)} showed a positive edge after both fees at the moment "
             "of the snapshot (a single moment; the logger in phase 2 measures how often and how long).", "",
             "Annualised = edge ÷ capital tied up (both legs) × 365 ÷ days until settlement; compare with ~4% risk-free.", "",
             "| grade | score | Polymarket | Kalshi | close | days | best edge | annualised | contracts at ≥0 | profit |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    order = sorted(range(len(pairs)), key=lambda i: (pairs[i].grade, -(snaps.get(i, {}).get("first_edge") or -9)))
    for i in order[:60]:
        p, s = pairs[i], snaps.get(i, {})
        close = dt.datetime.fromtimestamp(p.kalshi.close_ts, dt.timezone.utc).date() if p.kalshi.close_ts else "–"
        q = (p.poly.extra.get("question") or "")[:60] + (f" [{p.poly.extra['outcome']}]" if p.poly.extra.get("outcome") not in (None, "Yes") else "")
        lines.append(f"| {p.grade} | {p.score:.2f} | {q} | {p.kalshi.text[:60]} | {close} | {_days(p)} | "
                     f"{pct(s.get('first_edge'))} | {_annual(p, s)} | {s.get('contracts', 0):.0f} | ${s.get('profit', 0):.2f} |")
    by_cat: dict[str, list[int]] = {}
    for p in pairs:
        by_cat.setdefault(p.kalshi.category or "?", [0, 0])
        by_cat[p.kalshi.category or "?"][0 if p.grade == "A" else 1] += 1
    lines += ["", "Pairs by Kalshi category (A / B): " +
              ", ".join(f"{c} {v[0]}/{v[1]}" for c, v in sorted(by_cat.items(), key=lambda kv: -sum(kv[1])))]
    if misses:
        with open(out / "near_misses.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["poly_market", "poly_outcome", "closest_kalshi", "similarity", "why_not_matched"])
            w.writerows(misses)
        kinds = Counter()
        for *_, why in misses:
            for part in why.split("; "):
                kinds[part.split(" ")[0] if not part.startswith("would") else "would match"] += 1
        lines += ["", f"Near misses for the {len(misses)} most-traded Polymarket sides (closest Kalshi market, "
                  "why rejected): " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()), "",
                  "| Polymarket | closest Kalshi | sim | why not |", "|---|---|---|---|"]
        for q, o, k, s, why in misses[:40]:
            lines.append(f"| {(q or '')[:55]}{' [' + o + ']' if o and o != 'Yes' else ''} | {k[:55]} | {s} | {why[:70]} |")
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text)
    return text
