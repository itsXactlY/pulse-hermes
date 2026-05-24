"""bypass — multi-strategy fallback fetcher.

When a single fetch path fails (403, 429, captcha, JS-rendered, etc.),
walk a ranked list of alternative strategies for that source. Each
strategy is a callable that takes (url, source_type) and returns a
BypassResult.

Strategies registered per source-bucket:

    reddit       direct → json_endpoint → old_reddit → libreddit →
                 wayback → cross_source → headless* → manual_queue
    twitter      direct → alt_frontend (nitter) → wayback → manual_queue
    hackernews   direct → algolia_json → wayback → manual_queue
    github       direct → raw_endpoint → api_json → wayback → manual_queue
    arxiv        direct → wayback → manual_queue
    paper-journal direct → wayback → manual_queue   (we don't bypass paywalls)
    blog         direct → wayback → manual_queue
    vendor       direct → wayback → manual_queue
    unknown      direct → wayback → manual_queue

* headless only runs if PULSE_PLAYWRIGHT=1 AND the playwright extras
  are installed. Otherwise it's a no-op (skipped).

Result format is identical across strategies so worm.py only deals with
BypassResult.

CAPTCHA DETECTION: we sniff the response body for known signals
(Cloudflare challenge, hCaptcha, reCAPTCHA, Anubis) and treat that as
a failure of the current strategy → walk to the next one. We do NOT
attempt to SOLVE captchas (separate opt-in module, not bundled).

Stdlib only for the wire layer.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import quote, urlparse

from lib import politeness

logger = logging.getLogger(__name__)

_TIMEOUT          = int(os.environ.get("PULSE_BYPASS_TIMEOUT", "15"))
_MANUAL_QUEUE_PATH = os.environ.get(
    "PULSE_MANUAL_QUEUE",
    os.path.expanduser("~/.config/pulse/manual_queue.json"),
)
_PLAYWRIGHT_ENABLED = os.environ.get("PULSE_PLAYWRIGHT", "0") == "1"

# Public Nitter / Libreddit instance pools — rotated to avoid pinning to one.
# Operator can override with PULSE_NITTER_INSTANCES / PULSE_LIBREDDIT_INSTANCES.
_NITTER_INSTANCES = (os.environ.get("PULSE_NITTER_INSTANCES") or
                     "nitter.net,nitter.privacydev.net,nitter.poast.org").split(",")
_LIBREDDIT_INSTANCES = (os.environ.get("PULSE_LIBREDDIT_INSTANCES") or
                        "safereddit.com,redlib.catsarch.com,red.ngn.tf").split(",")


# Detect known captcha / WAF challenge pages so we walk the chain.
_CAPTCHA_SIGNALS = [
    re.compile(r"cloudflare", re.I),
    re.compile(r"cf-(?:challenge|please-wait)", re.I),
    re.compile(r"hcaptcha", re.I),
    re.compile(r"g-recaptcha", re.I),
    re.compile(r"anubis-challenge", re.I),
    re.compile(r"ddos protection by", re.I),
    re.compile(r"checking your browser", re.I),
]


@dataclass
class BypassResult:
    ok: bool
    url_used: str
    strategy: str
    content: str = ""           # raw response body (HTML / JSON / text)
    status_code: Optional[int] = None
    error: Optional[str] = None
    extra: dict = field(default_factory=dict)


# ─── low-level HTTP wrapper with politeness baked in ────────────────────────

def _polite_fetch(url: str, *, timeout: int = _TIMEOUT) -> tuple[int, str]:
    """Single fetch through the politeness layer. Returns (status_code, body).
    Raises on transport failure."""
    from lib import http as _http   # local import — circulars
    politeness.acquire(url, timeout_s=30)
    if not politeness.can_fetch(url):
        return 999, ""  # 999 = our convention for "blocked by robots.txt"
    headers = politeness.headers_for_host(url)
    try:
        # http.request() returns dict {status, body, headers}
        result = _http.request(url, method="GET", headers=headers, timeout=timeout)
    except Exception as exc:
        # Treat transport failure as 599 + propagate the error message in body
        politeness.record_response(url, status_code=599)
        raise
    status = int(result.get("status") or result.get("status_code") or 0)
    body = result.get("body") or result.get("text") or ""
    retry_after = (result.get("headers") or {}).get("Retry-After")
    politeness.record_response(url, status_code=status,
                                retry_after_header=retry_after)
    return status, body


def _looks_like_captcha(body: str) -> bool:
    if not body or len(body) < 100:
        return False
    head = body[:4000]
    for rx in _CAPTCHA_SIGNALS:
        if rx.search(head):
            return True
    return False


def _result_from(url: str, strategy: str, status: int, body: str) -> BypassResult:
    if _looks_like_captcha(body):
        return BypassResult(ok=False, url_used=url, strategy=strategy,
                            content=body[:2000], status_code=status,
                            error="captcha-detected")
    if status == 999:
        return BypassResult(ok=False, url_used=url, strategy=strategy,
                            status_code=status, error="blocked-by-robots")
    if 200 <= status < 300 and body:
        return BypassResult(ok=True, url_used=url, strategy=strategy,
                            content=body, status_code=status)
    return BypassResult(ok=False, url_used=url, strategy=strategy,
                        status_code=status, error=f"http-{status}")


# ─── strategies ─────────────────────────────────────────────────────────────

def strategy_direct(url: str, source_type: str) -> BypassResult:
    try:
        status, body = _polite_fetch(url)
    except Exception as exc:
        return BypassResult(ok=False, url_used=url, strategy="direct",
                            error=str(exc)[:200])
    return _result_from(url, "direct", status, body)


def strategy_wayback(url: str, source_type: str) -> BypassResult:
    """Latest snapshot on web.archive.org. Robust against most upstream
    blocks since archive.org is its own CDN."""
    wb = f"https://web.archive.org/web/2y/{url}"
    try:
        status, body = _polite_fetch(wb)
    except Exception as exc:
        return BypassResult(ok=False, url_used=wb, strategy="wayback",
                            error=str(exc)[:200])
    return _result_from(wb, "wayback", status, body)


def strategy_reddit_json(url: str, source_type: str) -> BypassResult:
    """reddit.com/X → reddit.com/X.json (works without auth, less rate-limited)."""
    if "reddit.com" not in url:
        return BypassResult(ok=False, url_used=url, strategy="reddit_json",
                            error="not-reddit")
    # Strip trailing slash + ensure .json suffix
    u = url.rstrip("/")
    if not u.endswith(".json"):
        u = u + ".json"
    try:
        status, body = _polite_fetch(u)
    except Exception as exc:
        return BypassResult(ok=False, url_used=u, strategy="reddit_json",
                            error=str(exc)[:200])
    return _result_from(u, "reddit_json", status, body)


def strategy_old_reddit(url: str, source_type: str) -> BypassResult:
    if "reddit.com" not in url or "old.reddit.com" in url:
        return BypassResult(ok=False, url_used=url, strategy="old_reddit",
                            error="not-applicable")
    alt = url.replace("://www.reddit.com", "://old.reddit.com").replace(
        "://reddit.com", "://old.reddit.com")
    try:
        status, body = _polite_fetch(alt)
    except Exception as exc:
        return BypassResult(ok=False, url_used=alt, strategy="old_reddit",
                            error=str(exc)[:200])
    return _result_from(alt, "old_reddit", status, body)


def strategy_libreddit(url: str, source_type: str) -> BypassResult:
    if "reddit.com" not in url:
        return BypassResult(ok=False, url_used=url, strategy="libreddit",
                            error="not-reddit")
    parsed = urlparse(url)
    for inst in _LIBREDDIT_INSTANCES:
        inst = inst.strip()
        if not inst:
            continue
        alt = f"https://{inst}{parsed.path}"
        if parsed.query:
            alt += f"?{parsed.query}"
        try:
            status, body = _polite_fetch(alt)
        except Exception:
            continue
        res = _result_from(alt, f"libreddit/{inst}", status, body)
        if res.ok:
            return res
    return BypassResult(ok=False, url_used=url, strategy="libreddit",
                        error="all-instances-failed")


def strategy_nitter(url: str, source_type: str) -> BypassResult:
    if "twitter.com" not in url and "x.com" not in url:
        return BypassResult(ok=False, url_used=url, strategy="nitter",
                            error="not-twitter")
    parsed = urlparse(url)
    for inst in _NITTER_INSTANCES:
        inst = inst.strip()
        if not inst:
            continue
        alt = f"https://{inst}{parsed.path}"
        try:
            status, body = _polite_fetch(alt)
        except Exception:
            continue
        res = _result_from(alt, f"nitter/{inst}", status, body)
        if res.ok:
            return res
    return BypassResult(ok=False, url_used=url, strategy="nitter",
                        error="all-instances-failed")


def strategy_hn_algolia(url: str, source_type: str) -> BypassResult:
    """HN item URL → Algolia HN-search API for full payload."""
    if "ycombinator.com" not in url:
        return BypassResult(ok=False, url_used=url, strategy="hn_algolia",
                            error="not-hn")
    m = re.search(r"id=(\d+)", url)
    if not m:
        return BypassResult(ok=False, url_used=url, strategy="hn_algolia",
                            error="no-item-id")
    api = f"https://hn.algolia.com/api/v1/items/{m.group(1)}"
    try:
        status, body = _polite_fetch(api)
    except Exception as exc:
        return BypassResult(ok=False, url_used=api, strategy="hn_algolia",
                            error=str(exc)[:200])
    return _result_from(api, "hn_algolia", status, body)


def strategy_github_raw(url: str, source_type: str) -> BypassResult:
    """github.com/X/Y/blob/main/Z → raw.githubusercontent.com/X/Y/main/Z."""
    if "github.com" not in url or "/blob/" not in url:
        return BypassResult(ok=False, url_used=url, strategy="github_raw",
                            error="not-github-blob")
    raw = url.replace("://github.com/", "://raw.githubusercontent.com/")
    raw = raw.replace("/blob/", "/")
    try:
        status, body = _polite_fetch(raw)
    except Exception as exc:
        return BypassResult(ok=False, url_used=raw, strategy="github_raw",
                            error=str(exc)[:200])
    return _result_from(raw, "github_raw", status, body)


def strategy_github_api(url: str, source_type: str) -> BypassResult:
    """github.com/X/Y → api.github.com/repos/X/Y for metadata."""
    if "github.com" not in url:
        return BypassResult(ok=False, url_used=url, strategy="github_api",
                            error="not-github")
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return BypassResult(ok=False, url_used=url, strategy="github_api",
                            error="not-repo-url")
    api = f"https://api.github.com/repos/{parts[0]}/{parts[1]}"
    try:
        status, body = _polite_fetch(api)
    except Exception as exc:
        return BypassResult(ok=False, url_used=api, strategy="github_api",
                            error=str(exc)[:200])
    return _result_from(api, "github_api", status, body)


def strategy_headless(url: str, source_type: str) -> BypassResult:
    """Playwright fallback. Disabled by default; opt in with
    PULSE_PLAYWRIGHT=1 + `pip install playwright && playwright install chromium`.
    """
    if not _PLAYWRIGHT_ENABLED:
        return BypassResult(ok=False, url_used=url, strategy="headless",
                            error="disabled (PULSE_PLAYWRIGHT=0)")
    try:
        from lib import headless as _headless
    except ImportError:
        return BypassResult(ok=False, url_used=url, strategy="headless",
                            error="playwright extras not installed")
    try:
        body = _headless.fetch(url, timeout_s=_TIMEOUT)
    except Exception as exc:
        return BypassResult(ok=False, url_used=url, strategy="headless",
                            error=str(exc)[:200])
    return _result_from(url, "headless", 200 if body else 0, body or "")


def strategy_manual_queue(url: str, source_type: str) -> BypassResult:
    """Last resort. Appends to ~/.config/pulse/manual_queue.json so the
    operator can fetch it manually + replay later. Returns a deliberate
    fail so the worm doesn't claim a hit."""
    import json
    try:
        path = _MANUAL_QUEUE_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        entry = {"url": url, "source_type": source_type,
                 "queued_at": int(time.time())}
        try:
            with open(path) as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = []
        existing.append(entry)
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as exc:
        logger.warning("manual_queue write failed: %s", exc)
    return BypassResult(ok=False, url_used=url, strategy="manual_queue",
                        error="queued-for-operator")


