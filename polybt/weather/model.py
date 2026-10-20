"""Forecast model and the early check: is the model more accurate than the market's own prices?

Model, per station and forecast lead (fitted only on days before the cutoff):
  - each weather model's mean error against the observed high is removed (bias correction);
  - the forecast is the average of the corrected models;
  - its typical miss (standard deviation of the error) sets the spread of a normal distribution.
A range's probability is the chance the high, read in whole degrees, lands in it.

The check compares, at the same decision time, the model's probabilities with the market's
(prices normalised to sum to 1) on which range actually won: lower log loss is better. Confidence
intervals resample whole city-days. A trading preview is included but is not the full simulation.
"""
from __future__ import annotations

import csv
import datetime as dt
import logging
import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..db import insert_many
from .data import decision_ts

log = logging.getLogger(__name__)


def norm_cdf(x: float) -> float:
    if x == math.inf:
        return 1.0
    if x == -math.inf:
        return 0.0
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bucket_probs(mu: float, sigma: float, bounds: list[tuple[float, float]]) -> list[float]:
    """P(lo <= T < hi) under Normal(mu, sigma), normalised over the given ranges."""
    p = [max(0.0, norm_cdf((hi - mu) / sigma) - norm_cdf((lo - mu) / sigma)) for lo, hi in bounds]
    s = sum(p)
    return [x / s for x in p] if s > 0 else [1 / len(p)] * len(p)


@dataclass
class Fit:
    bias: dict[str, float]     # per weather model, °C
    sigma: float               # °C
    n: int


def fit(forecasts: dict[str, dict[dt.date, float]], obs: dict[dt.date, float], before: dt.date,
        min_days: int = 30, sigma_floor: float = 0.8) -> Fit | None:
    """Bias per model and spread of the corrected ensemble mean, using days strictly before `before`."""
    bias = {}
    for model, series in forecasts.items():
        errs = [series[d] - obs[d] for d in series if d < before and d in obs]
        if len(errs) >= min_days:
            bias[model] = float(np.mean(errs))
    if not bias:
        return None
    resid = []
    for d in obs:
        if d >= before:
            continue
        mu = ensemble(forecasts, bias, d)
        if mu is not None:
            resid.append(mu - obs[d])
    if len(resid) < min_days:
        return None
    return Fit(bias, max(sigma_floor, float(np.std(resid))), len(resid))


def ensemble(forecasts: dict[str, dict[dt.date, float]], bias: dict[str, float], d: dt.date) -> float | None:
    vals = [forecasts[m][d] - b for m, b in bias.items() if d in forecasts.get(m, {})]
    return float(np.mean(vals)) if vals else None


def to_unit(mu_c: float, sigma_c: float, unit: str) -> tuple[float, float]:
    return (mu_c * 9 / 5 + 32, sigma_c * 9 / 5) if unit == "F" else (mu_c, sigma_c)


@dataclass
class Row:
    """One city-day at one lead: everything the check and the trading preview need."""
    event_key: str
    city: str
    date: dt.date
    lead: int
    split: str                 # train | test
    model_p: list[float]
    market_p: list[float]      # normalised
    prices: list[float]        # raw YES prices at the decision time
    won: int                   # index of the winning range
    fee_rates: list[float] = field(default_factory=list)

    def logloss(self, which: str) -> float:
        p = (self.model_p if which == "model" else self.market_p)[self.won]
        return -math.log(min(1.0, max(1e-4, p)))


def price_at(ts: list[int], px: list[float], t: int, max_age_s: int) -> float | None:
    i = bisect_right(ts, t) - 1
    if i < 0 or t - ts[i] > max_age_s:
        return None
    return px[i]


