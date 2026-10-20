"""The copy engine, shared by the backtest, paper trading and live trading.

Everything that decides *what* to trade lives here: which wallet fills are copied, how big each copy is,
the price cap, the minimum order, staleness and risk limits, how exits are mirrored, how resolution
settles a position. *How* an order gets filled is the only thing that differs between modes, and that
is the Executor's job:

    BacktestExecutor   historical price + modelled spread           (polybt.simulate)
    MirrorExecutor     the wallet's own fills at its real cost      (wallet ROI)
    PaperExecutor      walks the live CLOB order book, no order     (polybt.live)
    LiveExecutor       posts a real fill-or-kill order              (polybt.live)

So a paper session and a production session run byte-for-byte the same engine code; only the executor
differs, and paper fills against the same book a live order would hit.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from .fees import ZERO, FeeParams

EPS = 1e-9


@dataclass
class Fill:
    ts: int
    token_id: str
    condition_id: str
    side: str           # BUY | SELL | MERGE
    price: float
    size: float         # shares (pairs, for a MERGE)
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
    fees: FeeParams = ZERO
    token_ids: list[str] = field(default_factory=list)
    fee_category: str = "default"   # politics, sports, crypto, ... (used for specialist scoring)

    def resolved_by(self, ts: int) -> bool:
        return self.resolved and self.end_time is not None and self.end_time <= ts


@dataclass
class PriceSeries:
    ts: list[int]
    price: list[float]

    def at(self, fill_ts: int, wallet_price: float | None, target_ts: int) -> float | None:
        """Market price at target_ts for a fill at fill_ts.

        Uses the latest observation after the fill and at or before target_ts. With none
        (delays under the 1-minute resolution), interpolates linearly from the wallet's own
        fill to the next observation. With no later observation at all, falls back to the
        wallet's price. None only if the series is empty. Without a wallet price (a merge),
        the latest observation at or before target_ts, else the next one.
        """
        if not self.ts:
            return None
        i = bisect.bisect_right(self.ts, target_ts) - 1
        if i >= 0 and (self.ts[i] > fill_ts or wallet_price is None):
            return self.price[i]
        j = bisect.bisect_right(self.ts, fill_ts)
        if wallet_price is None:
            return self.price[j] if j < len(self.ts) else None
        if j < len(self.ts):
            t1, p1 = self.ts[j], self.price[j]
            w = (target_ts - fill_ts) / (t1 - fill_ts)
            return wallet_price + w * (p1 - wallet_price)
        return wallet_price


@dataclass
class Policy:
    """The trading rules. One instance, from config, for every mode."""
    stake_usd: float = 10.0
    sizing: str = "flat"                 # flat | proportional | mirror
    size_ref_usd: float | None = None    # wallet's median buy, for proportional sizing
    max_stake_multiple: float = 5.0
    max_copy_price: float = 0.97
    min_sell_price: float = 0.001
    min_order_usd: float = 1.0
    max_signal_age_s: float | None = None
    max_open_usd: float | None = None
    max_market_usd: float | None = None

    @classmethod
    def from_cfg(cls, cfg: dict, sizing: str = "flat", size_ref_usd: float | None = None) -> "Policy":
        s, r = cfg["simulate"], cfg.get("risk") or {}
        return cls(stake_usd=float(s["stake_usd"]), sizing=sizing, size_ref_usd=size_ref_usd,
                   max_stake_multiple=float(s.get("max_stake_multiple", 5.0)),
                   max_copy_price=float(s["max_copy_price"]), min_order_usd=float(s.get("min_order_usd", 1.0)),
                   max_signal_age_s=r.get("max_signal_age_s"), max_open_usd=r.get("max_open_usd"),
                   max_market_usd=r.get("max_market_usd"))

    @classmethod
    def mirror(cls) -> "Policy":
        return cls(sizing="mirror", max_copy_price=1.0, min_sell_price=0.0, min_order_usd=0.0)

    @property
    def is_mirror(self) -> bool:
        return self.sizing == "mirror"

    def stake(self, f: Fill) -> float:
        if self.sizing == "mirror":
            return f.usdc_size
        if self.sizing == "proportional":
            if not self.size_ref_usd or self.size_ref_usd <= 0:
                return self.stake_usd
            return self.stake_usd * min(self.max_stake_multiple, f.usdc_size / self.size_ref_usd)
        return self.stake_usd


@dataclass
class OrderRequest:
    fill: Fill
    market: Market
    side: str               # BUY | SELL
    token_id: str
    exec_ts: int
    usd: float = 0.0        # BUY: USDC to spend
    shares: float = 0.0     # SELL: shares to sell
    limit_price: float = 1.0  # BUY: worst (highest) price; SELL: worst (lowest)
    wallet_price: float | None = None


@dataclass
class Execution:
    ts: int
    price: float            # average fill price before fees
    shares: float           # BUY: shares received net of fees; SELL: shares sold
    usdc: float             # BUY: USDC spent; SELL: USDC received net of fees
    fee: float
    ref_price: float | None = None   # market price the executor saw (mid, or historical print)
    meta: dict = field(default_factory=dict)


class Executor(Protocol):
    def exec_ts(self, fill: Fill) -> int: ...
    def buy(self, req: OrderRequest) -> Execution | str: ...   # a str is a skip reason
    def sell(self, req: OrderRequest) -> Execution | str: ...


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
    stake: float        # cash out at entry
    fees: float
    open_shares: float = 0.0
    proceeds: float = 0.0
    close_ts: int | None = None
    exec_ts: int | None = None

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


class CopyEngine:
    """Feed it one wallet's fills in time order; it keeps the copy portfolio.

    Fills before start_ts only build up the wallet's position so later sell fractions are right.
    Executions at or after end_ts are ignored (and resolutions after end_ts too), which keeps a
    selection window free of lookahead.
    """

    def __init__(self, markets: Mapping[str, Market], executor: Executor, policy: Policy,
                 start_ts: int, end_ts: int | None = None):
        self.markets = markets
        self.executor = executor
        self.policy = policy
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.lots: list[Lot] = []
        self.skips: list[Skip] = []
        self.open_lots: dict[str, list[Lot]] = {}
        self.wallet_shares: dict[str, float] = {}
        self.stopped = False

    # ---- events ------------------------------------------------------------

    def on_fill(self, f: Fill) -> None:
        if self.stopped:
            return
        if self.end_ts is not None and f.ts >= self.end_ts:
            self.stopped = True
            return
        if f.side == "BUY":
            self._buy(f)
        elif f.side == "SELL":
            self._sell(f, f.token_id, f.size, f.price)
        elif f.side == "MERGE":
            # Merging YES+NO back into USDC exits both sides; copies holding either side sell it.
            m = self.markets.get(f.condition_id)
            for token in (m.token_ids if m else []):
                self._sell(f, token, f.size, None)

    def settle(self, now_ts: int | None = None) -> None:
        """Pay out lots in markets that have resolved (by now_ts, and before end_ts)."""
        for lot in self.lots:
            if lot.closed:
                continue
            m = self.markets.get(lot.condition_id)
            if not (m and m.resolved and m.end_time is not None):
                continue
            if self.end_ts is not None and m.end_time >= self.end_ts:
                continue
            if now_ts is not None and m.end_time > now_ts:
                continue
            lot.proceeds += lot.open_shares * m.payouts.get(lot.token_id, 0.0)
            lot.open_shares = 0.0
            lot.close_ts = max(m.end_time, lot.ts)

    # ---- internals ---------------------------------------------------------

    def _skip(self, f: Fill, token: str, side: str, reason: str) -> None:
        m = self.markets.get(f.condition_id)
        self.skips.append(Skip(f.tx_hash, token, f.condition_id, m.category if m else "unknown",
                               side, f.ts, f.price, reason))

    def _buy(self, f: Fill) -> None:
        p = self.policy
        self.wallet_shares[f.token_id] = self.wallet_shares.get(f.token_id, 0.0) + f.size
        if f.ts < self.start_ts:
            return
        m = self.markets.get(f.condition_id)
        if m is None:
            return self._skip(f, f.token_id, "BUY", "no_market_data")
        if p.is_mirror and f.size <= 0:
            return
        exec_ts = self.executor.exec_ts(f)
        if self.end_ts is not None and exec_ts >= self.end_ts:
            return
        if not p.is_mirror:
            if p.max_signal_age_s is not None and exec_ts - f.ts > p.max_signal_age_s:
                return self._skip(f, f.token_id, "BUY", "stale_signal")
            if m.resolved_by(exec_ts):
                return self._skip(f, f.token_id, "BUY", "resolved_before_entry")
        usd = p.stake(f)
        if usd < p.min_order_usd:
            return self._skip(f, f.token_id, "BUY", "below_min_order")
        if p.max_open_usd is not None and self.open_exposure() + usd > p.max_open_usd:
            return self._skip(f, f.token_id, "BUY", "risk_max_open")
        if p.max_market_usd is not None and self.open_exposure(f.condition_id) + usd > p.max_market_usd:
            return self._skip(f, f.token_id, "BUY", "risk_max_market")

        res = self.executor.buy(OrderRequest(f, m, "BUY", f.token_id, exec_ts, usd=usd,
                                             limit_price=p.max_copy_price, wallet_price=f.price))
        if isinstance(res, str):
            return self._skip(f, f.token_id, "BUY", res)
        lot = Lot(f.tx_hash, f.token_id, f.condition_id, m.category, f.ts, f.price, res.ref_price,
                  res.price, res.shares, res.usdc, res.fee, open_shares=res.shares, exec_ts=res.ts)
        self.lots.append(lot)
        self.open_lots.setdefault(f.token_id, []).append(lot)

    def _sell(self, f: Fill, token: str, size: float, wallet_price: float | None) -> None:
        held = self.wallet_shares.get(token, 0.0)
        self.wallet_shares[token] = max(0.0, held - size)
        mine = [lot for lot in self.open_lots.get(token, []) if not lot.closed]
        if not mine or held <= EPS or size <= EPS:  # zero-size exits (seen on real merges) sell nothing
            return
        frac = min(1.0, size / held)
        m = self.markets.get(f.condition_id)
        exec_ts = self.executor.exec_ts(f)
        if self.end_ts is not None and exec_ts >= self.end_ts:
            return
        if m is None or (not self.policy.is_mirror and m.resolved_by(exec_ts)):
            return  # too late to sell; the copy rides to resolution
        portions = [lot.open_shares * frac for lot in mine]
        total = sum(portions)
        est_price = wallet_price if wallet_price is not None else 0.5
        if total * est_price < self.policy.min_order_usd:
            return self._skip(f, token, "SELL", "below_min_order")  # position rides to resolution
        res = self.executor.sell(OrderRequest(f, m, "SELL", token, exec_ts, shares=total,
                                              limit_price=self.policy.min_sell_price, wallet_price=wallet_price))
        if isinstance(res, str):
            return self._skip(f, token, "SELL", res)
        sold = min(res.shares, total)
        for lot, portion in zip(mine, portions):
            share = portion / total
            lot.proceeds += res.usdc * share
            lot.fees += res.fee * share
            lot.open_shares -= portion * sold / total
            if lot.closed:
                lot.open_shares = 0.0
                lot.close_ts = res.ts

    def open_exposure(self, condition_id: str | None = None) -> float:
        """Cost basis still at risk in open lots."""
        return sum(lot.stake * lot.open_shares / lot.shares for lot in self.lots
                   if not lot.closed and lot.shares > 0
                   and (condition_id is None or lot.condition_id == condition_id))


class MirrorExecutor:
    """The wallet's own fills at their real cost; used to measure the wallet's ROI on the same basis."""

    def exec_ts(self, fill: Fill) -> int:
        return fill.ts

    def buy(self, req: OrderRequest) -> Execution:
        f = req.fill
        return Execution(f.ts, f.price, f.size, f.usdc_size, 0.0)

    def sell(self, req: OrderRequest) -> Execution:
        f = req.fill
        per_share = f.usdc_size / f.size if f.size > 0 else 0.0
        if f.side == "MERGE":  # $1 per pair, split across the market's outcomes
            per_share /= max(1, len(req.market.token_ids))
        return Execution(f.ts, per_share, req.shares, req.shares * per_share, 0.0)
