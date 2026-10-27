"""Forward paper test of buying longshots: the backtest's rule, traded on paper against live order books.

Each run:
  1. settles open bets whose markets have resolved;
  2. scans open markets ending within the next 1-7 days for a side at 10-20c (last hourly price, as in the
     backtest) in the market types where the edge held and the books were deep (game winners, draws,
     over/unders, crypto prices);
  3. buys each new one once, on paper: walks the real ask book with the stake, no more than max_slippage
     above the last price, and pays the market's own taker fee (taken in shares, as Polymarket does).

State is a CSV that the workflow keeps on a branch, so runs add to one ledger. Bankroll starts at
$bankroll; each stake is stake_pct of current equity (at least $1, Polymarket's minimum), and a bet is
skipped when cash can't cover it.
"""
from __future__ import annotations

import csv
import datetime as dt
import logging
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from ..api import PolymarketAPI, parse_market
from ..fees import ZERO, category_fallback, from_market_info
from ..ingest import fee_category
from ..live import walk_book
from .live_check import kind, open_markets

log = logging.getLogger(__name__)


@dataclass
class PaperBet:
    condition_id: str
    question: str
    kind: str
    token: str
    placed_ts: int
    end: str
    last_price: float
    avg_price: float
    stake: float          # USDC spent, fee included (the fee comes out of the shares)
    shares: float         # net of the fee
    fee: float
    fee_rate: float
    status: str = "open"  # open | won | lost | void
    payout: float = 0.0
    settled_ts: int = 0

    @property
    def pnl(self) -> float:
        return self.payout - self.stake if self.status != "open" else 0.0


def load(path: Path) -> list[PaperBet]:
    if not path.exists():
        return []
    conv = {f.name: f.type for f in fields(PaperBet)}
    out = []
    for r in csv.DictReader(open(path)):
        out.append(PaperBet(**{k: (float(v) if conv[k] == "float" else int(float(v)) if conv[k] == "int" else v)
                               for k, v in r.items() if k in conv}))
    return out


def save(path: Path, bets: list[PaperBet]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, [f.name for f in fields(PaperBet)])
        w.writeheader()
        w.writerows(asdict(b) for b in bets)


def cash(bets: list[PaperBet], bankroll: float) -> float:
    return bankroll - sum(b.stake for b in bets) + sum(b.payout for b in bets if b.status != "open")


def equity(bets: list[PaperBet], bankroll: float) -> float:
    """Cash plus open bets at cost (no mark-to-market: they are held to resolution)."""
    return cash(bets, bankroll) + sum(b.stake for b in bets if b.status == "open")


def settle(api: PolymarketAPI, bets: list[PaperBet], now: int) -> int:
    open_ = [b for b in bets if b.status == "open"]
    if not open_:
        return 0
    by_id = {}
    for i in range(0, len(open_), 50):
        for m in api.markets_by_condition([b.condition_id for b in open_[i:i + 50]]):
            by_id[m["conditionId"]] = parse_market(m)
    n = 0
    for b in open_:
        m = by_id.get(b.condition_id)
        if not m or not m["resolved"]:
            continue
        pay = dict(zip(m["token_ids"], m["payouts"])).get(b.token)
        if pay is None:
            continue
        b.payout = b.shares * pay
        b.status = "won" if pay > 0.999 else "lost" if pay < 0.001 else "void"
        b.settled_ts = now
        n += 1
    return n


def fee_params(api: PolymarketAPI, cfg, m: dict):
    try:
        info = api.clob_market_info(m["condition_id"])
    except Exception:
        info = None
    if info is not None:
        return from_market_info(info, cfg["fees"]["formula"]) or ZERO    # no fee details: fee-free
    return category_fallback(cfg, fee_category({"question": m["question"]}, cfg))


def place(api: PolymarketAPI, cfg, m: dict, bets: list[PaperBet], now: int) -> PaperBet | str:
    """One market: qualify it, size the stake, walk the book. Returns the bet or why not."""
    c = cfg["longshot"]
    p = c["paper"]
    k = kind(m["question"])
    if k not in p["kinds"]:
        return "kind"
    pts = api.prices_history(m["yes"], now - 2 * 3600, now, 60)
    if not pts:
        return "no recent price"
    last = pts[-1][1]
    q = min(last, 1 - last)
    if not float(p["min_price"]) < q <= float(p["max_price"]):
        return "price"
    bank = float(p["bankroll"])
    stake = max(float(p["min_stake"]), float(p["stake_pct"]) * equity(bets, bank))
    if cash(bets, bank) < stake:
        return "no cash"
    token = m["yes"] if last < 0.5 else m["no"]
    fill = walk_book(api.book(token)["asks"], usd=stake, limit=q + float(p["max_slippage"]), buying=True)
    if not fill:
        return "book too thin"
    fp = fee_params(api, cfg, m)
    shares = fee = 0.0
    for px, sh in fill:
        net, f = fp.buy(sh, px)
        shares += net
        fee += f
    gross = sum(sh for _, sh in fill)
    return PaperBet(m["condition_id"], m["question"], k, token, now, str(m.get("end") or ""), q,
                    stake / gross, stake, shares, fee, fp.rate)


