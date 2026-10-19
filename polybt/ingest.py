"""Ingest: discover candidate wallets, pull their activity, market metadata and price history."""
from __future__ import annotations

import datetime as dt
import logging
import re
import time
from collections import Counter

from .api import PolymarketAPI, parse_market
from .db import insert_many

log = logging.getLogger(__name__)


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
        since = dt.datetime.fromtimestamp(cfg.selection_start_ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            markets = api.top_closed_markets(int(am["top_markets"]), since)
        except Exception as e:
            log.warning("top markets failed: %s", e)
            markets = []
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


def ingest_wallet(con, api: PolymarketAPI, wallet: str, start_ts: int) -> int:
    """Pull activity since the last sync. Never re-pulls a range already stored."""
    state = con.execute("SELECT start_ts, synced_to FROM wallet_ingest_state WHERE wallet = ?",
                        [wallet]).fetchone()
    now = int(time.time())
    ranges = []
    if state is None:
        ranges.append((start_ts, None))
    else:
        if start_ts < state[0]:
            ranges.append((start_ts, state[0] - 1))  # lookback widened
        ranges.append((state[1], None))
    n = 0
    for lo, hi in ranges:
        batch = []
        for r in api.activity(wallet, lo, hi):
            batch.append(_activity_row(wallet, r))
            if len(batch) >= 2000:
                n += _insert_trades(con, batch)
                batch = []
        n += _insert_trades(con, batch)
    new_start = min(start_ts, state[0]) if state else start_ts
    con.execute("INSERT OR REPLACE INTO wallet_ingest_state VALUES (?, ?, ?, ?)",
                [wallet, new_start, now, now])
    return n


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
    ids = [r[0] for r in con.execute("""
        SELECT DISTINCT t.condition_id FROM wallet_trades t
        LEFT JOIN markets m USING (condition_id)
        WHERE t.condition_id <> '' AND (m.condition_id IS NULL OR (NOT m.resolved AND m.fetched_at < ?))
    """, [stale]).fetchall()]
    rows = []
    for i in range(0, len(ids), batch):
        rows.extend(market_row(parse_market(raw), cfg) for raw in api.markets_by_condition(ids[i:i + batch]))
    insert_many(con, "markets", rows, "INSERT OR REPLACE")
    n = len(rows)
    log.info("markets: %d requested, %d stored", len(ids), n)
    return n


def market_row(m: dict, cfg) -> tuple:
    return (m["condition_id"], m["question"], m["slug"], m["token_ids"], m["outcomes"], m["payouts"],
            categorize(m["question"], m["slug"], cfg), m["volume"], m["end_time"], m["closed"],
            m["resolved"], m["resolved_outcome"], int(time.time()))


# ---- price history -------------------------------------------------------

def needed_price_chunks(con, cfg, wallets: list[str], since_ts: int) -> list[tuple[str, int]]:
    """(token_id, chunk_start) pairs covering every test-period trade, minus those already fetched."""
    ph = cfg["price_history"]
    chunk = int(ph["chunk_hours"]) * 3600
    pad = int(ph["pad_s"])
    max_delay = max(int(d) for d in cfg["simulate"]["delays_s"])
    if not wallets:
        return []
    rows = con.execute(f"""
        SELECT DISTINCT token_id, timestamp FROM wallet_trades
        WHERE type = 'TRADE' AND token_id <> '' AND timestamp >= ?
          AND wallet IN ({",".join("?" * len(wallets))})
    """, [since_ts, *wallets]).fetchall()
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
    for i, (token, start) in enumerate(todo):
        end = start + chunk
        try:
            points = api.prices_history(token, start, end, fidelity)
        except Exception as e:
            log.warning("prices for %s @ %d failed: %s", token, start, e)
            continue
        if points:
            insert_many(con, "price_history", [(token, t, p) for t, p in points])
            n += len(points)
        if end < time.time() - 3600:  # only a closed window is final
            con.execute("INSERT OR IGNORE INTO price_fetches VALUES (?, ?, ?)", [token, start, end])
        if (i + 1) % 100 == 0:
            log.info("  %d/%d chunks", i + 1, len(todo))
    return n


def run(con, api: PolymarketAPI, cfg, wallets: list[str] | None = None, skip_discovery: bool = False) -> list[str]:
    if wallets:
        wallets = [w.lower() for w in wallets]
        insert_many(con, "candidates", [(w, "manual", int(time.time())) for w in wallets])
    elif skip_discovery:
        wallets = [r[0] for r in con.execute("SELECT wallet FROM candidates ORDER BY wallet").fetchall()]
    else:
        wallets = discover(con, api, cfg)
    for i, w in enumerate(wallets):
        try:
            n = ingest_wallet(con, api, w, cfg.selection_start_ts)
            log.info("[%d/%d] %s: %d new rows", i + 1, len(wallets), w, n)
        except Exception as e:
            log.warning("[%d/%d] %s failed: %s", i + 1, len(wallets), w, e)
    ingest_markets(con, api, cfg)
    return wallets
