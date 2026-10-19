"""Report: metrics per wallet x delay x category, bootstrap intervals, go/no-go, CSV and HTML outputs."""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .db import insert_many

log = logging.getLogger(__name__)

CATEGORIES = ("all", "short_term_crypto", "other")


@dataclass
class LotRow:
    ts: int
    close_ts: int
    entry: float
    stake: float
    pnl: float


def roi(lots: list[LotRow]) -> float | None:
    staked = sum(l.stake for l in lots)
    return sum(l.pnl for l in lots) / staked if staked > 0 else None


def max_drawdown(lots: list[LotRow]) -> float:
    """Worst peak-to-trough fall, in dollars, of cumulative P&L ordered by close time."""
    peak = equity = worst = 0.0
    for l in sorted(lots, key=lambda l: (l.close_ts, l.ts)):
        equity += l.pnl
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def bootstrap_roi_ci(lots: list[LotRow], samples: int, level: float, seed: int) -> tuple[float | None, float | None]:
    if len(lots) < 2:
        return None, None
    rng = np.random.default_rng(seed)
    pnl = np.array([l.pnl for l in lots])
    stake = np.array([l.stake for l in lots])
    idx = rng.integers(0, len(lots), size=(samples, len(lots)))
    rois = pnl[idx].sum(axis=1) / stake[idx].sum(axis=1)
    a = (1 - level) / 2
    return float(np.quantile(rois, a)), float(np.quantile(rois, 1 - a))


def monthly_positive(lots: list[LotRow], end_ts: int, months: int, month_days: int) -> list[bool | None]:
    """P&L sign in consecutive month_days buckets ending at end_ts, oldest first. None = no trades."""
    out = []
    for k in range(months, 0, -1):
        lo, hi = end_ts - k * month_days * 86400, end_ts - (k - 1) * month_days * 86400
        bucket = [l for l in lots if lo <= l.close_ts < hi]
        out.append(sum(l.pnl for l in bucket) > 0 if bucket else None)
    return out


def _load(con):
    """lots[(wallet, mode, delay)] -> rows; skips[(wallet, delay)] -> [(category, reason)]; open counts."""
    lots: dict[tuple, list[tuple[str, LotRow]]] = defaultdict(list)
    skips: dict[tuple, list[tuple[str, str]]] = defaultdict(list)
    opens: Counter = Counter()
    for w, mode, d, cat, status, reason, ts, close_ts, entry, stake, pnl in con.execute("""
        SELECT wallet, mode, delay_s, category, status, skipped_reason, ts, close_ts, copy_price, stake, pnl
        FROM sim_trades
    """).fetchall():
        if status == "closed":
            lots[(w, mode, d)].append((cat, LotRow(ts, close_ts, entry, stake, pnl)))
        elif status == "skipped":
            skips[(w, d)].append((cat, reason))
        else:
            opens[(w, mode, d, cat)] += 1
    return lots, skips, opens


def _pick(rows, category):
    return [l for c, l in rows if category == "all" or c == category]


