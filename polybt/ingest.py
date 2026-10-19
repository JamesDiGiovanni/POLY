"""Ingest: discover candidate wallets, pull their activity, market metadata and price history."""
from __future__ import annotations

import datetime as dt
import logging
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import fees as fees_mod
from .api import PolymarketAPI, parse_market
from .db import insert_many

log = logging.getLogger(__name__)


def fee_category(m: dict, cfg: dict) -> str:
    """Polymarket fee category for the config fallback: Gamma's category/tags, then keyword patterns."""
    known = cfg["fees"]["category_rates"]
    for label in [m.get("gamma_category", "")] + list(m.get("tags", [])):
        for cat in known:
            if cat != "default" and label and (label == cat or label.startswith(cat)):
                return cat
    text = f"{m.get('question', '')} {m.get('slug', '')}".lower()
    for cat, patterns in (cfg["fees"].get("category_patterns") or {}).items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            return cat
    return "default"


def market_fees(api: PolymarketAPI | None, m: dict, cfg: dict) -> tuple[float, float, str, str]:
    """(rate, exponent, source, fee_category). The market's own CLOB fee details win."""
    cat = fee_category(m, cfg)
    if api is not None and cfg["fees"].get("fetch_market_info", True):
        try:
            info = api.clob_market_info(m["condition_id"])
        except Exception as e:
            log.debug("market info for %s failed: %s", m["condition_id"], e)
            info = None
        if info is not None:
            fp = fees_mod.from_market_info(info, cfg["fees"]["formula"])
            if fp is not None:
                return fp.rate, fp.exponent, "market", cat
            # Checked against the live API (Oct 2026): active fee-free markets (geopolitics) and markets
            # from before the fee rollout come back without `fd`. No fd means no fee.
            return 0.0, 1.0, "market", cat
    fb = fees_mod.category_fallback(cfg, cat)
    return fb.rate, fb.exponent, "category", cat


def categorize(question: str, slug: str, cfg: dict) -> str:
    text = f"{question} {slug}".lower()
    for pattern in cfg["categories"]["short_term_crypto"]:
        if re.search(pattern, text, re.IGNORECASE):
            return "short_term_crypto"
    return cfg["categories"]["default"]


# ---- discovery -----------------------------------------------------------

def discover(con, api: PolymarketAPI, cfg) -> list[str]:
    disc = cfg["discovery"]
    sources: dict[str, set[str]] = {}

    def add(wallet, source):
        if wallet and isinstance(wallet, str) and wallet.startswith("0x"):
            sources.setdefault(wallet.lower(), set()).add(source)

    for w in disc.get("seed_wallets") or []:
        add(w, "seed")

    lb = disc["leaderboard"]
    if lb["enabled"]:
        for q in lb["queries"]:
            tag = "lb:" + "/".join(str(v) for v in q.values())
            for page in range(int(lb["pages"])):
                try:
                    rows = api.leaderboard(lb["path"], q, int(lb["page_size"]), page * int(lb["page_size"]))
                except Exception as e:  # one bad board shouldn't stop discovery
                    log.warning("leaderboard %s failed: %s", tag, e)
                    break
                for r in rows:
                    add(r.get("proxyWallet") or r.get("user") or r.get("address"), tag)
                if len(rows) < int(lb["page_size"]):
                    break

    am = disc["active_in_markets"]
    if am["enabled"]:
        iso = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Only markets that ended before the cutoff, so nothing after it influences who is picked.
        markets, page = [], 100
        for offset in range(0, int(am["top_markets"]), page):
            try:
                got = api.top_closed_markets(min(page, int(am["top_markets"]) - offset), iso(cfg.selection_start_ts),
                                             iso(cfg.cutoff_ts), offset)
            except Exception as e:
                log.warning("top markets failed: %s", e)
                break
            markets += got
            if len(got) < page:
                break
        for m in markets:
            cid = m.get("conditionId")
            if not cid:
                continue
            counts: Counter = Counter()
            limit = 500
            for offset in range(0, int(am["trades_per_market"]), limit):
                try:
                    rows = api.market_trades(cid, limit, offset)
                except Exception as e:
                    log.warning("trades for %s failed: %s", cid, e)
                    break
                counts.update(r.get("proxyWallet", "").lower() for r in rows)
                if len(rows) < limit:
                    break
            for w, _ in counts.most_common(int(am["wallets_per_market"])):
                add(w, "active_market")

    # Seeds first, then wallets found by the most sources.
    ranked = sorted(sources, key=lambda w: ("seed" not in sources[w], -len(sources[w]), w))
    ranked = ranked[: int(disc["max_candidates"])]
    now = int(time.time())
    # Discovery defines the pool: candidates from earlier runs (possibly found with other, e.g.
    # lookahead-prone, sources) must not leak into this one.
    con.execute("DELETE FROM candidates")
    insert_many(con, "candidates", [(w, ",".join(sorted(sources[w])), now) for w in ranked], "INSERT OR REPLACE")
    log.info("discovered %d candidate wallets", len(ranked))
    return ranked


