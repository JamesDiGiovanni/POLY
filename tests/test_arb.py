import datetime as dt

import pytest

from polybt.arb.kalshi import Kalshi, _dollars, asks_from_bids, taker_fee
from polybt.arb.match import Ref, consistent, match, polymarket_refs
from polybt.arb.run import walk_pair
from polybt.config import load

T = int(dt.datetime(2026, 12, 10, tzinfo=dt.timezone.utc).timestamp())


def test_kalshi_prices_and_fees():
    assert _dollars({"yes_bid": 42}, "yes_bid") == 0.42
    assert _dollars({"yes_bid": 1}, "yes_bid") == 0.01          # cents, not a dollar
    assert _dollars({"yes_bid_dollars": "0.4200", "yes_bid": 99}, "yes_bid") == 0.42
    assert taker_fee(100, 0.5) == 1.75                          # 0.07 x 100 x 0.25
    assert taker_fee(1, 0.5) == 0.02                            # 0.0175 rounds up to 2c
    assert taker_fee(100, 0.5, multiplier=0.5) == pytest.approx(0.88)
    assert asks_from_bids([(0.60, 10), (0.55, 5)]) == [(0.40, 10), (0.45, 5)]


def test_orderbook_parsing_cents_and_dollars():
    class C:
        def __init__(self, body):
            self.body = body

        def get_json(self, *a, **k):
            return self.body

    cents = Kalshi(C({"orderbook": {"yes": [[40, 100], [42, 50]], "no": [[55, 20]]}})).orderbook("X")
    assert cents["yes_bids"] == [(0.42, 50), (0.40, 100)] and cents["no_bids"] == [(0.55, 20)]
    dollars = Kalshi(C({"orderbook": {"yes_dollars": [["0.42", "50"]], "no_dollars": []}})).orderbook("X")
    assert dollars["yes_bids"] == [(0.42, 50)]


def test_walk_pair_stops_when_the_pair_costs_more_than_a_dollar():
    no_fee = lambda p: 0.0
    r = walk_pair([(0.40, 10), (0.45, 10)], [(0.55, 15), (0.60, 10)], no_fee, no_fee)
    # 10 @ 0.40+0.55 (5c), then 5 @ 0.45+0.55 (0c), then 0.45+0.60 > 1 stops
    assert r["first_edge"] == pytest.approx(0.05) and r["contracts"] == 15 and r["profit"] == pytest.approx(0.5)
    fee = lambda p: 0.07 * p * (1 - p)
    assert walk_pair([(0.40, 10)], [(0.55, 10)], fee, fee)["first_edge"] == pytest.approx(0.05 - 0.07 * (0.24 + 0.2475))


def test_ref_extracts_numbers_and_dates_but_not_years():
    r = Ref("poly", "x", "Will the Fed cut by 25 bps on December 10, 2026? Bitcoin above $100k", T).analyse()
    assert r.numbers == {25.0, 100000.0} and r.dates == {(12, 10)} and "federal" in r.tokens


def test_consistency_rules():
    a = Ref("poly", "a", "Bitcoin above $100,000 on December 31", T).analyse()
    b = Ref("kalshi", "b", "Bitcoin price above 100000 on Dec 31", T + 3600).analyse()
    c = Ref("kalshi", "c", "Bitcoin price above 105000 on Dec 31", T).analyse()
    d = Ref("kalshi", "d", "Bitcoin price above 100000 on Dec 31", T + 10 * 86400).analyse()
    assert consistent(a, b, 3) == []
    assert "numbers" in consistent(a, c, 3)[0]
    assert "close" in consistent(a, d, 3)[0]


def test_match_grades_on_shared_source_and_rejects_different_thresholds():
    cfg = load()
    polys = [Ref("poly", "p1", "Fed decision in December | Fed decreases interest rates by 25 bps after December 2026 meeting",
                 T, rules="Resolves per the Federal Reserve statement at https://www.federalreserve.gov/").analyse(),
             Ref("poly", "p2", "Will Bitcoin close above $120,000 on December 10?", T, rules="Source: coingecko.com").analyse()]
    kalshis = [Ref("kalshi", "K1", "Fed decision December 2026 | Federal Reserve decreases interest rates by 25 bps",
                   T, rules="Resolves using the Federal Reserve's announcement.").analyse(),
               Ref("kalshi", "K2", "Bitcoin price on December 10 | Bitcoin close above $125,000", T,
                   rules="CF Benchmarks").analyse(),
               Ref("kalshi", "K3", "Chiefs vs Bills winner", T).analyse()]
    pairs = match(polys, kalshis, cfg)
    assert [(p.poly.id, p.kalshi.id, p.grade) for p in pairs] == [("p1", "K1", "A")]
    assert "federal reserve" in pairs[0].shared_sources


def test_two_outcome_markets_become_one_side_per_outcome():
    cfg = load(overrides={"arb": {"max_poly_markets": 500}})

    class C:
        def get_json(self, *a, **k):
            return [{"conditionId": "c1", "question": "Lakers vs. Celtics", "outcomes": '["Lakers", "Celtics"]',
                     "clobTokenIds": '["t1", "t2"]', "endDate": "2026-12-10T00:00:00Z", "events": [{"title": "NBA"}]},
                    {"conditionId": "c2", "question": "Will it rain?", "outcomes": '["Yes", "No"]',
                     "clobTokenIds": '["t3", "t4"]', "endDate": "2026-12-10T00:00:00Z"}]

    refs = {r.id: r for r in polymarket_refs(C(), cfg)}
    assert set(refs) == {"c1#0", "c1#1", "c2"}
    assert (refs["c1#1"].extra["yes_token"], refs["c1#1"].extra["no_token"]) == ("t2", "t1")
    assert "celtics" in refs["c1#1"].tokens