# ─── Per-source chains ──────────────────────────────────────────────────────

# Order matters: cheapest / most-likely-to-work first.
BYPASS_CHAINS: dict[str, list[Callable[[str, str], BypassResult]]] = {
    "reddit":         [strategy_direct, strategy_reddit_json, strategy_old_reddit,
                       strategy_libreddit, strategy_wayback, strategy_headless,
                       strategy_manual_queue],
    "twitter":        [strategy_direct, strategy_nitter, strategy_wayback,
                       strategy_headless, strategy_manual_queue],
    "hackernews":     [strategy_direct, strategy_hn_algolia, strategy_wayback,
                       strategy_manual_queue],
    "github":         [strategy_direct, strategy_github_raw, strategy_github_api,
                       strategy_wayback, strategy_manual_queue],
    "arxiv":          [strategy_direct, strategy_wayback, strategy_manual_queue],
    "paper-journal":  [strategy_direct, strategy_wayback, strategy_manual_queue],
    "blog":           [strategy_direct, strategy_wayback, strategy_headless,
                       strategy_manual_queue],
    "vendor":         [strategy_direct, strategy_wayback, strategy_headless,
                       strategy_manual_queue],
    "huggingface":    [strategy_direct, strategy_wayback, strategy_manual_queue],
    "kaggle":         [strategy_direct, strategy_wayback, strategy_manual_queue],
    "bluesky":        [strategy_direct, strategy_wayback, strategy_manual_queue],
    "mastodon":       [strategy_direct, strategy_wayback, strategy_manual_queue],
    "stackexchange":  [strategy_direct, strategy_wayback, strategy_manual_queue],
    "lemmy":          [strategy_direct, strategy_wayback, strategy_manual_queue],
    "lobsters":       [strategy_direct, strategy_wayback, strategy_manual_queue],
    "devto":          [strategy_direct, strategy_wayback, strategy_manual_queue],
    "youtube":        [strategy_direct, strategy_wayback, strategy_manual_queue],
    "doc":            [strategy_direct, strategy_wayback, strategy_manual_queue],
    "wikipedia":      [strategy_direct, strategy_wayback, strategy_manual_queue],
    "archive":        [strategy_direct, strategy_manual_queue],
    "polymarket":     [strategy_direct, strategy_wayback, strategy_manual_queue],
    "manifold":       [strategy_direct, strategy_wayback, strategy_manual_queue],
    "metaculus":      [strategy_direct, strategy_wayback, strategy_manual_queue],
    "openalex":       [strategy_direct, strategy_wayback, strategy_manual_queue],
    "semscholar":     [strategy_direct, strategy_wayback, strategy_manual_queue],
    "unknown":        [strategy_direct, strategy_wayback, strategy_manual_queue],
}


def fetch_with_bypass(url: str, source_type: str = "unknown"
                       ) -> BypassResult:
    """Walk the chain for `source_type`, return the first OK result. If
    every strategy fails, returns the last attempt's BypassResult (ok=False)."""
    chain = BYPASS_CHAINS.get(source_type) or BYPASS_CHAINS["unknown"]
    last: Optional[BypassResult] = None
    for strat in chain:
        last = strat(url, source_type)
        if last.ok:
            logger.debug("bypass: %s → %s OK", url, last.strategy)
            return last
        logger.debug("bypass: %s strategy=%s failed: %s",
                     url, last.strategy, last.error)
    return last or BypassResult(ok=False, url_used=url,
                                 strategy="(empty-chain)",
                                 error="no-strategies-defined")
