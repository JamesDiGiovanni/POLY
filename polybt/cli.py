"""Command line: python -m polybt <step> [options]

Steps run in order (ingest -> filter -> prices -> simulate -> report) and each can be re-run alone.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys

from . import db, filter as filter_mod, ingest, report, simulate
from .api import PolymarketAPI
from .config import load
from .http import HttpClient


def _api(cfg) -> PolymarketAPI:
    h = cfg["http"]
    client = HttpClient(cfg["cache_dir"], h["requests_per_second"], h["timeout_s"], h["max_retries"], h["backoff_s"])
    return PolymarketAPI(client, cfg)


def _price_wallets(con, args) -> list[str]:
    if args.wallet:
        return [w.lower() for w in args.wallet]
    q = "SELECT wallet FROM wallet_scores" + ("" if args.all else " WHERE passed")
    return [r[0] for r in con.execute(q).fetchall()]


def inspect(con, cfg, wallet: str) -> None:
    """Summary to check by hand against the wallet's Polymarket profile."""
    wallet = wallet.lower()
    row = con.execute("""
        SELECT count(*) FILTER (WHERE type = 'TRADE'),
               count(*) FILTER (WHERE type = 'TRADE' AND side = 'BUY'),
               sum(usdc_size) FILTER (WHERE type = 'TRADE' AND side = 'BUY'),
               sum(usdc_size) FILTER (WHERE type = 'TRADE' AND side = 'SELL'),
               sum(usdc_size) FILTER (WHERE type = 'REDEEM'),
               count(DISTINCT condition_id), min(timestamp), max(timestamp)
        FROM wallet_trades WHERE wallet = ?
    """, [wallet]).fetchone()
    fmt = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") if t else "–"
    print(f"wallet          {wallet}")
    print(f"profile         https://polymarket.com/profile/{wallet}")
    print(f"trades          {row[0]} ({row[1]} buys) across {row[5]} markets")
    print(f"first / last    {fmt(row[6])} / {fmt(row[7])}")
    print(f"bought / sold   ${row[2] or 0:,.2f} / ${row[3] or 0:,.2f}")
    print(f"redeemed        ${row[4] or 0:,.2f}")
    print(f"cash P&L        ${(row[3] or 0) + (row[4] or 0) - (row[2] or 0):,.2f}  (open positions not valued)")
    print("latest trades:")
    for ts, side, price, size, usdc, q in con.execute("""
        SELECT t.timestamp, t.side, t.price, t.size, t.usdc_size, coalesce(m.question, t.condition_id)
        FROM wallet_trades t LEFT JOIN markets m USING (condition_id)
        WHERE wallet = ? AND type = 'TRADE' ORDER BY timestamp DESC LIMIT 10
    """, [wallet]).fetchall():
        print(f"  {fmt(ts)}  {side:4} {size:>10.2f} @ {price:.3f}  ${usdc or 0:>9.2f}  {q[:60]}")
    s = con.execute("SELECT passed, rejection_reason FROM wallet_scores WHERE wallet = ?", [wallet]).fetchone()
    if s:
        print(f"filters         {'PASSED' if s[0] else 'rejected: ' + (s[1] or '')}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="polybt", description="Polymarket copy-trade backtester")
    p.add_argument("--config", default=None, help="YAML merged over the bundled config.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest", help="discover wallets, pull their activity and market metadata")
    s.add_argument("--wallet", action="append", help="skip discovery; ingest these wallets (repeatable)")
    s.add_argument("--no-discovery", action="store_true", help="re-sync wallets already in candidates")
    s = sub.add_parser("filter", help="score candidates and log rejection reasons")
    s.add_argument("--wallet", action="append")
    s = sub.add_parser("prices", help="pull price history around test-period trades")
    s.add_argument("--wallet", action="append")
    s.add_argument("--all", action="store_true", help="all scored wallets, not only those that passed")
    s = sub.add_parser("simulate", help="run the copy simulation")
    s.add_argument("--wallet", action="append", help="default: wallets that passed the filters")
    sub.add_parser("report", help="metrics, report.html and CSVs")
    s = sub.add_parser("run", help="every step in order")
    s.add_argument("--wallet", action="append")
    s.add_argument("--no-discovery", action="store_true")
    s = sub.add_parser("inspect", help="summarise one wallet's stored trades for a manual check")
    s.add_argument("wallet")

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    cfg = load(args.config)
    con = db.connect(cfg["db_path"])

    if args.cmd == "ingest":
        ingest.run(con, _api(cfg), cfg, args.wallet, args.no_discovery)
    elif args.cmd == "filter":
        filter_mod.run(con, cfg, args.wallet)
    elif args.cmd == "prices":
        ingest.ingest_prices(con, _api(cfg), cfg, _price_wallets(con, args), cfg.cutoff_ts)
    elif args.cmd == "simulate":
        simulate.run(con, cfg, args.wallet)
    elif args.cmd == "report":
        r = report.run(con, cfg)
        print(f"{r['go']} of {r['wallets']} wallets meet the go criteria -> {'GO' if r['verdict'] else 'NO-GO'}")
    elif args.cmd == "run":
        api = _api(cfg)
        wallets = ingest.run(con, api, cfg, args.wallet, args.no_discovery)
        passed = filter_mod.run(con, cfg, wallets)
        ingest.ingest_prices(con, api, cfg, passed, cfg.cutoff_ts)
        simulate.run(con, cfg, passed)
        r = report.run(con, cfg)
        print(f"{r['go']} of {r['wallets']} wallets meet the go criteria -> {'GO' if r['verdict'] else 'NO-GO'}")
    elif args.cmd == "inspect":
        inspect(con, cfg, args.wallet)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
