"""Filter: score each candidate on its selection-window history (before the cutoff) and log why it fails."""
from __future__ import annotations

import logging
import statistics
import time
from collections import defaultdict

from .simulate import Fill, Market, SimParams, load_fills, load_markets, simulate

log = logging.getLogger(__name__)

DAY = 86400


def wash_fraction(fills: list[Fill], window_s: int) -> float:
    """Share of buys with a buy of a different outcome of the same market within window_s."""
    buys = [f for f in fills if f.side == "BUY"]
    if not buys:
        return 0.0
    by_market: dict[str, list[Fill]] = defaultdict(list)
    for f in buys:
        by_market[f.condition_id].append(f)
    flagged = 0
    for group in by_market.values():
        group.sort(key=lambda f: f.ts)
        for i, f in enumerate(group):
            hit = False
            for j in range(i - 1, -1, -1):
                if f.ts - group[j].ts > window_s:
                    break
                hit = hit or group[j].token_id != f.token_id
            for j in range(i + 1, len(group)):
                if group[j].ts - f.ts > window_s:
                    break
                hit = hit or group[j].token_id != f.token_id
            flagged += hit
    return flagged / len(buys)


def score_wallet(fills: list[Fill], markets: dict[str, Market], cfg, start_ts: int, cutoff_ts: int) -> dict:
    """Metrics and pass/fail for one wallet, using only data in [start_ts, cutoff_ts)."""
    fc = cfg["filters"]
    window = [f for f in fills if start_ts <= f.ts < cutoff_ts]
    lots, _ = simulate(fills, markets, {}, SimParams(), 0, start_ts, end_ts=cutoff_ts, mode="wallet")
    closed = [lot for lot in lots if lot.closed]

    staked = sum(lot.stake for lot in closed)
    pnl = sum(lot.pnl for lot in closed)
    roi = pnl / staked if staked > 0 else None
    win_rate = sum(lot.pnl > 0 for lot in closed) / len(closed) if closed else None
    avg_entry = sum(lot.entry_price for lot in closed) / len(closed) if closed else None
    edge_pts = (win_rate - avg_entry) * 100 if closed else None
    profits = sorted((lot.pnl for lot in closed), reverse=True)
    top3_share = sum(p for p in profits[:3] if p > 0) / pnl if pnl > 0 else None

    buys = [f for f in window if f.side == "BUY"]
    median_usd = statistics.median(f.usdc_size for f in buys) if buys else None
    if window:
        first, last = window[0].ts, window[-1].ts
        span_days = (last - first) / DAY
        days_since_last = (cutoff_ts - last) / DAY
        active_days = len({f.ts // DAY for f in window})
        trades_per_day = len(window) / active_days
    else:
        span_days = days_since_last = trades_per_day = None
    wash = wash_fraction(window, int(fc["wash_window_s"]))

    reasons = []
    n_markets = len({lot.condition_id for lot in closed})
    if fc.get("min_markets") and n_markets < fc["min_markets"]:
        reasons.append(f"markets {n_markets} < {fc['min_markets']}")
    if len(closed) < fc["min_resolved_trades"]:
        reasons.append(f"resolved_trades {len(closed)} < {fc['min_resolved_trades']}")
    if span_days is None or span_days < fc["min_active_span_days"]:
        reasons.append(f"active_span {span_days or 0:.0f}d < {fc['min_active_span_days']}d")
    if days_since_last is None or days_since_last > fc["active_within_days"]:
        reasons.append(f"inactive: last trade {'never' if days_since_last is None else f'{days_since_last:.0f}d'} before cutoff")
    if roi is None or roi <= fc["min_roi"]:
        reasons.append(f"roi {'n/a' if roi is None else f'{roi:.1%}'} <= {fc['min_roi']:.0%}")
    if edge_pts is None or edge_pts <= fc["min_edge_pts"]:
        reasons.append(f"edge {'n/a' if edge_pts is None else f'{edge_pts:.1f}'}pts <= {fc['min_edge_pts']}")
    if top3_share is None or top3_share >= fc["max_top3_profit_share"]:
        reasons.append(f"top3_profit_share {'n/a' if top3_share is None else f'{top3_share:.0%}'} >= {fc['max_top3_profit_share']:.0%}")
    if median_usd is None or median_usd < fc["min_median_trade_usd"]:
        reasons.append(f"median_trade ${median_usd or 0:.2f} < ${fc['min_median_trade_usd']}")
    if trades_per_day is not None and trades_per_day > fc["max_trades_per_day"]:
        reasons.append(f"trades_per_day {trades_per_day:.0f} > {fc['max_trades_per_day']}")
    if wash > fc["max_wash_fraction"]:
        reasons.append(f"wash_fraction {wash:.0%} > {fc['max_wash_fraction']:.0%}")

    return {
        "resolved_trades": len(closed), "span_days": span_days, "days_since_last": days_since_last,
        "roi": roi, "win_rate": win_rate, "avg_entry": avg_entry, "edge_pts": edge_pts,
        "top3_share": top3_share, "median_trade_usd": median_usd, "trades_per_day": trades_per_day,
        "wash_fraction": wash, "passed": not reasons, "rejection_reason": "; ".join(reasons) or None,
    }


def score_specialist(fills: list[Fill], markets: dict[str, Market], cfg, start_ts: int, cutoff_ts: int) -> dict:
    """Score a wallet within each category on its own; it qualifies in its best passing category.

    Returns the best passing category's score (highest ROI), else the category with the most
    resolved trades, labelled with that category so the rejection reasons make sense.
    """
    by_cat: dict[str, list[Fill]] = defaultdict(list)
    for f in fills:
        m = markets.get(f.condition_id)
        if m is not None:
            by_cat[m.fee_category].append(f)
    scores = []
    for cat, cat_fills in by_cat.items():
        if cat == "default" and not cfg["filters"].get("specialist_include_uncategorised", False):
            continue
        s = score_wallet(cat_fills, markets, cfg, start_ts, cutoff_ts)
        s["specialty"] = cat
        scores.append(s)
    if not scores:
        s = score_wallet([], markets, cfg, start_ts, cutoff_ts)
        s["specialty"] = None
        return s
    ok = [s for s in scores if s["passed"]]
    best = max(ok, key=lambda s: s["roi"]) if ok else max(scores, key=lambda s: s["resolved_trades"])
    if not ok:
        best["rejection_reason"] = f"[{best['specialty']}] {best['rejection_reason']}"
    return best


COLUMNS = ["resolved_trades", "span_days", "days_since_last", "roi", "win_rate", "avg_entry", "edge_pts",
           "top3_share", "median_trade_usd", "trades_per_day", "wash_fraction", "passed", "rejection_reason"]


def run(con, cfg, wallets: list[str] | None = None) -> list[str]:
    if not wallets:
        wallets = [r[0] for r in con.execute("SELECT wallet FROM candidates ORDER BY wallet").fetchall()]
        con.execute("DELETE FROM wallet_scores")  # scoring the whole pool: drop scores of past pools
    markets = load_markets(con)
    start, cutoff = cfg.selection_start_ts, cfg.cutoff_ts
    capped = {r[0] for r in con.execute("SELECT wallet FROM wallet_ingest_state WHERE capped").fetchall()}
    passed, now = [], int(time.time())
    specialist = bool(cfg["filters"].get("specialist"))
    for w in wallets:
        fills = load_fills(con, w)
        if specialist:
            s = score_specialist(fills, markets, cfg, start, cutoff)
        else:
            s = score_wallet(fills, markets, cfg, start, cutoff)
            s["specialty"] = None
        if w in capped:
            s["passed"] = False
            s["rejection_reason"] = "; ".join(filter(None, [
                "high_frequency: activity over the ingest cap or prescreen rate", s["rejection_reason"]]))
        con.execute("INSERT OR REPLACE INTO wallet_scores VALUES (?," + ",".join("?" * len(COLUMNS)) + ",?,?)",
                    [w, *(s[c] for c in COLUMNS), now, s["specialty"]])
        if s["passed"]:
            passed.append(w)
        else:
            log.debug("%s rejected: %s", w, s["rejection_reason"])
    log.info("filters: %d of %d wallets passed", len(passed), len(wallets))
    return passed
