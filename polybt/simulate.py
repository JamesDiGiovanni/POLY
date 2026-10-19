"""Backtest: replay a wallet's fills through the shared CopyEngine with a historical-price executor.

The engine (polybt.engine) decides what to trade; BacktestExecutor decides the fill from price
history and the spread model. Paper and live trading drive the same engine with other executors.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field

from .db import insert_many
from .engine import (CopyEngine, Execution, Fill, Lot, Market, MirrorExecutor, OrderRequest, Policy,
                     PriceSeries, Skip)
from .fees import FeeParams

log = logging.getLogger(__name__)

__all__ = ["Fill", "Market", "PriceSeries", "SimParams", "Lot", "Skip", "BacktestExecutor", "simulate",
           "copy_buy_price", "copy_sell_price", "run"]


@dataclass
class SimParams:
    """The spread model, plus the policy knobs the hand-built tests set directly."""
    stake_usd: float = 10.0
    spread_penalty: float = 0.01
    spread_penalty_low_volume: float = 0.02
    low_volume_threshold_usd: float = 50_000
    max_copy_price: float = 0.97
    min_order_usd: float = 0.0
    policy: Policy | None = field(default=None, repr=False)

    @classmethod
    def from_cfg(cls, cfg: dict) -> "SimParams":
        s = cfg["simulate"]
        return cls(stake_usd=float(s["stake_usd"]), spread_penalty=float(s["spread_penalty"]),
                   spread_penalty_low_volume=float(s["spread_penalty_low_volume"]),
                   low_volume_threshold_usd=float(s["low_volume_threshold_usd"]),
                   max_copy_price=float(s["max_copy_price"]),
                   min_order_usd=float(s.get("min_order_usd", 1.0)))

    def spread(self, market: Market) -> float:
        if market.volume is not None and market.volume < self.low_volume_threshold_usd:
            return self.spread_penalty_low_volume
        return self.spread_penalty

    def to_policy(self) -> Policy:
        return self.policy or Policy(stake_usd=self.stake_usd, max_copy_price=self.max_copy_price,
                                     min_order_usd=self.min_order_usd)


def copy_buy_price(wallet_price: float, market_price: float, spread: float) -> float:
    """Never fill better than the wallet did, then pay the spread."""
    return max(wallet_price, market_price) + spread


def copy_sell_price(wallet_price: float | None, market_price: float, spread: float) -> float:
    ref = market_price if wallet_price is None else min(wallet_price, market_price)
    return max(0.0, ref - spread)


class BacktestExecutor:
    """Fills at the historical market price `delay_s` after the wallet, with the modelled spread."""

    def __init__(self, prices: dict[str, PriceSeries], params: SimParams, delay_s: int):
        self.prices = prices
        self.params = params
        self.delay_s = delay_s

    def exec_ts(self, fill: Fill) -> int:
        return fill.ts + self.delay_s

    def _market_price(self, req: OrderRequest) -> float | None:
        series = self.prices.get(req.token_id)
        return series.at(req.fill.ts, req.wallet_price, req.exec_ts) if series else None

    def buy(self, req: OrderRequest) -> Execution | str:
        mp = self._market_price(req)
        if mp is None:
            return "no_price_history"
        cp = copy_buy_price(req.wallet_price, mp, self.params.spread(req.market))
        if cp > req.limit_price:
            return "price_above_max"
        shares, fee = req.market.fees.buy(req.usd / cp, cp)
        return Execution(req.exec_ts, cp, shares, req.usd, fee, ref_price=mp)

    def sell(self, req: OrderRequest) -> Execution | str:
        mp = self._market_price(req)
        if mp is None:
            if req.wallet_price is None:
                return "no_price_history"
            mp = req.wallet_price
        price = copy_sell_price(req.wallet_price, mp, self.params.spread(req.market))
        if price <= 0:
            return Execution(req.exec_ts, 0.0, req.shares, 0.0, 0.0, ref_price=mp)
        usdc, fee = req.market.fees.sell(req.shares, price)
        return Execution(req.exec_ts, price, req.shares, usdc, fee, ref_price=mp)


def simulate(fills: list[Fill], markets: dict[str, Market], prices: dict[str, PriceSeries],
             params: SimParams, delay_s: int, start_ts: int, end_ts: int | None = None,
             mode: str = "copy") -> tuple[list[Lot], list[Skip]]:
    """Replay fills through the engine.

    mode='copy': delayed copies via BacktestExecutor. mode='wallet': the wallet's own fills at
    their real cost (MirrorExecutor), for wallet ROI on the same lot basis.
    """
    if mode == "wallet":
        engine = CopyEngine(markets, MirrorExecutor(), Policy.mirror(), start_ts, end_ts)
    else:
        engine = CopyEngine(markets, BacktestExecutor(prices, params, delay_s), params.to_policy(), start_ts, end_ts)
    for f in sorted(fills, key=lambda f: (f.ts, f.side != "BUY")):
        engine.on_fill(f)
    engine.settle()
    return engine.lots, engine.skips


# ---- database glue -------------------------------------------------------

def load_markets(con, formula: str = "v2") -> dict[str, Market]:
    out = {}
    for cid, cat, vol, resolved, end_time, tokens, payouts, rate, exponent in con.execute("""
            SELECT condition_id, category, volume, resolved, end_time, token_ids, payouts, fee_rate, fee_exponent
            FROM markets""").fetchall():
        fees = FeeParams(rate=rate or 0.0, exponent=exponent or 1.0, formula=formula)
        out[cid] = Market(cid, cat, vol, bool(resolved), end_time, dict(zip(tokens or [], payouts or [])),
                          fees, list(tokens or []))
    return out


def load_fills(con, wallet: str, since_ts: int | None = None) -> list[Fill]:
    rows = con.execute("""
        SELECT timestamp, token_id, condition_id, CASE WHEN type = 'MERGE' THEN 'MERGE' ELSE side END,
               price, size, coalesce(usdc_size, price * size), tx_hash
        FROM wallet_trades
        WHERE wallet = ? AND timestamp >= ?
          AND ((type = 'TRADE' AND side IN ('BUY', 'SELL')) OR type = 'MERGE')
        ORDER BY timestamp
    """, [wallet, since_ts or 0]).fetchall()
    return [Fill(*r) for r in rows]


def load_prices(con, token_ids) -> dict[str, PriceSeries]:
    token_ids = list(token_ids)
    if not token_ids:
        return {}
    con.execute("CREATE OR REPLACE TEMP TABLE _tok (token_id VARCHAR)")
    insert_many(con, "_tok", [(t,) for t in token_ids], "INSERT")
    out: dict[str, PriceSeries] = {}
    for token, ts, price in con.execute("""
        SELECT p.token_id, p.timestamp, p.price FROM price_history p JOIN _tok USING (token_id)
        ORDER BY p.token_id, p.timestamp
    """).fetchall():
        s = out.setdefault(token, PriceSeries([], []))
        s.ts.append(ts)
        s.price.append(price)
    return out


def size_reference(con, wallet: str, start_ts: int, cutoff_ts: int) -> float | None:
    """The wallet's median buy in the selection window: the unit for proportional sizing."""
    sizes = [r[0] for r in con.execute("""
        SELECT usdc_size FROM wallet_trades WHERE wallet = ? AND type = 'TRADE' AND side = 'BUY'
          AND timestamp >= ? AND timestamp < ? AND usdc_size > 0""", [wallet, start_ts, cutoff_ts]).fetchall()]
    return statistics.median(sizes) if sizes else None


