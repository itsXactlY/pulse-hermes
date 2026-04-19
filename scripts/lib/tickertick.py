"""TickerTick search — crypto/blockchain focused news aggregator, NO auth required.

TickerTick aggregates news from 100+ crypto sources with topic filtering.
API: https://api.tickertick.com/v1/tickers (news feeds by topic)

Free, no API key needed. Focus: crypto, blockchain, DeFi, NFTs, Web3.
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

# TickerTick API endpoints
TICKERTICK_FEED_URL = "https://api.tickertick.com/feed"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}


def _source_log(msg: str):
    log.source_log("TickerTick", msg)


def _fetch_json(url: str, timeout: int = 15) -> Dict[str, Any]:
    """Fetch JSON from TickerTick API."""
    headers = {
        "User-Agent": "pulse-hermes/3.0",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _source_log(f"HTTP {e.code}: {e.reason}")
        return {}
    except Exception as e:
        _source_log(f"Request failed: {e}")
        return {}


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search TickerTick for crypto/blockchain news.

    TickerTick is a news feed aggregator — it aggregates stories from
    crypto/finance sources. It works best with tag-based filtering.

    Response: {"stories": [{"id", "title", "url", "site", "time", "tags", "description", "tickers"}]}
    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    results: List[Dict[str, Any]] = []
    topic_lower = topic.lower()

    # Detect crypto-relevant tags from topic
    crypto_tag_map = {
        "bitcoin": "btc", "btc": "btc",
        "ethereum": "eth", "eth": "eth",
        "solana": "sol", "sol": "sol",
        "defi": "defi",
        "nft": "nft", "nfts": "nft",
        "web3": "web3",
        "dao": "dao",
        "meme": "meme",
        "stablecoin": "stablecoin",
        "layer2": "layer2", "l2": "layer2",
        "staking": "staking",
        "gaming": "gaming",
        "metaverse": "metaverse",
        "regulation": "regulation",
        "sec": "regulation",
        "etf": "etf",
        "halving": "halving",
    }

    matched_tags = []
    for kw, tag in crypto_tag_map.items():
        if kw in topic_lower and tag not in matched_tags:
            matched_tags.append(tag)

    # Method 1: Tag-based feed (primary)
    tag_param = ",".join(matched_tags[:3]) if matched_tags else ""
    if tag_param:
        url = f"{TICKERTICK_FEED_URL}?tag={tag_param}&n={min(count, 50)}"
    else:
        url = f"{TICKERTICK_FEED_URL}?n={min(count, 50)}"

    _source_log(f"Fetching TickerTick feed: {url}")
    data = _fetch_json(url)
    stories = data.get("stories", [])

    if stories:
        for i, story in enumerate(stories[:count]):
            result = _parse_story(story, i, topic)
            if result:
                # Accept any result with minimal relevance or with crypto tags
                if result.get("relevance", 0) >= 0.05 or result.get("metadata", {}).get("tags") or result.get("metadata", {}).get("tickers"):
                    results.append(result)

    results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    results = results[:count]

    _source_log(f"Found {len(results)} TickerTick results")
    return results


def _parse_story(story: Dict[str, Any], index: int, topic: str) -> Dict[str, Any]:
    """Parse a TickerTick story into PULSE format.

    Story format: {id, title, url, site, time, favicon_url, tags, description, tickers}
    """
    title = story.get("title", "") or ""
    body = (story.get("description") or "")[:500]
    url = story.get("url", "") or ""
    source_name = story.get("site", "TickerTick") or "TickerTick"

    # Date from unix timestamp
    date = ""
    time_val = story.get("time")
    if time_val:
        try:
            from datetime import datetime, timezone
            if isinstance(time_val, (int, float)):
                date = datetime.fromtimestamp(time_val / 1000 if time_val > 1e12 else time_val, tz=timezone.utc).strftime("%Y-%m-%d")
            else:
                date = str(time_val)[:10]
        except (ValueError, OSError, OverflowError):
            pass

    # Tags and tickers
    tags = story.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tickers = story.get("tickers", [])
    if isinstance(tickers, str):
        tickers = [t.strip() for t in tickers.split(",") if t.strip()]

    # Relevance scoring
    relevance = token_overlap_relevance(topic, f"{title} {body}")
    # Boost if story has crypto tags/tickers
    if tags or tickers:
        relevance = min(1.0, relevance + 0.1)

    if not title and not url:
        return None

    return {
        "id": f"tt-{story.get('id', index)}",
        "title": title,
        "body": body,
        "url": url,
        "author": source_name,
        "date": date,
        "engagement": {},
        "relevance": round(relevance, 3),
        "why_relevant": f"Crypto: {source_name}" + (f" [{', '.join((tags + tickers)[:3])}]" if (tags or tickers) else ""),
        "metadata": {
            "tags": tags,
            "tickers": tickers,
        },
    }
