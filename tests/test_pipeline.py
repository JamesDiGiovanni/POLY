"""Offline end-to-end run: a fake API feeds every pipeline step into a real DuckDB file."""
import random
import time

from polybt import db, filter as filter_mod, ingest, report, simulate
from polybt.config import load

DAY = 86400


class FakeAPI:
    def __init__(self, now):
        rng = random.Random(1)
        self.rows, self.markets, self.prices = {}, {}, {}
        start = now - 300 * DAY
        # Skilled: buys at 40c, wins 60%. Unlucky: buys at 60c, wins 40%. Bot: 60 trades a day.
        for wallet, price, p_win, per_day, days in (("0xskilled", 0.40, 0.6, 3, range(295)),
                                                    ("0xunlucky", 0.60, 0.4, 3, range(295)),
                                                    ("0xbot", 0.50, 0.5, 60, range(100, 140))):
            rows = []
            for day in days:
                for k in range(per_day):
                    i = len(self.markets)
                    cid, ts = f"c{i}", start + day * DAY + k * 60
                    win = rng.random() < p_win
                    crypto = i % 4 == 0
                    self.markets[cid] = {
                        "conditionId": cid, "closed": True,
                        "question": "Bitcoin Up or Down 15m" if crypto else f"Question {i}",
                        "slug": f"m-{i}", "clobTokenIds": f'["{cid}y","{cid}n"]', "outcomes": '["Yes","No"]',
                        "outcomePrices": '["1","0"]' if win else '["0","1"]', "volumeNum": 1e6,
                        "closedTime": time.strftime("%Y-%m-%d %H:%M:%S+00", time.gmtime(ts + 2 * DAY)),
                    }
                    self.prices[f"{cid}y"] = [(ts + 30, price), (ts + 90, price + 0.01), (ts + 400, price + 0.02)]
                    rows.append({"type": "TRADE", "side": "BUY", "asset": f"{cid}y", "conditionId": cid,
                                 "price": price, "size": 50 / price, "usdcSize": 50, "timestamp": ts,
                                 "transactionHash": f"{wallet}-{i}"})
            self.rows[wallet] = rows

    def leaderboard(self, path, query, limit, offset):
        return [{"proxyWallet": w} for w in self.rows][offset:offset + limit]

    def top_closed_markets(self, limit, end_date_min):
        return []

    def market_trades(self, *a):
        return []

    def activity(self, user, start, end=None):
        return [r for r in self.rows.get(user, []) if r["timestamp"] >= start and (end is None or r["timestamp"] <= end)]

    def markets_by_condition(self, ids):
        return [self.markets[c] for c in ids if c in self.markets]

    def prices_history(self, token, start, end, fidelity):
        return [(t, p) for t, p in self.prices.get(token, []) if start <= t < end]


def test_full_pipeline(tmp_path):
    now = int(time.time())
    cfg = load(overrides={"db_path": str(tmp_path / "t.duckdb"), "output_dir": str(tmp_path / "out"),
                          "discovery": {"active_in_markets": {"enabled": False},
                                        "leaderboard": {"queries": [{"category": "OVERALL"}], "pages": 1}}})
    con = db.connect(cfg["db_path"])
    api = FakeAPI(now)

    wallets = ingest.run(con, api, cfg)
    assert set(wallets) == {"0xskilled", "0xunlucky", "0xbot"}
    n_rows = con.execute("SELECT count(*) FROM wallet_trades").fetchone()[0]
    ingest.run(con, api, cfg, skip_discovery=True)  # re-run: nothing duplicated
    assert con.execute("SELECT count(*) FROM wallet_trades").fetchone()[0] == n_rows

    passed = filter_mod.run(con, cfg, wallets)
    assert passed == ["0xskilled"]
    reasons = dict(con.execute("SELECT wallet, rejection_reason FROM wallet_scores").fetchall())
    assert "roi" in reasons["0xunlucky"] and "trades_per_day" in reasons["0xbot"]

    ingest.ingest_prices(con, api, cfg, passed, cfg.cutoff_ts)
    fetched = con.execute("SELECT count(*) FROM price_fetches").fetchone()[0]
    assert fetched > 0
    assert ingest.needed_price_chunks(con, cfg, passed, cfg.cutoff_ts) == []  # never re-pulled

    assert simulate.run(con, cfg) > 0
    first_copy_ts = con.execute("SELECT min(ts) FROM sim_trades WHERE mode = 'copy'").fetchone()[0]
    assert first_copy_ts >= cfg.cutoff_ts  # tested only after the cutoff

    out = report.run(con, cfg)
    assert out["wallets"] == 1
    rows = con.execute("""SELECT delay_s, copy_roi, wallet_roi FROM sim_results
                          WHERE category = 'all' ORDER BY delay_s""").fetchall()
    assert [r[0] for r in rows] == [10, 60, 300, 900]
    rois = [r[1] for r in rows]
    assert rois == sorted(rois, reverse=True)  # later copies, worse prices
    assert all(r[1] < r[2] for r in rows)       # copying costs edge
    cats = {r[0] for r in con.execute("SELECT DISTINCT category FROM sim_results").fetchall()}
    assert cats == {"all", "short_term_crypto", "other"}
    html = (tmp_path / "out" / "report.html").read_text()
    assert "0xskilled" in html and "<svg" in html
    for f in ("results.csv", "trades.csv", "wallet_scores.csv"):
        assert (tmp_path / "out" / f).exists()