# ---- wallet activity -----------------------------------------------------

def _activity_row(wallet: str, r: dict):
    def f(k):
        v = r.get(k)
        try:
            return float(v) if v is not None and v != "" else None
        except (TypeError, ValueError):
            return None

    price, size, usdc = f("price"), f("size"), f("usdcSize")
    if usdc is None and price is not None and size is not None:
        usdc = price * size  # fallback only; usdcSize includes fees and is preferred
    oi = r.get("outcomeIndex")
    return (
        wallet,
        r.get("transactionHash") or "",
        (r.get("type") or "TRADE").upper(),
        str(r.get("asset") or ""),
        r.get("conditionId") or "",
        int(oi) if oi not in (None, "") else None,
        (r.get("side") or "").upper(),
        price if price is not None else 0.0,
        size if size is not None else 0.0,
        usdc,
        int(r.get("timestamp") or 0),
    )


def _wallet_plan(con, wallet: str, start_ts: int):
    """(ranges to pull, earliest start) for a wallet, or None if it was capped before. DB-only."""
    state = con.execute("SELECT start_ts, synced_to, capped FROM wallet_ingest_state WHERE wallet = ?",
                        [wallet]).fetchone()
    if state and state[2]:
        return None
    if state is None:
        return [(start_ts, None)], start_ts
    ranges = [(start_ts, state[0] - 1)] if start_ts < state[0] else []  # lookback widened
    return ranges + [(state[1], None)], min(start_ts, state[0])


def _fetch_wallet(api: PolymarketAPI, wallet: str, ranges, max_rows: int | None):
    """Network only (safe in a worker thread): (rows, capped)."""
    rows, capped = [], False
    for lo, hi in ranges:
        for r in api.activity(wallet, lo, hi):
            rows.append(_activity_row(wallet, r))
            if max_rows and len(rows) >= max_rows:
                capped = True
                break
        if capped:
            log.info("%s: stopped at %d activity rows (capped)", wallet, len(rows))
            break
    return rows, capped


def _store_wallet(con, wallet: str, new_start: int, rows, capped: bool, synced_at: int) -> int:
    n = _insert_trades(con, rows)
    con.execute("INSERT OR REPLACE INTO wallet_ingest_state VALUES (?, ?, ?, ?, ?)",
                [wallet, new_start, synced_at, synced_at, capped])
    return n


def ingest_wallet(con, api: PolymarketAPI, wallet: str, start_ts: int, max_rows: int | None = None) -> int:
    """Pull activity since the last sync. Never re-pulls a range already stored."""
    plan = _wallet_plan(con, wallet, start_ts)
    if plan is None:
        return 0
    now = int(time.time())
    rows, capped = _fetch_wallet(api, wallet, plan[0], max_rows)
    return _store_wallet(con, wallet, plan[1], rows, capped, now)


def is_high_frequency(rows: list[dict], page: int, max_rows_per_day: float) -> bool:
    """A full page of newest activity spanning so little time that the wallet trades far above the limit."""
    if len(rows) < page:
        return False
    ts = [int(r.get("timestamp") or 0) for r in rows]
    span_days = max(1e-6, (max(ts) - min(ts)) / 86400)
    return len(rows) / span_days > max_rows_per_day


