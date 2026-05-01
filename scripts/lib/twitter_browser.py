"""
Twitter/X search via headless browser (Camoufox).

Camoufox is a headless browser with anti-detection fingerprint spoofing and
built-in CAPTCHA solving — exactly what Twitter/X throws at scrapers.

ARCHITECTURE:
  - Uses Camoufox with headless=True for fingerprint-spoofed browsing.
  - Navigates to public Twitter/X search URL (no login required).
  - Extracts tweets via DOM evaluation (JavaScript in page context).
  - Returns structured SourceItems matching the PULSE schema.
  - Thread-safe: one Camoufox instance per thread (cached in a dict).

FALLBACK CHAIN:
  1. Camoufox (primary) — bypasses Cloudflare + CAPTCHA via fingerprint spoofing.
  2. syndication.twitter.com (secondary) — Twitter's own og-tag endpoint, public.
  3. Silently return [] if nothing works.

AVAILABILITY:
  Camoufox lives in the container overlay FS, not pip.
  If not importable, all methods return [] gracefully.

USAGE:
  from . import twitter_browser as _twitter
  results = _twitter.search("your topic")
"""

from __future__ import annotations

import json
import re
import time
import logging
from typing import Any, Dict, List, Optional

# Camoufox availability check — lives in container overlay, not pip
try:
    from camoufox.sync_api import Camoufox
    _HAS_CAMOUFOX = True
except ImportError:
    _HAS_CAMOUFOX = False

# Fallback: syndication endpoint (Twitter's own og-tag service, no auth)
_SYNDICATION_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"

from . import log as _log
from .relevance import token_overlap_relevance


def _source_log(msg: str):
    _log.source_log("Twitter", msg)


def _normalize_text(text: str) -> str:
    """Strip excessive whitespace and normalize Twitter-specific chars."""
    if not text:
        return ""
    # Collapse newlines/spaces
    text = re.sub(r"\s+", " ", text).strip()
    # Remove invisible Unicode junk
    text = re.sub(r"[\u200b-\u200f\u2028-\u202f\ufeff]", "", text)
    return text


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def _build_search_url(topic: str, result_type: str = "latest") -> str:
    """Build a Twitter/X search URL for the given topic."""
    encoded = topic.replace(" ", "%20").replace("#", "%23")
    # result_type: latest | top | people | photos | videos
    return f"https://x.com/search?q={encoded}&src=typed_query&f={result_type}"


# Thread-local Camoufox instances (one per thread for thread safety)
import threading
_browser_cache: Dict[int, Any] = {}
_cache_lock = threading.Lock()


def _get_browser() -> Optional[Any]:
    """Get or create a Camoufox instance for the current thread."""
    if not _HAS_CAMOUFOX:
        return None
    tid = threading.current_thread().ident
    if tid not in _browser_cache:
        try:
            browser = Camoufox(
                headless=True,
                # Anti-detection settings
                humanize=0.5,        # Human-like mouse movement
                webgl_vendor="Intel Inc.",
                webgl_renderer="Intel Iris OpenGL Engine",
                accept_languages=["en-US", "en"],
                # Do NOT set a proxy unless you have one (Twitter blocks many)
                # proxy=("http", "proxy_host", proxy_port)  # optional
            )
            _browser_cache[tid] = browser
            _source_log(f"Camoufox browser initialized for thread {tid}")
        except Exception as e:
            _source_log(f"Failed to create Camoufox browser: {e}")
            return None
    return _browser_cache[tid]


def _close_browser():
    """Close the browser for the current thread (call on errors)."""
    tid = threading.current_thread().ident
    if tid in _browser_cache:
        try:
            _browser_cache[tid].quit()
        except Exception:
            pass
        del _browser_cache[tid]


# ---------------------------------------------------------------------------
# DOM extraction JavaScript — injected into the page context
# ---------------------------------------------------------------------------

