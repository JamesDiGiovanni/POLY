"""Match open Polymarket and Kalshi markets that settle on the same proposition, and grade the pairs.

Matching (deliberately strict, since a wrong pair is a one-way bet, not an arbitrage):
  - text similarity: IDF-weighted overlap of significant words (numbers and dates excluded);
  - numbers (thresholds, rates, prices) must be identical sets;
  - dates must agree when both sides name one, and close times must be within a few days.
Grade A: strong text match, identical numbers and dates, close within a day, and at least one shared
resolution source (same website domain, or the same named source such as "Associated Press").
Grade B: everything else that passed matching: plausible, but settlement may differ (basis risk).
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..api import GAMMA_API, _as_list, _json_field
from .kalshi import Kalshi, _dollars

log = logging.getLogger(__name__)

STOP = set("""a an the of in on at to for by be will is are was were and or not no yes with from than as this that
these those it its into over under before after between during per any which who whom whose what when where
how market markets price prices end ending close above below least most more less greater higher lower reach
hit exceed exceeds exceeded than or-higher at-least by-the year month week day today tomorrow""".split())
SYNONYMS = {"fed": "federal", "u.s.": "us", "usa": "us", "btc": "bitcoin", "eth": "ethereum", "sol": "solana",
            "gop": "republican", "republicans": "republican", "democrats": "democrat", "dems": "democrat",
            "pres": "president", "presidential": "president", "nyc": "newyork", "ny": "newyork",
            "la": "losangeles", "sf": "sanfrancisco", "cpi": "inflation", "bps": "bp"}
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
KNOWN_SOURCES = ["associated press", "federal reserve", "bureau of labor statistics", "bls", "coingecko",
                 "cf benchmarks", "coinbase", "binance", "national weather service", "noaa", "weather underground",
                 "espn", "nfl", "nba", "mlb", "nhl", "fifa", "uefa", "ap news", "decision desk", "fox news", "cnn",
                 "bea", "census bureau", "cme", "nasdaq", "nyse", "s&p", "wikipedia", "rotten tomatoes", "box office mojo"]

_NUM = re.compile(r"(?<![\w.])([$€£]?)(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*(%|k|m|bn|b|bps|°f|°c|°)?(?![\w])", re.IGNORECASE)
_DATE = re.compile(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?",
                   re.IGNORECASE)
_URL = re.compile(r"https?://([^/\s\"')]+)", re.IGNORECASE)


@dataclass
class Ref:
    venue: str               # poly | kalshi
    id: str                  # condition id | ticker
    text: str                # what the market asks, for matching
    close_ts: int | None
    rules: str = ""
    category: str = ""
    liquidity: float = 0.0
    extra: dict = field(default_factory=dict)
    tokens: set = field(default_factory=set)
    numbers: frozenset = frozenset()
    dates: frozenset = frozenset()

    def analyse(self) -> "Ref":
        t = self.text.lower().replace("’", "'")
        dates = set()
        for mon, day, year in _DATE.findall(t):
            dates.add((MONTHS[mon.lower()], int(day)))
        t_no_dates = _DATE.sub(" ", t)
        nums = set()
        for cur, n, unit in _NUM.findall(t_no_dates):
            v = float(n.replace(",", ""))
            if not unit and 1900 <= v <= 2100 and float(v).is_integer():
                continue  # a year: too common to be informative, and often implicit on one side
            mult = {"k": 1e3, "m": 1e6, "b": 1e9, "bn": 1e9}.get(unit.lower(), 1)
            nums.add(round(v * mult, 6))
        words = re.findall(r"[a-z][a-z'.&-]+", re.sub(r"\d", " ", t_no_dates))
        toks = set()
        for w in words:
            w = SYNONYMS.get(w.strip(".'-"), w.strip(".'-"))
            if w and w not in STOP and len(w) > 1:
                toks.add(w)
        self.tokens, self.numbers, self.dates = toks, frozenset(nums), frozenset(dates)
        return self

    def sources(self) -> set[str]:
        text = f"{self.rules} {self.extra.get('sources_text', '')}".lower()
        out = {d.lower().removeprefix("www.") for d in _URL.findall(text)}
        out |= {s for s in KNOWN_SOURCES if re.search(rf"\b{re.escape(s)}\b", text)}
        return out


# ---- fetching ----------------------------------------------------------------

def _poly_pages(client, a: dict):
    """Open markets with real liquidity. Gamma returns at most 100 per page and stops paging near
    1,000 results, so the end-date range is walked in windows small enough to page through."""
    page_size, cap = 100, int(a.get("max_per_window", 1000))
    step = int(a.get("window_days", 7)) * 86400
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    iso = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for lo in range(now - step, now + int(a.get("horizon_days", 400)) * 86400, step):
        for offset in range(0, cap, page_size):
            page = _as_list(client.get_json(GAMMA_API, "/markets", {
                "active": "true", "closed": "false", "end_date_min": iso(lo), "end_date_max": iso(lo + step),
                "liquidity_num_min": a.get("min_poly_liquidity", 500), "order": "volume24hr", "ascending": "false",
                "limit": page_size, "offset": offset}, cache=False))
            yield from page
            if len(page) < page_size:
                break


def polymarket_refs(client, cfg) -> list[Ref]:
    """Open two-outcome Polymarket markets with real liquidity."""
    a = cfg["arb"]
    refs, seen = [], set()
    for m in _poly_pages(client, a):
        outcomes = [str(o) for o in _json_field(m.get("outcomes"))]
        tokens = [str(t) for t in _json_field(m.get("clobTokenIds"))]
        if len(outcomes) != 2 or len(tokens) != 2 or m.get("conditionId") in seen:
            continue
        seen.add(m.get("conditionId"))
        ev = (m.get("events") or [{}])[0] if isinstance(m.get("events"), list) else {}
        end = m.get("endDate")
        close = int(dt.datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp()) if end else None
        base = m.get("question") or ""
        if ev.get("title") and ev["title"].lower() not in base.lower():
            base = f"{ev['title']} | {base}"
        # Yes/No markets have one "yes" side. Two-outcome markets ("Lakers" vs "Celtics") are matched
        # once per outcome: holding that outcome is the YES side, the other outcome the NO side.
        sides = [(0, "")] if [o.lower() for o in outcomes] == ["yes", "no"] else [(0, outcomes[0]), (1, outcomes[1])]
        rules = " ".join(x for x in (m.get("description"), m.get("resolutionSource"), ev.get("resolutionSource")) if x)
        for idx, label in sides:
            refs.append(Ref("poly", m["conditionId"] + (f"#{idx}" if label else ""),
                            f"{base} | {label}" if label else base, close, rules=rules,
                            category=str(ev.get("category") or m.get("category") or ""),
                            liquidity=float(m.get("liquidityNum") or m.get("liquidity") or 0),
                            extra={"yes_token": tokens[idx], "no_token": tokens[1 - idx], "question": m.get("question"),
                                   "outcome": label or "Yes", "volume24h": float(m.get("volume24hr") or 0)}).analyse())
    log.info("polymarket: %d matchable sides from open two-outcome markets", len(refs))
    return refs


def kalshi_refs(kalshi: Kalshi, cfg) -> list[Ref]:
    a = cfg["arb"]
    refs = []
    for ev in kalshi.events("open", max_pages=int(a["max_kalshi_event_pages"])):
        ev_sources = " ".join(f"{x.get('name', '')} {x.get('url', '')}" for x in ev.get("settlement_sources") or []
                              if isinstance(x, dict))
        for m in ev.get("markets") or []:
            if m.get("status") not in (None, "active", "open", "initialized"):
                continue
            if str(m.get("ticker", "")).startswith(tuple(a.get("kalshi_skip_prefixes", []))):
                continue  # multi-leg combos: no one-to-one Polymarket counterpart
            parts = [ev.get("title") or "", m.get("title") or "", m.get("yes_sub_title") or m.get("subtitle") or ""]
            text = " | ".join(dict.fromkeys(p for p in parts if p))
            close = m.get("close_time") or m.get("expected_expiration_time")
            close_ts = int(dt.datetime.fromisoformat(close.replace("Z", "+00:00")).timestamp()) if close else None
            refs.append(Ref("kalshi", m["ticker"], text, close_ts,
                            rules=f"{m.get('rules_primary') or ''} {m.get('rules_secondary') or ''}",
                            category=str(ev.get("category") or ""),
                            liquidity=float(_dollars(m, "liquidity") or 0),
                            extra={"event_ticker": ev.get("event_ticker"), "series_ticker": ev.get("series_ticker"),
                                   "sources_text": ev_sources,
                                   "volume24h": float(m.get("volume_24h_fp") or m.get("volume_24h") or 0),
                                   "yes_bid": _dollars(m, "yes_bid"), "yes_ask": _dollars(m, "yes_ask")}).analyse())
    log.info("kalshi: %d open markets", len(refs))
    return refs


# ---- matching ----------------------------------------------------------------

@dataclass
class Pair:
    poly: Ref
    kalshi: Ref
    score: float
    grade: str
    shared_sources: set
    reasons: list = field(default_factory=list)


def idf_weights(refs: list[Ref]) -> dict[str, float]:
    df = Counter(t for r in refs for t in r.tokens)
    n = len(refs)
    return {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}


def similarity(a: Ref, b: Ref, idf: dict[str, float]) -> float:
    inter = sum(idf.get(t, 1) for t in a.tokens & b.tokens)
    union = sum(idf.get(t, 1) for t in a.tokens | b.tokens)
    return inter / union if union else 0.0


def consistent(p: Ref, k: Ref, max_close_days: float) -> list[str]:
    """Reasons the two can't be the same proposition (empty = consistent)."""
    why = []
    if p.numbers != k.numbers:
        why.append(f"numbers {sorted(p.numbers)} vs {sorted(k.numbers)}")
    if p.dates and k.dates and not (p.dates & k.dates):
        why.append("dates differ")
    if p.close_ts and k.close_ts and abs(p.close_ts - k.close_ts) > max_close_days * 86400:
        why.append(f"close {abs(p.close_ts - k.close_ts) / 86400:.0f} days apart")
    return why