def lot_rows(wallet, mode, delay_s, sizing, lots, skips):
    """sim_trades rows (column order matches the table)."""
    for lot in lots:
        yield (wallet, mode, delay_s, lot.tx_hash, lot.token_id, lot.condition_id, lot.category, "BUY",
               lot.ts, lot.wallet_price, lot.market_price, lot.entry_price, lot.shares, lot.stake,
               lot.fees, lot.proceeds, lot.pnl if lot.closed else None, lot.close_ts,
               "closed" if lot.closed else "open", None, sizing, lot.exec_ts)
    for s in skips:
        yield (wallet, mode, delay_s, s.tx_hash, s.token_id, s.condition_id, s.category, s.side, s.ts,
               s.wallet_price, None, None, None, None, None, None, None, None, "skipped", s.reason, sizing, None)


def run(con, cfg, wallets: list[str] | None = None) -> int:
    """Simulate the test period (after the cutoff) for the given wallets, default all that passed filters."""
    if not wallets:
        wallets = [r[0] for r in con.execute(
            "SELECT wallet FROM wallet_scores WHERE passed ORDER BY wallet").fetchall()]
        con.execute("DELETE FROM sim_trades WHERE mode IN ('copy', 'wallet')")  # results = this shortlist only
    if not wallets:
        log.warning("no wallets to simulate (none passed the filters?)")
        return 0
    params = SimParams.from_cfg(cfg)
    markets = load_markets(con, cfg["fees"]["formula"])
    cutoff = cfg.cutoff_ts
    sizings = cfg["simulate"].get("sizing") or ["flat"]
    n = 0
    for w in wallets:
        fills = load_fills(con, w)
        prices = load_prices(con, {f.token_id for f in fills if f.ts >= cutoff}
                             | {t for f in fills if f.side == "MERGE" and f.condition_id in markets
                                for t in markets[f.condition_id].token_ids})
        ref = size_reference(con, w, cfg.selection_start_ts, cutoff)
        con.execute("DELETE FROM sim_trades WHERE wallet = ? AND mode IN ('copy', 'wallet')", [w])
        rows = []
        lots, skips = simulate(fills, markets, prices, params, 0, cutoff, mode="wallet")
        rows.extend(lot_rows(w, "wallet", 0, "mirror", lots, skips))
        for sizing in sizings:
            params.policy = Policy.from_cfg(cfg, sizing, ref)
            for d in cfg["simulate"]["delays_s"]:
                lots, skips = simulate(fills, markets, prices, params, int(d), cutoff)
                rows.extend(lot_rows(w, "copy", int(d), sizing, lots, skips))
        params.policy = None
        insert_many(con, "sim_trades", rows, "INSERT")
        n += len(rows)
        log.info("simulated %s: %d rows", w, len(rows))
    return n
