"""Polymarket taker fees, shared by the backtest, paper and live executors.

Polymarket charges takers only (makers pay nothing). Per the fee docs:

    fee_usdc = C * rate * p * (1 - p)                      formula "v2" (current, simplified)
    fee_usdc = C * p * rate * (p * (1 - p)) ** exponent    formula "v1" (pre-July 2026 docs)

where C is shares filled and p the fill price. The fee is computed in USDC, rounded to 4 decimal
places (anything under 0.0001 is free), and collected in *shares* on buys and in USDC on sells.

Each market's own parameters (rate, exponent, taker-only) come from the CLOB's market info
(`GET /clob-markets/{condition_id}` -> `fd: {r, e, to}`), which is what actually governs; the
category table in config.yaml is only the fallback for markets without it. Use
`python -m polybt fees` to check which formula matches the wallets' real fills.
"""
from __future__ import annotations

from dataclasses import dataclass

FEE_DECIMALS = 4


@dataclass(frozen=True)
class FeeParams:
    rate: float = 0.0
    exponent: float = 1.0
    taker_only: bool = True
    formula: str = "v2"

    def fee_usdc(self, shares: float, price: float) -> float:
        """Taker fee in USDC for `shares` filled at `price`."""
        if self.rate <= 0 or shares <= 0 or not 0 < price < 1:
            return 0.0
        if self.formula == "v1":
            fee = shares * price * self.rate * (price * (1 - price)) ** self.exponent
        else:
            fee = shares * self.rate * price * (1 - price)
        return round(fee, FEE_DECIMALS)

    def buy(self, shares: float, price: float) -> tuple[float, float]:
        """(net shares received, fee in USDC). The fee is taken out of the shares."""
        fee = self.fee_usdc(shares, price)
        return shares - fee / price if fee else shares, fee

    def sell(self, shares: float, price: float) -> tuple[float, float]:
        """(net USDC received, fee in USDC)."""
        fee = self.fee_usdc(shares, price)
        return shares * price - fee, fee


ZERO = FeeParams()


def from_market_info(info: dict | None, formula: str) -> FeeParams | None:
    """FeeParams from a CLOB market-info response, or None if it carries no fee details."""
    fd = (info or {}).get("fd")
    if not isinstance(fd, dict) or fd.get("r") is None:
        return None
    try:
        return FeeParams(rate=float(fd["r"]), exponent=float(fd.get("e") or 1.0),
                         taker_only=bool(fd.get("to", True)), formula=formula)
    except (TypeError, ValueError):
        return None


def category_fallback(cfg: dict, fee_category: str | None) -> FeeParams:
    fc = cfg["fees"]
    rates = fc["category_rates"]
    rate = rates.get(fee_category or "", rates.get("default", 0.0))
    return FeeParams(rate=float(rate), exponent=float(fc.get("exponent", 1.0)), formula=fc["formula"])


def calibrate(con, since_ts: int, exponent_default: float = 1.0, tolerance: float = 0.15) -> dict:
    """Which formula explains the wallets' real fills?

    For each stored trade in a fee-bearing market, the fee implied by the Data API is
    |usdcSize - price * size|. It is compared with what v1 and v2 predict. Maker fills and fee-free
    trades imply ~0, so the useful signal is the share of non-zero implied fees each formula matches.
    """
    rows = con.execute("""
        SELECT t.price, t.size, t.usdc_size, m.fee_rate, coalesce(m.fee_exponent, ?)
        FROM wallet_trades t JOIN markets m USING (condition_id)
        WHERE t.type = 'TRADE' AND t.timestamp >= ? AND m.fee_rate > 0
          AND t.usdc_size IS NOT NULL AND t.price > 0 AND t.price < 1 AND t.size > 0
    """, [exponent_default, since_ts]).fetchall()
    out = {"trades": len(rows), "zero_fee": 0, "charged": 0, "v1": 0, "v2": 0, "neither": 0}
    for price, size, usdc, rate, exponent in rows:
        implied = abs(usdc - price * size)
        if implied < 0.0002:
            out["zero_fee"] += 1
            continue
        out["charged"] += 1
        hit = False
        for formula in ("v1", "v2"):
            pred = FeeParams(rate, exponent, formula=formula).fee_usdc(size, price)
            if pred > 0 and abs(implied - pred) <= max(0.0002, tolerance * pred):
                out[formula] += 1
                hit = True
        out["neither"] += not hit
    return out