def near_misses(polys: list[Ref], kalshis: list[Ref], cfg, top: int = 400) -> list[tuple]:
    """For the most-traded Polymarket sides: the most similar Kalshi market regardless of the rules,
    and why `match` would reject it. Diagnoses a matcher that is too strict (or a real lack of overlap)."""
    idf = idf_weights(polys + kalshis)
    index: dict[str, list[int]] = defaultdict(list)
    for i, k in enumerate(kalshis):
        for t in k.tokens:
            index[t].append(i)
    out = []
    for p in sorted(polys, key=lambda r: -r.extra.get("volume24h", 0))[:top]:
        hits = Counter(i for t in p.tokens for i in index.get(t, []) if len(index[t]) < 5000)
        best = max(((similarity(p, kalshis[i], idf), kalshis[i]) for i, _ in hits.most_common(300)),
                   key=lambda x: x[0], default=None)
        if best is None:
            out.append((p.extra.get("question"), p.extra.get("outcome"), "", 0.0, "no Kalshi market shares a word"))
            continue
        s, k = best
        why = consistent(p, k, float(cfg["arb"]["max_close_days"]))
        if s < float(cfg["arb"]["min_score"]):
            why.append(f"similarity {s:.2f} < {cfg['arb']['min_score']}")
        out.append((p.extra.get("question"), p.extra.get("outcome"), k.text, round(s, 2), "; ".join(why) or "would match"))
    return out


