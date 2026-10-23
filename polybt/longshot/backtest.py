"""Does buying the favourite against a longshot pay, after costs?

At a fixed time before each market's *scheduled* end (known in advance, unlike the close time), take the
last price. If one side trades at or below a bucket's ceiling, buy the other side at its price plus a
spread penalty and the taker fee, and hold to resolution. Stake is $1 per bet.

Bets in one event (e.g. every candidate in an election) share an outcome, so the confidence interval
resamples whole events. The last test_days are reported separately: buckets are judged there, on markets
that played no part in choosing them.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from ..fees import category_fallback
from ..report import LotRow, bootstrap_roi_ci


@dataclass
class Bet:
    condition_id: str
    event_id: str
    question: str
    horizon: int
    ts: int
    end: int
    longshot_price: float   # market's price of the side we bet against
    cost: float             # what we pay per share of the favourite, spread and fee included
    won: bool               # the favourite won

    @property
    def pnl(self) -> float:
        return (1.0 if self.won else 0.0) - self.cost


def price_at(path: list[tuple[int, float]], ts: int, max_age: int) -> float | None:
    """Last price at or before ts, if no older than max_age seconds."""
    best = None
    for t, p in path:
        if t > ts:
            break
        best = (t, p)
    if best is None or ts - best[0] > max_age:
        return None
    return best[1]


def bets_for_market(m: dict, path: list[tuple[int, float]], c: dict, fee_rate: float) -> list[Bet]:
    out = []
    for h in c["horizons_days"]:
        ts = m["scheduled_end"] - int(h) * 86400
        if m["closed_ts"] and m["closed_ts"] <= ts:
            continue            # already over before we could bet
        p = price_at(path, ts, int(c["max_price_age_h"]) * 3600)
        if p is None:
            continue
        q = min(p, 1 - p)
        if q <= 0 or q > max(float(b) for b in c["buckets"]):
            continue
        fav_yes = p > 0.5
        price = min(0.999, (1 - q) + float(c["spread"]))
        cost = price + fee_rate * price * (1 - price)        # v2 taker fee per share, paid on the buy
        won = (m["yes_won"] == 1.0) == fav_yes
        out.append(Bet(m["condition_id"], m["event_id"], m["question"], int(h), ts, m["scheduled_end"], q, cost, won))
    return out


def load_bets(con, cfg) -> list[Bet]:
    c = cfg["longshot"]
    markets = [dict(zip(("condition_id", "question", "event_id", "yes_token", "yes_won", "scheduled_end",
                         "closed_ts", "fee_category"), r)) for r in con.execute("""
        SELECT condition_id, question, event_id, yes_token, yes_won, scheduled_end, closed_ts, fee_category
        FROM ls_markets WHERE scheduled_end IS NOT NULL""").fetchall()]
    paths: dict[str, list] = {}
    for token, t, p in con.execute("SELECT token, ts, price FROM ls_prices ORDER BY token, ts").fetchall():
        paths.setdefault(token, []).append((t, p))
    bets = []
    for m in markets:
        rate = category_fallback(cfg, m["fee_category"]).rate if c["fees"] else 0.0
        bets += bets_for_market(m, paths.get(m["yes_token"], []), c, rate)
    return bets


def bucket_of(q: float, buckets) -> float:
    for b in sorted(float(x) for x in buckets):
        if q <= b + 1e-12:
            return b
    return float("inf")


def summarise(bets: list[Bet], cfg) -> dict | None:
    if not bets:
        return None
    r = cfg["report"]
    lots = [LotRow(b.ts, b.end, b.cost, b.cost, b.pnl, b.event_id) for b in bets]
    stake = sum(b.cost for b in bets)
    roi = sum(b.pnl for b in bets) / stake
    lo, hi = bootstrap_roi_ci(lots, int(r["bootstrap_samples"]), float(r["ci_level"]), int(r["seed"]))
    return {"bets": len(bets), "events": len({b.event_id for b in bets}),
            "implied": sum(b.longshot_price for b in bets) / len(bets),
            "hit": sum(not b.won for b in bets) / len(bets),
            "roi": roi, "ci_lo": lo, "ci_hi": hi,
            "worst_event": min(sum(x.pnl for x in bets if x.event_id == e) for e in {b.event_id for b in bets})}


def evaluate(con, cfg) -> str:
    from .data import SCHEMA
    c = cfg["longshot"]
    con.execute(SCHEMA)
    bets = load_bets(con, cfg)
    if not bets:
        return "## Longshot backtest\n\nNo bets: no price data yet.\n"
    split = max(b.ts for b in bets) - int(c["test_days"]) * 86400
    n_markets = con.execute("SELECT count(*) FROM ls_markets").fetchone()[0]
    n_paths = con.execute("SELECT count(*) FROM ls_fetched WHERE n > 0").fetchone()[0]
    day = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()
    rows, gate = [], []
    for h in c["horizons_days"]:
        for b in sorted(float(x) for x in c["buckets"]):
            group = [x for x in bets if x.horizon == int(h) and bucket_of(x.longshot_price, c["buckets"]) == b]
            for period, sel in (("all", group), ("test", [x for x in group if x.ts >= split])):
                s = summarise(sel, cfg)
                if s:
                    rows.append((int(h), b, period, s))
                    if (period == "test" and s["events"] >= int(c["min_events"]) and s["ci_lo"] is not None
                            and s["ci_lo"] > 0 and s["roi"] * 365 / int(h) >= float(c["min_annual"])):
                        gate.append((int(h), b, s))
    pct = lambda v: "–" if v is None else f"{v * 100:+.1f}%"
    passed = bool(gate)
    lines = [f"## Longshot backtest: {'PASSED' if passed else 'FAILED'}", "",
             f"{n_markets:,} resolved two-outcome markets (volume ≥ ${float(c['min_volume']):,.0f}, ending "
             f"{c['lookback_days']} days back), {n_paths:,} with price history. {len(bets):,} bets. Test period: "
             f"bets placed from {day(split)} on.", "",
             f"Rule: {', '.join(str(h) for h in c['horizons_days'])} days before the scheduled end, if one side trades at "
             f"or below the bucket's price, buy the other side (+{float(c['spread']) * 100:.0f}¢ spread"
             f"{', plus the taker fee' if c['fees'] else ''}) and hold to resolution.", "",
             f"Gate: a bucket whose test-period ROI has its {cfg['report']['ci_level']:.0%} interval (resampling whole "
             f"events) above zero, ≥ {c['min_events']} events, and ≥ {float(c['min_annual']):.0%} a year "
             f"on the capital held. Passing: " + (", ".join(f"{h}d ≤{b * 100:g}¢" for h, b, _ in gate) or "none") + ".", "",
             "Longshot price = what the market gave the side we bet against; longshot hit = how often it happened. "
             "If the hit rate is below the price, longshots are overpriced.", "",
             "| days before end | longshot ≤ | period | bets | events | longshot price | longshot hit | ROI | 90% CI | "
             "annualised | worst event |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for h, b, period, s in rows:
        lines.append(f"| {h} | {b * 100:g}¢ | {period} | {s['bets']:,} | {s['events']:,} | {s['implied'] * 100:.1f}% | "
                     f"{s['hit'] * 100:.1f}% | {pct(s['roi'])} | {pct(s['ci_lo'])} to {pct(s['ci_hi'])} | "
                     f"{s['roi'] * 365 / h * 100:+.0f}% | ${s['worst_event']:.2f} |")
    losses = sorted((x for x in bets if not x.won and x.ts >= split), key=lambda x: x.longshot_price)[:15]
    if losses:
        lines += ["", "Longshots that hit in the test period (cheapest first):", ""]
        lines += [f"- {x.question[:90]} — {x.longshot_price * 100:.1f}¢, {x.horizon} days out" for x in losses]
    text = "\n".join(lines) + "\n"
    out = Path(cfg["output_dir"]) / "longshot"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(text)
    with open(out / "bets.csv", "w") as f:
        f.write("condition_id,event_id,horizon_days,ts,longshot_price,cost,favourite_won,question\n")
        for x in bets:
            f.write(f"{x.condition_id},{x.event_id},{x.horizon},{x.ts},{x.longshot_price:.4f},{x.cost:.4f},"
                    f"{int(x.won)},\"{x.question.replace(chr(34), '')}\"\n")
    return text
