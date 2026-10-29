import pytest

from polybt import db
from polybt.config import load
from polybt.longshot.backtest import Bet, bets_for_market, bucket_of, evaluate, price_at
from polybt.longshot.data import SCHEMA, market_row

DAY = 86400
END = 1_800_000_000
C = {**load()["longshot"], "horizons_days": [1, 7], "spread": 0.01, "fees": True}


def test_price_at_uses_last_print_and_rejects_stale():
    path = [(100, 0.1), (200, 0.2), (300, 0.3)]
    assert price_at(path, 250, 1000) == 0.2
    assert price_at(path, 50, 1000) is None
    assert price_at(path, 5000, 1000) is None


def test_bets_against_a_cheap_yes_buy_no_with_spread_and_fee():
    m = {"condition_id": "c", "event_id": "e", "question": "Q", "yes_won": 0.0, "scheduled_end": END, "closed_ts": END}
    path = [(END - 7 * DAY - 3600, 0.04), (END - DAY - 3600, 0.02)]
    bets = {b.horizon: b for b in bets_for_market(m, path, C, fee_rate=0.05)}
    b7 = bets[7]
    assert b7.longshot_price == pytest.approx(0.04) and b7.won
    price = 0.96 + 0.01
    assert b7.cost == pytest.approx(price + 0.05 * price * (1 - price))
    assert b7.pnl == pytest.approx(1 - b7.cost)
    assert bets[1].longshot_price == pytest.approx(0.02)


def test_cheap_no_means_betting_yes_and_losing_when_no_wins():
    m = {"condition_id": "c", "event_id": "e", "question": "Q", "yes_won": 0.0, "scheduled_end": END, "closed_ts": END}
    (b,) = [x for x in bets_for_market(m, [(END - DAY - 60, 0.97)], C, 0.0) if x.horizon == 1]
    assert b.longshot_price == pytest.approx(0.03) and not b.won and b.pnl == pytest.approx(-b.cost)


def test_no_bet_once_the_market_already_closed_or_price_too_high():
    m = {"condition_id": "c", "event_id": "e", "question": "Q", "yes_won": 1.0, "scheduled_end": END,
         "closed_ts": END - 10 * DAY}                    # resolved early: nothing left to bet on
    assert bets_for_market(m, [(END - 30 * DAY, 0.05)], C, 0.0) == []
    m["closed_ts"] = END
    assert bets_for_market(m, [(END - DAY - 60, 0.40)], C, 0.0) == []   # no longshot side


def test_buckets_are_ceilings():
    assert bucket_of(0.004, [0.01, 0.05]) == 0.01
    assert bucket_of(0.03, [0.01, 0.05]) == 0.05
    assert bucket_of(0.5, [0.01, 0.05]) == float("inf")


def test_market_row_keeps_resolved_binary_markets_only():
    cfg = load()
    base = {"conditionId": "c1", "question": "Will X?", "outcomes": '["Yes", "No"]', "clobTokenIds": '["y", "n"]',
            "closed": True, "endDate": "2026-06-01T00:00:00Z", "closedTime": "2026-06-01 12:00:00+00",
            "volumeNum": 9000, "events": [{"id": 42}], "negRisk": True}
    row = market_row({**base, "outcomePrices": '["0", "1"]'}, cfg)
    assert row[0] == "c1" and row[2] == "42" and row[3] is True and row[4] == "y" and row[5] == 0.0
    assert market_row({**base, "outcomePrices": '["0.5", "0.5"]'}, cfg) is None
    assert market_row({**base, "outcomePrices": '["0.3", "0.7"]', "closed": False}, cfg) is None