def compute(con, cfg) -> tuple[list[dict], list[dict]]:
    """Fill sim_results; return (result rows, per-wallet summaries with go/no-go)."""
    rc = cfg["report"]
    gng = rc["go_no_go"]
    delays = [int(d) for d in cfg["simulate"]["delays_s"]]
    lots, skips, opens = _load(con)
    wallets = sorted({k[0] for k in lots} | {k[0] for k in skips})
    end_ts = int(time.time())

    results, summaries = [], []
    for w in wallets:
        wallet_lots = lots.get((w, "wallet", 0), [])
        for cat in CATEGORIES:
            own = _pick(wallet_lots, cat)
            own_roi = roi(own)
            for d in delays:
                mine = _pick(lots.get((w, "copy", d), []), cat)
                sk = [r for c, r in skips.get((w, d), []) if cat == "all" or c == cat]
                if not mine and not sk:
                    continue
                copy_roi = roi(mine)
                lo, hi = bootstrap_roi_ci(mine, int(rc["bootstrap_samples"]), float(rc["ci_level"]), int(rc["seed"]))
                n_open = sum(v for (ww, m, dd, c), v in opens.items()
                             if ww == w and m == "copy" and dd == d and (cat == "all" or c == cat))
                results.append({
                    "wallet": w, "delay_s": d, "category": cat, "trades": len(mine), "skipped": len(sk),
                    "skipped_reasons": json.dumps(dict(Counter(sk))), "open_positions": n_open,
                    "staked": sum(l.stake for l in mine), "pnl": sum(l.pnl for l in mine),
                    "copy_roi": copy_roi, "wallet_roi": own_roi,
                    "edge_decay": copy_roi / own_roi if copy_roi is not None and own_roi and own_roi > 0 else None,
                    "win_rate": sum(l.pnl > 0 for l in mine) / len(mine) if mine else None,
                    "avg_entry": sum(l.entry for l in mine) / len(mine) if mine else None,
                    "ci_low": lo, "ci_high": hi, "drawdown": max_drawdown(mine),
                })

        key = _pick(lots.get((w, "copy", int(gng["delay_s"])), []), "all")
        months = monthly_positive(key, end_ts, int(gng["months_window"]), int(gng["month_days"]))
        head = next((r for r in results if r["wallet"] == w and r["category"] == "all"
                     and r["delay_s"] == int(gng["delay_s"])), None)
        checks = {
            "roi_positive": bool(head and head["copy_roi"] is not None and head["copy_roi"] > 0),
            "ci_above_zero": bool(head and head["ci_low"] is not None and head["ci_low"] > 0),
            "enough_trades": bool(head and head["trades"] >= int(gng["min_copyable_trades"])),
            "months_positive": sum(bool(m) for m in months) >= int(gng["months_positive"]),
        }
        summaries.append({"wallet": w, "go": all(checks.values()), "checks": checks, "months": months,
                          "wallet_roi": roi(_pick(wallet_lots, "all")),
                          "wallet_trades": len(wallet_lots)})

    con.execute("DELETE FROM sim_results")
    cols = ["wallet", "delay_s", "category", "trades", "skipped", "skipped_reasons", "open_positions", "staked",
            "pnl", "copy_roi", "wallet_roi", "edge_decay", "win_rate", "avg_entry", "ci_low", "ci_high", "drawdown"]
    insert_many(con, "sim_results", [tuple(r[c] for c in cols) for r in results], "INSERT")
    return results, summaries


# ---- outputs -------------------------------------------------------------

