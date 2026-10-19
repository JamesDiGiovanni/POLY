import json

import pytest

from polybt.api import PolymarketAPI, parse_market
from polybt.config import load
from polybt.http import HttpClient, HttpError, build_url


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)
        self.headers = {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        return self.responses.pop(0)


def client(tmp_path, responses):
    s = FakeSession(responses)
    return HttpClient(tmp_path, {"x": 1000}, backoff_s=0, session=s), s


def test_build_url_is_stable_and_drops_none():
    assert build_url("https://a/", "/p", {"b": 2, "a": 1, "c": None}) == "https://a/p?a=1&b=2"
    assert build_url("https://a", "p", {"ids": ["x", "y"]}) == "https://a/p?ids=x&ids=y"


def test_cache_hit_avoids_second_request(tmp_path):
    c, s = client(tmp_path, [FakeResp(200, [1, 2])])
    assert c.get_json("https://x", "/a", {"q": 1}) == [1, 2]
    assert c.get_json("https://x", "/a", {"q": 1}) == [1, 2]
    assert len(s.urls) == 1 and c.stats == {"hits": 1, "requests": 1}


def test_ttl_expiry_refetches(tmp_path):
    c, s = client(tmp_path, [FakeResp(200, 1), FakeResp(200, 2)])
    c.get_json("https://x", "/a", ttl=-1)
    assert c.get_json("https://x", "/a", ttl=-1) == 2


def test_retries_on_429_then_raises_on_4xx(tmp_path):
    c, s = client(tmp_path, [FakeResp(429, {}), FakeResp(200, "ok")])
    assert c.get_json("https://x", "/a") == "ok"
    c, s = client(tmp_path, [FakeResp(404, {})])
    with pytest.raises(HttpError):
        c.get_json("https://x", "/b")


class FakeClient:
    """Serves /activity from a list of rows, honouring start/offset/limit and an offset cap."""

    def __init__(self, rows, cap):
        self.rows, self.cap, self.calls = rows, cap, []

    def get_json(self, base, path, params=None, ttl=None):
        self.calls.append(dict(params))
        if params["offset"] >= self.cap:
            raise HttpError(400, path)
        sel = [r for r in self.rows if r["timestamp"] >= params["start"]]
        return sel[params["offset"]: params["offset"] + params["limit"]]


def test_activity_pagination_rewindows_past_offset_cap():
    rows = [{"timestamp": 1000 + i // 3, "transactionHash": f"h{i}"} for i in range(50)]
    cfg = load(overrides={"http": {"activity_page_size": 5, "activity_offset_cap": 20}})
    api = PolymarketAPI(FakeClient(rows, 20), cfg)
    got = list(api.activity("0xabc", 1000))
    assert {r["transactionHash"] for r in got} == {r["transactionHash"] for r in rows}


def test_parse_market_resolved_and_open():
    m = parse_market({"conditionId": "c", "question": "Q", "slug": "s", "clobTokenIds": '["1","2"]',
                      "outcomes": '["Yes","No"]', "outcomePrices": '["0","1"]', "closed": True,
                      "closedTime": "2025-01-02 03:04:05+00", "volumeNum": 1234.5})
    assert m["resolved"] and m["resolved_outcome"] == "2" and m["payouts"] == [0.0, 1.0]
    assert m["end_time"] is not None and m["volume"] == 1234.5
    m = parse_market({"conditionId": "c", "clobTokenIds": '["1","2"]', "outcomePrices": '["0.4","0.6"]',
                      "closed": False, "endDate": "2025-01-02T00:00:00Z"})
    assert not m["resolved"] and m["payouts"] == []
