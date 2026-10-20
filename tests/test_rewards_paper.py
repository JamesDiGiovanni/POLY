import pytest

from polybt.config import load
from polybt.rewards.paper import MarketState, Quote, apply_print, quote_prices, report, step, summarise, write_session, yes_print

P = {**load()["rewards"], **load()["rewards"]["paper"]}
M = {"condition_id": "c", "question": "Q?", "daily_rate": 86.4, "min_size": 20, "max_spread": 0.04,
     "yes_token": "Y", "no_token": "N", "tick": 0.01}


def book(bid=0.40, ask=0.60, size=100):
    return {"bids": [(bid, size)], "asks": [(ask, size)]}


def pr(asset, side, price, size, ts, tx="t"):
    return {"asset": asset, "side": side, "price": price, "size": size, "timestamp": ts, "transactionHash": tx}


def test_no_prints_become_yes_prints_on_the_other_side():
    assert yes_print(pr("Y", "BUY", 0.6, 10, 5), "Y") == ("buy", 0.6, 10, 5)
    assert yes_print(pr("N", "BUY", 0.3, 10, 5), "Y") == ("sell", pytest.approx(0.7), 10, 5)
    assert yes_print(pr("N", "SELL", 0.3, 10, 5), "Y")[0] == "buy"


def test_queue_at_our_price_fills_after_the_size_ahead():
    q = Quote("bid", 0.48, 100, 0, queue_ahead=30)
    assert apply_print(q, "buy", 0.40, 50) == 0          # wrong side
    assert apply_print(q, "sell", 0.49, 50) == 0         # above our bid
    assert apply_print(q, "sell", 0.48, 50) == 20        # 30 ahead of us
    assert apply_print(q, "sell", 0.47, 500) == 80       # through: the rest
    assert q.size == 0


def test_quote_prices_round_inside_the_spread():
    assert quote_prices(0.50, 0.04, 0.5, 0.01) == (0.48, 0.52)
    assert quote_prices(0.505, 0.045, 0.5, 0.01) == (0.49, 0.52)


def test_session_fills_rewards_and_markouts():
    st = MarketState(dict(M), "empty")
    step(st, book(), [pr("Y", "BUY", 0.6, 5, 0, "old")], 1000.0, P)   # old print: no quotes yet
    assert st.fills == [] and set(st.quotes) == {"bid", "ask"} and st.share == 1.0   # nobody near the mid
    assert (st.quotes["bid"].price, st.quotes["ask"].price) == (0.48, 0.52)
    size = st.quotes["bid"].size
    # a taker sells NO at 0.45 = buys YES at 0.55: lifts our 0.52 ask
    step(st, book(0.40, 0.60), [pr("N", "SELL", 0.45, 200, 1030)], 1060.0, P)
    assert len(st.fills) == 1 and st.fills[0].side == "ask" and st.inv == -200
    assert st.rewards == pytest.approx(86.4 * 60 / 86400)                 # whole pool for one minute
    assert st.quotes["ask"].size == pytest.approx(size - 200)              # same price: keeps its place in the queue
    # mid moves up to 0.60 later: selling at 0.52 lost 8c a share
    for k in range(2, 40):
        step(st, book(0.58, 0.62), [], 1000.0 + 60 * k, P)
    s = summarise(st, [5, 30], 1000.0 + 60 * 39)
    assert s["markout_5m"] == pytest.approx(200 * (0.52 - 0.60))
    assert s["trading_pnl"] == pytest.approx(200 * 0.52 - 200 * 0.60)
    assert s["fills"] == 1 and s["rewards"] > 0
    # the jump to 0.60 went through the 0.52 ask still resting (size - 200): counted as picked off
    assert s["stale_loss"] == pytest.approx(0.08 * (size - 200))


def test_inventory_cap_stops_one_side():
    st = MarketState(dict(M), "medium")
    step(st, book(), [], 0.0, P)
    st.inv = 10 * st.quotes["bid"].size
    step(st, book(), [], 60.0, P)
    assert set(st.quotes) == {"ask"}


def test_report_aggregates_sessions(tmp_path):
    for name in ("s1", "s2"):
        st = MarketState(dict(M), "crowded")
        for k in range(3):
            step(st, book(), [], 60.0 * k, P)
        (tmp_path / name).mkdir()
        write_session(tmp_path / name, [st], P, 180.0)
    text = report(tmp_path, P)
    assert "2 sessions" in text and "| crowded |" in text
