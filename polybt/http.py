"""HTTP client with an on-disk response cache, per-host rate limiting and retries."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

log = logging.getLogger(__name__)


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {url}: {body[:200]}")
        self.status = status
        self.url = url


def build_url(base: str, path: str, params: dict | None) -> str:
    clean = {k: v for k, v in sorted((params or {}).items()) if v is not None}
    query = urlencode(clean, doseq=True)
    return f"{base.rstrip('/')}/{path.lstrip('/')}" + (f"?{query}" if query else "")


class RateLimiter:
    def __init__(self, per_second: dict[str, float], default: float = 2.0):
        self.per_second = per_second
        self.default = default
        self.last: dict[str, float] = {}
        self.lock = threading.Lock()

    def wait(self, host: str) -> None:
        interval = 1.0 / float(self.per_second.get(host, self.default))
        with self.lock:
            now = time.monotonic()
            ready = self.last.get(host, 0.0) + interval
            if ready > now:
                time.sleep(ready - now)
            self.last[host] = max(now, ready)


class HttpClient:
    """GET JSON with caching.

    ttl=None caches forever (immutable data); ttl=N reuses a cached body for N seconds.
    """

    def __init__(self, cache_dir: str | Path, requests_per_second: dict | None = None,
                 timeout_s: float = 30, max_retries: int = 5, backoff_s: float = 2.0,
                 session: requests.Session | None = None):
        self.cache_dir = Path(cache_dir)
        self.limiter = RateLimiter(requests_per_second or {})
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self.session = session or requests.Session()
        self.stats = {"hits": 0, "requests": 0}

    def _cache_path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode()).hexdigest()
        return self.cache_dir / key[:2] / f"{key}.json"

    def _read_cache(self, url: str, ttl: float | None):
        p = self._cache_path(url)
        if not p.exists():
            return None
        try:
            entry = json.loads(p.read_text())
        except (OSError, ValueError):
            return None
        if ttl is not None and time.time() - entry["fetched_at"] > ttl:
            return None
        return entry

    def _write_cache(self, url: str, body) -> None:
        p = self._cache_path(url)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"url": url, "fetched_at": time.time(), "body": body}))
        os.replace(tmp, p)

    def get_json(self, base: str, path: str, params: dict | None = None, ttl: float | None = None,
                 cache: bool = True):
        """cache=False neither reads nor writes the cache (live polling)."""
        url = build_url(base, path, params)
        cached = self._read_cache(url, ttl) if cache else None
        if cached is not None:
            self.stats["hits"] += 1
            return cached["body"]

        host = urlsplit(url).hostname or ""
        for attempt in range(self.max_retries + 1):
            self.limiter.wait(host)
            self.stats["requests"] += 1
            try:
                resp = self.session.get(url, timeout=self.timeout_s)
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise
                log.warning("request error %s (%s), retrying", url, e)
                time.sleep(self.backoff_s * 2 ** attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self.max_retries:
                    raise HttpError(resp.status_code, url, resp.text)
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else self.backoff_s * 2 ** attempt
                log.warning("HTTP %s from %s, retrying in %.1fs", resp.status_code, host, delay)
                time.sleep(delay)
                continue
            if resp.status_code >= 400:
                raise HttpError(resp.status_code, url, resp.text)
            body = resp.json()
            if cache:
                self._write_cache(url, body)
            return body
        raise AssertionError("unreachable")
