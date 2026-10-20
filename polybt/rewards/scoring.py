"""Polymarket liquidity-rewards scoring (docs.polymarket.com, "Liquidity Rewards").

Each resting order within max_spread of the size-cutoff-adjusted midpoint scores
    S(v, s) = ((v - s) / v) ** 2 * size
where v is the market's max spread and s the order's distance from that midpoint (both in price units).
Q_one sums bids on YES (and asks on NO); Q_two sums asks on YES (and bids on NO). Polymarket mirrors the
two outcome books, so the YES book alone holds both. A maker's score is
    Q_min = max(min(Q_one, Q_two), max(Q_one, Q_two) / c)   if 0.10 <= mid <= 0.90
    Q_min = min(Q_one, Q_two)                                otherwise (both sides required)
sampled every minute; the day's reward pool is split in proportion to each maker's Q_min.
"""
from __future__ import annotations

SINGLE_SIDED_C = 3.0


def adjusted_mid(bids, asks, min_size: float) -> float | None:
    """Midpoint of the best bid and ask among orders of at least min_size."""
    b = [p for p, q in bids if q >= min_size]
    a = [p for p, q in asks if q >= min_size]
    if not b or not a:
        return None
    return (max(b) + min(a)) / 2


def side_score(levels, mid: float, max_spread: float, min_size: float) -> float:
    total = 0.0
    for p, q in levels:
        s = abs(p - mid)
        if q >= min_size and s < max_spread:
            total += ((max_spread - s) / max_spread) ** 2 * q
    return total


def q_min(q_one: float, q_two: float, mid: float, c: float = SINGLE_SIDED_C) -> float:
    if 0.10 <= mid <= 0.90:
        return max(min(q_one, q_two), max(q_one, q_two) / c)
    return min(q_one, q_two)


def book_score(bids, asks, max_spread: float, min_size: float) -> dict | None:
    """Score of everything resting on the book, treated as one maker (makers can't be told apart)."""
    mid = adjusted_mid(bids, asks, min_size)
    if mid is None:
        return None
    q1 = side_score(bids, mid, max_spread, min_size)
    q2 = side_score(asks, mid, max_spread, min_size)
    return {"mid": mid, "q_one": q1, "q_two": q2, "q_min": q_min(q1, q2, mid)}


def our_quote(capital: float, mid: float, max_spread: float, min_size: float, frac: float = 0.5) -> dict:
    """A two-sided quote at frac x max_spread from the mid: buy YES at mid - d and buy NO at 1 - (mid + d)
    (the mirror of selling YES at mid + d). Each pair of shares costs 1 - 2d, so capital buys Q of each."""
    d = frac * max_spread
    bid, ask = mid - d, mid + d
    if bid <= 0 or ask >= 1:
        return {"size": 0.0, "q_min": 0.0, "d": d}
    size = capital / (1 - 2 * d)
    if size < min_size:
        return {"size": size, "q_min": 0.0, "d": d}
    s = ((max_spread - d) / max_spread) ** 2 * size
    return {"size": size, "q_min": q_min(s, s, mid), "d": d}


def expected_daily(rate: float, ours: float, theirs: float, competition_mult: float = 1.0) -> float:
    """Our share of the day's pool if both sides held their scores all day."""
    if ours <= 0:
        return 0.0
    return rate * ours / (ours + competition_mult * theirs)
