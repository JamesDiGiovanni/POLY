"""Paper and live trading: the backtest's CopyEngine, fed by polling wallets in real time.

Paper and production are the same code path. The runner, engine, policy, risk limits, fee model,
journal and reporting are identical; the only difference is the executor passed in:

    PaperExecutor   walks the live CLOB order book exactly as a fill-or-kill order would, sends nothing
    LiveExecutor    sends that fill-or-kill order

Every decision is written to `live_orders` keyed by (session, wallet, fill, token, side). On restart
the runner rebuilds each engine by replaying the wallet's stored fills; anything already in the
journal returns its recorded result instead of executing again, so a restart can never double-order.

`Runner` also runs offline against stored history (`ReplayAPI` + a simulated clock + the backtest
executor), which is how the tests prove the runner reproduces the backtest exactly.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Callable

from . import ingest
from .api import parse_market
from .db import insert_many
from .engine import CopyEngine, Execution, Fill, Market, OrderRequest, Policy
from .simulate import SimParams, copy_buy_price, copy_sell_price, load_fills, load_markets, size_reference

log = logging.getLogger(__name__)


# ---- executors -----------------------------------------------------------

def walk_book(levels: list[tuple[float, float]], *, usd: float | None = None, shares: float | None = None,
              limit: float, buying: bool) -> list[tuple[float, float]] | None:
    """Fill-or-kill against book levels (best first). Returns [(price, shares)] or None if it can't fill.

    Buys spend `usd` on asks priced at or below `limit`; sells sell `shares` into bids at or above it.
    """
    taken, need = [], usd if buying else shares
    for price, size in levels:
        if (buying and price > limit + 1e-12) or (not buying and price < limit - 1e-12):
            break
        if buying:
            sh = min(size, need / price)
            need -= sh * price
        else:
            sh = min(size, need)
            need -= sh
        if sh > 0:
            taken.append((price, sh))
        if need <= 1e-9:
            return taken
    return None


class PaperExecutor:
    """Fills against the live order book at the moment of execution. Sends nothing."""

    def __init__(self, api, params: SimParams, clock: Callable[[], float] = time.time):
        self.api = api
        self.params = params
        self.clock = clock

    def exec_ts(self, fill: Fill) -> int:
        return int(self.clock())

    def _book(self, token_id):
        book = self.api.book(token_id)
        bid = book["bids"][0][0] if book["bids"] else None
        ask = book["asks"][0][0] if book["asks"] else None
        mid = (bid + ask) / 2 if bid is not None and ask is not None else (bid if ask is None else ask)
        return book, bid, ask, mid

    def buy(self, req: OrderRequest) -> Execution | str:
        book, bid, ask, mid = self._book(req.token_id)
        taken = walk_book(book["asks"], usd=req.usd, limit=req.limit_price, buying=True)
        if taken is None:
            return "price_above_max" if ask is not None and ask > req.limit_price else "insufficient_liquidity"
        gross = sum(sh for _, sh in taken)
        net, fee = gross, 0.0
        for price, sh in taken:  # each match is charged at its own price
            got, f = req.market.fees.buy(sh, price)
            net -= sh - got
            fee += f
        model = copy_buy_price(req.wallet_price, mid, self.params.spread(req.market)) if mid is not None else None
        return Execution(req.exec_ts, req.usd / gross, net, req.usd, round(fee, 4), ref_price=mid,
                         meta={"best_bid": bid, "best_ask": ask, "levels": len(taken), "model_price": model})

    def sell(self, req: OrderRequest) -> Execution | str:
        book, bid, ask, mid = self._book(req.token_id)
        taken = walk_book(book["bids"], shares=req.shares, limit=req.limit_price, buying=False)
        if taken is None:
            return "insufficient_liquidity"
        usdc, fee = 0.0, 0.0
        for price, sh in taken:
            got, f = req.market.fees.sell(sh, price)
            usdc += got
            fee += f
        model = copy_sell_price(req.wallet_price, mid, self.params.spread(req.market)) if mid is not None else None
        avg = sum(p * s for p, s in taken) / req.shares
        return Execution(req.exec_ts, avg, req.shares, usdc, round(fee, 4), ref_price=mid,
                         meta={"best_bid": bid, "best_ask": ask, "levels": len(taken), "model_price": model})


class LiveExecutor:
    """Sends real fill-or-kill market orders. Same inputs and outputs as PaperExecutor."""

    def __init__(self, order_client, api, params: SimParams, clock: Callable[[], float] = time.time):
        self.client = order_client
        self.paper = PaperExecutor(api, params, clock)  # for the reference/model prices we record
        self.clock = clock

    def exec_ts(self, fill: Fill) -> int:
        return int(self.clock())

    def buy(self, req: OrderRequest) -> Execution | str:
        try:
            _, bid, ask, mid = self.paper._book(req.token_id)
        except Exception:
            bid = ask = mid = None
        res = self.client.market_buy(req.token_id, req.usd, req.limit_price)
        if isinstance(res, str):
            return res
        usdc, shares = res["usdc"], res["shares"]
        avg = usdc / shares if shares else 0.0
        fee = req.market.fees.fee_usdc(shares, avg)
        model = copy_buy_price(req.wallet_price, mid, self.paper.params.spread(req.market)) if mid is not None else None
        return Execution(int(self.clock()), avg, shares, usdc, fee, ref_price=mid,
                         meta={"order_id": res.get("order_id"), "best_bid": bid, "best_ask": ask, "model_price": model})

    def sell(self, req: OrderRequest) -> Execution | str:
        try:
            _, bid, ask, mid = self.paper._book(req.token_id)
        except Exception:
            bid = ask = mid = None
        res = self.client.market_sell(req.token_id, req.shares, req.limit_price)
        if isinstance(res, str):
            return res
        usdc, shares = res["usdc"], res["shares"]
        avg = usdc / shares if shares else 0.0
        fee = req.market.fees.fee_usdc(shares, avg)
        model = copy_sell_price(req.wallet_price, mid, self.paper.params.spread(req.market)) if mid is not None else None
        return Execution(int(self.clock()), avg, shares, usdc, fee, ref_price=mid,
                         meta={"order_id": res.get("order_id"), "best_bid": bid, "best_ask": ask, "model_price": model})


class ClobOrderClient:
    """Adapter over Polymarket's py-clob-client-v2. The only code that signs or sends anything.

    VERIFY against the installed SDK version before the first live session: the V2 SDK's names and
    response fields are taken from its README and may move between releases.
    """

    def __init__(self, private_key: str, funder: str | None, signature_type: int,
                 host: str = "https://clob.polymarket.com", chain_id: int = 137):
        from py_clob_client_v2.client import ClobClient  # imported here: paper mode never needs it
        from py_clob_client_v2.clob_types import MarketOrderArgs, OrderType

        self._MarketOrderArgs, self._OrderType = MarketOrderArgs, OrderType
        self.client = ClobClient(host, key=private_key, chain_id=chain_id,
                                 signature_type=signature_type, funder=funder)
        self.client.set_api_creds(self.client.create_or_derive_api_creds())

    def _post(self, token_id: str, amount: float, side: str, worst_price: float) -> dict | str:
        args = self._MarketOrderArgs(token_id=token_id, amount=round(amount, 6), side=side,
                                     price=worst_price, order_type=self._OrderType.FOK)
        try:
            resp = self.client.create_and_post_market_order(args)
        except Exception as e:
            log.error("order failed: %s", e)
            return f"order_error: {str(e)[:80]}"
        if not resp or not resp.get("success", False):
            return f"order_rejected: {(resp or {}).get('errorMsg', 'unknown')[:80]}"
        making, taking = float(resp.get("makingAmount") or 0), float(resp.get("takingAmount") or 0)
        if side == "BUY":   # we give USDC, take shares
            return {"usdc": making, "shares": taking, "order_id": resp.get("orderID")}
        return {"usdc": taking, "shares": making, "order_id": resp.get("orderID")}

    def market_buy(self, token_id: str, usd: float, worst_price: float):
        return self._post(token_id, usd, "BUY", worst_price)

    def market_sell(self, token_id: str, shares: float, worst_price: float):
        return self._post(token_id, shares, "SELL", worst_price)


# ---- journal -------------------------------------------------------------

class Journal:
    def __init__(self, con, session: str):
        self.con = con
        self.session = session
        self.rows: dict[tuple, tuple] = {}
        self.exec_at: dict[tuple, int] = {}  # (wallet, tx_hash) -> exec_ts of the first decision on it
        for r in con.execute("""SELECT wallet, tx_hash, token_id, side, exec_ts, status, reason, price, shares, usdc,
                                       fee, ref_price, meta FROM live_orders WHERE session = ?""", [session]).fetchall():
            self.rows[r[:4]] = r[4:]
            if r[4] is not None:
                self.exec_at.setdefault((r[0], r[1]), r[4])

    def get(self, wallet, tx_hash, token_id, side):
        return self.rows.get((wallet, tx_hash, token_id, side))

    def put(self, wallet: str, fill: Fill, token_id: str, side: str, seen_ts: int, exec_ts: int | None,
            result: Execution | str) -> None:
        key = (wallet, fill.tx_hash, token_id, side)
        if key in self.rows:
            return
        if isinstance(result, Execution):
            row = (exec_ts, "filled", None, result.price, result.shares, result.usdc, result.fee,
                   result.ref_price, json.dumps(result.meta))
            model = result.meta.get("model_price")
        else:
            row = (exec_ts, "skipped", result, None, None, None, None, None, None)
            model = None
        self.rows[key] = row
        if exec_ts is not None:
            self.exec_at.setdefault((wallet, fill.tx_hash), exec_ts)
        self.con.execute("INSERT OR IGNORE INTO live_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            self.session, wallet, fill.tx_hash, token_id, side, fill.ts, seen_ts, exec_ts, row[1], row[2],
            fill.price, row[3], row[4], row[5], row[6], row[7], model, row[8]])


class JournaledExecutor:
    """Returns the recorded result for anything already decided; executes and records everything else."""

    def __init__(self, inner, journal: Journal, wallet: str, seen: Callable[[Fill], int]):
        self.inner = inner
        self.journal = journal
        self.wallet = wallet
        self.seen = seen
        self.sent = 0

    def exec_ts(self, fill: Fill) -> int:
        recorded = self.journal.exec_at.get((self.wallet, fill.tx_hash))
        return recorded if recorded is not None else self.inner.exec_ts(fill)

    def _run(self, req: OrderRequest, fn) -> Execution | str:
        rec = self.journal.get(self.wallet, req.fill.tx_hash, req.token_id, req.side)
        if rec is not None:
            exec_ts, status, reason, price, shares, usdc, fee, ref, meta = rec
            if status != "filled":
                return reason
            return Execution(exec_ts, price, shares, usdc, fee, ref_price=ref, meta=json.loads(meta or "{}"))
        result = fn(req)
        self.sent += 1
        ts = result.ts if isinstance(result, Execution) else req.exec_ts
        self.journal.put(self.wallet, req.fill, req.token_id, req.side, self.seen(req.fill), ts, result)
        return result

    def buy(self, req):
        return self._run(req, self.inner.buy)

    def sell(self, req):
        return self._run(req, self.inner.sell)


# ---- runner --------------------------------------------------------------

def fill_key(f: Fill) -> tuple:
    return (f.tx_hash, f.token_id, f.side, f.size, f.price)


def activity_fill(row: dict) -> Fill | None:
    t = (row.get("type") or "TRADE").upper()
    side = (row.get("side") or "").upper()
    if t == "MERGE":
        side = "MERGE"
    elif t != "TRADE" or side not in ("BUY", "SELL"):
        return None
    price, size = float(row.get("price") or 0), float(row.get("size") or 0)
    usdc = row.get("usdcSize")
    return Fill(int(row["timestamp"]), str(row.get("asset") or ""), row.get("conditionId") or "", side, price, size,
                float(usdc) if usdc not in (None, "") else price * size, row.get("transactionHash") or "")


class Runner:
    def __init__(self, con, cfg, api, make_executor: Callable[[], object], session: str, mode: str,
                 wallets: list[str], clock: Callable[[], float] = time.time, sizing: str | None = None):
        self.con, self.cfg, self.api, self.clock = con, cfg, api, clock
        self.session, self.mode = session, mode
        self.markets: dict[str, Market] = load_markets(con, cfg["fees"]["formula"])
        row = con.execute("SELECT start_ts, wallets FROM live_sessions WHERE session = ?", [session]).fetchone()
        if row:
            self.start_ts = row[0]
            wallets = sorted(set(row[1]) | set(wallets))
            con.execute("UPDATE live_sessions SET wallets = ? WHERE session = ?", [wallets, session])
        else:
            self.start_ts = int(clock())
            con.execute("INSERT INTO live_sessions VALUES (?, ?, ?, ?, ?, ?)",
                        [session, mode, self.start_ts, wallets, json.dumps(cfg, default=str), int(time.time())])
        self.wallets = wallets
        self.journal = Journal(con, session)
        self.seen_at: dict[tuple, int] = {}
        sizing = sizing or cfg["live"].get("sizing", "flat")
        self.engines: dict[str, CopyEngine] = {}
        self.executors: dict[str, JournaledExecutor] = {}
        for w in wallets:
            ref = size_reference(con, w, cfg.selection_start_ts, cfg.cutoff_ts)
            ex = JournaledExecutor(make_executor(), self.journal, w,
                                   lambda f: self.seen_at.get(fill_key(f), int(self.clock())))
            self.executors[w] = ex
            self.engines[w] = CopyEngine(self.markets, ex, Policy.from_cfg(cfg, sizing, ref), self.start_ts)
        self.processed: dict[str, set] = {w: set() for w in wallets}
        self.last_ts: dict[str, int] = {}
        self.last_resolution_check = 0.0

    # Rebuild every engine from stored fills. Journaled decisions replay; nothing is re-sent.
    def bootstrap(self) -> None:
        now = int(self.clock())
        for w in self.wallets:
            fills = [f for f in load_fills(self.con, w) if f.ts <= now]
            for f in sorted(fills, key=lambda f: (f.ts, f.side != "BUY")):
                self._process(w, f)
            self.last_ts[w] = max([f.ts for f in fills] + [self.start_ts])
        for e in self.engines.values():
            e.settle(now)
        log.info("session %s (%s): %d wallets, started %s", self.session, self.mode, len(self.wallets),
                 time.strftime("%Y-%m-%d %H:%M", time.gmtime(self.start_ts)))

    def _ensure_market(self, condition_id: str) -> None:
        if condition_id in self.markets or not condition_id:
            return
        try:
            raws = self.api.markets_by_condition([condition_id], live=True)
        except Exception as e:
            log.warning("market %s lookup failed: %s", condition_id, e)
            return
        self._store_markets(raws)

    def _store_markets(self, raws) -> None:
        rows = [ingest.market_row(parse_market(r), self.cfg, self.api) for r in raws]
        if not rows:
            return
        insert_many(self.con, "markets", rows, "INSERT OR REPLACE")
        fresh = load_markets(self.con, self.cfg["fees"]["formula"])
        for r in rows:
            self.markets[r[0]] = fresh[r[0]]

    def _process(self, wallet: str, f: Fill) -> None:
        key = fill_key(f)
        if key in self.processed[wallet]:
            return
        self.processed[wallet].add(key)
        if f.ts >= self.start_ts:  # older fills only rebuild the wallet's position; no market needed
            self._ensure_market(f.condition_id)
        engine = self.engines[wallet]
        n_skips = len(engine.skips)
        engine.on_fill(f)
        for s in engine.skips[n_skips:]:  # engine-level skips (stale, risk, min order, ...) are decisions too
            self.journal.put(wallet, f, s.token_id, s.side, self.seen_at.get(key, int(self.clock())),
                             self.executors[wallet].exec_ts(f), s.reason)

    def poll_once(self) -> int:
        """One cycle: pull new activity for every wallet, act on it, settle resolutions. Returns new fills."""
        now = int(self.clock())
        new = 0
        for w in self.wallets:
            try:
                rows = list(self.api.activity(w, self.last_ts.get(w, self.start_ts), live=True))
            except Exception as e:
                log.warning("poll %s failed: %s", w, e)
                continue
            if not rows:
                continue
            insert_many(self.con, "wallet_trades", [ingest._activity_row(w, r) for r in rows])
            fills = sorted(filter(None, map(activity_fill, rows)), key=lambda f: (f.ts, f.side != "BUY"))
            for f in fills:
                if fill_key(f) in self.processed[w]:
                    continue
                self.seen_at.setdefault(fill_key(f), now)
                self._process(w, f)
                new += 1
            self.last_ts[w] = max([self.last_ts.get(w, self.start_ts)] + [int(r.get("timestamp", 0)) for r in rows])
        if now - self.last_resolution_check >= float(self.cfg["live"]["resolution_check_s"]):
            self.check_resolutions()
            self.last_resolution_check = now
        for e in self.engines.values():
            e.settle(now)
        return new

    def check_resolutions(self) -> None:
        open_ids = sorted({lot.condition_id for e in self.engines.values() for lot in e.lots if not lot.closed}
                          - {cid for cid, m in self.markets.items() if m.resolved})
        for i in range(0, len(open_ids), 20):
            try:
                self._store_markets(self.api.markets_by_condition(open_ids[i:i + 20], live=True))
            except Exception as e:
                log.warning("resolution check failed: %s", e)

    def snapshot(self) -> None:
        """Write the current portfolio to live_lots (replaced per session)."""
        self.con.execute("DELETE FROM live_lots WHERE session = ?", [self.session])
        rows = []
        for w, e in self.engines.items():
            for lot in e.lots:
                rows.append((self.session, w, lot.tx_hash, lot.token_id, lot.condition_id, lot.category, lot.ts,
                             lot.exec_ts, lot.wallet_price, lot.entry_price, lot.shares, lot.open_shares, lot.stake,
                             lot.fees, lot.proceeds, lot.pnl if lot.closed else None, lot.close_ts,
                             "closed" if lot.closed else "open"))
        insert_many(self.con, "live_lots", rows, "INSERT")

    def run(self, max_cycles: int | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self.bootstrap()
        self.snapshot()
        interval = float(self.cfg["live"]["poll_interval_s"])
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            started = self.clock()
            if self.poll_once():
                self.snapshot()
            cycles += 1
            sleep(max(0.0, interval - (self.clock() - started)))
        self.snapshot()


# ---- offline replay ------------------------------------------------------

class ReplayClock:
    def __init__(self, t: float):
        self.t = t

    def __call__(self) -> float:
        return self.t


class ReplayAPI:
    """Serves stored activity as if it were arriving live, up to the replay clock."""

    def __init__(self, con, clock: ReplayClock):
        self.clock = clock
        self.rows: dict[str, list[dict]] = {}
        for w, tx, typ, token, cid, side, price, size, usdc, ts in con.execute("""
                SELECT wallet, tx_hash, type, token_id, condition_id, side, price, size, usdc_size, timestamp
                FROM wallet_trades ORDER BY timestamp""").fetchall():
            self.rows.setdefault(w, []).append({"transactionHash": tx, "type": typ, "asset": token, "conditionId": cid,
                                                "side": side, "price": price, "size": size, "usdcSize": usdc,
                                                "timestamp": ts})

    def activity(self, user, start, end=None, live=False):
        now = self.clock()
        return [r for r in self.rows.get(user, []) if start <= r["timestamp"] <= now]

    def next_event_after(self, wallets, t) -> int | None:
        times = [r["timestamp"] for w in wallets for r in self.rows.get(w, []) if r["timestamp"] > t]
        return min(times) if times else None

    def markets_by_condition(self, ids, live=False):
        return []  # markets come from the stored table, already carrying their final resolution

    def clob_market_info(self, condition_id):
        return None


def replay(con, cfg, wallets: list[str], start_ts: int, make_executor, session: str, poll_interval: int = 5) -> Runner:
    """Run the live runner over stored history, jumping the clock between events."""
    clock = ReplayClock(start_ts)
    api = ReplayAPI(con, clock)
    runner = Runner(con, cfg, api, make_executor, session, "replay", wallets, clock=clock)
    runner.last_resolution_check = float("inf")  # resolutions are already in the stored markets
    runner.bootstrap()
    while True:
        nxt = api.next_event_after(wallets, clock.t)
        if nxt is None:
            break
        clock.t = max(nxt, clock.t + poll_interval)
        runner.poll_once()
    for e in runner.engines.values():
        e.settle()
    runner.snapshot()
    return runner


# ---- construction from config --------------------------------------------

@dataclass
class LiveCredentials:
    private_key: str
    funder: str | None

    @classmethod
    def from_env(cls) -> "LiveCredentials":
        pk = os.environ.get("POLYBT_PRIVATE_KEY")
        if not pk:
            raise SystemExit("live trading needs POLYBT_PRIVATE_KEY in the environment")
        return cls(pk, os.environ.get("POLYBT_FUNDER"))


def make_executor_factory(mode: str, cfg, api, clock=time.time):
    params = SimParams.from_cfg(cfg)
    if mode == "paper":
        return lambda: PaperExecutor(api, params, clock)
    if mode == "live":
        creds = LiveCredentials.from_env()
        client = ClobOrderClient(creds.private_key, creds.funder, int(cfg["live"].get("signature_type", 1)))
        return lambda: LiveExecutor(client, api, params, clock)
    raise ValueError(mode)