def run(api: PolymarketAPI, cfg, state_dir: str) -> str:
    c = cfg["longshot"]
    p = c["paper"]
    path = Path(state_dir) / "bets.csv"
    bets = load(path)
    now = int(time.time())
    settled = settle(api, bets, now)
    seen = {b.condition_id for b in bets}
    markets = [m for m in open_markets(api.client, {**c, "live_days": p["max_days"]}) if m["condition_id"] not in seen]
    soonest = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=float(p["min_days"]))
    markets = [m for m in markets if not m["end"] or str(m["end"]) >= soonest.strftime("%Y-%m-%dT%H:%M:%SZ")]
    reasons: dict[str, int] = {}
    placed = 0
    for m in markets:
        try:
            r = place(api, cfg, m, bets, now)
        except Exception as e:
            r = f"error: {type(e).__name__}"
        if isinstance(r, PaperBet):
            bets.append(r)
            placed += 1
        else:
            reasons[r] = reasons.get(r, 0) + 1
    save(path, bets)
    log.info("settled %d, placed %d, skipped %s", settled, placed, reasons)
    text = report(bets, cfg, {"settled": settled, "placed": placed, "scanned": len(markets), "skipped": reasons})
    (Path(state_dir) / "report.md").write_text(text)
    return text


def report(bets: list[PaperBet], cfg, last_run: dict | None = None) -> str:
    p = cfg["longshot"]["paper"]
    bank = float(p["bankroll"])
    done = [b for b in bets if b.status in ("won", "lost")]
    open_ = [b for b in bets if b.status == "open"]
    staked = sum(b.stake for b in done)
    pnl = sum(b.pnl for b in done)
    day = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%b %d %H:%M")
    lines = ["## Longshot forward paper test", "",
             f"Bankroll ${bank:,.0f}, stakes {float(p['stake_pct']):.1%} of equity (min ${float(p['min_stake']):g}). "
             f"Buys the {float(p['min_price']) * 100:g}-{float(p['max_price']) * 100:g}¢ side of "
             f"{', '.join(p['kinds'])} markets ending in {p['min_days']}-{p['max_days']} days, at the real ask "
             f"(≤ {float(p['max_slippage']) * 100:g}¢ over the last price) plus the market's taker fee; holds to resolution.", "",
             f"**Equity ${equity(bets, bank):,.2f}** (cash ${cash(bets, bank):,.2f}, ${sum(b.stake for b in open_):,.2f} in "
             f"{len(open_)} open bets).", "",
             f"Settled: {len(done)} bets, {sum(b.status == 'won' for b in done)} won, P&L **${pnl:+,.2f}** on ${staked:,.2f} staked "
             f"(ROI {pnl / staked:+.1%})." if staked else "Settled: none yet.", ""]
    if done:
        exp = sum(b.last_price for b in done) / len(done)
        lines += [f"Win rate {sum(b.status == 'won' for b in done) / len(done):.1%} against an average price of {exp:.1%} "
                  f"(the backtest: about 20-21% at 15¢). Fees paid ${sum(b.fee for b in bets):,.2f}; average fill "
                  f"{sum(b.avg_price - b.last_price for b in bets) / len(bets) * 100:+.2f}¢ over the last price.", "",
                  "| kind | settled | won | win rate | avg price | P&L | ROI |", "|---|---|---|---|---|---|---|"]
        for k in sorted({b.kind for b in done}):
            g = [b for b in done if b.kind == k]
            st = sum(b.stake for b in g)
            lines.append(f"| {k} | {len(g)} | {sum(b.status == 'won' for b in g)} | "
                         f"{sum(b.status == 'won' for b in g) / len(g):.0%} | {sum(b.last_price for b in g) / len(g) * 100:.1f}¢ | "
                         f"${sum(b.pnl for b in g):+,.2f} | {sum(b.pnl for b in g) / st:+.0%} |")
    if last_run:
        lines += ["", f"Last run: scanned {last_run['scanned']} new markets, placed {last_run['placed']}, settled "
                  f"{last_run['settled']}. Skipped: " + ", ".join(f"{k} {v}" for k, v in sorted(last_run['skipped'].items()))]
    lines += ["", "Latest bets:", "", "| placed | market | kind | price | paid | stake | status | P&L |",
              "|---|---|---|---|---|---|---|---|"]
    for b in sorted(bets, key=lambda b: -b.placed_ts)[:25]:
        lines.append(f"| {day(b.placed_ts)} | {b.question[:55]} | {b.kind} | {b.last_price * 100:.1f}¢ | "
                     f"{b.avg_price * 100:.1f}¢ | ${b.stake:.2f} | {b.status} | "
                     f"{'' if b.status == 'open' else f'${b.pnl:+.2f}'} |")
    return "\n".join(lines) + "\n"