def test_polymarket_paging_follows_100_per_page_and_windows():
    """Gamma returns at most 100 a page; a short page ends a window, a full one continues it."""
    cfg = load(overrides={"arb": {"window_days": 7, "horizon_days": 14}})
    calls = []

    class C:
        def get_json(self, base, path, params=None, **k):
            calls.append((params["end_date_min"], params["offset"]))
            first_window = len({c[0] for c in calls}) == 1
            n = (100 if params["offset"] == 0 else 30) if first_window else 0
            return [{"conditionId": f"{params['offset']}-{i}", "question": f"Q{i}", "outcomes": '["Yes", "No"]',
                     "clobTokenIds": f'["a{i}", "b{i}"]', "endDate": "2026-12-10T00:00:00Z"} for i in range(n)]

    refs = polymarket_refs(C(), cfg)
    assert len(refs) == 130
    assert calls[:2] == [(calls[0][0], 0), (calls[0][0], 100)] and len({c[0] for c in calls}) == 3


def test_iso_dates_are_dates_not_thresholds():
    r = Ref("poly", "x", "Will FC Barcelona win on 2026-10-20?", T).analyse()
    assert r.dates == {(10, 20)} and r.numbers == frozenset()


def test_candidates_found_when_shared_words_are_not_the_rarest():
    """Regression: indexing only words rarer than the median word dropped every word both venues share."""
    cfg = load()
    word = lambda i, tag: tag + "".join(chr(97 + (i // 26 ** k) % 26) for k in range(3))  # distinct, digit-free
    # Like the real data: most words occur in just one market.
    filler = [Ref("kalshi", f"F{i}", f"{word(i, 'zq')} {word(i, 'yq')} {word(i, 'xq')} Ballon", T).analyse()
              for i in range(300)]
    target = Ref("kalshi", "KBALLON", "Who will win the Ballon d'Or in 2026? | Erling Haaland", T,
                 extra={"yes_side": "erling haaland"}).analyse()
    others = [Ref("kalshi", f"O{i}", f"Who will win the Ballon d'Or in 2026? | Player{i} Name{i}", T,
                  extra={"yes_side": f"player{i} name{i}"}).analyse() for i in range(5)]
    poly = Ref("poly", "P", "2026 Ballon d'Or winner | Will Erling Haaland win the 2026 Ballon d'Or?", T).analyse()
    pairs = match([poly], filler + others + [target], cfg)
    assert [(p.poly.id, p.kalshi.id) for p in pairs] == [("P", "KBALLON")]


def test_two_outcome_side_pairs_only_with_its_own_kalshi_yes_side():
    cfg = load()
    k_big = Ref("kalshi", "KBIG", "BIG vs. TheMongolz | BIG wins | BIG", T, extra={"yes_side": "big"}).analyse()
    k_mon = Ref("kalshi", "KMON", "BIG vs. TheMongolz | TheMongolz wins | TheMongolz", T,
                extra={"yes_side": "themongolz"}).analyse()
    side = lambda lab: Ref("poly", f"P-{lab}", f"Counter-Strike: TheMongolz vs BIG (BO3) | {lab}", T,
                           extra={"outcome": lab}).analyse()
    pairs = {p.poly.id: p.kalshi.id for p in match([side("TheMongolz"), side("BIG")], [k_big, k_mon], cfg)}
    assert pairs == {"P-TheMongolz": "KMON", "P-BIG": "KBIG"}


def test_meaning_changing_words_block_or_downgrade_pairs():
    cfg = load()
    src = "https://www.rbi.org.in"
    p_up = Ref("poly", "P1", "Will the Reserve Bank of India increase the policy repo rate by 25 bps at the December meeting?",
               T, rules=src).analyse()
    k_cut = Ref("kalshi", "K1", "Reserve Bank of India rate decision in December | Will the Reserve Bank of India cut more "
                "than 25bps at the December Monetary Policy Committee meeting? | Cut more than 25bps", T, rules=src).analyse()
    assert any("direction" in w for w in consistent(p_up, k_cut, 7))

    p3 = Ref("poly", "P2", "Will Moonshot be the third-best Chinese AI company at the end of October 2026?", T).analyse()
    k1 = Ref("kalshi", "K2", "Top Chinese AI Company week of October 26th | Moonshot", T).analyse()
    assert any("rank" in w for w in consistent(p3, k1, 7))

    rt = "https://www.rottentomatoes.com"
    p_incl = Ref("poly", "P3", 'Will "Wild Horse Nine" score at least 95 on the Rotten Tomatoes Tomatometer?', T, rules=rt).analyse()
    k_strict = Ref("kalshi", "K3", "Wild Horse Nine · Rotten Tomatoes score | Wild Horse Nine Rotten Tomatoes score? | Above 95",
                   T, rules=rt).analyse()
    assert consistent(p_incl, k_strict, 7) == []
    (pair,) = match([p_incl], [k_strict], cfg)
    assert pair.grade == "B" and any("threshold" in r for r in pair.reasons)


def test_annualised_return_penalises_long_lockups():
    from polybt.arb.run import annualised
    assert annualised(0.02, 365) == pytest.approx(0.02 / 0.98)
    assert annualised(0.02, 36.5) == pytest.approx(10 * 0.02 / 0.98)
    assert annualised(None, 10) is None


def test_exact_value_never_pairs_with_an_open_threshold():
    p = Ref("poly", "P", "Will the Reserve Bank of India increase the policy repo rate by 25 bps at the December meeting?", T).analyse()
    k = Ref("kalshi", "K", "Reserve Bank of India rate decision in December | Will the Reserve Bank of India hike more "
            "than 25bps at the December meeting? | Hike more than 25bps", T).analyse()
    assert any("exact value vs threshold" in w for w in consistent(p, k, 7))