def build_rows(con, cfg) -> tuple[list[Row], dict[str, int]]:
    w = cfg["weather"]
    cutoff = cutoff_date(cfg)
    leads = [int(x) for x in w["leads"]]
    tz = dict(con.execute("SELECT station, tz FROM wx_stations WHERE tz IS NOT NULL").fetchall())
    obs: dict[str, dict] = defaultdict(dict)
    for s, d, c in con.execute("SELECT station, date, tmax_c FROM wx_obs WHERE n_obs >= ?", [int(w["min_obs_per_day"])]).fetchall():
        obs[s][d] = c
    fc: dict[tuple, dict] = defaultdict(lambda: defaultdict(dict))
    for s, m, l, d, c in con.execute("SELECT station, model, lead, date, tmax_c FROM wx_forecasts").fetchall():
        fc[(s, l)][m][d] = c
    fits = {key: fit(series, obs[key[0]], cutoff) for key, series in fc.items()}

    events: dict[str, list] = defaultdict(list)
    for r in con.execute("""
            SELECT event_key, city, station, unit, lo, hi, date, yes_token, yes_won, coalesce(fee_rate, ?)
            FROM wx_markets WHERE resolved AND yes_won IS NOT NULL ORDER BY event_key, lo NULLS FIRST""",
                         [float(w["default_fee_rate"])]).fetchall():
        events[r[0]].append(r)
    tokens = {r[7] for rs in events.values() for r in rs}
    prices: dict[str, tuple[list, list]] = {}
    con.execute("CREATE OR REPLACE TEMP TABLE _wxtok (token_id VARCHAR)")
    insert_many(con, "_wxtok", [(t,) for t in tokens], "INSERT")
    for token, ts, p in con.execute("""SELECT p.token_id, p.timestamp, p.price FROM price_history p
                                       JOIN _wxtok USING (token_id) ORDER BY 1, 2""").fetchall():
        prices.setdefault(token, ([], []))
        prices[token][0].append(ts)
        prices[token][1].append(p)

    rows, skipped = [], defaultdict(int)
    for key, rs in events.items():
        station, unit, date = rs[0][2], rs[0][3], rs[0][6]
        winners = [i for i, r in enumerate(rs) if r[8]]
        if len(winners) != 1:
            skipped["not exactly one winning range"] += 1
            continue
        if station not in tz:
            skipped["station not located"] += 1
            continue
        bounds = [((-math.inf if r[4] is None else r[4] - 0.5), (math.inf if r[5] is None else r[5] + 0.5)) for r in rs]
        for lead in leads:
            f = fits.get((station, lead))
            mu_c = ensemble(fc[(station, lead)], f.bias, date) if f else None
            if mu_c is None:
                skipped[f"no forecast/fit (lead {lead})"] += 1
                continue
            t = decision_ts(date, lead, tz[station], int(w["decision_hour_local"]))
            px = [price_at(*prices.get(r[7], ([], [])), t, int(w["max_price_age_h"]) * 3600) for r in rs]
            if any(p is None for p in px):
                skipped[f"no market price at decision time (lead {lead})"] += 1
                continue
            mu, sd = to_unit(mu_c, f.sigma, unit)
            total = sum(px)
            if total <= 0:
                continue
            rows.append(Row(key, rs[0][1], date, lead, "train" if date < cutoff else "test",
                            bucket_probs(mu, sd, bounds), [p / total for p in px], px, winners[0],
                            [r[9] for r in rs]))
    log.info("weather rows: %d; skipped: %s", len(rows), dict(skipped))
    return rows, dict(skipped)


def cutoff_date(cfg) -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=int(cfg["weather"]["test_days"]))


def clustered_ci(values: dict[str, list[float]], samples: int = 4000, level: float = 0.9, seed: int = 7):
    """Mean over rows, CI by resampling clusters (city-days)."""
    groups = [v for v in values.values() if v]
    if len(groups) < 2:
        return None, None, None
    sums = np.array([sum(v) for v in groups])
    ns = np.array([len(v) for v in groups])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(groups), (samples, len(groups)))
    means = sums[idx].sum(1) / ns[idx].sum(1)
    a = (1 - level) / 2
    return float(sums.sum() / ns.sum()), float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def trade_preview(rows: list[Row], threshold: float, spread: float, stake: float = 10.0, max_price: float = 0.97):
    """Bet `stake` on every range where model probability exceeds the (spread-adjusted) price by `threshold`.

    A preview of phase 4: entry at the price plus spread, current taker fee formula, held to resolution.
    """
    pnl: dict[str, list[float]] = defaultdict(list)
    stakes: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        for i, (pm, px) in enumerate(zip(r.model_p, r.prices)):
            entry = px + spread
            if entry >= max_price or entry <= 0 or pm - entry <= threshold:
                continue
            shares = stake / entry
            fee = shares * r.fee_rates[i] * entry * (1 - entry)
            payout = (shares - fee / entry) if i == r.won else 0.0
            pnl[r.event_key].append(payout - stake)
            stakes[r.event_key].append(stake)
    groups = list(pnl)
    if not groups:
        return {"bets": 0, "days": 0, "roi": None, "ci": (None, None)}
    p = np.array([sum(pnl[g]) for g in groups])
    s = np.array([sum(stakes[g]) for g in groups])
    rng = np.random.default_rng(7)
    idx = rng.integers(0, len(groups), (4000, len(groups)))
    rois = p[idx].sum(1) / s[idx].sum(1)
    return {"bets": int(sum(len(v) for v in pnl.values())), "days": len(groups), "roi": float(p.sum() / s.sum()),
            "ci": (float(np.quantile(rois, 0.05)), float(np.quantile(rois, 0.95)))}