def ingest_wallets(con, api: PolymarketAPI, cfg, wallets: list[str]) -> None:
    """ingest_wallet for many wallets, fetching in parallel (the rate limiter still caps each host).

    Wallets never seen before are pre-screened with one request: if their newest page of activity shows
    them trading at several times the trades-per-day limit, they're marked capped (rejected by the
    filter) without downloading their full history. Most leaderboard wallets are such bots.
    """
    max_rows = cfg["http"].get("max_activity_rows")
    plans = {w: _wallet_plan(con, w, cfg.selection_start_ts) for w in wallets}
    now = int(time.time())
    workers = int(cfg["http"].get("workers", 8))
    pre = cfg["http"].get("prescreen_rows_per_day")
    new = [w for w in wallets if plans[w] is not None and not con.execute(
        "SELECT 1 FROM wallet_ingest_state WHERE wallet = ?", [w]).fetchone()]
    if pre and new:
        page = 500
        with ThreadPoolExecutor(workers) as pool:
            def screen(w):
                try:
                    return w, is_high_frequency(api.recent_activity(w, page), page, float(pre))
                except Exception as e:
                    log.warning("prescreen %s failed: %s", w, e)
                    return w, False
            for w, hot in pool.map(screen, new):
                if hot:
                    con.execute("INSERT OR REPLACE INTO wallet_ingest_state VALUES (?, ?, ?, ?, ?)",
                                [w, cfg.selection_start_ts, now, now, True])
                    plans[w] = None
        log.info("prescreen: %d of %d new wallets skipped as high-frequency", sum(plans[w] is None for w in new), len(new))
    todo = [w for w in wallets if plans[w] is not None]
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(_fetch_wallet, api, w, plans[w][0], max_rows): w for w in todo}
        for i, fut in enumerate(as_completed(futures)):
            w = futures[fut]
            try:
                rows, capped = fut.result()
                n = _store_wallet(con, w, plans[w][1], rows, capped, now)
                log.info("[%d/%d] %s: %d new rows%s", i + 1, len(todo), w, n, " (capped)" if capped else "")
            except Exception as e:
                log.warning("[%d/%d] %s failed: %s", i + 1, len(todo), w, e)


def _insert_trades(con, rows) -> int:
    if not rows:
        return 0
    before = con.execute("SELECT count(*) FROM wallet_trades").fetchone()[0]
    insert_many(con, "wallet_trades", rows)
    return con.execute("SELECT count(*) FROM wallet_trades").fetchone()[0] - before


# ---- markets -------------------------------------------------------------

def ingest_markets(con, api: PolymarketAPI, cfg, batch: int = 20) -> int:
    """Fetch metadata for every traded market we don't have, or have only as still-open."""
    stale = int(time.time()) - int(cfg["http"]["mutable_ttl_s"])
    # High-frequency wallets are rejected without scoring, so their markets are never needed.
    ids = [r[0] for r in con.execute("""
        SELECT DISTINCT t.condition_id FROM wallet_trades t
        LEFT JOIN markets m USING (condition_id)
        LEFT JOIN wallet_ingest_state s ON s.wallet = t.wallet
        WHERE t.condition_id <> '' AND NOT coalesce(s.capped, false)
          AND (m.condition_id IS NULL OR (NOT m.resolved AND m.fetched_at < ?))
    """, [stale]).fetchall()]
    log.info("markets: %d to fetch", len(ids))
    workers = int(cfg["http"].get("workers", 8))
    n = 0
    step = batch * 50  # store as we go, so an interrupted run keeps what it fetched
    with ThreadPoolExecutor(workers) as pool:
        for start in range(0, len(ids), step):
            part = ids[start:start + step]
            batches = pool.map(api.markets_by_condition, [part[i:i + batch] for i in range(0, len(part), batch)])
            parsed = [parse_market(raw) for b in batches for raw in b]
            rows = list(pool.map(lambda m: market_row(m, cfg, api), parsed))
            insert_many(con, "markets", rows, "INSERT OR REPLACE")
            n += len(rows)
            log.info("markets: %d/%d stored", n, len(ids))
    return n


