import datetime as dt
import math

import numpy as np
import pytest

from polybt import db
from polybt.config import load
from polybt.weather.data import daily_max_forecasts, daily_max_from_csv, decision_ts, market_rows
from polybt.weather.model import bucket_probs, evaluate, fit, to_unit, write_outputs
from polybt.weather.parse import market_date, parse_question, parse_station


@pytest.mark.parametrize("q,lo,hi,unit", [
    ("Will the highest temperature in New York City be between 84-85°F on August 12?", 84, 85, "F"),
    ("Will the highest temperature in New York City be 83°F or below on August 12?", None, 83, "F"),
    ("Will the highest temperature in Chicago be 92°F or higher on August 12?", 92, None, "F"),
    ("Will the highest temperature in London be 20°C on August 12?", 20, 20, "C"),
    ("Will the highest temperature in Toronto be -3°C or below on January 5, 2026?", None, -3, "C"),
    ("Will the highest temperature in Seoul be between 30–31 °C on July 3rd?", 30, 31, "C"),
])
def test_parse_question(q, lo, hi, unit):
    b = parse_question(q)
    assert (b.lo, b.hi, b.unit) == (lo, hi, unit)


def test_parse_rejects_other_markets_and_finds_station():
    assert parse_question("Will Bitcoin be above $100k on August 12?") is None
    assert parse_station("Source: https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA.") == "KLGA"
    assert parse_station("available here: https://www.weather.gov/wrh/timeseries?site=ksfo\n") == "KSFO"
    assert parse_station("no link here") is None
    assert parse_question("Will the lowest temperature in San Francisco be 45°F or below on October 19?") is None


def test_market_date_year_rollover():
    b = parse_question("Will the highest temperature in London be 5°C on December 31?")
    jan2 = int(dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc).timestamp())
    assert market_date(b, jan2) == dt.date(2025, 12, 31)


def test_bucket_bounds_and_probs():
    b = parse_question("Will the highest temperature in X be between 84-85°F on August 12?")
    assert b.bounds() == (83.5, 85.5) and b.contains(85.4) and not b.contains(85.5)
    p = bucket_probs(84.5, 2.0, [(-math.inf, 83.5), (83.5, 85.5), (85.5, math.inf)])
    assert sum(p) == pytest.approx(1) and p[1] == max(p) and p[0] == pytest.approx(p[2])
    assert to_unit(20, 1, "F") == (68, 1.8)


def test_fit_recovers_bias_and_spread_using_only_pre_cutoff_days():
    rng = np.random.default_rng(1)
    days = [dt.date(2025, 1, 1) + dt.timedelta(days=i) for i in range(400)]
    obs = {d: 15 + 10 * math.sin(i / 58) for i, d in enumerate(days)}
    fc = {"a": {d: obs[d] + 2 + rng.normal(0, 1.5) for d in days},
          "b": {d: obs[d] - 1 + rng.normal(0, 1.5) for d in days}}
    cutoff = days[300]
    for d in days[300:]:          # wild errors after the cutoff must not leak into the fit
        fc["a"][d] += 50
    f = fit(fc, obs, cutoff)
    assert f.bias["a"] == pytest.approx(2, abs=0.3) and f.bias["b"] == pytest.approx(-1, abs=0.3)
    assert f.sigma == pytest.approx(1.5 / math.sqrt(2), abs=0.3) and f.n == 300


def test_daily_max_from_iem_csv_uses_local_day():
    text = "station,valid,tmpf\nLGA,2026-06-01 03:51,70.0\nLGA,2026-06-01 19:51,86.0\nLGA,2026-06-02 02:51,90.0\n"
    days = daily_max_from_csv(text, "America/New_York")
    # 02:51 UTC on 2 June is 22:51 on 1 June in New York
    assert days[dt.date(2026, 6, 1)][0] == pytest.approx((90 - 32) * 5 / 9)
    assert days[dt.date(2026, 5, 31)][1] == 1


def test_daily_max_forecasts_reads_suffixed_series():
    times = [f"2026-06-01T{h:02d}:00" for h in range(24)]
    body = {"timezone": "America/New_York", "hourly": {
        "time": times,
        "temperature_2m_previous_day1_m1": [20 + h / 10 for h in range(24)],
        "temperature_2m_previous_day1_m2": [None] * 24}}
    rows, tz = daily_max_forecasts(body, ["m1", "m2"], [1])
    assert tz == "America/New_York" and rows == [("m1", 1, dt.date(2026, 6, 1), pytest.approx(22.3))]


def test_decision_time_is_morning_before_for_lead_two():
    t = decision_ts(dt.date(2026, 6, 10), 2, "America/New_York", 8)
    assert dt.datetime.fromtimestamp(t, dt.timezone.utc) == dt.datetime(2026, 6, 9, 12, tzinfo=dt.timezone.utc)


