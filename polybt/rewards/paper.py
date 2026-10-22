"""Phase 2: paper market making for liquidity rewards.

Quotes both sides of a set of reward markets (on paper) around the adjusted midpoint, re-quoting every
minute. Real taker prints from the Data API decide fills: a print through our price fills us, a print at
our price fills us only after the size that was resting there before us. Every minute it also accrues
our share of the market's reward pool against the real resting book. Fills are marked against the
midpoint 5, 30 and 120 minutes later: the markout is what being picked off costs.

Prices are in YES terms throughout. The YES and NO books mirror each other (checked by rw-probe), so a
bid on NO at p is an ask on YES at 1 - p, and a NO print is a YES print on the other side at 1 - p.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import math
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from ..api import PolymarketAPI
from ..http import HttpClient
from .api import RewardsAPI, parse_config
from .scoring import book_score, q_min, side_score

log = logging.getLogger(__name__)
EPS = 1e-9


@dataclass
class Quote:
    side: str            # "bid" (buy YES) or "ask" (sell YES / buy NO)
    price: float
    size: float          # remaining shares
    placed_ts: float
    queue_ahead: float   # shares resting at our price before we joined


@dataclass
class Fill:
    ts: float
    side: str
    price: float
    size: float
    mid: float           # midpoint when the quote was placed


@dataclass
class MarketState:
    m: dict
    tier: str
    inv: float = 0.0     # YES shares; negative = NO shares
    cash: float = 0.0
    rewards: float = 0.0
    quotes: dict = field(default_factory=dict)
    fills: list = field(default_factory=list)
    mids: list = field(default_factory=list)      # (ts, mid)
    minutes: list = field(default_factory=list)   # per-cycle rows
    seen: set = field(default_factory=set)
    share: float = 0.0   # our share of the pool over the last interval
    last_ts: float | None = None
    final: float | None = None   # resolution value of YES, once known
    quoted_s: float = 0.0
    stale_loss: float = 0.0   # mid jumped past a quote before we re-quoted: what a fast trader takes
    jumps: list = field(default_factory=list)   # (ts, side, price, size) of each such quote
    side_check: list = field(default_factory=lambda: [0, 0])   # prints on the expected side of the mid / not


def yes_print(t: dict, yes_token: str) -> tuple[str, float, float, float] | None:
    """A Data API taker print -> (taker side in YES terms, YES price, shares, ts)."""
    try:
        side, price, size, ts = str(t["side"]).upper(), float(t["price"]), float(t["size"]), float(t["timestamp"])
    except (KeyError, TypeError, ValueError):
        return None
    if str(t.get("asset")) == str(yes_token):
        return ("buy" if side == "BUY" else "sell"), price, size, ts
    return ("sell" if side == "BUY" else "buy"), 1 - price, size, ts


def apply_print(q: Quote, taker: str, price: float, size: float) -> float:
    """Shares of our quote this print fills. A taker selling hits bids, a taker buying lifts asks."""
    if q.size <= EPS:
        return 0.0
    if q.side == "bid" and taker == "sell":
        through, at = price < q.price - EPS, abs(price - q.price) <= EPS
    elif q.side == "ask" and taker == "buy":
        through, at = price > q.price + EPS, abs(price - q.price) <= EPS
    else:
        return 0.0
    if through:
        filled = min(size, q.size)
    elif at:
        ahead = min(size, q.queue_ahead)
        q.queue_ahead -= ahead
        filled = min(size - ahead, q.size)
    else:
        return 0.0
    q.size -= filled
    return filled


def quote_prices(mid: float, max_spread: float, frac: float, tick: float) -> tuple[float, float]:
    d = frac * max_spread
    tick = tick or 0.01
    bid = math.ceil(round((mid - d) / tick, 6)) * tick    # round towards the mid: stays within the spread
    ask = math.floor(round((mid + d) / tick, 6)) * tick
    if bid >= ask:
        bid, ask = ask - tick, bid + tick
    return round(bid, 6), round(ask, 6)


def our_score(quotes: dict, mid: float, max_spread: float, min_size: float) -> float:
    lv = lambda side: [(q.price, q.size) for q in quotes.values() if q.side == side]
    return q_min(side_score(lv("bid"), mid, max_spread, min_size), side_score(lv("ask"), mid, max_spread, min_size), mid)


def target_quotes(mid: float, inv: float, m: dict, p: dict) -> dict:
    """The quotes to rest: {"bid"|"ask": (YES price, shares)}. Shared by paper and live, so both quote alike.
    A side that would push inventory past max_inventory_mult x the quote size is dropped."""
    bid, ask = quote_prices(mid, m["max_spread"], p["quote_frac"], m.get("tick") or 0.01)
    size = p["capital_usd"] / max(0.05, 1 - (ask - bid))
    cap = p["max_inventory_mult"] * size
    want = {}
    if inv < cap and bid > 0:
        want["bid"] = (bid, size)
    if inv > -cap and ask < 1:
        want["ask"] = (ask, size)
    return want


def excluded(question: str, patterns) -> bool:
    return any(re.search(pt, question or "", re.I) for pt in patterns or [])


def resting_at(levels, price: float) -> float:
    return sum(q for p, q in levels if abs(p - price) <= EPS)


def step(st: MarketState, book: dict | None, prints: list[dict], now: float, p: dict) -> None:
    """One cycle for one market: fills from the prints since the last cycle, rewards for the interval
    just ended, then fresh quotes against the current book."""
    m = st.m
    if st.last_ts is not None:
        dt_s = now - st.last_ts
        st.rewards += m["daily_rate"] * dt_s / 86400 * st.share
        if st.share > 0:
            st.quoted_s += dt_s
    for t in sorted(prints, key=lambda t: float(t.get("timestamp") or 0)):
        key = (t.get("transactionHash"), t.get("asset"), t.get("side"), t.get("price"), t.get("size"), t.get("timestamp"))
        if key in st.seen:
            continue
        st.seen.add(key)
        yp = yes_print(t, m["yes_token"])
        if yp is None:
            continue
        taker, price, size, ts = yp
        if st.mids and abs(price - st.mids[-1][1]) > EPS:
            st.side_check[(price > st.mids[-1][1]) != (taker == "buy")] += 1
        for q in st.quotes.values():
            if ts + 1 < q.placed_ts:    # prints carry whole seconds
                continue
            n = apply_print(q, taker, price, size)
            if n > EPS:
                sign = 1 if q.side == "bid" else -1
                st.inv += sign * n
                st.cash -= sign * n * q.price
                st.fills.append(Fill(ts, q.side, q.price, n, st.mids[-1][1] if st.mids else q.price))
    st.last_ts = now
    st.share = 0.0
    bs = book_score(book["bids"], book["asks"], m["max_spread"], m["min_size"]) if book else None
    if bs is None:
        st.quotes = {}
        st.minutes.append({"ts": now, "mid": None, "theirs": None, "ours": 0, "inv": st.inv})
        return
    mid = bs["mid"]
    # Without us the book may never trade at our prices (empty books): count every jump through a quote
    # as if someone picked it off before the re-quote.
    for q in st.quotes.values():
        gap = (mid - q.price) if q.side == "ask" else (q.price - mid)
        if gap > EPS:
            st.stale_loss += gap * q.size
            st.jumps.append((now, q.side, q.price, q.size))
    st.mids.append((now, mid))
    want = target_quotes(mid, st.inv, m, p)
    quotes = {}
    for side, (price, size) in want.items():
        old = st.quotes.get(side)
        if old and abs(old.price - price) <= EPS and old.size >= m["min_size"]:
            quotes[side] = old             # unchanged price: keep the place in the queue
        else:
            levels = book["bids"] if side == "bid" else book["asks"]
            quotes[side] = Quote(side, price, size, now, resting_at(levels, price))
    st.quotes = quotes
    ours = our_score(quotes, mid, m["max_spread"], m["min_size"])
    theirs = bs["q_min"]
    st.share = ours / (ours + theirs) if ours > 0 else 0.0
    st.minutes.append({"ts": now, "mid": mid, "theirs": theirs, "ours": ours, "inv": st.inv})


def mid_at(mids: list, ts: float) -> float | None:
    for t, mid in mids:
        if t >= ts:
            return mid
    return None


def summarise(st: MarketState, horizons_min, end_ts: float) -> dict:
    last = st.final if st.final is not None else (st.mids[-1][1] if st.mids else 0.0)
    pnl = st.cash + st.inv * last
    hours = (st.minutes[-1]["ts"] - st.minutes[0]["ts"]) / 3600 if len(st.minutes) > 1 else 0.0
    out = {"condition_id": st.m["condition_id"], "question": st.m["question"], "tier": st.tier,
           "pool": st.m["daily_rate"], "hours": hours, "quoted_hours": st.quoted_s / 3600,
           "rewards": st.rewards, "trading_pnl": pnl, "net": st.rewards + pnl, "inventory": st.inv,
           "stale_loss": st.stale_loss, "net_if_picked_off": st.rewards + pnl - st.stale_loss,
           "fills": len(st.fills), "filled_shares": sum(f.size for f in st.fills),
           "edge_at_fill": sum((f.mid - f.price if f.side == "bid" else f.price - f.mid) * f.size for f in st.fills),
           "resolved": st.final is not None,
           "prints_side_ok": st.side_check[0], "prints_side_wrong": st.side_check[1],
           "median_theirs": statistics.median([r["theirs"] for r in st.minutes if r["theirs"] is not None] or [0])}
    # A jump that has reverted 5 minutes later was a quote coming and going in a thin book, not news.
    persist = 0.0
    for ts, side, price, size in st.jumps:
        mids = [m for t, m in st.mids if ts <= t <= ts + 300]
        gaps = [(m - price) if side == "ask" else (price - m) for m in mids]
        if gaps and min(gaps) > 0:
            persist += min(gaps) * size
    out["stale_loss_persistent"] = persist
    out["net_if_picked_off_persistent"] = st.rewards + pnl - persist
    for h in horizons_min:
        tot = 0.0
        for f in st.fills:
            later = st.final if st.final is not None and f.ts + 60 * h > end_ts else mid_at(st.mids, f.ts + 60 * h)
            if later is None:
                later = last
            tot += ((later - f.price) if f.side == "bid" else (f.price - later)) * f.size
        out[f"markout_{h}m"] = tot
    return out


def select_markets(rapi: RewardsAPI, papi: PolymarketAPI, p: dict) -> list[tuple[dict, str]]:
    """Fresh pick at session start: top markets by expected reward in each competition tier."""
    from .run import _fill_tokens, score_market
    ms = [m for m in rapi.current() if m["condition_id"] and m["daily_rate"] >= float(p["min_pool"])]
    log.info("%d markets with pools >= $%s/day", len(ms), p["min_pool"])
    for m in ms:
        m["yes_token"] = None              # need both tokens and the tick: fetch the full market
    _fill_tokens(rapi, ms)
    today = dt.datetime.now(dt.timezone.utc).date()
    # Markets about to resolve carry the event itself (vote counts, deadlines): skip the last days.
    soonest = (today + dt.timedelta(days=int(p.get("min_days_to_end") or 0))).isoformat()
    # A market past its end date is waiting on resolution: no market maker would quote it.
    # Markets whose news lands in public jumps (temperatures, leaderboards, view and post counts) picked off
    # every paper session: config lists them.
    ms = [m for m in ms if m["yes_token"] and m.get("no_token") and m["max_spread"] > 0
          and not (m.get("end") and str(m["end"])[:10] < soonest) and not excluded(m["question"], p.get("exclude_patterns"))]

    def one(m):
        try:
            return m, score_market(m, papi.book(m["yes_token"]), {**p, "competition_mult": 2})
        except Exception as e:
            return m, {"error": str(e)}

    with ThreadPoolExecutor(6) as pool:
        scored = [(m, s) for m, s in pool.map(one, ms) if "error" not in s and 0.10 <= s["mid"] <= 0.90]
    t = p["tiers"]
    tier = lambda theirs: "empty" if theirs < t["thin_below"] else "crowded" if theirs >= t["crowded_from"] else "medium"
    picked = []
    for name in p.get("tiers_used") or ("empty", "medium", "crowded"):
        group = sorted([(m, s) for m, s in scored if tier(s["theirs"]) == name], key=lambda x: -x[1]["daily_haircut"])
        # Parallel sessions each take every n-th market (shard i of n), so they never quote the same one.
        group = group[int(p.get("shard", 0))::int(p.get("shards", 1))]
        picked += [(m, name) for m, _ in group[: int(p["per_tier"])]]
        log.info("tier %s: %d candidates, picked %d", name, len(group), min(len(group), int(p["per_tier"])))
    return picked


def _resolution(rapi: RewardsAPI, m: dict) -> float | None:
    try:
        full = rapi.market(m["condition_id"])
    except Exception:
        return None
    for t in full.get("tokens") or []:
        if t.get("winner") is True:
            return 1.0 if str(t.get("token_id")) == str(m["yes_token"]) else 0.0
    return None


def run(cfg, session: str, minutes: float | None = None) -> str:
    p = {**cfg["rewards"], **cfg["rewards"]["paper"]}
    h = cfg["http"]
    client = HttpClient(cfg["cache_dir"], h["requests_per_second"], h["timeout_s"], h["max_retries"], h["backoff_s"])
    rapi, papi = RewardsAPI(client), PolymarketAPI(client, cfg)
    out = Path(cfg["output_dir"]) / "mm" / session
    out.mkdir(parents=True, exist_ok=True)
    states = [MarketState(m, tier) for m, tier in select_markets(rapi, papi, p)]
    # The quoting loop waits for every market each cycle: one request stuck in 30 s timeouts and retries
    # would freeze every quote. Fail fast instead; a market that misses a cycle catches up on the next.
    fast = HttpClient(cfg["cache_dir"], h["requests_per_second"], float(p["request_timeout_s"]),
                      int(p["request_retries"]), 0.5)
    rapi, papi = RewardsAPI(fast), PolymarketAPI(fast, cfg)
    (out / "markets.json").write_text(json.dumps([{**s.m, "tier": s.tier} for s in states], indent=1))
    end = time.time() + 60 * float(minutes if minutes is not None else p["minutes"])
    k = 0
    while time.time() < end and states:
        start = time.time()

        def one(st):
            if st.final is not None:
                return
            try:
                prints = rapi.taker_trades(st.m["condition_id"])
            except Exception as e:
                log.warning("trades %s: %s", st.m["condition_id"][:10], e)
                prints = []
            try:
                book = papi.book(st.m["yes_token"])
            except Exception:
                book = None
                st.final = _resolution(rapi, st.m)
            step(st, book, prints, time.time(), p)

        with ThreadPoolExecutor(8) as pool:
            list(pool.map(one, states))
        k += 1
        if k % max(1, int(600 / float(p["interval_s"]))) == 0:
            write_session(out, states, p, time.time())
            log.info("cycle %d: rewards $%.2f, fills %d", k, sum(s.rewards for s in states), sum(len(s.fills) for s in states))
        time.sleep(max(0.0, float(p["interval_s"]) - (time.time() - start)))
    return write_session(out, states, p, time.time())


def write_session(out: Path, states: list[MarketState], p: dict, now: float) -> str:
    rows = [{**summarise(s, p["markout_min"], now), "interval_s": p["interval_s"], "quote_frac": p["quote_frac"],
             "selection": ("filtered" if p.get("exclude_patterns") else "all")
             + (f"+{p['min_days_to_end']}d" if p.get("min_days_to_end") else "")} for s in states]
    if rows:
        with open(out / "summary.csv", "w", newline="") as f:
            w = csv.DictWriter(f, list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    with open(out / "fills.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition_id", "tier", "ts", "side", "price", "size", "mid_at_quote"])
        for s in states:
            w.writerows([s.m["condition_id"], s.tier, int(x.ts), x.side, x.price, round(x.size, 2), round(x.mid, 4)]
                        for x in s.fills)
    return report(out.parent, p)


def report(root: Path, p: dict) -> str:
    """Every session under root, by tier: rewards against what fills cost, per $1,000 per day."""
    rows = []
    for f in sorted(root.glob("*/summary.csv")):
        for r in csv.DictReader(open(f)):
            rows.append({"interval_s": 60.0, "selection": "all", "quote_frac": 0.5,
                         **{k: (float(v) if k not in ("condition_id", "question", "tier", "resolved", "selection") else v)
                            for k, v in r.items()}, "session": f.parent.name})
    cap = float(p["capital_usd"])
    hz = p["markout_min"]
    lines = [f"## Paper market making for liquidity rewards: {len({r['session'] for r in rows})} sessions", "",
             f"${cap:,.0f} quoted per market on both sides at {p['quote_frac']} x the max spread from the midpoint, "
             "re-quoted every `requote` seconds (\"at 0.3x\": quoted at 0.3 x the max spread instead). Fills come from real taker prints (through our price, or at it once the queue "
             "ahead is gone). Markout = fill price against the midpoint later; negative = picked off.", "",
             "Stale-quote loss: whenever the midpoint jumps past one of our quotes between re-quotes, the whole "
             "quote is assumed picked off at that gap, even with no print (an empty book only trades once someone "
             "quotes). Net if picked off subtracts it. Lasting jumps counts only jumps still past the quote 5 minutes "
             "later (news, not a thin book's quotes coming and going): the most realistic of the three.", "",
             "| tier | requote | market-hours | rewards | trading P&L | net | net $/day per $1k | stale-quote loss | "
             "net if picked off $/day per $1k | lasting jumps loss | net, lasting jumps $/day per $1k | fills | " +
             " | ".join(f"markout {h}m" for h in hz) + " |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|" + "---|" * len(hz)]
    for name, iv, sel, qf in sorted({(r["tier"], r["interval_s"], r["selection"], r["quote_frac"]) for r in rows},
                                    key=lambda k: (("empty", "medium", "crowded").index(k[0]), -k[1], k[2], k[3])):
        g = [r for r in rows if (r["tier"], r["interval_s"], r["selection"], r["quote_frac"]) == (name, iv, sel, qf)]
        hrs = sum(r["hours"] for r in g)
        rw, tp = sum(r["rewards"] for r in g), sum(r["trading_pnl"] for r in g)
        sl = sum(r.get("stale_loss", 0) for r in g)
        sp = sum(r.get("stale_loss_persistent", r.get("stale_loss", 0)) for r in g)   # older sessions: all jumps
        persist_day = (rw + tp - sp) / hrs * 24 if hrs else 0.0
        per_day = (rw + tp) / hrs * 24 if hrs else 0.0
        worst = (rw + tp - sl) / hrs * 24 if hrs else 0.0
        lines.append(f"| {name} | {iv:.0f}s{' ' + sel if sel != 'all' else ''}{f' at {qf:g}x' if qf != 0.5 else ''} | {hrs:,.0f} | ${rw:,.2f} | ${tp:,.2f} | ${rw + tp:,.2f} | ${per_day:,.2f} | "
                     f"${sl:,.2f} | ${worst:,.2f} | ${sp:,.2f} | ${persist_day:,.2f} | "
                     f"{sum(r['fills'] for r in g):.0f} | " + " | ".join(f"${sum(r[f'markout_{h}m'] for r in g):,.2f}" for h in hz) + " |")
    ok, wrong = sum(r.get("prints_side_ok", 0) for r in rows), sum(r.get("prints_side_wrong", 0) for r in rows)
    lines += ["", f"Check on the print data: {ok:.0f} taker prints sat on the expected side of the midpoint "
              f"(buys above, sells below), {wrong:.0f} did not."]
    lines += ["", "Per market (latest first):", "",
              "| session | tier | market | pool | hours | rewards | trading P&L | net | lasting jumps loss | fills | inventory | markout 30m |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["session"], r["tier"], -r["net"]), reverse=False)[-80:]:
        lines.append(f"| {r['session']} | {r['tier']} | {r['question'][:50]} | {r['pool']:.0f} | {r['hours']:.1f} | "
                     f"${r['rewards']:.2f} | ${r['trading_pnl']:.2f} | ${r['net']:.2f} | ${r.get('stale_loss_persistent', r.get('stale_loss', 0)):.2f} | {r['fills']:.0f} | "
                     f"{r['inventory']:.0f} | ${r.get('markout_30m', 0):.2f} |")
    text = "\n".join(lines) + "\n"
    (root / "report.md").write_text(text)
    return text
