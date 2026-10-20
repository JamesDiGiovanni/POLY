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


def test_bootstrap_resamples_markets_not_fills():
    # 300 fills in 3 markets: one big loser, two winners. Per-fill resampling would give a narrow
    # interval; per-market resampling must admit the losing outcome.
    fills = []
    for m, p in (("a", 6.0), ("b", 6.0), ("c", -9.0)):
        fills += [LotRow(T0, T0, 0.5, 10.0, p, m) for _ in range(100)]
    lo, hi = bootstrap_roi_ci(fills, 2000, 0.9, 7)
    naive = bootstrap_roi_ci([LotRow(l.ts, l.close_ts, l.entry, l.stake, l.pnl) for l in fills], 2000, 0.9, 7)
    assert lo < 0 < hi
    assert naive[0] > 0  # what the old per-fill bootstrap would have claimed


def test_monthly_positive():
    end = T0 + 90 * DAY
    ls = [LotRow(0, T0 + 5 * DAY, .5, 10, -1), LotRow(0, T0 + 70 * DAY, .5, 10, 2)]
    assert monthly_positive(ls, end, 3, 30) == [False, None, True]


def test_svg_renders_with_missing_points():
    svg = edge_decay_svg([{"copy_roi": 0.1, "ci_low": 0.0, "ci_high": 0.2, "trades": 5, "delay_label": "10s"},
                          {"copy_roi": None, "ci_low": None, "ci_high": None, "trades": 0, "delay_label": "1m"}], 0.15)
    assert svg.startswith("<svg") and "Wallet ROI" in svg


def test_specialist_qualifies_in_its_best_category_only():
    from polybt.filter import score_specialist
    cfg = load(overrides={"filters": {"specialist": True, "min_resolved_trades": 100, "min_median_trade_usd": 5}})
    good, gm = _history(150, win_every=3, price=0.25, spacing=DAY)   # wins 1 in 3 at 25c: profitable
    bad, bm = _history(150, win_every=5, price=0.5, spacing=DAY)     # wins 1 in 5 at 50c: loses
    for m in gm.values():
        m.fee_category = "politics"
    for f in bad:
        f.condition_id = "s" + f.condition_id
        f.token_id = "s" + f.token_id
    bm = {"s" + k: Market("s" + k, "other", 1e6, True, v.end_time, {"s" + t: p for t, p in v.payouts.items()},
                          fee_category="sports") for k, v in bm.items()}
    s = score_specialist(good + bad, {**gm, **bm}, cfg, T0 - DAY, T0 + 155 * DAY)
    assert s["passed"] and s["specialty"] == "politics" and s["resolved_trades"] == 150
    s = score_specialist(bad, bm, cfg, T0 - DAY, T0 + 155 * DAY)
    assert not s["passed"] and s["rejection_reason"].startswith("[sports]")