def match(polys: list[Ref], kalshis: list[Ref], cfg, series_sources=None) -> list[Pair]:
    a = cfg["arb"]
    idf = idf_weights(polys + kalshis)
    rare_cut = sorted(idf.values())[len(idf) // 2] if idf else 0
    index: dict[str, list[int]] = defaultdict(list)
    for i, k in enumerate(kalshis):
        for t in k.tokens:
            if idf[t] >= rare_cut:
                index[t].append(i)
    pairs = []
    for p in polys:
        hits = Counter(i for t in p.tokens if idf.get(t, 0) >= rare_cut for i in index.get(t, []))
        best = None
        for i, shared in hits.most_common(200):
            if shared < 2:
                break
            k = kalshis[i]
            if consistent(p, k, float(a["max_close_days"])):
                continue
            s = similarity(p, k, idf)
            if s >= float(a["min_score"]) and (best is None or s > best[0]):
                best = (s, k)
        if best is None:
            continue
        s, k = best
        k_sources = k.sources() | (series_sources(k) if series_sources else set())
        shared = p.sources() & k_sources
        close_days = abs(p.close_ts - k.close_ts) / 86400 if p.close_ts and k.close_ts else None
        reasons = []
        if s < float(a["grade_a_score"]):
            reasons.append(f"text similarity {s:.2f} < {a['grade_a_score']}")
        if close_days is not None and close_days > 1:
            reasons.append(f"close {close_days:.1f} days apart")
        if not shared:
            reasons.append("no shared resolution source found")
        pairs.append(Pair(p, k, s, "B" if reasons else "A", shared, reasons))
    log.info("pairs: %d (%d grade A)", len(pairs), sum(x.grade == "A" for x in pairs))
    return pairs