def market_row(m: dict, cfg, api: PolymarketAPI | None = None) -> tuple:
    """markets row (column order matches the table)."""
    rate, exponent, source, cat = market_fees(api, m, cfg)
    return (m["condition_id"], m["question"], m["slug"], m["token_ids"], m["outcomes"], m["payouts"],
            categorize(m["question"], m["slug"], cfg), m["volume"], m["end_time"], m["closed"],
            m["resolved"], m["resolved_outcome"], int(time.time()), rate, exponent, source, cat)


# ---- price history -------------------------------------------------------

def needed_price_chunks(con, cfg, wallets: list[str], since_ts: int) -> list[tuple[str, int]]:
    """(token_id, chunk_start) pairs covering every test-period trade, minus those already fetched."""
    ph = cfg["price_history"]
    chunk = int(ph["chunk_hours"]) * 3600
    pad = int(ph["pad_s"])
    max_delay = max(int(d) for d in cfg["simulate"]["delays_s"])
    if not wallets:
        return []
    in_wallets = ",".join("?" * len(wallets))
    rows = con.execute(f"""
        SELECT DISTINCT token_id, timestamp FROM wallet_trades
        WHERE type = 'TRADE' AND token_id <> '' AND timestamp >= ? AND wallet IN ({in_wallets})
        UNION
        -- a merge exits every outcome of its market
        SELECT DISTINCT unnest(m.token_ids), t.timestamp FROM wallet_trades t JOIN markets m USING (condition_id)
        WHERE t.type = 'MERGE' AND t.timestamp >= ? AND t.wallet IN ({in_wallets})
    """, [since_ts, *wallets, since_ts, *wallets]).fetchall()
    want: set[tuple[str, int]] = set()
    for token, ts in rows:
        lo, hi = ts - pad, ts + max_delay + pad
        for k in range(lo // chunk, hi // chunk + 1):
            want.add((token, k * chunk))
    have = set(con.execute("SELECT token_id, start_ts FROM price_fetches").fetchall())
    now = time.time()
    return sorted(c for c in want - have if c[1] < now)


def ingest_prices(con, api: PolymarketAPI, cfg, wallets: list[str], since_ts: int) -> int:
    chunk = int(cfg["price_history"]["chunk_hours"]) * 3600
    fidelity = int(cfg["price_history"]["fidelity_min"])
    todo = needed_price_chunks(con, cfg, wallets, since_ts)
    log.info("price history: %d chunks to fetch", len(todo))
    n = 0

    def fetch(item):
        token, start = item
        try:
            return item, api.prices_history(token, start, start + chunk, fidelity)
        except Exception as e:
            log.warning("prices for %s @ %d failed: %s", token, start, e)
            return item, None

    workers = int(cfg["price_history"].get("workers") or cfg["http"].get("workers", 8))
    with ThreadPoolExecutor(workers) as pool:
        results = pool.map(fetch, todo)
        for i, ((token, start), points) in enumerate(results):
            if points is None:
                continue
            n += _store_prices(con, token, start, start + chunk, points)
            if (i + 1) % 500 == 0:
                log.info("  %d/%d chunks", i + 1, len(todo))
    return n


def _store_prices(con, token: str, start: int, end: int, points) -> int:
    if points:
        insert_many(con, "price_history", [(token, t, p) for t, p in points])
    if end < time.time() - 3600:  # only a closed window is final
        con.execute("INSERT OR IGNORE INTO price_fetches VALUES (?, ?, ?)", [token, start, end])
    return len(points)


def run(con, api: PolymarketAPI, cfg, wallets: list[str] | None = None, skip_discovery: bool = False) -> list[str]:
    if wallets:
        wallets = [w.lower() for w in wallets]
        insert_many(con, "candidates", [(w, "manual", int(time.time())) for w in wallets])
    elif skip_discovery:
        wallets = [r[0] for r in con.execute("SELECT wallet FROM candidates ORDER BY wallet").fetchall()]
    else:
        wallets = discover(con, api, cfg)
    ingest_wallets(con, api, cfg, wallets)
    ingest_markets(con, api, cfg)
    return wallets
