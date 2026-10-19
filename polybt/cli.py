"""Command line: python -m polybt <step> [options]

Steps run in order (ingest -> filter -> prices -> simulate -> report) and each can be re-run alone.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys

from . import db, fees, filter as filter_mod, ingest, live, report, simulate
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


def _session_wallets(con, cfg, args) -> list[str]:
    if args.wallet:
        return [w.lower() for w in args.wallet]
    if cfg["live"].get("wallets"):
        return [w.lower() for w in cfg["live"]["wallets"]]
    _, summaries = report.compute(con, cfg)
    wallets = [s["wallet"] for s in summaries if s["go"]]
    if not wallets:
        raise SystemExit("no wallets: pass --wallet, set live.wallets, or run the backtest until some are GO")
    return wallets


def run_session(con, cfg, args, mode: str) -> None:
    session = args.session or cfg["live"]["session"]
    if args.replay:
        wallets = _session_wallets(con, cfg, args)
        prices = simulate.load_prices(con, {f.token_id for w in wallets for f in simulate.load_fills(con, w)})
        params = simulate.SimParams.from_cfg(cfg)
        start = cfg.cutoff_ts if not args.since else int(dt.datetime.fromisoformat(args.since)
                                                          .replace(tzinfo=dt.timezone.utc).timestamp())
        con.execute("DELETE FROM live_orders WHERE session = ?", [session])
        con.execute("DELETE FROM live_sessions WHERE session = ?", [session])
        live.replay(con, cfg, wallets, start, lambda: simulate.BacktestExecutor(prices, params, args.delay), session)
    else:
        api = _api(cfg)
        wallets = _session_wallets(con, cfg, args)
        runner = live.Runner(con, cfg, api, live.make_executor_factory(mode, cfg, api), session, mode, wallets)
        try:
            runner.run(args.cycles)
        except KeyboardInterrupt:
            runner.snapshot()
    print_session(con, cfg, session)


def print_session(con, cfg, session: str) -> None:
    rows = report.write_session(con, cfg, session)
    pct = lambda v: "–" if v is None else f"{v * 100:+.1f}%"
    print(f"session {session}")
    print(f"{'wallet':44} {'filled':>6} {'closed':>6} {'ROI':>8} {'open $':>8} {'latency':>8} {'slip¢':>6} {'backtest':>14}")
    for r in rows:
        bt = f"{pct(r['backtest_roi'])} @{r['backtest_delay_s']}s" if r["backtest_delay_s"] is not None else "–"
        slip = "–" if r["avg_slippage_vs_model_c"] is None else f"{r['avg_slippage_vs_model_c']:+.2f}"
        lat = "–" if r["median_latency_s"] is None else f"{r['median_latency_s']}s"
        print(f"{r['wallet']:44} {r['filled']:>6} {r['closed']:>6} {pct(r['roi']):>8} {r['open_exposure']:>8.2f} "
              f"{lat:>8} {slip:>6} {bt:>14}")
        if r["skipped"] != "{}":
            print(f"{'':44} skipped: {r['skipped']}")


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
    for name, text in (("paper", "paper trade: the live engine against the live order book, no orders sent"),
                       ("live", "live trade: identical to paper, but sends real orders (needs --confirm-live)")):
        s = sub.add_parser(name, help=text)
        s.add_argument("--wallet", action="append", help="default: live.wallets, else the GO wallets")
        s.add_argument("--session", help="default: live.session; reusing a name resumes that session")
        s.add_argument("--cycles", type=int, help="stop after this many polls (default: run until stopped)")
        if name == "paper":
            s.add_argument("--replay", action="store_true",
                           help="offline: run the session over stored history with the backtest's fill model")
            s.add_argument("--delay", type=int, default=60, help="replay fill delay in seconds")
            s.add_argument("--since", help="replay start date (default: the cutoff)")
        else:
            s.add_argument("--confirm-live", action="store_true", help="required: acknowledges real orders")
    s = sub.add_parser("session", help="summarise a paper/live session against the backtest")
    s.add_argument("--session")
    s = sub.add_parser("fees", help="fee sources per market, and which formula matches real fills")
    s.add_argument("--since", default="2026-03-30", help="only trades after this date (fee schedule V2)")

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
    elif args.cmd == "paper":
        run_session(con, cfg, args, "paper")
    elif args.cmd == "live":
        if not args.confirm_live:
            raise SystemExit("live trading sends real orders; re-run with --confirm-live once paper results justify it")
        args.replay = False
        run_session(con, cfg, args, "live")
    elif args.cmd == "session":
        print_session(con, cfg, args.session or cfg["live"]["session"])
    elif args.cmd == "fees":
        for src, cat, n, avg in con.execute("""
                SELECT fee_source, fee_category, count(*), avg(fee_rate) FROM markets
                GROUP BY ALL ORDER BY fee_source, count(*) DESC""").fetchall():
            print(f"{src or 'none':9} {cat or '-':12} {n:6} markets  avg rate {avg or 0:.3f}")
        since = int(dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc).timestamp())
        c = fees.calibrate(con, since)
        print(f"\ncalibration on {c['trades']} trades in fee-bearing markets since {args.since}:")
        print(f"  {c['zero_fee']} show no fee (maker fills or fee-free); {c['charged']} were charged")
        if c["charged"]:
            print(f"  matched v1: {c['v1']}  v2: {c['v2']}  neither: {c['neither']}")
            best = "v1" if c["v1"] > c["v2"] else "v2"
            if best != cfg["fees"]["formula"] and c[best] > 1.5 * c[cfg["fees"]["formula"]]:
                print(f"  -> set fees.formula: {best} in config.yaml")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
