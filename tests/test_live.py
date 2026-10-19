"""Paper / live trading: same engine as the backtest, restart-safe, paper and live executors interchangeable."""
import time

import pytest

from polybt import db, filter as filter_mod, ingest, simulate
from polybt.config import load
from polybt.engine import CopyEngine, Fill, Market, Policy
from polybt.fees import FeeParams
from polybt.live import (JournaledExecutor, Journal, LiveExecutor, PaperExecutor, ReplayAPI, ReplayClock, Runner,
                         replay, walk_book)
from polybt.simulate import BacktestExecutor, SimParams, load_fills, load_markets, load_prices

from test_pipeline import FakeAPI

T0 = 1_700_000_000


# ---- order book ----------------------------------------------------------

def test_walk_book_buy_and_sell():
    asks = [(0.50, 10), (0.52, 10), (0.60, 100)]
    assert walk_book(asks, usd=5, limit=0.97, buying=True) == [(0.50, 10)]
    taken = walk_book(asks, usd=10, limit=0.97, buying=True)
    assert taken[0] == (0.50, 10) and taken[1][0] == 0.52 and taken[1][1] == pytest.approx(5 / 0.52)
    assert walk_book(asks, usd=100, limit=0.55, buying=True) is None          # fill-or-kill under the cap
    bids = [(0.48, 5), (0.40, 5)]
    assert walk_book(bids, shares=8, limit=0.0, buying=False) == [(0.48, 5), (0.40, 3)]
    assert walk_book(bids, shares=20, limit=0.0, buying=False) is None


class FakeBookAPI:
    def __init__(self, books):
        self.books = books

    def book(self, token_id):
        return self.books[token_id]


class BookOrderClient:
    """A fake exchange that fills market orders by walking the same book. Stands in for the CLOB."""

    def __init__(self, api, fees: FeeParams):
        self.api, self.fees, self.orders = api, fees, []

    def market_buy(self, token_id, usd, worst_price):
        self.orders.append(("BUY", token_id, usd, worst_price))
        taken = walk_book(self.api.book(token_id)["asks"], usd=usd, limit=worst_price, buying=True)
        if taken is None:
            return "order_rejected: FOK"
        shares = sum(s - (s - self.fees.buy(s, p)[0]) for p, s in taken)
        return {"usdc": usd, "shares": shares, "order_id": "x"}

    def market_sell(self, token_id, shares, worst_price):
        self.orders.append(("SELL", token_id, shares, worst_price))
        taken = walk_book(self.api.book(token_id)["bids"], shares=shares, limit=worst_price, buying=False)
        return {"usdc": sum(self.fees.sell(s, p)[0] for p, s in taken), "shares": shares, "order_id": "y"}


def _market(fees=FeeParams(0.07)):
    return {"c": Market("c", "other", 1e6, True, T0 + 86400, {"y": 1.0, "n": 0.0}, fees, ["y", "n"])}


def test_paper_fill_walks_book_and_charges_fees_per_level():
    api = FakeBookAPI({"y": {"bids": [(0.49, 100)], "asks": [(0.50, 10), (0.52, 100)]}})
    ex = PaperExecutor(api, SimParams(), clock=lambda: T0 + 7)
    eng = CopyEngine(_market(), ex, Policy(), T0)
    eng.on_fill(Fill(T0, "y", "c", "BUY", 0.50, 100, 50, "t1"))
    (lot,) = eng.lots
    gross = 10 + 5 / 0.52
    fee = round(10 * 0.07 * 0.5 * 0.5, 4) + round(5 / 0.52 * 0.07 * 0.52 * 0.48, 4)
    assert lot.stake == 10 and lot.entry_price == pytest.approx(10 / gross)
    assert lot.fees == pytest.approx(fee, abs=1e-4)
    assert lot.exec_ts == T0 + 7


def test_paper_and_live_executors_produce_identical_portfolios():
    """1:1: the same fills against the same book give the same lots whether paper or live."""
    books = FakeBookAPI({"y": {"bids": [(0.60, 30), (0.55, 100)], "asks": [(0.50, 10), (0.52, 100)]}})
    fills = [Fill(T0, "y", "c", "BUY", 0.50, 100, 50, "t1"), Fill(T0 + 60, "y", "c", "BUY", 0.51, 50, 25.5, "t2"),
             Fill(T0 + 600, "y", "c", "SELL", 0.61, 75, 45.75, "t3")]
    clock = lambda: T0 + 1000
    paper = CopyEngine(_market(), PaperExecutor(books, SimParams(), clock), Policy(), T0)
    client = BookOrderClient(books, FeeParams(0.07))
    live = CopyEngine(_market(), LiveExecutor(client, books, SimParams(), clock), Policy(), T0)
    for f in fills:
        paper.on_fill(f)
        live.on_fill(f)
    assert len(client.orders) == 3
    for a, b in zip(paper.lots, live.lots):
        assert (a.shares, a.stake, a.open_shares) == pytest.approx((b.shares, b.stake, b.open_shares))
        assert a.proceeds == pytest.approx(b.proceeds, abs=1e-3)