def write_csvs(con, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, sql in {
        "results.csv": "SELECT * FROM sim_results ORDER BY wallet, category, delay_s",
        "trades.csv": "SELECT * FROM sim_trades ORDER BY wallet, mode, delay_s, ts",
        "wallet_scores.csv": "SELECT * FROM wallet_scores ORDER BY passed DESC, wallet",
    }.items():
        cur = con.execute(sql)
        with open(out / name, "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow([d[0] for d in cur.description])
            wr.writerows(cur.fetchall())


def _pct(v, digits=1):
    return "–" if v is None else f"{v * 100:+.{digits}f}%"


def _short(w):
    return f"{w[:6]}…{w[-4:]}"


def edge_decay_svg(points: list[dict], wallet_roi: float | None) -> str:
    """Copy ROI by delay with 90% interval whiskers, against the wallet's own ROI."""
    W, H, L, R, T, B = 300, 150, 44, 10, 10, 26
    vals = [0.0] + [v for p in points for v in (p["copy_roi"], p["ci_low"], p["ci_high"]) if v is not None]
    if wallet_roi is not None:
        vals.append(wallet_roi)
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.1 or 0.05
    lo, hi = lo - pad, hi + pad
    n = len(points)

    def x(i):
        return L + (W - L - R) * (i + 0.5) / max(n, 1)

    def y(v):
        return T + (H - T - B) * (hi - v) / (hi - lo)

    parts = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Copy ROI by delay">']
    for v in (lo + pad, 0.0, hi - pad):
        parts.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="{"zero" if v == 0 else "grid"}"/>'
                     f'<text x="{L - 6}" y="{y(v) + 3:.1f}" class="tick" text-anchor="end">{v * 100:.0f}%</text>')
    if wallet_roi is not None:
        parts.append(f'<line x1="{L}" x2="{W - R}" y1="{y(wallet_roi):.1f}" y2="{y(wallet_roi):.1f}" class="ref">'
                     f'<title>Wallet ROI {_pct(wallet_roi)}</title></line>')
    path = [(x(i), y(p["copy_roi"])) for i, p in enumerate(points) if p["copy_roi"] is not None]
    if len(path) > 1:
        parts.append('<polyline class="series" points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in path) + '"/>')
    for i, p in enumerate(points):
        label = p["delay_label"]
        parts.append(f'<text x="{x(i):.1f}" y="{H - 8}" class="tick" text-anchor="middle">{label}</text>')
        if p["copy_roi"] is None:
            continue
        tip = (f"{label} delay: copy ROI {_pct(p['copy_roi'])} (90% CI {_pct(p['ci_low'])} to "
               f"{_pct(p['ci_high'])}), {p['trades']} trades")
        g = [f'<g class="pt"><title>{html.escape(tip)}</title>',
             f'<rect x="{x(i) - 16:.1f}" y="{T}" width="32" height="{H - T - B}" class="hit"/>']
        if p["ci_low"] is not None:
            g.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(p["ci_low"]):.1f}" y2="{y(p["ci_high"]):.1f}" class="whisker"/>')
        g.append(f'<circle cx="{x(i):.1f}" cy="{y(p["copy_roi"]):.1f}" r="4" class="dot"/></g>')
        parts.extend(g)
    parts.append("</svg>")
    return "".join(parts)


def _delay_label(d: int) -> str:
    return f"{d}s" if d < 60 else f"{d // 60}m"


CSS = """
:root{color-scheme:light;--bg:#fcfcfb;--panel:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a8984;--line:#e6e5e0;
--series:#2a78d6;--good:#008300;--bad:#e34948;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#1a1a19;--panel:#222221;
--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e86;--line:#3a3936;--series:#3987e5;--good:#3fae3f;--bad:#e66767;}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#1a1a19;--panel:#222221;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e86;
--line:#3a3936;--series:#3987e5;--good:#3fae3f;--bad:#e66767;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 8px}
.sub{color:var(--ink2);margin:0 0 16px}
.verdict{padding:14px 16px;border:1px solid var(--line);border-radius:8px;background:var(--panel);margin:16px 0}
.verdict b{font-size:16px}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:7px 10px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--line)}
th{color:var(--ink2);font-weight:600;font-size:12px;background:var(--panel);position:sticky;top:0}
td:first-child,th:first-child{text-align:left}
tr:last-child td{border-bottom:0}
.ci{color:var(--ink3);font-size:12px}
.go{color:var(--good);font-weight:600}.nogo{color:var(--ink3)}
.neg{color:var(--bad)}
code{font-size:12px}
.grid-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:10px 12px}
.card{min-width:0}.card h3{font-size:13px;margin:0 0 2px;font-weight:600;overflow-wrap:anywhere}
.card p{margin:0;color:var(--ink2);font-size:12px}
.chart{width:100%;height:auto;display:block;margin-top:6px}
.chart .grid{stroke:var(--line);stroke-width:1}
.chart .zero{stroke:var(--ink3);stroke-width:1}
.chart .ref{stroke:var(--ink2);stroke-width:1.5;stroke-dasharray:4 3}
.chart .series{fill:none;stroke:var(--series);stroke-width:2}
.chart .whisker{stroke:var(--series);stroke-width:2;stroke-linecap:round;opacity:.45}
.chart .dot{fill:var(--series);stroke:var(--panel);stroke-width:2}
.chart .hit{fill:transparent}
.chart .pt:hover .dot{r:5}
.chart .tick{fill:var(--ink3);font-size:10px}
.legend{display:flex;gap:16px;color:var(--ink2);font-size:12px;margin:4px 0 8px}
.legend i{display:inline-block;width:14px;height:0;border-top:2px solid var(--series);vertical-align:middle;margin-right:6px}
.legend i.ref{border-top:1.5px dashed var(--ink2)}
ul.reasons{margin:4px 0;padding-left:18px;color:var(--ink2)}
"""


def render_html(cfg, results: list[dict], summaries: list[dict], scores: list[tuple], generated: str) -> str:
    delays = [int(d) for d in cfg["simulate"]["delays_s"]]
    gng = cfg["report"]["go_no_go"]
    key_delay = int(gng["delay_s"])
    by = {(r["wallet"], r["category"], r["delay_s"]): r for r in results}
    summ = {s["wallet"]: s for s in summaries}

    def sort_key(s):
        r = by.get((s["wallet"], "all", key_delay))
        return -(r["copy_roi"] if r and r["copy_roi"] is not None else -9)

    ranked = sorted(summaries, key=sort_key)
    n_go = sum(s["go"] for s in summaries)
    passed = n_go >= int(gng["min_wallets"])
    cutoff = dt.datetime.fromtimestamp(cfg.cutoff_ts, dt.timezone.utc).strftime("%Y-%m-%d")

    def cls(v):
        return ' class="neg"' if v is not None and v < 0 else ""

    rows = []
    for s in ranked:
        w = s["wallet"]
        cells = [f'<td><code title="{w}">{_short(w)}</code></td>', f"<td>{_pct(s['wallet_roi'])}</td>"]
        for d in delays:
            r = by.get((w, "all", d))
            if not r:
                cells.append("<td>–</td>")
                continue
            cells.append(f"<td><span{cls(r['copy_roi'])}>{_pct(r['copy_roi'])}</span><br>"
                         f"<span class=ci>{_pct(r['ci_low'], 0)} … {_pct(r['ci_high'], 0)}</span></td>")
        k = by.get((w, "all", key_delay)) or {}
        wr, ae = k.get("win_rate"), k.get("avg_entry")
        cells.append(f"<td>{'–' if wr is None else f'{wr:.0%} / {ae * 100:.0f}¢'}</td>")
        cells.append(f"<td>{k.get('trades', 0)}</td><td>{k.get('skipped', 0)}</td>")
        cells.append(f"<td>${k.get('drawdown', 0):.0f}</td>")
        months = "".join("–" if m is None else ("+" if m else "−") for m in s["months"])
        cells.append(f"<td><code>{months}</code></td>")
        failed = [c for c, ok in s["checks"].items() if not ok]
        cells.append(f'<td class="{"go" if s["go"] else "nogo"}" title="{html.escape(", ".join(failed))}">'
                     f'{"GO" if s["go"] else "no"}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")

    cat_rows = []
    for s in ranked:
        for cat in ("short_term_crypto", "other"):
            rs = [by.get((s["wallet"], cat, d)) for d in delays]
            if not any(rs):
                continue
            cells = [f'<td><code title="{s["wallet"]}">{_short(s["wallet"])}</code></td><td>{cat}</td>',
                     f"<td>{_pct(next((r['wallet_roi'] for r in rs if r), None))}</td>"]
            for r in rs:
                if r:
                    cells.append(f"<td{cls(r['copy_roi'])}>{_pct(r['copy_roi'])} <span class=ci>({r['trades']})</span></td>")
                else:
                    cells.append("<td>–</td>")
            cat_rows.append("<tr>" + "".join(cells) + "</tr>")

    cards = []
    for s in ranked:
        pts = []
        for d in delays:
            r = by.get((s["wallet"], "all", d)) or {"copy_roi": None, "ci_low": None, "ci_high": None, "trades": 0}
            pts.append({**r, "delay_label": _delay_label(d)})
        skipped = by.get((s["wallet"], "all", key_delay))
        reasons = json.loads(skipped["skipped_reasons"]) if skipped else {}
        reason_txt = ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())) or "none"
        cards.append(f'<div class="card"><h3><code>{s["wallet"]}</code></h3>'
                     f'<p>Wallet ROI {_pct(s["wallet_roi"])} on {s["wallet_trades"]} trades · skipped @{_delay_label(key_delay)}: '
                     f'{html.escape(reason_txt)}</p>{edge_decay_svg(pts, s["wallet_roi"])}</div>')

    rejected = Counter()
    for _, ok, reason in scores:
        if not ok and reason:
            for part in reason.split("; "):
                rejected[part.split(" ")[0].rstrip(":")] += 1
    n_scored, n_pass = len(scores), sum(1 for _, ok, _ in scores if ok)
    reject_items = "".join(f"<li>{html.escape(k)}: {v}</li>" for k, v in rejected.most_common())

    head = "".join(f"<th>Copy ROI @{_delay_label(d)}</th>" for d in delays)
    cat_head = "".join(f"<th>@{_delay_label(d)}</th>" for d in delays)
    fees = ", ".join(f"{k} {v:.2%}" for k, v in cfg["simulate"]["fees"].items())
    sim = cfg["simulate"]
    verdict = (f'<b class="{"go" if passed else "nogo"}">{"GO to paper trading" if passed else "NO-GO"}</b> — '
               f'{n_go} wallet{"s" if n_go != 1 else ""} met every go criterion; {gng["min_wallets"]} needed.')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Copy-Trade Backtest</title>