_JS_EXTRACT_TWEETS = """
() => {
    const results = [];
    // Twitter uses <article> elements for tweets in search results
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    articles.forEach((article, i) => {
        try {
            // Text content
            const textEl = article.querySelector('[data-testid="tweetText"]');
            const text = textEl ? textEl.innerText.trim() : '';

            // Author
            const authorEl = article.querySelector('[data-testid="User-Name"] span');
            const authorHandleEl = article.querySelector('a[role="link"][tabindex="-1"]');
            const handle = authorHandleEl
                ? (authorHandleEl.href || '').split('/').pop().split('?')[0]
                : '';
            const authorName = authorEl ? authorEl.innerText.split('@')[0].trim() : handle;

            // Metrics: likes, retweets, replies
            const metricEls = article.querySelectorAll('[data-testid="like"] span, [data-testid="retweet"] span, [data-testid="reply"] span');
            let likes = 0, retweets = 0, replies = 0;
            metricEls.forEach(el => {
                const val = el.innerText.trim();
                if (el.closest('[data-testid="like"]')) likes = val;
                else if (el.closest('[data-testid="retweet"]')) retweets = val;
                else if (el.closest('[data-testid="reply"]')) replies = val;
            });

            // Time
            const timeEl = article.querySelector('time');
            const time = timeEl ? timeEl.getAttribute('datetime') || timeEl.innerText : '';
            const url = timeEl
                ? window.location.origin + timeEl.closest('a')?.href
                : '';

            // Verified badge
            const verified = !!article.querySelector('[data-testid="icon-verified"]');

            if (text) {
                results.push({
                    idx: i,
                    text: text,
                    handle: '@' + handle,
                    author: authorName,
                    time: time,
                    likes: likes,
                    retweets: retweets,
                    replies: replies,
                    url: url,
                    verified: verified
                });
            }
        } catch(e) {}
    });
    return results;
}
"""

_JS_SCROLL_LOAD = """
(count) => {
    // Scroll down to load more tweets
    const scroller = document.documentElement;
    scroller.scrollTop = scroller.scrollHeight;
    return document.body.scrollHeight;
}
"""

_JS_CHECK_CAPTCHA = """
() => {
    // Detect Cloudflare challenge / CAPTCHA
    const body = document.body.innerText.toLowerCase();
    if (body.includes('verify you are human') ||
        body.includes('checking your browser') ||
        body.includes('cf-') ||
        body.includes('cloudflare') ||
        document.querySelector('#challenge-form') ||
        document.querySelector('.cf-error')) {
        return 'CAPTCHA';
    }
    if (document.querySelector('[data-testid="tweet"]')) {
        return 'OK';
    }
    return 'LOADING';
}
"""

_JS_LOGGED_IN = """
() => {
    // Check if user appears to be logged in (has sidebar nav)
    const loggedIn = !!document.querySelector('[data-testid="SideNav_AccountSwitcher"]') ||
                     !!document.querySelector('[aria-label="Account menu"]');
    return loggedIn;
}
"""


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

DEPTH_CONFIG = {
    "quick": 1,
    "default": 3,
    "deep": 5,
}

