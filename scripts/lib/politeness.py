"""politeness — per-host token bucket + Retry-After respect + UA
rotation + robots.txt cache.

Used by lib/bypass.py and lib/worm.py to keep the crawler well-behaved
without operator hand-holding:

    from lib import politeness
    politeness.acquire("reddit.com")       # blocks until a token is free
    headers = politeness.headers_for_host("reddit.com")
    # ... do the fetch ...
    politeness.record_response("reddit.com", status_code=200,
                               retry_after_header=resp.get("Retry-After"))

Tunables (env-overridable):

    PULSE_POLITE_RPS=1.0           sustained rate per host
    PULSE_POLITE_BURST=5           initial burst tokens per host
    PULSE_POLITE_JITTER=0.2        ±20% randomisation
    PULSE_POLITE_RATE_429=0.30     cool-down if >30% of last-window are 429
    PULSE_POLITE_COOLDOWN=60       seconds to halve every bucket on cool-down
    PULSE_POLITE_ROBOTS=1          1 = respect robots.txt; 0 = ignore (dev only)

Stdlib only. Thread-safe.
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
import urllib.parse
import urllib.robotparser
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_RPS         = float(os.environ.get("PULSE_POLITE_RPS", "1.0"))
_BURST       = int(os.environ.get("PULSE_POLITE_BURST", "5"))
_JITTER      = float(os.environ.get("PULSE_POLITE_JITTER", "0.2"))
_RATE_429    = float(os.environ.get("PULSE_POLITE_RATE_429", "0.30"))
_COOLDOWN_S  = int(os.environ.get("PULSE_POLITE_COOLDOWN", "60"))
_ROBOTS      = os.environ.get("PULSE_POLITE_ROBOTS", "1") == "1"

# Realistic UA pool. Rotated per call so target hosts can't trivially
# block us via UA. ALL are real published UAs as of 2026-Q2.
_UA_POOL = [
    # Firefox stable on a current Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Firedragon (Garuda's brand) — common on the operator's stack
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firedragon/128.0",
    # Chrome stable on macOS — looks like "regular user from a Mac"
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # curl-like — honest about being an automated client when source likes it
    "pulse-research-bot/0.0.3 (+https://remainder.online; respects-robots)",
]


@dataclass
class _HostState:
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.time)
    capacity: float = float(_BURST)
    refill_rps: float = float(_RPS)
    # rolling window of (timestamp, status_code) for last 50 requests
    recent: deque = field(default_factory=lambda: deque(maxlen=50))
    cooldown_until: float = 0.0
    # robots-parser cache
    robots_parser: Optional[urllib.robotparser.RobotFileParser] = None
    robots_fetched_at: float = 0.0


_states: dict[str, _HostState] = {}
_lock = threading.Lock()


def _host_of(url_or_host: str) -> str:
    s = url_or_host.strip().lower()
    if "://" in s:
        try:
            s = (urllib.parse.urlparse(s).hostname or "").lower()
        except ValueError:
            return ""
    if s.startswith("www."):
        s = s[4:]
    return s


def _state(host: str) -> _HostState:
    with _lock:
        st = _states.get(host)
        if st is None:
            st = _HostState()
            _states[host] = st
        return st


def _refill(st: _HostState, now: float) -> None:
    elapsed = max(0.0, now - st.last_refill)
    st.tokens = min(st.capacity, st.tokens + elapsed * st.refill_rps)
    st.last_refill = now


def acquire(url_or_host: str, *, timeout_s: float = 30.0) -> None:
    """Block until a token is available for this host. Raises TimeoutError
    if no token in `timeout_s`. Honours per-host cool-down."""
    host = _host_of(url_or_host)
    if not host:
        return
    st = _state(host)
    deadline = time.time() + timeout_s
    while True:
        now = time.time()
        with _lock:
            # Honour cool-down — sleeps until the cooldown expires
            if now < st.cooldown_until:
                sleep_for = min(st.cooldown_until - now, 5.0)
            else:
                _refill(st, now)
                if st.tokens >= 1.0:
                    st.tokens -= 1.0
                    return
                # Compute time until next token would be ready
                needed = 1.0 - st.tokens
                base = needed / max(0.01, st.refill_rps)
                sleep_for = base * (1.0 + (random.random() - 0.5) * 2 * _JITTER)
                sleep_for = max(0.01, sleep_for)
        if time.time() + sleep_for > deadline:
            raise TimeoutError(f"politeness: timeout waiting for host {host}")
        time.sleep(sleep_for)


def record_response(url_or_host: str, status_code: int,
                    retry_after_header: Optional[str] = None) -> None:
    """Feed back what happened with the last fetch. Adjusts bucket on
    Retry-After + cool-down on high-429 rate."""
    host = _host_of(url_or_host)
    if not host:
        return
    st = _state(host)
    now = time.time()
    with _lock:
        st.recent.append((now, int(status_code)))
        # Retry-After: force a hard wait on every subsequent acquire.
        if retry_after_header:
            try:
                sec = int(retry_after_header.strip())
                if sec > 0:
                    st.cooldown_until = max(st.cooldown_until, now + min(sec, 600))
                    logger.info("politeness: %s Retry-After=%ds → cooldown",
                                host, sec)
                    return
            except ValueError:
                pass
        # Otherwise check rolling 429 rate
        window = [s for ts, s in st.recent if now - ts < 120.0]
        if len(window) >= 5:
            rate429 = sum(1 for s in window if s == 429) / len(window)
            if rate429 >= _RATE_429:
                # Halve the bucket capacity + cool down for _COOLDOWN_S
                st.capacity = max(1.0, st.capacity * 0.5)
                st.refill_rps = max(0.1, st.refill_rps * 0.5)
                st.cooldown_until = max(st.cooldown_until, now + _COOLDOWN_S)
                logger.warning(
                    "politeness: %s 429-rate=%.0f%% over %d → cool-down %ds "
                    "(new rps=%.2f, cap=%.1f)",
                    host, rate429 * 100, len(window), _COOLDOWN_S,
                    st.refill_rps, st.capacity,
                )


def headers_for_host(url_or_host: str) -> dict[str, str]:
    """Pick a UA + supporting headers for this request. Rotates UA per call."""
    ua = random.choice(_UA_POOL)
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.7,de;q=0.3",
        "Accept-Encoding": "identity",  # don't ask for gzip — stdlib http doesn't decode
        "Connection": "close",
    }


def can_fetch(url: str) -> bool:
    """Cheap robots.txt check. Returns True if allowed OR robots disabled."""
    if not _ROBOTS:
        return True
    host = _host_of(url)
    if not host:
        return True
    st = _state(host)
    now = time.time()
    with _lock:
        rp = st.robots_parser
        age = now - st.robots_fetched_at
    # Re-fetch after 24h
    if rp is None or age > 86400:
        rp = urllib.robotparser.RobotFileParser()
        scheme = "https" if not url.startswith("http://") else "http"
        rp.set_url(f"{scheme}://{host}/robots.txt")
        try:
            rp.read()
        except Exception:
            # If robots.txt is unreachable, default to ALLOW (open web norm)
            rp = None
        with _lock:
            st.robots_parser = rp
            st.robots_fetched_at = now
    if rp is None:
        return True
    ua = "pulse-research-bot"
    return rp.can_fetch(ua, url)


def snapshot() -> dict:
    """Operator-facing dump for `pulse --polite-state` (debug)."""
    out = []
    now = time.time()
    with _lock:
        for host, st in sorted(_states.items()):
            window = [s for ts, s in st.recent if now - ts < 120.0]
            out.append({
                "host": host,
                "tokens": round(st.tokens, 2),
                "capacity": round(st.capacity, 2),
                "rps": round(st.refill_rps, 2),
                "recent_n": len(window),
                "recent_429_pct": round(
                    100 * sum(1 for s in window if s == 429) / max(1, len(window)), 1),
                "cooldown_remaining_s": max(0, round(st.cooldown_until - now, 1)),
            })
    return {"hosts": out, "rps_default": _RPS, "burst_default": _BURST,
            "robots_enabled": _ROBOTS}
