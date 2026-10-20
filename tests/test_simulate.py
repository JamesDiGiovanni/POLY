import pytest

from polybt.fees import FeeParams
from polybt.simulate import (Fill, Market, PriceSeries, SimParams, copy_buy_price, copy_sell_price, simulate)

T0 = 1_700_000_000
CID, YES, NO = "c1", "yes", "no"


def market(**kw):
    base = dict(condition_id=CID, category="other", volume=1e6, resolved=True, end_time=T0 + 86400,
                payouts={YES: 1.0, NO: 0.0})
    base.update(kw)
    return {CID: Market(**base)}


def buy(ts, price, size=100, token=YES):
    return Fill(ts, token, CID, "BUY", price, size, price * size, f"b{ts}")


def sell(ts, price, size=100, token=YES):
    return Fill(ts, token, CID, "SELL", price, size, price * size, f"s{ts}")


# ---- fill price model (hand-built cases) ---------------------------------

@pytest.mark.parametrize("wallet,market_price,spread,expected", [
    (0.50, 0.55, 0.01, 0.56),   # market moved against us: pay the market plus spread
    (0.50, 0.45, 0.01, 0.51),   # market moved in our favour: never better than the wallet
    (0.50, 0.50, 0.02, 0.52),   # low-volume spread
])
def test_copy_buy_price(wallet, market_price, spread, expected):
    assert copy_buy_price(wallet, market_price, spread) == pytest.approx(expected)


@pytest.mark.parametrize("wallet,market_price,spread,expected", [
    (0.70, 0.65, 0.01, 0.64),
    (0.70, 0.75, 0.01, 0.69),
    (0.005, 0.01, 0.01, 0.0),   # floored at zero
])
def test_copy_sell_price(wallet, market_price, spread, expected):
    assert copy_sell_price(wallet, market_price, spread) == pytest.approx(expected)


def test_spread_by_volume():
    p = SimParams()
    assert p.spread(market(volume=10_000)[CID]) == 0.02
    assert p.spread(market(volume=50_000)[CID]) == 0.01
    assert p.spread(market(volume=None)[CID]) == 0.01


# ---- price lookup --------------------------------------------------------

def test_price_at_uses_latest_observation_after_fill():
    s = PriceSeries([T0 - 60, T0 + 60, T0 + 120, T0 + 400], [0.40, 0.52, 0.55, 0.60])
    assert s.at(T0, 0.50, T0 + 300) == 0.55
    assert s.at(T0, 0.50, T0 + 60) == 0.52


def test_price_at_interpolates_sub_minute_delay_from_wallet_fill():
    s = PriceSeries([T0 - 30, T0 + 60], [0.40, 0.56])
    # 10 s into a 60 s gap between the wallet's 0.50 fill and the next 0.56 print
    assert s.at(T0, 0.50, T0 + 10) == pytest.approx(0.51)


def test_price_at_falls_back_to_wallet_price_without_later_data():
    s = PriceSeries([T0 - 60], [0.40])
    assert s.at(T0, 0.50, T0 + 60) == 0.50
    assert PriceSeries([], []).at(T0, 0.5, T0 + 60) is None


# ---- engine --------------------------------------------------------------

def test_hold_to_resolution_win():
    prices = {YES: PriceSeries([T0 + 60], [0.55])}
    lots, skips = simulate([buy(T0, 0.50)], market(), prices, SimParams(), 60, T0)
    assert not skips
    (lot,) = lots
    assert lot.entry_price == pytest.approx(0.56)
    assert lot.shares == pytest.approx(10 / 0.56)
    assert lot.closed and lot.close_ts == T0 + 86400
    assert lot.pnl == pytest.approx(10 / 0.56 - 10)


def test_hold_to_resolution_loss():
    lots, _ = simulate([buy(T0, 0.50, token=NO)], market(), {NO: PriceSeries([T0 + 60], [0.5])},
                       SimParams(), 60, T0)
    assert lots[0].pnl == pytest.approx(-10)