<style>{CSS}</style></head><body><main>
<h1>Polymarket copy-trade backtest</h1>
<p class="sub">Generated {generated} · selection before {cutoff}, tested after · ${sim['stake_usd']:.0f} flat per copy ·
spread {sim['spread_penalty'] * 100:.0f}¢ ({sim['spread_penalty_low_volume'] * 100:.0f}¢ under ${sim['low_volume_threshold_usd']:,.0f} volume) ·
skip above {sim['max_copy_price'] * 100:.0f}¢ · fees {html.escape(fees)}</p>
<div class="verdict">{verdict}<br><span class="sub">Go criteria: copy ROI &gt; 0 at {_delay_label(key_delay)} with
the {cfg['report']['ci_level']:.0%} interval above 0, ≥ {gng['min_copyable_trades']} copyable trades, positive in ≥
{gng['months_positive']} of the last {gng['months_window']} {gng['month_days']}-day periods.</span></div>

<h2>Ranked wallets</h2>
<p class="sub">Ranked by copy ROI at {_delay_label(key_delay)}. Small grey figures are the {cfg['report']['ci_level']:.0%}
bootstrap interval. Wallet ROI is the wallet's own result on the same test period. Win rate / avg entry, trades,
skips and drawdown are at {_delay_label(key_delay)}. Months: oldest → newest, + positive, − negative, – no closed trades.</p>
<div class="scroll"><table><thead><tr><th>Wallet</th><th>Wallet ROI</th>{head}<th>Win / entry</th><th>Trades</th>
<th>Skipped</th><th>Max DD</th><th>Months</th><th>Go</th></tr></thead><tbody>{"".join(rows) or '<tr><td colspan=20>No simulated wallets.</td></tr>'}</tbody></table></div>

