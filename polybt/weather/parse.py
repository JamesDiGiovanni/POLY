"""Parse Polymarket's daily highest-temperature markets.

A city-day is one event with several binary markets, one per temperature range, e.g.

    Will the highest temperature in New York City be between 84-85°F on August 12?
    Will the highest temperature in New York City be 83°F or below on August 12?
    Will the highest temperature in London be 20°C on August 12?

They resolve to the day's high at one airport station, in whole degrees, named in the market's rules
with a link to Weather Underground (wunderground.com/history/daily/.../<ICAO>) or NOAA
(weather.gov/wrh/timeseries?site=<icao>). "Lowest temperature" markets are not parsed.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}

_Q = re.compile(r"highest temperature in (?P<city>.+?) (?:be|reach|hit) (?P<body>.+?) on "
                r"(?P<month>[A-Za-z]+)\.? (?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,? (?P<year>\d{4}))?\s*\??\s*$",
                re.IGNORECASE)
_NUM = r"(-?\d+(?:\.\d+)?)"
_DEG = r"\s*°?\s*([FC])\b"
_BETWEEN = re.compile(rf"between {_NUM}\s*(?:-|–|—|to|and)\s*{_NUM}{_DEG}", re.IGNORECASE)
_RANGE = re.compile(rf"^{_NUM}\s*(?:-|–|—|to)\s*{_NUM}{_DEG}$", re.IGNORECASE)
_BELOW = re.compile(rf"{_NUM}{_DEG}\s*or (?:below|lower|less|under)", re.IGNORECASE)
_ABOVE = re.compile(rf"{_NUM}{_DEG}\s*or (?:higher|above|more|over)", re.IGNORECASE)
_SINGLE = re.compile(rf"^(?:exactly )?{_NUM}{_DEG}$", re.IGNORECASE)
_ICAO = re.compile(r"wunderground\.com/history/daily/[^\s\"')]*?/([A-Z]{4})(?=[/\s\"')?.,;]|$)")
_NOAA = re.compile(r"weather\.gov/[^\s\"')]*?[?&]site=([A-Za-z]{4})\b")


@dataclass
class Bucket:
    city: str
    unit: str            # F | C
    lo: float | None     # inclusive whole degrees; None = open below
    hi: float | None     # inclusive whole degrees; None = open above
    month: int
    day: int
    year: int | None

    def bounds(self) -> tuple[float, float]:
        """Continuous bounds in the market's unit: a whole-degree reading r covers [r-0.5, r+0.5)."""
        return (-math.inf if self.lo is None else self.lo - 0.5,
                math.inf if self.hi is None else self.hi + 0.5)

    def contains(self, reading: float) -> bool:
        r = round(reading)
        return (self.lo is None or r >= self.lo) and (self.hi is None or r <= self.hi)


def parse_question(q: str) -> Bucket | None:
    m = _Q.search(" ".join((q or "").split()))
    if not m or m["month"].lower() not in MONTHS:
        return None
    body = m["body"].strip()
    lo = hi = None
    if b := _BETWEEN.search(body):
        lo, hi, unit = float(b[1]), float(b[2]), b[3]
    elif b := _BELOW.search(body):
        hi, unit = float(b[1]), b[2]
    elif b := _ABOVE.search(body):
        lo, unit = float(b[1]), b[2]
    elif b := _RANGE.match(body):
        lo, hi, unit = float(b[1]), float(b[2]), b[3]
    elif b := _SINGLE.match(body):
        lo = hi = float(b[1])
        unit = b[2]
    else:
        return None
    return Bucket(m["city"].strip(), unit.upper(), lo, hi, MONTHS[m["month"].lower()], int(m["day"]),
                  int(m["year"]) if m["year"] else None)


def parse_station(text: str) -> str | None:
    """ICAO code from the resolution link in a market's rules: Weather Underground or NOAA weather.gov."""
    m = _ICAO.search(text or "") or _NOAA.search(text or "")
    return m[1].upper() if m else None


def market_date(b: Bucket, end_ts: int | None) -> dt.date | None:
    """The calendar date the market is about. The year comes from the question, else from the market's
    end date (which is on or just after the day; a December day can end in January)."""
    if b.year:
        return dt.date(b.year, b.month, b.day)
    if end_ts is None:
        return None
    end = dt.datetime.fromtimestamp(end_ts, dt.timezone.utc).date()
    year = end.year - 1 if b.month == 12 and end.month == 1 else end.year
    try:
        return dt.date(year, b.month, b.day)
    except ValueError:
        return None