def test_partial_then_full_exit_copies_fraction_at_delay():
    prices = {YES: PriceSeries([T0 + 60, T0 + 1060, T0 + 2060], [0.50, 0.70, 0.80])}
    fills = [buy(T0, 0.50, 100), sell(T0 + 1000, 0.72, 50), sell(T0 + 2000, 0.81, 50)]
    lots, _ = simulate(fills, market(), prices, SimParams(), 60, T0)
    (lot,) = lots
    shares = 10 / 0.51
    # first exit: half at min(0.72, 0.70) - 0.01; second: rest at min(0.81, 0.80) - 0.01
    assert lot.proceeds == pytest.approx(shares / 2 * 0.69 + shares / 2 * 0.79)
    assert lot.close_ts == T0 + 2060


def test_fees_taken_in_shares_on_buy_and_usdc_on_sell():
    prices = {YES: PriceSeries([T0 + 60, T0 + 1060], [0.50, 0.70])}
    m = market(fees=FeeParams(rate=0.07))
    lots, _ = simulate([buy(T0, 0.50), sell(T0 + 1000, 0.70)], m, prices, SimParams(), 60, T0)
    (lot,) = lots
    gross = 10 / 0.51
    buy_fee = round(gross * 0.07 * 0.51 * 0.49, 4)
    assert lot.stake == 10
    assert lot.shares == pytest.approx(gross - buy_fee / 0.51)
    sell_fee = round(lot.shares * 0.07 * 0.69 * 0.31, 4)
    assert lot.proceeds == pytest.approx(lot.shares * 0.69 - sell_fee)
    assert lot.fees == pytest.approx(buy_fee + sell_fee)


def test_fee_formulas_and_rounding():
    v2, v1 = FeeParams(0.07), FeeParams(0.072, exponent=1, formula="v1")
    assert v2.fee_usdc(100, 0.5) == pytest.approx(1.75)        # $1.75 per 100 shares at 50c
    assert v1.fee_usdc(200, 0.5) == pytest.approx(1.80)        # 1.80% of a $100 fill at 50c
    assert FeeParams(0.25, 2, formula="v1").fee_usdc(200, 0.5) == pytest.approx(1.5625)  # old 15m crypto
    assert v2.fee_usdc(0.001, 0.5) == 0.0                       # under 0.0001 USDC rounds to free
    assert FeeParams(0.0).fee_usdc(100, 0.5) == 0.0
    shares, fee = v2.sell(100, 0.5)
    assert (shares, fee) == (pytest.approx(48.25), 1.75)


def test_skip_reasons():
    prices = {YES: PriceSeries([T0 + 60], [0.97])}
    m = market()
    lots, skips = simulate([buy(T0, 0.96)], m, prices, SimParams(), 60, T0)
    assert not lots and skips[0].reason == "price_above_max"

    early = market(end_time=T0 + 30)
    _, skips = simulate([buy(T0, 0.5)], early, prices, SimParams(), 60, T0)
    assert skips[0].reason == "resolved_before_entry"

    _, skips = simulate([buy(T0, 0.5)], m, {}, SimParams(), 60, T0)
    assert skips[0].reason == "no_price_history"

    _, skips = simulate([buy(T0, 0.5)], {}, prices, SimParams(), 60, T0)
    assert skips[0].reason == "no_market_data"


def test_sell_after_resolution_rides_to_payout():
    m = market(end_time=T0 + 1000)
    prices = {YES: PriceSeries([T0 + 60], [0.5])}
    lots, _ = simulate([buy(T0, 0.5), sell(T0 + 990, 0.99)], m, prices, SimParams(), 60, T0)
    assert lots[0].proceeds == pytest.approx(10 / 0.51)  # paid out at $1, not sold at 0.99 - spread


def test_pre_window_buys_only_set_sell_fraction():
    prices = {YES: PriceSeries([T0 + 60, T0 + 1060], [0.5, 0.6])}
    fills = [buy(T0 - 5000, 0.4, 100), buy(T0, 0.5, 100), sell(T0 + 1000, 0.6, 100)]
    lots, _ = simulate(fills, market(), prices, SimParams(), 60, T0)
    (lot,) = lots
    assert lot.open_shares == 0.0  # settled at resolution after selling half
    assert lot.proceeds == pytest.approx(lot.shares / 2 * 0.59 + lot.shares / 2 * 1.0)


