"""Copy simulation: replay a wallet's fills as delayed copies at worse prices, after fees.

The engine works on plain objects so it can be unit-tested without a database;
`run` at the bottom loads from and writes to DuckDB.
"""
from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass, field

from .db import insert_many

log = logging.getLogger(__name__)

EPS = 1e-9


@dataclass
class Fill:
    ts: int
    token_id: str
    condition_id: str
    side: str           # BUY | SELL
    price: float
    size: float         # shares
    usdc_size: float    # what the wallet actually paid / received, fees included
    tx_hash: str = ""


@dataclass
class Market:
    condition_id: str
    category: str
    volume: float | None
    resolved: bool
    end_time: int | None
    payouts: dict[str, float] = field(default_factory=dict)  # token_id -> payout per share

    def resolved_by(self, ts: int) -> bool:
        return self.resolved and self.end_time is not None and self.end_time <= ts


@dataclass
class PriceSeries:
    ts: list[int]
    price: list[float]

    def at(self, fill_ts: int, wallet_price: float, target_ts: int) -> float | None:
        """Market price at target_ts for a fill at fill_ts.

        Uses the latest observation after the fill and at or before target_ts. With none
        (delays under the 1-minute resolution), interpolates linearly from the wallet's own
        fill to the next observation. With no later observation at all, falls back to the
        wallet's price. None only if the series is empty.
        """
        if not self.ts:
            return None
        i = bisect.bisect_right(self.ts, target_ts) - 1
        if i >= 0 and self.ts[i] > fill_ts:
            return self.price[i]
        j = bisect.bisect_right(self.ts, fill_ts)
        if j < len(self.ts):
            t1, p1 = self.ts[j], self.price[j]
            w = (target_ts - fill_ts) / (t1 - fill_ts)
            return wallet_price + w * (p1 - wallet_price)
        return wallet_price


@dataclass
class SimParams:
    stake_usd: float = 10.0
    spread_penalty: float = 0.01
    spread_penalty_low_volume: float = 0.02
    low_volume_threshold_usd: float = 50_000
    max_copy_price: float = 0.97
    fees: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_cfg(cls, cfg: dict) -> "SimParams":
        s = cfg["simulate"]
        return cls(stake_usd=float(s["stake_usd"]), spread_penalty=float(s["spread_penalty"]),
                   spread_penalty_low_volume=float(s["spread_penalty_low_volume"]),
                   low_volume_threshold_usd=float(s["low_volume_threshold_usd"]),
                   max_copy_price=float(s["max_copy_price"]),
                   fees={k: float(v) for k, v in (s.get("fees") or {}).items()})

    def spread(self, market: Market) -> float:
        if market.volume is not None and market.volume < self.low_volume_threshold_usd:
            return self.spread_penalty_low_volume
        return self.spread_penalty

    def fee_rate(self, market: Market) -> float:
        return self.fees.get(market.category, 0.0)


def copy_buy_price(wallet_price: float, market_price: float, spread: float) -> float:
    """Never fill better than the wallet did, then pay the spread."""
    return max(wallet_price, market_price) + spread


def copy_sell_price(wallet_price: float, market_price: float, spread: float) -> float:
    return max(0.0, min(wallet_price, market_price) - spread)


@dataclass
class Lot:
    """One copied buy. P&L from later exits is allocated to it pro rata."""
    tx_hash: str
    token_id: str
    condition_id: str
    category: str
    ts: int
    wallet_price: float
    market_price: float | None
    entry_price: float
    shares: float
    stake: float        # cash out at entry, fees included
    fees: float
    open_shares: float = 0.0
    proceeds: float = 0.0
    close_ts: int | None = None

    @property
    def closed(self) -> bool:
        return self.open_shares <= EPS * max(1.0, self.shares)

    @property
    def pnl(self) -> float:
        return self.proceeds - self.stake


@dataclass
class Skip:
    tx_hash: str
    token_id: str
    condition_id: str
    category: str
    side: str
    ts: int
    wallet_price: float
    reason: str


