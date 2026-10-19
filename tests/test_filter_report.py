import pytest

from polybt.config import load
from polybt.filter import score_wallet, wash_fraction
from polybt.report import LotRow, bootstrap_roi_ci, edge_decay_svg, max_drawdown, monthly_positive, roi
from polybt.simulate import Fill, Market

DAY = 86400
T0 = 1_700_000_000


def test_wash_fraction():
    fills = [Fill(T0, "yes", "c", "BUY", .5, 10, 5), Fill(T0 + 600, "no", "c", "BUY", .5, 10, 5),
             Fill(T0 + 10_000, "yes", "c2", "BUY", .5, 10, 5), Fill(T0 + 99_999, "no", "c2", "BUY", .5, 10, 5)]
    assert wash_fraction(fills, 3600) == pytest.approx(0.5)


def _history(n_markets, win_every, price=0.5, start=T0, spacing=DAY // 2, usd=50):
    """n buys, one per market, each resolving a day later; every win_every-th wins."""
    fills, markets = [], {}
    for i in range(n_markets):
        cid = f"c{i}"
        ts = start + i * spacing
        fills.append(Fill(ts, f"t{i}", cid, "BUY", price, usd / price, usd))
        won = i % win_every == 0
        markets[cid] = Market(cid, "other", 1e6, True, ts + DAY, {f"t{i}": 1.0 if won else 0.0})
    return fills, markets


def test_score_wallet_passes_good_history():
    cfg = load()
    fills, markets = _history(260, win_every=3, price=0.25)  # 1/3 wins bought at 25c
    start, cutoff = T0 - DAY, T0 + 140 * DAY
    s = score_wallet(fills, markets, cfg, start, cutoff)
    assert s["resolved_trades"] == 260
    assert s["roi"] == pytest.approx((87 * 200 - 260 * 50) / (260 * 50), rel=1e-6)
    assert s["edge_pts"] > 3
    assert s["passed"], s["rejection_reason"]


def test_score_wallet_logs_every_failed_filter():
    cfg = load()
    fills, markets = _history(50, win_every=2, price=0.85, usd=5)  # 50% wins at 85c, tiny
    s = score_wallet(fills, markets, cfg, T0 - DAY, T0 + 30 * DAY)
    assert not s["passed"]
    for key in ("resolved_trades", "active_span", "roi", "edge", "median_trade"):
        assert key in s["rejection_reason"]


def test_score_wallet_ignores_post_cutoff_resolutions():
    cfg = load()
    fills, markets = _history(10, win_every=1)
    s = score_wallet(fills, markets, cfg, T0 - DAY, T0 + 5 * DAY)  # cutoff before most resolve
    assert s["resolved_trades"] < 10


def test_profit_concentration():
    cfg = load()
    fills, markets = _history(260, win_every=100, price=0.01)  # 3 wins at 100x carry it all
    s = score_wallet(fills, markets, cfg, T0 - DAY, T0 + 140 * DAY)
    assert s["top3_share"] > 0.4 and "top3_profit_share" in s["rejection_reason"]


def lots(pnls, stake=10.0):
    return [LotRow(T0 + i, T0 + i, 0.5, stake, p) for i, p in enumerate(pnls)]


def test_roi_and_drawdown():
    ls = lots([5, -3, -4, 6, -1])
    assert roi(ls) == pytest.approx(3 / 50)
    assert max_drawdown(ls) == pytest.approx(7)


def test_bootstrap_is_deterministic_and_brackets_roi():
    ls = lots([10, -10, 5, -2, 8, -10, 3] * 20)
    a = bootstrap_roi_ci(ls, 1000, 0.9, 7)
    assert a == bootstrap_roi_ci(ls, 1000, 0.9, 7)
    assert a[0] < roi(ls) < a[1]
    assert bootstrap_roi_ci(lots([1]), 100, 0.9, 7) == (None, None)


def test_monthly_positive():
    end = T0 + 90 * DAY
    ls = [LotRow(0, T0 + 5 * DAY, .5, 10, -1), LotRow(0, T0 + 70 * DAY, .5, 10, 2)]
    assert monthly_positive(ls, end, 3, 30) == [False, None, True]


def test_svg_renders_with_missing_points():
    svg = edge_decay_svg([{"copy_roi": 0.1, "ci_low": 0.0, "ci_high": 0.2, "trades": 5, "delay_label": "10s"},
                          {"copy_roi": None, "ci_low": None, "ci_high": None, "trades": 0, "delay_label": "1m"}], 0.15)
    assert svg.startswith("<svg") and "Wallet ROI" in svg