def test_evaluate_end_to_end(tmp_path):
    cfg = load(overrides={"output_dir": str(tmp_path), "longshot": {"horizons_days": [1], "min_events": 1,
                                                                   "test_days": 10_000}})
    con = db.connect(str(tmp_path / "t.duckdb"))
    con.execute(SCHEMA)
    for i in range(40):
        yes_won = 1.0 if i == 0 else 0.0                       # one longshot in 40 hits
        con.execute("INSERT INTO ls_markets VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [f"c{i}", f"Q{i}", f"e{i}", False, f"y{i}", yes_won, END, END, 10000.0, "politics"])
        con.execute("INSERT INTO ls_prices VALUES (?,?,?)", [f"y{i}", END - DAY - 600, 0.05])
        con.execute("INSERT INTO ls_fetched VALUES (?, 1)", [f"y{i}"])
    text = evaluate(con, cfg)
    assert "| 1 | 5¢ | all | 40 | 40 |" in text and "2.5%" in text      # hit rate 1/40
    assert (tmp_path / "longshot" / "bets.csv").exists()


def test_prices_fetch_one_day_per_decision_time(tmp_path):
    from polybt.longshot.data import ingest_prices
    cfg = load(overrides={"longshot": {"horizons_days": [1, 7, 30]}})
    con = db.connect(str(tmp_path / "t.duckdb"))
    con.execute(SCHEMA)
    # closed 10 days early: the 1- and 7-day decision times are after the close, only 30 is fetched
    con.execute("INSERT INTO ls_markets VALUES ('c','Q','e',false,'y',0.0,?,?,1e4,'politics')", [END, END - 10 * DAY])
    calls = []

    class Api:
        def prices_history(self, token, start, end, fidelity):
            calls.append((start, end))
            return [(end - 60, 0.03)]

    assert ingest_prices(con, Api(), cfg) == 1
    assert calls == [(END - 30 * DAY - 24 * 3600, END - 30 * DAY)]
    assert con.execute("SELECT count(*) FROM ls_prices").fetchone()[0] == 1


def test_buying_the_longshot_pays_on_a_hit():
    c = {**C, "side": "longshot", "spread": 0.02}
    m = {"condition_id": "c", "event_id": "e", "question": "Q", "yes_won": 1.0, "scheduled_end": END, "closed_ts": END}
    (b,) = [x for x in bets_for_market(m, [(END - DAY - 60, 0.05)], c, 0.0) if x.horizon == 1]
    assert b.hit and b.won and b.cost == pytest.approx(0.07) and b.pnl == pytest.approx(0.93)
    m["yes_won"] = 0.0
    (b,) = [x for x in bets_for_market(m, [(END - DAY - 60, 0.05)], c, 0.0) if x.horizon == 1]
    assert not b.hit and not b.won and b.pnl == pytest.approx(-0.07)


def test_live_check_measures_the_gap_to_the_real_ask():
    from polybt.longshot.live_check import check, kind
    c = load()["longshot"]

    class Api:
        def prices_history(self, token, start, end, fidelity):
            return [(end - 600, 0.85)]                      # NO side is the 15c longshot

        def book(self, token):
            assert token == "n"
            return {"bids": [(0.13, 100)], "asks": [(0.19, 50), (0.20, 1000)]}

    r = check(Api(), {"question": "Arsenal vs. Chelsea", "yes": "y", "no": "n", "volume": 1e4, "end": ""}, c, 10_000)
    assert r["kind"] == "game winner" and r["last"] == pytest.approx(0.15) and r["gap"] == pytest.approx(0.04)
    assert r["usd_within_2c"] == 0 and r["usd_within_5c"] == pytest.approx(0.19 * 50 + 0.20 * 1000)
    assert kind("Will Inter vs. Milan end in a draw?") == "draw"


def test_kind_does_not_mistake_governor_for_over_under():
    from polybt.longshot.live_check import kind
    assert kind("Will the Democrats win the Nevada governor race in 2026?") == "other"
    assert kind("Arsenal vs. Chelsea: O/U 2.5") == "over/under"
    assert kind("Will the total be over 220.5 points?") == "over/under"
