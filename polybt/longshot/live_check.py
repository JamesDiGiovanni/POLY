"""Can the backtest's prices actually be bought? Open markets ending in 1-7 days whose cheap side trades at
10-20c by the same last-price measure the backtest used, against their live order books.

The backtest paid last price + 2c. Here: the real best ask on the cheap side, how much it costs over the
last price, and how many dollars can be bought within a few cents of it.
"""
from __future__ import annotations

import csv
import datetime as dt
import logging
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..api import GAMMA_API, PolymarketAPI, _as_list, _json_field

log = logging.getLogger(__name__)

KINDS = [("draw", r"draw"), ("over/under", r"o/u|over|under"),
         ("game winner", r" vs\.? |win on \d{4}-\d\d-\d\d|\(bo\d\)|map \d"),
         ("crypto price", r"bitcoin|btc|ethereum|solana|xrp|price of"),
         ("tweets/temperature", r"tweet|posts?\b|truth social|temperature|°"),
         ("other", r".")]


def kind(question: str) -> str:
    q = question.lower()
    return next(n for n, pt in KINDS if re.search(pt, q))


def open_markets(client, c: dict) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc)
    out, seen = [], set()
    for d in range(int(c["live_days"])):
        lo = (now + dt.timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hi = (now + dt.timedelta(days=d + 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for offset in range(0, 1000, 100):
            page = _as_list(client.get_json(GAMMA_API, "/markets", {
                "active": "true", "closed": "false", "end_date_min": lo, "end_date_max": hi, "order": "volumeNum",
                "ascending": "false", "limit": 100, "offset": offset}, cache=False))
            for m in page:
                toks, outs = _json_field(m.get("clobTokenIds")), _json_field(m.get("outcomes"))
                if (m.get("conditionId") in seen or len(toks) != 2 or not m.get("enableOrderBook", True)
                        or float(m.get("volumeNum") or 0) < float(c["min_volume"])):
                    continue
                seen.add(m["conditionId"])
                low = [str(o).lower() for o in outs]
                yes_i = low.index("yes") if "yes" in low else 0
                out.append({"question": m.get("question") or "", "end": m.get("endDate"),
                            "yes": str(toks[yes_i]), "no": str(toks[1 - yes_i]),
                            "volume": float(m.get("volumeNum") or 0)})
            if len(page) < 100 or float(page[-1].get("volumeNum") or 0) < float(c["min_volume"]):
                break
    return out


def check(api: PolymarketAPI, m: dict, c: dict, now: int) -> dict | None:
    pts = api.prices_history(m["yes"], now - 2 * 3600, now, 60)
    if not pts:
        return None
    p = pts[-1][1]
    q = min(p, 1 - p)
    if not 0.10 < q <= 0.20:
        return None
    token = m["yes"] if p < 0.5 else m["no"]
    book = api.book(token)
    asks, bids = book["asks"], book["bids"]
    if not asks:
        return {**m, "kind": kind(m["question"]), "last": q, "ask": None}
    ask = asks[0][0]
    depth = lambda within: sum(px * sz for px, sz in asks if px <= q + within + 1e-9)
    return {**m, "kind": kind(m["question"]), "last": q, "ask": ask, "bid": bids[0][0] if bids else None,
            "gap": ask - q, "usd_within_2c": depth(0.02), "usd_within_5c": depth(0.05), "usd_at_ask": asks[0][0] * asks[0][1]}


def run(api: PolymarketAPI, cfg) -> str:
    c = cfg["longshot"]
    markets = open_markets(api.client, c)
    log.info("open markets ending in %s days, volume >= $%s: %d", c["live_days"], c["min_volume"], len(markets))
    now = int(time.time())

    def one(m):
        try:
            return check(api, m, c, now)
        except Exception as e:
            log.warning("%s: %s", m["question"][:40], str(e)[:100])
            return None

    with ThreadPoolExecutor(16) as pool:
        rows = [r for r in pool.map(one, markets) if r]
    return write(cfg, markets, rows)


def write(cfg, markets, rows) -> str:
    out = Path(cfg["output_dir"]) / "longshot"
    out.mkdir(parents=True, exist_ok=True)
    cols = ["kind", "question", "end", "last", "bid", "ask", "gap", "usd_at_ask", "usd_within_2c", "usd_within_5c", "volume"]
    with open(out / "live_check.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    priced = [r for r in rows if r.get("ask") is not None]
    med = lambda xs: statistics.median(xs) if xs else float("nan")
    lines = ["## Longshot live check: can the backtest's prices be bought?", "",
             f"{len(markets):,} open two-outcome markets ending in the next {cfg['longshot']['live_days']} days "
             f"(volume ≥ ${float(cfg['longshot']['min_volume']):,.0f}). {len(rows)} have a side at 10-20¢ by the backtest's "
             f"measure (last hourly price); {len(rows) - len(priced)} of those have no ask at all.", "",
             "Gap = best ask on the cheap side minus that price. The backtest assumed 2¢.", "",
             "| kind | markets | median gap | gap ≤ 2¢ | gap ≤ 5¢ | median $ at ask | median $ within 5¢ |",
             "|---|---|---|---|---|---|---|"]
    for name, _ in KINDS + [("all", "")]:
        g = priced if name == "all" else [r for r in priced if r["kind"] == name]
        if not g:
            continue
        lines.append(f"| {name} | {len(g)} | {med([r['gap'] for r in g]) * 100:+.1f}¢ | "
                     f"{sum(r['gap'] <= 0.02 + 1e-9 for r in g) / len(g):.0%} | {sum(r['gap'] <= 0.05 + 1e-9 for r in g) / len(g):.0%} | "
                     f"${med([r['usd_at_ask'] for r in g]):,.0f} | ${med([r['usd_within_5c'] for r in g]):,.0f} |")
    lines += ["", "Examples (largest volume first):", "", "| kind | market | last | bid | ask | $ within 5¢ |", "|---|---|---|---|---|---|"]
    for r in sorted(priced, key=lambda r: -r["volume"])[:30]:
        bid = "–" if r["bid"] is None else f"{r['bid'] * 100:.1f}¢"
        lines.append(f"| {r['kind']} | {r['question'][:60]} | {r['last'] * 100:.1f}¢ | {bid} | {r['ask'] * 100:.1f}¢ | "
                     f"${r['usd_within_5c']:,.0f} |")
    text = "\n".join(lines) + "\n"
    (out / "live_check.md").write_text(text)
    return text