def simulate(fills: list[Fill], markets: dict[str, Market], prices: dict[str, PriceSeries],
             params: SimParams, delay_s: int, start_ts: int, end_ts: int | None = None,
             mode: str = "copy") -> tuple[list[Lot], list[Skip]]:
    """Replay fills.

    mode='copy': each BUY at or after start_ts is copied with a flat stake at the delayed,
    penalised price; SELLs close the same fraction of the copy position at the same delay;
    anything still held is settled at resolution.
    mode='wallet': the wallet's own fills at their real cost (delay and penalties ignored),
    used for wallet ROI on the same lot basis.

    Fills before start_ts only build up the wallet's position so later sell fractions are right.
    Exits after end_ts are ignored (and resolutions after end_ts too), which keeps the
    selection window free of lookahead.
    """
    lots: list[Lot] = []
    skips: list[Skip] = []
    open_lots: dict[str, list[Lot]] = {}
    wallet_shares: dict[str, float] = {}

    for f in sorted(fills, key=lambda f: (f.ts, f.side != "BUY")):
        if end_ts is not None and f.ts >= end_ts:
            break
        held = wallet_shares.get(f.token_id, 0.0)
        if f.side == "BUY":
            wallet_shares[f.token_id] = held + f.size
            if f.ts < start_ts:
                continue
            m = markets.get(f.condition_id)
            cat = m.category if m else "unknown"

            def skip(reason):
                skips.append(Skip(f.tx_hash, f.token_id, f.condition_id, cat, "BUY", f.ts, f.price, reason))

            if m is None:
                skip("no_market_data")
                continue
            if mode == "wallet":
                if f.size <= 0:
                    continue
                lot = Lot(f.tx_hash, f.token_id, f.condition_id, cat, f.ts, f.price, None, f.price,
                          f.size, f.usdc_size, 0.0, open_shares=f.size)
            else:
                entry_ts = f.ts + delay_s
                if m.resolved_by(entry_ts):
                    skip("resolved_before_entry")
                    continue
                series = prices.get(f.token_id)
                mp = series.at(f.ts, f.price, entry_ts) if series else None
                if mp is None:
                    skip("no_price_history")
                    continue
                cp = copy_buy_price(f.price, mp, params.spread(m))
                if cp > params.max_copy_price:
                    skip("price_above_max")
                    continue
                fee = params.stake_usd * params.fee_rate(m)
                shares = params.stake_usd / cp
                lot = Lot(f.tx_hash, f.token_id, f.condition_id, cat, f.ts, f.price, mp, cp,
                          shares, params.stake_usd + fee, fee, open_shares=shares)
            lots.append(lot)
            open_lots.setdefault(f.token_id, []).append(lot)

        elif f.side == "SELL":
            wallet_shares[f.token_id] = max(0.0, held - f.size)
            mine = [lot for lot in open_lots.get(f.token_id, []) if not lot.closed]
            if not mine or held <= EPS:
                continue
            frac = min(1.0, f.size / held)
            m = markets.get(f.condition_id)
            if mode == "wallet":
                # Proceeds for the shares we know about; any excess came from before the window.
                per_share = f.usdc_size / f.size if f.size > 0 else 0.0
                exit_ts, price, fee_rate = f.ts, per_share, 0.0
            else:
                exit_ts = f.ts + delay_s
                if m is None or m.resolved_by(exit_ts):
                    continue  # too late to sell; the copy rides to resolution
                series = prices.get(f.token_id)
                mp = series.at(f.ts, f.price, exit_ts) if series else None
                if mp is None:
                    mp = f.price
                price = copy_sell_price(f.price, mp, params.spread(m))
                fee_rate = params.fee_rate(m)
            if end_ts is not None and exit_ts >= end_ts:
                continue
            for lot in mine:
                sh = lot.open_shares * frac
                gross = sh * price
                fee = gross * fee_rate
                lot.proceeds += gross - fee
                lot.fees += fee
                lot.open_shares -= sh
                if lot.closed:
                    lot.open_shares = 0.0
                    lot.close_ts = exit_ts

    for lot in lots:
        if lot.closed:
            continue
        m = markets.get(lot.condition_id)
        if m and m.resolved and m.end_time is not None and (end_ts is None or m.end_time < end_ts):
            lot.proceeds += lot.open_shares * m.payouts.get(lot.token_id, 0.0)
            lot.open_shares = 0.0
            lot.close_ts = max(m.end_time, lot.ts)
    return lots, skips


# ---- database glue -------------------------------------------------------

def load_markets(con) -> dict[str, Market]:
    out = {}
    for cid, cat, vol, resolved, end_time, tokens, payouts in con.execute(
            "SELECT condition_id, category, volume, resolved, end_time, token_ids, payouts FROM markets").fetchall():
        out[cid] = Market(cid, cat, vol, bool(resolved), end_time,
                          dict(zip(tokens or [], payouts or [])))
    return out


def load_fills(con, wallet: str) -> list[Fill]:
    rows = con.execute("""
        SELECT timestamp, token_id, condition_id, side, price, size, coalesce(usdc_size, price * size), tx_hash
        FROM wallet_trades WHERE wallet = ? AND type = 'TRADE' AND side IN ('BUY', 'SELL')
        ORDER BY timestamp
    """, [wallet]).fetchall()
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


def _rows(wallet, mode, delay_s, lots, skips):
    for lot in lots:
        yield (wallet, mode, delay_s, lot.tx_hash, lot.token_id, lot.condition_id, lot.category, "BUY",
               lot.ts, lot.wallet_price, lot.market_price, lot.entry_price, lot.shares, lot.stake,
               lot.fees, lot.proceeds, lot.pnl if lot.closed else None, lot.close_ts,
               "closed" if lot.closed else "open", None)
    for s in skips:
        yield (wallet, mode, delay_s, s.tx_hash, s.token_id, s.condition_id, s.category, s.side, s.ts,
               s.wallet_price, None, None, None, None, None, None, None, None, "skipped", s.reason)


def run(con, cfg, wallets: list[str] | None = None) -> int:
    """Simulate the test period (after the cutoff) for the given wallets, default all that passed filters."""
    if not wallets:
        wallets = [r[0] for r in con.execute(
            "SELECT wallet FROM wallet_scores WHERE passed ORDER BY wallet").fetchall()]
    if not wallets:
        log.warning("no wallets to simulate (none passed the filters?)")
        return 0
    params = SimParams.from_cfg(cfg)
    markets = load_markets(con)
    cutoff = cfg.cutoff_ts
    n = 0
    for w in wallets:
        fills = load_fills(con, w)
        prices = load_prices(con, {f.token_id for f in fills if f.ts >= cutoff})
        con.execute("DELETE FROM sim_trades WHERE wallet = ?", [w])
        rows = []
        lots, skips = simulate(fills, markets, prices, params, 0, cutoff, mode="wallet")
        rows.extend(_rows(w, "wallet", 0, lots, skips))
        for d in cfg["simulate"]["delays_s"]:
            lots, skips = simulate(fills, markets, prices, params, int(d), cutoff)
            rows.extend(_rows(w, "copy", int(d), lots, skips))
        insert_many(con, "sim_trades", rows, "INSERT")
        n += len(rows)
        log.info("simulated %s: %d rows", w, len(rows))
    return n