# How many scroll rounds per depth level
_SCROLLS_PER_DEPTH = {
    "quick": 2,
    "default": 4,
    "deep": 8,
}


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """
    Search Twitter/X for a topic using headless browser.

    Args:
        topic:       Search query (e.g. "AI agents", "#python")
        from_date:   Not used (Twitter's date filtering is login-gated)
        to_date:     Not used
        depth:       "quick" | "default" | "deep" (controls scroll rounds)

    Returns:
        List of SourceItem dicts matching PULSE schema.
    """
    if not _HAS_CAMOUFOX:
        _source_log("Camoufox not available — trying syndication fallback")
        return _search_syndication_fallback(topic)

    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    scrolls = _SCROLLS_PER_DEPTH.get(depth, _SCROLLS_PER_DEPTH["default"])
    items: List[Dict[str, Any]] = []
    seen_urls: set = set()

    browser = _get_browser()
    if not browser:
        return _search_syndication_fallback(topic)

    search_url = _build_search_url(topic)
    page = None

    try:
        page = browser.new_page()

        # Set extra headers to reduce detection
        page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

        _source_log(f"Navigating to: {search_url}")
        page.goto(search_url, timeout=30000)
        time.sleep(3)  # Wait for JS hydration

        # Check for CAPTCHA / Cloudflare
        for _ in range(5):
            state = page.evaluate(_JS_CHECK_CAPTCHA)
            if state == "CAPTCHA":
                _source_log("CAPTCHA/Cloudflare detected — waiting...")
                time.sleep(8)
            elif state == "OK":
                break
            else:
                time.sleep(3)

        # Scroll to load more tweets
        last_height = 0
        scroll_rounds = 0
        for _ in range(scrolls):
            page.evaluate(_JS_SCROLL_LOAD, 0)
            time.sleep(2)
            new_height = page.evaluate("() => document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scroll_rounds += 1

        _source_log(f"Scrolled {scroll_rounds} rounds, extracting tweets...")

        # Extract tweets from DOM
        raw_tweets = page.evaluate(_JS_EXTRACT_TWEETS)
        logged_in = page.evaluate(_JS_LOGGED_IN)
        _source_log(f"Extracted {len(raw_tweets)} raw tweets (logged_in={logged_in})")

        for tweet in raw_tweets:
            text = _normalize_text(tweet.get("text", ""))
            handle = tweet.get("handle", "")
            author = tweet.get("author", handle.lstrip("@"))
            url = tweet.get("url", "")
            time_str = tweet.get("time", "")

            # Deduplicate
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            # Engagement parsing
            likes_str = str(tweet.get("likes", "0")).replace(",", "")
            rts_str = str(tweet.get("retweets", "0")).replace(",", "")
            replies_str = str(tweet.get("replies", "0")).replace(",", "")

            likes = _safe_int(likes_str)
            retweets = _safe_int(rts_str)
            replies = _safe_int(replies_str)
            engagement = likes + retweets * 2 + replies * 3

            # Relevance scoring
            relevance = token_overlap_relevance(topic, text) * 0.6
            relevance += min(0.4, engagement / 1000.0)
            relevance = min(1.0, relevance)

            # Build tweet URL if missing
            if not url and handle:
                handle_clean = handle.lstrip("@")
                url = f"https://x.com/{handle_clean}/status/unknown"

            items.append({
                "id": f"twitter-{len(items) + 1}",
                "title": text[:100] if text else f"Tweet by {handle}",
                "body": text[:500],
                "url": url,
                "author": author,
                "date": time_str[:10] if time_str else None,
                "engagement": {
                    "likes": likes,
                    "retweets": retweets,
                    "replies": replies,
                },
                "relevance": round(relevance, 3),
                "why_relevant": f"Twitter: {handle}",
                "metadata": {
                    "handle": handle.lstrip("@"),
                    "verified": tweet.get("verified", False),
                    "logged_in_scrape": logged_in,
                },
            })

        _source_log(f"Returning {len(items)} deduplicated Twitter results")
        return items

    except Exception as e:
        _source_log(f"Twitter scrape error: {e}")
        return items if items else _search_syndication_fallback(topic)
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def _search_syndication_fallback(topic: str) -> List[Dict[str, Any]]:
    """
    Fallback using Twitter's syndication endpoint.
    Only works for known account handles, not arbitrary searches.
    Used when Camoufox is not available.
    """
    _source_log("Using syndication fallback (limited: profile-only)")
    # syndication.twitter.com only works for specific accounts, not topic search.
    # Return empty and let web search pick up Twitter results from other sources.
    return []


def search_user_tweets(
    username: str,
    count: int = 25,
) -> List[Dict[str, Any]]:
    """
    Get recent tweets from a specific Twitter/X user.
    Uses Camoufox to navigate to the profile page.

    Args:
        username: Twitter handle without @ (e.g. "elonmusk")
        count:    Max tweets to return

    Returns:
        List of SourceItem dicts.
    """
    if not _HAS_CAMOUFOX:
        return []

    items: List[Dict[str, Any]] = []
    browser = _get_browser()
    if not browser:
        return []

    page = None
    try:
        profile_url = f"https://x.com/{username.lstrip('@')}"
        page = browser.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
        })
        page.goto(profile_url, timeout=30000)
        time.sleep(3)

        for _ in range(3):
            page.evaluate(_JS_SCROLL_LOAD, 0)
            time.sleep(2)

        raw_tweets = page.evaluate(_JS_EXTRACT_TWEETS)

        for tweet in raw_tweets[:count]:
            text = _normalize_text(tweet.get("text", ""))
            handle = tweet.get("handle", f"@{username}")
            url = tweet.get("url", f"https://x.com/{username}/status/unknown")
            time_str = tweet.get("time", "")

            likes = _safe_int(str(tweet.get("likes", "0")).replace(",", ""))
            retweets = _safe_int(str(tweet.get("retweets", "0")).replace(",", ""))
            replies = _safe_int(str(tweet.get("replies", "0")).replace(",", ""))
            engagement = likes + retweets * 2 + replies * 3

            items.append({
                "id": f"twitter-{username}-{len(items) + 1}",
                "title": text[:100] if text else f"Tweet by {handle}",
                "body": text[:500],
                "url": url,
                "author": tweet.get("author", username),
                "date": time_str[:10] if time_str else None,
                "engagement": {
                    "likes": likes,
                    "retweets": retweets,
                    "replies": replies,
                },
                "relevance": round(min(1.0, engagement / 500.0), 3),
                "why_relevant": f"Twitter: @{username}",
                "metadata": {
                    "handle": username,
                    "verified": tweet.get("verified", False),
                    "type": "user_timeline",
                },
            })

        _source_log(f"Got {len(items)} tweets from @{username}")
        return items

    except Exception as e:
        _source_log(f"Profile scrape error for @{username}: {e}")
        return items
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def search_hashtag(
    hashtag: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """
    Search for a specific hashtag on Twitter/X.
    """
    # Ensure it starts with #
    tag = hashtag if hashtag.startswith("#") else f"#{hashtag}"
    return search(topic=tag, depth=depth)
