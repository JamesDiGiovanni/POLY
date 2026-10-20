"""Phase 1: what would a $1,000 two-sided quote earn in liquidity rewards, market by market?

Pull every market paying rewards, snapshot its book several times, score the resting competition with
Polymarket's formula, and estimate our share of each day's pool. Ignores fills: being picked off by
informed traders is what phase 2 (paper market making with markouts) measures.
"""
from __future__ import annotations

import csv
import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..api import PolymarketAPI
from ..http import HttpClient
from .api import RewardsAPI, parse_config
from .scoring import book_score, expected_daily, our_quote

log = logging.getLogger(__name__)


def score_market(cfg_m: dict, book: dict, r: dict) -> dict:
    """One snapshot of one market."""
    bs = book_score(book["bids"], book["asks"], cfg_m["max_spread"], cfg_m["min_size"])
    if bs is None:
        return {"error": "no two-sided book above min size"}
    ours = our_quote(float(r["capital_usd"]), bs["mid"], cfg_m["max_spread"], cfg_m["min_size"],
                     float(r["quote_frac"]))
    rate = cfg_m["daily_rate"]
    return {"mid": bs["mid"], "theirs": bs["q_min"], "ours": ours["q_min"], "size": ours["size"],
            "daily": expected_daily(rate, ours["q_min"], bs["q_min"]),
            "daily_haircut": expected_daily(rate, ours["q_min"], bs["q_min"], float(r["competition_mult"]))}


def _fill_tokens(rapi: RewardsAPI, markets: list[dict]) -> None:
    missing = [m for m in markets if not m["yes_token"]]

    def one(m):
        try:
            full = parse_config(rapi.market(m["condition_id"]))
            m["yes_token"] = full["yes_token"]
            m["question"] = m["question"] or full["question"]
            for k in ("min_size", "max_spread", "daily_rate"):
                m[k] = m[k] or full[k]
        except Exception as e:
            log.warning("market %s: %s", m["condition_id"], e)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(one, missing))


def run(cfg) -> str:
    r = cfg["rewards"]
    h = cfg["http"]
    client = HttpClient(cfg["cache_dir"], h["requests_per_second"], h["timeout_s"], h["max_retries"], h["backoff_s"])
    rapi, papi = RewardsAPI(client), PolymarketAPI(client, cfg)
    # A pool smaller than the bar can never pay the bar, whatever our share.
    markets = [m for m in rapi.current() if m["condition_id"] and m["daily_rate"] >= float(r["min_daily_usd"])]
    log.info("%d markets pay rewards, $%.0f/day in total", len(markets), sum(m["daily_rate"] for m in markets))
    _fill_tokens(rapi, markets)
    markets = [m for m in markets if m["yes_token"] and m["max_spread"] > 0]

    snaps: dict[str, list[dict]] = {m["condition_id"]: [] for m in markets}
    n = int(r["snapshots"])
    for k in range(n):
        start = time.time()

        def one(m):
            try:
                return m["condition_id"], score_market(m, papi.book(m["yes_token"]), r)
            except Exception as e:
                return m["condition_id"], {"error": f"{type(e).__name__}: {str(e)[:80]}"}

        with ThreadPoolExecutor(16) as pool:
            for cid, s in pool.map(one, markets):
                snaps[cid].append(s)
        log.info("snapshot %d/%d done in %.0fs", k + 1, n, time.time() - start)
        if k + 1 < n:
            time.sleep(max(0.0, float(r["snapshot_interval_s"]) - (time.time() - start)))
    holding = []
    try:
        holding = rapi.holding_reward_markets()
    except Exception as e:
        log.warning("holding rewards: %s", e)
    return write_report(cfg, markets, snaps, holding)


def summarise(m: dict, ss: list[dict]) -> dict:
    ok = [s for s in ss if "error" not in s]
    med = lambda key: statistics.median(s[key] for s in ok) if ok else 0.0
    return {**m, "snapshots_ok": len(ok), "mid": med("mid"), "theirs": med("theirs"), "ours": med("ours"), "size": med("size"),
            "daily": med("daily"), "daily_haircut": med("daily_haircut"),
            "daily_haircut_min": min((s["daily_haircut"] for s in ok), default=0.0),
            "error": next((s["error"] for s in ss if "error" in s), "") if not ok else ""}


def write_report(cfg, markets, snaps, holding=()) -> str:
    r = cfg["rewards"]
    out = Path(cfg["output_dir"]) / "rewards"
    out.mkdir(parents=True, exist_ok=True)
    rows = sorted((summarise(m, snaps.get(m["condition_id"], [])) for m in markets), key=lambda x: -x["daily_haircut"])
    cols = ["condition_id", "question", "daily_rate", "min_size", "max_spread", "sponsored", "mid", "theirs",
            "size", "daily", "daily_haircut", "daily_haircut_min", "snapshots_ok", "error"]
    with open(out / "markets.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    cap, bar = float(r["capital_usd"]), float(r["min_daily_usd"])
    passing = [x for x in rows if x["daily_haircut"] >= bar]
    stable = [x for x in passing if x["daily_haircut_min"] >= bar]
    gate = len(passing) >= int(r["min_markets"])
    pool = sum(m["daily_rate"] for m in markets)
    top = rows[: int(r["top_n"])]
    top_daily = sum(x["daily_haircut"] for x in top)
    lines = [f"## Liquidity rewards phase 1: {'PASSED' if gate else 'FAILED'}", "",
             f"{len(markets)} markets pay at least ${bar:.0f}/day in rewards, **${pool:,.0f}/day** in total. Snapshots per market: {r['snapshots']} "
             f"(every {int(r['snapshot_interval_s']) // 60} min).", "",
             f"Hypothetical: ${cap:,.0f} per market, quoted on both sides at {r['quote_frac']} x the max spread from "
             f"the midpoint. Our share of each pool against the orders already resting there, with that competition "
             f"x{r['competition_mult']} as a haircut. Fills (being picked off) are not counted; phase 2 measures them.", "",
             f"Gate: at least {r['min_markets']} markets paying ≥ ${bar:.0f}/day per ${cap:,.0f} after the haircut. "
             f"Found **{len(passing)}** ({len(stable)} cleared the bar in every snapshot).", "",
             f"Best {len(top)} markets together: ${top_daily:,.2f}/day on ${cap * len(top):,.0f} "
             f"= {top_daily * 365 / (cap * len(top)) * 100 if top else 0:.0f}% a year before fills.", "",
             "| market | pool $/day | min size | max spread | mid | resting score | ours | $/day | $/day haircut | worst snapshot | annualised |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in rows[:50]:
        lines.append(f"| {x['question'][:60]} | {x['daily_rate']:.0f} | {x['min_size']:.0f} | {x['max_spread'] * 100:.1f}¢ | "
                     f"{x['mid']:.2f} | {x['theirs']:,.0f} | {x['ours']:,.0f} | {x['daily']:.2f} | "
                     f"{x['daily_haircut']:.2f} | {x['daily_haircut_min']:.2f} | {x['daily_haircut'] * 365 / cap * 100:.0f}% |")
    errs = sum(1 for x in rows if x["snapshots_ok"] == 0)
    if errs:
        lines += ["", f"{errs} markets had no usable book in any snapshot."]
    if holding:
        lines += ["", f"Holding rewards (4%/yr on positions held): {len(holding)} open markets flagged: " +
                  "; ".join((h['question'] or '')[:50] for h in holding[:15])]
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text)
    return text