def _event(day: dt.date, ranges, winner, station="KLGA", city="New York City"):
    mon = day.strftime("%B")
    markets = []
    for i, (lo, hi) in enumerate(ranges):
        body = (f"{hi}°F or below" if lo is None else f"{lo}°F or higher" if hi is None else f"between {lo}-{hi}°F")
        markets.append({
            "conditionId": f"{day}-{i}", "question": f"Will the highest temperature in {city} be {body} on {mon} {day.day}?",
            "clobTokenIds": f'["{day}-{i}-y", "{day}-{i}-n"]', "outcomes": '["Yes", "No"]',
            "outcomePrices": '["1", "0"]' if i == winner else '["0", "1"]', "closed": True,
            "closedTime": f"{day + dt.timedelta(days=1)} 12:00:00+00", "volumeNum": 5000,
            "description": f"Resolves per https://www.wunderground.com/history/daily/us/ny/x/{station}."})
    return {"id": str(day), "title": f"Highest temperature in NYC on {mon} {day.day}?", "markets": markets}


def test_market_rows_from_events():
    rows, unparsed = market_rows([_event(dt.date(2026, 6, 1), [(None, 79), (80, 81), (82, None)], 1)])
    assert not unparsed and len(rows) == 3
    assert {r[5] for r in rows} == {"KLGA"} and [r[12] for r in rows] == [False, True, False]


@pytest.mark.parametrize("informed_market", [False, True])
def test_evaluate_end_to_end(tmp_path, informed_market):
    """Synthetic world with informative forecasts. Against a noise market the model must pass; against a
    market that already prices the winner well it must not. Only after-cutoff days count as test."""
    cfg = load(overrides={"output_dir": str(tmp_path), "weather": {"test_days": 60, "leads": [1],
                                                                  "models": ["m1"], "min_test_days": 20}})
    con = db.connect(":memory:")
    rng = np.random.default_rng(3)
    today = dt.datetime.now(dt.timezone.utc).date()
    con.execute("INSERT INTO wx_stations VALUES ('KLGA', 40.78, -73.88, 'America/New_York')")
    ranges = [(None, 69), (70, 73), (74, 77), (78, 81), (82, None)]
    events = []
    for i in range(300):
        day = today - dt.timedelta(days=300 - i)
        obs_c = 24 + 3 * math.sin(i / 20) + rng.normal(0, 1)
        obs_f = obs_c * 9 / 5 + 32
        con.execute("INSERT INTO wx_obs VALUES ('KLGA', ?, ?, 24)", [day, obs_c])
        con.execute("INSERT INTO wx_forecasts VALUES ('KLGA', 'm1', 1, ?, ?)", [day, obs_c + 1 + rng.normal(0, 0.8)])
        win = next(j for j, (lo, hi) in enumerate(ranges)
                   if (lo is None or round(obs_f) >= lo) and (hi is None or round(obs_f) <= hi))
        events.append(_event(day, ranges, win))
        t = decision_ts(day, 1, "America/New_York", 8)
        for j in range(len(ranges)):
            if informed_market:
                px = 0.9 if j == win else 0.025
            else:  # uninformed: flat-ish noisy prices
                px = 0.2 + rng.normal(0, 0.03)
            con.execute("INSERT INTO price_history VALUES (?, ?, ?)", [f"{day}-{j}-y", t - 600, px])
    rows, _ = market_rows(events)
    db.insert_many(con, "wx_markets", rows, "INSERT OR REPLACE")
    res = evaluate(con, cfg)
    test = res["by"][("test", None)]
    assert res["by"][("train", None)]["n"] > 200 and 55 <= test["n"] <= 61
    if informed_market:
        assert test["diff"] > 0 and not res["accuracy_pass"]
    else:
        assert test["diff"] < 0 and test["diff_ci"][1] < 0 and res["accuracy_pass"]
    assert "Weather early check" in write_outputs(con, cfg, res)


def test_rolling_bias_tracks_seasonal_drift_without_lookahead():
    from polybt.weather.model import predict
    days = [dt.date(2025, 1, 1) + dt.timedelta(days=i) for i in range(400)]
    obs = {d: 20.0 for d in days}
    # The model runs 3 degrees warm in "summer" (days 150-250) and 1 cold otherwise.
    fc = {"m": {d: obs[d] + (3.0 if 150 <= i < 250 else -1.0) for i, d in enumerate(days)}}
    g = fit(fc, obs, days[100])                  # long-run fit sees only the cold-bias season
    mu, sigma = predict(fc, obs, g, days[200], 1, 30, 10, 10)
    assert g.bias["m"] == pytest.approx(-1)
    assert mu == pytest.approx(20 + 3 - (30 * 3 + 10 * -1) / 40)   # mostly the recent +3 bias
    # Errors after the target day must not matter: change them and the prediction is identical.
    for d in days[201:]:
        fc["m"][d] += 40
    assert predict(fc, obs, g, days[200], 1, 30, 10, 10)[0] == pytest.approx(mu)