def test_unresolved_market_leaves_lot_open():
    m = market(resolved=False, end_time=None)
    lots, _ = simulate([buy(T0, 0.5)], m, {YES: PriceSeries([T0 + 60], [0.5])}, SimParams(), 60, T0)
    assert not lots[0].closed


def test_wallet_mode_uses_real_cost_and_ignores_delay():
    fills = [Fill(T0, YES, CID, "BUY", 0.5, 100, 50.5, "b"), Fill(T0 + 100, YES, CID, "SELL", 0.7, 100, 69.5, "s")]
    lots, skips = simulate(fills, market(), {}, SimParams(), 0, T0, mode="wallet")
    assert not skips
    assert lots[0].stake == 50.5 and lots[0].proceeds == pytest.approx(69.5)


def test_end_ts_excludes_later_exits_and_resolutions():
    fills = [buy(T0, 0.5)]
    lots, _ = simulate(fills, market(), {}, SimParams(), 0, T0, end_ts=T0 + 1000, mode="wallet")
    assert not lots[0].closed  # resolves after end_ts: no lookahead


def test_merge_exits_copies_at_market():
    from polybt.engine import CopyEngine, Policy
    from polybt.simulate import BacktestExecutor
    m = market()
    m[CID].token_ids = [YES, NO]
    prices = {YES: PriceSeries([T0 + 60, T0 + 1060], [0.50, 0.70])}
    fills = [buy(T0, 0.50), buy(T0 + 1, 0.50, token=NO),
             Fill(T0 + 1000, "", CID, "MERGE", 0.0, 100, 100, "m1")]
    eng = CopyEngine(m, BacktestExecutor(prices, SimParams(), 60), Policy(), T0)
    for f in fills:
        eng.on_fill(f)
    yes_lot = eng.lots[0]
    assert yes_lot.closed and yes_lot.proceeds == pytest.approx(yes_lot.shares * 0.69)  # market 0.70 - spread
    no_skip = [s for s in eng.skips if s.token_id == NO]
    assert no_skip and no_skip[0].reason == "no_price_history"  # NO side had no prices: rides to resolution


def test_proportional_sizing_and_risk_limits():
    from polybt.engine import CopyEngine, Policy
    from polybt.simulate import BacktestExecutor
    prices = {YES: PriceSeries([T0 + 60], [0.50])}
    pol = Policy(sizing="proportional", size_ref_usd=50, max_stake_multiple=3, max_open_usd=40)
    eng = CopyEngine(market(), BacktestExecutor(prices, SimParams(), 60), pol, T0)
    for i, usd in enumerate((25, 100, 500, 10)):
        eng.on_fill(Fill(T0 + i, YES, CID, "BUY", 0.5, usd / 0.5, usd, f"b{i}"))
    assert [l.stake for l in eng.lots] == [5, 20, 2]           # 0.5x, 2x, (3x capped at $30: over limit), 0.2x
    assert [s.reason for s in eng.skips] == ["risk_max_open"]


def test_stale_signal_and_min_order():
    from polybt.engine import CopyEngine, Policy
    from polybt.simulate import BacktestExecutor
    prices = {YES: PriceSeries([T0 + 60], [0.50])}
    eng = CopyEngine(market(), BacktestExecutor(prices, SimParams(), 900), Policy(max_signal_age_s=600), T0)
    eng.on_fill(buy(T0, 0.5))
    assert eng.skips[0].reason == "stale_signal"
    eng = CopyEngine(market(), BacktestExecutor(prices, SimParams(), 60), Policy(stake_usd=0.5), T0)
    eng.on_fill(buy(T0, 0.5))
    assert eng.skips[0].reason == "below_min_order"


def test_zero_size_exit_is_ignored():
    from polybt.engine import CopyEngine, MirrorExecutor, Policy
    m = market()
    m[CID].token_ids = [YES, NO]
    fills = [buy(T0, 0.5), Fill(T0 + 10, "", CID, "MERGE", 0.0, 0.0, 0.0, "m0"), sell(T0 + 20, 0.6, 0)]
    eng = CopyEngine(m, MirrorExecutor(), Policy.mirror(), T0)
    for f in fills:
        eng.on_fill(f)  # used to raise ZeroDivisionError
    assert eng.lots[0].open_shares == 100
