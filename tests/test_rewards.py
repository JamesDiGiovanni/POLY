import pytest

from polybt.config import load
from polybt.rewards.api import RewardsAPI, parse_config
from polybt.rewards.run import score_market, write_report
from polybt.rewards.scoring import adjusted_mid, book_score, expected_daily, our_quote, q_min, side_score


def test_adjusted_mid_ignores_orders_below_min_size():
    assert adjusted_mid([(0.49, 5), (0.45, 100)], [(0.51, 5), (0.55, 100)], 50) == pytest.approx(0.50)


def test_score_falls_off_quadratically_and_stops_at_max_spread():
    # 3c max spread: at the mid scores fully, 1.5c away a quarter, 3c away nothing; small orders nothing
    assert side_score([(0.50, 100)], 0.50, 0.03, 10) == pytest.approx(100)
    assert side_score([(0.485, 100)], 0.50, 0.03, 10) == pytest.approx(25)
    assert side_score([(0.47, 100), (0.499, 5)], 0.50, 0.03, 10) == 0


def test_single_sided_quotes_count_a_third_only_inside_the_10_90_band():
    assert q_min(90, 0, 0.5) == pytest.approx(30)
    assert q_min(90, 30, 0.5) == pytest.approx(30)
    assert q_min(90, 60, 0.5) == 60
    assert q_min(90, 0, 0.95) == 0


def test_our_quote_buys_both_sides_with_the_capital():
    q = our_quote(1000, 0.50, 0.04, 20)
    # buy YES at 0.48 and NO at 0.48: 0.96 a pair -> 1041.67 of each, scoring a quarter each
    assert q["size"] == pytest.approx(1000 / 0.96) and q["q_min"] == pytest.approx(0.25 * 1000 / 0.96)
    assert our_quote(10, 0.50, 0.04, 100)["q_min"] == 0          # below min size: scores nothing


def test_share_of_pool_and_haircut():
    assert expected_daily(100, 50, 150) == pytest.approx(25)
    assert expected_daily(100, 50, 150, 2) == pytest.approx(100 * 50 / 350)
    assert expected_daily(100, 0, 0) == 0


def test_score_market_end_to_end():
    r = load()["rewards"]
    m = {"daily_rate": 50.0, "min_size": 20, "max_spread": 0.03}
    book = {"bids": [(0.49, 1000)], "asks": [(0.51, 1000)]}
    s = score_market(m, book, r)
    bs = book_score(book["bids"], book["asks"], 0.03, 20)
    assert s["mid"] == pytest.approx(0.5) and s["theirs"] == pytest.approx(bs["q_min"])
    assert 0 < s["daily_haircut"] < s["daily"] < 50
    assert "error" in score_market(m, {"bids": [], "asks": [(0.5, 10)]}, r)


def test_parse_config_handles_both_shapes():
    cur = parse_config({"condition_id": "c", "rewards_max_spread": 3.5, "rewards_min_size": 50,
                        "rewards_config": [{"rate_per_day": 20}, {"rate_per_day": "5"}]})
    assert (cur["daily_rate"], cur["min_size"], cur["max_spread"]) == (25, 50, pytest.approx(0.035))
    full = parse_config({"condition_id": "c", "question": "Q?", "tokens": [{"token_id": "n", "outcome": "No"},
                                                                          {"token_id": "y", "outcome": "Yes", "price": 0.3}],
                         "rewards": {"rates": [{"rewards_daily_rate": 10}], "min_size": 100, "max_spread": 2}})
    assert (full["yes_token"], full["daily_rate"], full["max_spread"]) == ("y", 10, pytest.approx(0.02))


def test_current_follows_cursor_until_end():
    pages = {"": {"data": [{"condition_id": "a", "rewards_config": [{"rate_per_day": 1}]}], "next_cursor": "MQ=="},
             "MQ==": {"data": [{"condition_id": "b"}], "next_cursor": "LTE="}}

    class C:
        def get_json(self, base, path, params=None, **k):
            return pages[(params or {}).get("next_cursor", "")]

    assert [m["condition_id"] for m in RewardsAPI(C()).current()] == ["a", "b"]


def test_report_gate(tmp_path):
    cfg = load(overrides={"output_dir": str(tmp_path), "rewards": {"min_markets": 1}})
    ms = [{"condition_id": "a", "question": "A?", "daily_rate": 50, "min_size": 20, "max_spread": 0.03, "sponsored": False},
          {"condition_id": "b", "question": "B?", "daily_rate": 1, "min_size": 20, "max_spread": 0.03, "sponsored": False}]
    snap = lambda d: {"mid": 0.5, "theirs": 100, "ours": 50, "size": 200, "daily": d, "daily_haircut": d / 2}
    text = write_report(cfg, ms, {"a": [snap(20), snap(10)], "b": [{"error": "x"}]})
    assert "PASSED" in text and "Found **1**" in text and (tmp_path / "rewards" / "markets.csv").exists()