def test_fok_rejection_and_price_cap_are_skips():
    books = FakeBookAPI({"y": {"bids": [], "asks": [(0.98, 1000)]}})
    eng = CopyEngine(_market(), PaperExecutor(books, SimParams(), lambda: T0), Policy(), T0)
    eng.on_fill(Fill(T0, "y", "c", "BUY", 0.95, 10, 9.5, "t1"))
    assert eng.skips[0].reason == "price_above_max" and not eng.lots


# ---- runner == backtest --------------------------------------------------

@pytest.fixture(scope="module")
def history(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("live")
    cfg = load(overrides={"db_path": str(tmp / "t.duckdb"), "output_dir": str(tmp / "out"),
                          "discovery": {"active_in_markets": {"enabled": False},
                                        "leaderboard": {"queries": [{"category": "OVERALL"}], "pages": 1}}})
    con = db.connect(cfg["db_path"])
    api = FakeAPI(int(time.time()))
    wallets = ingest.run(con, api, cfg)
    passed = filter_mod.run(con, cfg, wallets)
    ingest.ingest_prices(con, api, cfg, passed, cfg.cutoff_ts)
    # Give every market a fee so parity covers the fee path too.
    con.execute("UPDATE markets SET fee_rate = 0.05, fee_exponent = 1")
    return con, cfg, passed[0]


def _backtest(con, cfg, wallet, delay):
    fills = load_fills(con, wallet)
    markets = load_markets(con, cfg["fees"]["formula"])
    params = SimParams.from_cfg(cfg)
    params.policy = Policy.from_cfg(cfg, "flat", simulate.size_reference(con, wallet, cfg.selection_start_ts, cfg.cutoff_ts))
    return simulate.simulate(fills, markets, load_prices(con, {f.token_id for f in fills}), params, delay, cfg.cutoff_ts)


def _lot_tuple(lot):
    return (lot.tx_hash, round(lot.entry_price, 9), round(lot.shares, 9), round(lot.proceeds, 9), lot.close_ts)


def test_runner_reproduces_backtest_exactly(history):
    con, cfg, wallet = history
    delay = 60
    lots, skips = _backtest(con, cfg, wallet, delay)
    prices = load_prices(con, {f.token_id for f in load_fills(con, wallet)})
    params = SimParams.from_cfg(cfg)
    runner = replay(con, cfg, [wallet], cfg.cutoff_ts, lambda: BacktestExecutor(prices, params, delay), "parity")
    live_lots = runner.engines[wallet].lots
    assert len(lots) > 50
    sold = [l for l in lots if l.close_ts is not None and l.proceeds > 0 and l.close_ts < l.ts + 86400]
    assert sold, "parity must cover exits, not only holds to resolution"
    assert sorted(map(_lot_tuple, live_lots)) == sorted(map(_lot_tuple, lots))
    assert sorted(s.reason for s in runner.engines[wallet].skips) == sorted(s.reason for s in skips)
    stored = con.execute("SELECT count(*), sum(pnl) FROM live_lots WHERE session = 'parity' AND status = 'closed'").fetchone()
    assert stored[0] == sum(l.closed for l in lots)
    assert stored[1] == pytest.approx(sum(l.pnl for l in lots if l.closed))


def test_restart_replays_journal_and_never_resends(history):
    con, cfg, wallet = history
    prices = load_prices(con, {f.token_id for f in load_fills(con, wallet)})
    params = SimParams.from_cfg(cfg)
    make = lambda: BacktestExecutor(prices, params, 60)

    # First run: stop halfway through the test period.
    clock = ReplayClock(cfg.cutoff_ts)
    api = ReplayAPI(con, clock)
    r1 = Runner(con, cfg, api, make, "restart", "replay", [wallet], clock=clock)
    r1.last_resolution_check = float("inf")
    r1.bootstrap()
    halfway = cfg.cutoff_ts + (int(time.time()) - cfg.cutoff_ts) // 2
    while (nxt := api.next_event_after([wallet], clock.t)) is not None and nxt < halfway:
        clock.t = max(nxt, clock.t + 5)
        r1.poll_once()
    sent_first = r1.executors[wallet].sent
    assert sent_first > 0

    # "Crash" and restart: a new runner on the same session rebuilds from the journal.
    r2 = Runner(con, cfg, api, make, "restart", "replay", [wallet], clock=clock)
    r2.last_resolution_check = float("inf")
    r2.bootstrap()
    assert r2.executors[wallet].sent == 0  # nothing re-sent
    assert sorted(map(_lot_tuple, r2.engines[wallet].lots)) == sorted(map(_lot_tuple, r1.engines[wallet].lots))
    while (nxt := api.next_event_after([wallet], clock.t)) is not None:
        clock.t = max(nxt, clock.t + 5)
        r2.poll_once()
    for e in r2.engines.values():
        e.settle()

    lots, _ = _backtest(con, cfg, wallet, 60)
    assert sorted(map(_lot_tuple, r2.engines[wallet].lots)) == sorted(map(_lot_tuple, lots))
    # Exactly one journal entry per executor call across both runs: nothing was sent twice.
    executed = con.execute("""SELECT count(*) FROM live_orders WHERE session = 'restart'
                              AND (status = 'filled' OR reason IN ('no_price_history', 'price_above_max'))""").fetchone()[0]
    assert executed == sent_first + r2.executors[wallet].sent


class LiveFeedAPI:
    """Simulated Polymarket: wallet activity appears over time; books are static."""

    def __init__(self, clock, books, markets):
        self.clock, self.books, self.markets, self.feed = clock, books, markets, []

    def activity(self, user, start, end=None, live=False):
        return [r for r in self.feed if r["ts_user"] == user and start <= r["timestamp"] <= self.clock()]

    def book(self, token_id):
        return self.books[token_id]

    def markets_by_condition(self, ids, live=False):
        return [self.markets[i] for i in ids if i in self.markets]

    def clob_market_info(self, cid):
        return {"fd": {"r": 0.07, "e": 1, "to": True}}


def test_paper_session_end_to_end_with_restart(tmp_path):
    cfg = load(overrides={"db_path": str(tmp_path / "p.duckdb")})
    con = db.connect(cfg["db_path"])
    clock = ReplayClock(T0)
    gamma = {"conditionId": "c", "question": "Will it rain?", "slug": "rain", "clobTokenIds": '["y","n"]',
             "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]', "closed": False, "volumeNum": 1e6,
             "endDate": "2030-01-01T00:00:00Z"}
    api = LiveFeedAPI(clock, {"y": {"bids": [(0.48, 1000)], "asks": [(0.50, 1000)]}}, {"c": gamma})
    make = lambda: PaperExecutor(api, SimParams.from_cfg(cfg), clock)

    r = Runner(con, cfg, api, make, "paper-test", "paper", ["0xw"], clock=clock)
    r.bootstrap()
    api.feed.append({"ts_user": "0xw", "type": "TRADE", "side": "BUY", "asset": "y", "conditionId": "c",
                     "price": 0.49, "size": 100, "usdcSize": 49, "timestamp": T0 + 10, "transactionHash": "a"})
    clock.t = T0 + 13
    assert r.poll_once() == 1
    assert r.poll_once() == 0  # the same activity row again is not a new signal
    (lot,) = r.engines["0xw"].lots
    assert lot.entry_price == 0.50 and lot.exec_ts == T0 + 13
    assert r.markets["c"].fees.rate == 0.07  # the new market's own fee parameters were fetched
    latency, model = con.execute(
        "SELECT seen_ts - signal_ts, model_price FROM live_orders WHERE session = 'paper-test'").fetchone()
    assert latency == 3 and model == pytest.approx(0.50)  # backtest model: max(0.49, mid 0.49) + 1c

    # Restart: the new runner rebuilds the position from the journal and sends nothing.
    clock.t = T0 + 30
    r2 = Runner(con, cfg, api, make, "paper-test", "paper", ["0xw"], clock=clock)
    r2.bootstrap()
    assert r2.executors["0xw"].sent == 0
    assert [l.shares for l in r2.engines["0xw"].lots] == [lot.shares]

    # The wallet exits; the copy follows into the bid.
    api.feed.append({"ts_user": "0xw", "type": "TRADE", "side": "SELL", "asset": "y", "conditionId": "c",
                     "price": 0.48, "size": 100, "usdcSize": 48, "timestamp": T0 + 40, "transactionHash": "b"})
    clock.t = T0 + 42
    assert r2.poll_once() == 1
    (lot2,) = r2.engines["0xw"].lots
    assert lot2.closed and lot2.proceeds == pytest.approx(lot2.shares * 0.48 - round(lot2.shares * 0.07 * 0.48 * 0.52, 4))
    r2.snapshot()
    assert con.execute("SELECT status FROM live_lots WHERE session = 'paper-test'").fetchone()[0] == "closed"