<h2>By category</h2>
<p class="sub">Copy ROI per delay (trades in brackets). Expect the worst decay in short-term crypto, where many top wallets are bots.</p>
<div class="scroll"><table><thead><tr><th>Wallet</th><th>Category</th><th>Wallet ROI</th>{cat_head}</tr></thead>
<tbody>{"".join(cat_rows) or '<tr><td colspan=20>–</td></tr>'}</tbody></table></div>

<h2>Edge decay</h2>
<div class="legend"><span><i></i>Copy ROI with {cfg['report']['ci_level']:.0%} interval</span><span><i class="ref"></i>Wallet's own ROI</span></div>
<div class="grid-cards">{"".join(cards)}</div>

<h2>Filter funnel</h2>
<p class="sub">{n_pass} of {n_scored} candidate wallets passed every filter. Failures by filter (a wallet can fail several):</p>
<ul class="reasons">{reject_items or '<li>none</li>'}</ul>
<p class="sub">Full detail: <code>wallet_scores.csv</code>, <code>results.csv</code>, <code>trades.csv</code>.</p>
</main></body></html>"""


def run(con, cfg) -> dict:
    results, summaries = compute(con, cfg)
    out = Path(cfg["output_dir"])
    write_csvs(con, out)
    scores = con.execute("SELECT wallet, passed, rejection_reason FROM wallet_scores").fetchall()
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (out / "report.html").write_text(render_html(cfg, results, summaries, scores, generated))
    n_go = sum(s["go"] for s in summaries)
    log.info("report written to %s (%d wallets, %d go)", out / "report.html", len(summaries), n_go)
    return {"wallets": len(summaries), "go": n_go,
            "verdict": n_go >= int(cfg["report"]["go_no_go"]["min_wallets"])}
