import pytest

from polybt.config import load
from polybt.longshot.paper import PaperBet, cash, equity, load as load_bets, place, report, save, settle

CFG = load()


class Api:
    def __init__(self, last=0.85, asks=((0.16, 100.0),), fd=None, resolved=None):
        self.last, self.asks, self.fd, self.resolved = last, list(asks), fd, resolved

    def prices_history(self, token, start, end, fidelity):
        return [(end - 300, self.last)]

    def book(self, token):
        return {"bids": [], "asks": self.asks}

    def clob_market_info(self, cid):
        return {"fd": self.fd} if self.fd else {}

    def markets_by_condition(self, ids):
        return [self.resolved] if self.resolved else []


M = {"condition_id": "c1", "question": "Nets vs. Celtics", "yes": "y", "no": "n", "end": "2026-11-01T00:00:00Z"}


def test_place_buys_the_cheap_side_at_the_ask_and_pays_the_fee_in_shares():
    b = place(Api(fd={"r": 0.05, "e": 1}), CFG, M, [], 1000)
    assert isinstance(b, PaperBet) and b.token == "n" and b.kind == "game winner"
    assert b.stake == pytest.approx(1.5) and b.last_price == pytest.approx(0.15) and b.avg_price == pytest.approx(0.16)
    gross = 1.5 / 0.16
    fee = round(gross * 0.05 * 0.16 * 0.84, 4)
    assert b.fee == pytest.approx(fee) and b.shares == pytest.approx(gross - fee / 0.16)


def test_no_fee_details_means_fee_free_and_rules_skip_bad_markets():
    assert place(Api(), CFG, M, [], 1000).fee == 0
    assert place(Api(last=0.5), CFG, M, [], 1000) == "price"
    assert place(Api(asks=[(0.30, 100.0)]), CFG, M, [], 1000) == "book too thin"      # > 3c over the last price
    assert place(Api(), CFG, {**M, "question": "Will Elon Musk post 300 tweets?"}, [], 1000) == "kind"


def test_stake_follows_equity_and_cash_runs_out():
    many = [PaperBet("x", "q", "draw", "t", 0, "", 0.15, 0.15, 99.5, 600, 0, 0)]
    assert cash(many, 100) == pytest.approx(0.5) and place(Api(), CFG, M, many, 1000) == "no cash"
    assert equity(many, 100) == pytest.approx(100)


def test_settle_pays_the_shares_and_report_and_ledger_round_trip(tmp_path):
    b = place(Api(), CFG, M, [], 1000)
    won = {"conditionId": "c1", "clobTokenIds": '["y", "n"]', "outcomes": '["Nets", "Celtics"]',
           "outcomePrices": '["0", "1"]', "closed": True}
    assert settle(Api(resolved=won), [b], 2000) == 1
    assert b.status == "won" and b.payout == pytest.approx(b.shares) and b.pnl > 0
    save(tmp_path / "bets.csv", [b])
    (back,) = load_bets(tmp_path / "bets.csv")
    assert back == b
    text = report([back], CFG)
    assert "1 won" in text and "game winner" in text