def evaluate(con, cfg) -> dict:
    w = cfg["weather"]
    rows, skipped = build_rows(con, cfg)
    out = {"rows": len(rows), "skipped": skipped, "by": {}}
    for split in ("train", "test"):
        for lead in [None] + [int(x) for x in w["leads"]]:
            sel = [r for r in rows if r.split == split and (lead is None or r.lead == lead)]
            diffs: dict[str, list[float]] = defaultdict(list)
            for r in sel:
                diffs[r.event_key].append(r.logloss("model") - r.logloss("market"))
            mean, lo, hi = clustered_ci(diffs)
            out["by"][(split, lead)] = {
                "n": len(sel), "days": len(diffs),
                "model_ll": float(np.mean([r.logloss("model") for r in sel])) if sel else None,
                "market_ll": float(np.mean([r.logloss("market") for r in sel])) if sel else None,
                "diff": mean, "diff_ci": (lo, hi)}
    test = [r for r in rows if r.split == "test"]
    out["preview"] = {th: trade_preview(test, th, float(w["spread"])) for th in w["edge_thresholds"]}
    # Accuracy edge: on the test period, model log loss below the market's with the whole 90% CI below 0.
    t = out["by"][("test", None)]
    out["accuracy_pass"] = bool(t["diff_ci"][1] is not None and t["diff_ci"][1] < 0 and t["days"] >= int(w["min_test_days"]))
    out["trading_pass"] = any(p["ci"][0] is not None and p["ci"][0] > 0 and p["days"] >= int(w["min_test_days"]) // 2
                              for p in out["preview"].values())
    out["rows_list"] = rows
    return out


# ---- outputs ---------------------------------------------------------------

def inventory(con) -> list[tuple]:
    return con.execute("""
        SELECT city, any_value(station), any_value(unit), count(DISTINCT event_key) AS days, count(*) AS markets,
               min(date), max(date), count(*) FILTER (WHERE resolved), round(median(volume))
        FROM wx_markets GROUP BY city ORDER BY days DESC""").fetchall()


def write_outputs(con, cfg, res: dict | None, unparsed: list[str] | None = None) -> str:
    out = Path(cfg["output_dir"]) / "weather"
    out.mkdir(parents=True, exist_ok=True)
    w = cfg["weather"]
    pct = lambda v: "–" if v is None else f"{v * 100:+.1f}%"
    num = lambda v, d=3: "–" if v is None else f"{v:.{d}f}"
    lines = []
    if res is not None:
        verdict = ("PASSED" if res["accuracy_pass"] or res["trading_pass"] else "FAILED")
        lines += [f"## Weather early check: {verdict}", "",
                  f"Cutoff {cutoff_date(cfg)} (train before, test after, {w['test_days']} days). Decision at "
                  f"{w['decision_hour_local']}:00 local, lead 1 = same day, lead 2 = day before. "
                  "Log loss: lower is better; diff = model minus market (negative = model more accurate). "
                  "CIs resample city-days.", "",
                  "| split | lead | city-days | rows | model log loss | market log loss | diff | 90% CI |",
                  "|---|---|---|---|---|---|---|---|"]
        for (split, lead), b in res["by"].items():
            lines.append(f"| {split} | {lead or 'all'} | {b['days']} | {b['n']} | {num(b['model_ll'])} | "
                         f"{num(b['market_ll'])} | {num(b['diff'])} | {num(b['diff_ci'][0])} … {num(b['diff_ci'][1])} |")
        lines += ["", "**Trading preview (test period, not the full simulation):** buy a range when the model's",
                  f"probability beats price + {w['spread'] * 100:.0f}¢ by the threshold; $10 a bet, fees included.", "",
                  "| threshold | bets | city-days | ROI | 90% CI |", "|---|---|---|---|---|"]
        for th, p in res["preview"].items():
            lines.append(f"| {th:.2f} | {p['bets']} | {p['days']} | {pct(p['roi'])} | {pct(p['ci'][0])} … {pct(p['ci'][1])} |")
        lines += ["", f"Rows skipped: {res['skipped']}", ""]
        with open(out / "rows.csv", "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["event", "city", "date", "lead", "split", "won", "model_p", "market_p", "prices"])
            for r in res["rows_list"]:
                wr.writerow([r.event_key, r.city, r.date, r.lead, r.split, r.won,
                             " ".join(f"{x:.3f}" for x in r.model_p), " ".join(f"{x:.3f}" for x in r.market_p),
                             " ".join(f"{x:.3f}" for x in r.prices)])
    inv = inventory(con)
    lines += ["### Inventory", "", "| city | station | unit | days | markets | first | last | resolved | median vol |",
              "|---|---|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join("–" if v is None else str(v) for v in row) + " |" for row in inv]
    n_st = con.execute("SELECT count(*), count(tz) FROM wx_stations").fetchone()
    n_obs = con.execute("SELECT count(DISTINCT station), count(*) FROM wx_obs").fetchone()
    n_fc = con.execute("SELECT count(DISTINCT station), count(DISTINCT model), count(*) FROM wx_forecasts").fetchone()
    lines += ["", f"Stations located: {n_st[0]} ({n_st[1]} with timezone). Observations: {n_obs[1]} station-days "
              f"across {n_obs[0]} stations. Forecasts: {n_fc[2]} rows, {n_fc[1]} models, {n_fc[0]} stations."]
    if unparsed:
        lines += ["", f"Unparsed questions ({len(unparsed)}), first 10:", ""] + [f"- {q}" for q in unparsed[:10]]
    text = "\n".join(lines) + "\n"
    (out / "scorecard.md").write_text(text)
    return text
