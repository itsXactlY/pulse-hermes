"""Manifold Markets search — 1M+ play-money prediction markets, NO auth.

API: https://api.manifold.markets/v0/markets?term=QUERY
"""

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

MANIFOLD_SEARCH_URL = "https://api.manifold.markets/v0/search-markets"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}

_NOISE_WORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "of", "for", "and", "or", "to", "is", "are",
    "was", "were", "will", "be", "by", "with", "from", "as", "it", "its", "not", "no",
})


def _source_log(msg: str):
    log.source_log("Manifold", msg)


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Manifold Markets."""
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    params = {
        "term": topic,
        "limit": str(count),
        "sort": "liquidity",
    }

    url = f"{MANIFOLD_SEARCH_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pulse-hermes/3.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        _source_log(f"Search failed: {e}")
        return []

    if not isinstance(data, list):
        data = []

    items = []
    seen_ids = set()

    for i, market in enumerate(data[:count]):
        mid = market.get("id", "")
        if mid in seen_ids:
            continue
        seen_ids.add(mid)

        question = market.get("question", "") or ""
        description = market.get("description", "") or ""
        url = market.get("url", "") or ""
        creator = market.get("creatorUsername", "")
        created_time = market.get("createdTime", 0)

        # Probability
        probability = market.get("probability", 0) or 0

        # Volume
        volume = market.get("volume", 0) or 0
        liquidity = market.get("liquidity", 0) or 0

        # Close time
        close_time = market.get("closeTime", 0)

        # Date
        date_str = None
        if created_time:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(created_time / 1000, tz=timezone.utc)
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        # Filter noise
        informative_words = [w for w in topic.lower().split() if w not in _NOISE_WORDS and len(w) > 2]
        if informative_words:
            q_lower = question.lower()
            matches = sum(1 for w in informative_words if w in q_lower)
            if matches < min(2, len(informative_words)):
                continue

        # Relevance
        relevance = token_overlap_relevance(topic, question) * 0.6
        relevance += min(0.3, math.log1p(volume) / 15)
        relevance = min(1.0, relevance + 0.1)

        # Body
        body = f"Probability: {probability*100:.0f}% | Volume: ${volume:,.0f} | Liquidity: ${liquidity:,.0f}"
        if description:
            body = f"{body}\n{description[:300]}"

        items.append({
            "id": f"manifold-{mid[:12]}",
            "title": question[:200],
            "body": body[:500],
            "url": url,
            "author": creator,
            "date": date_str,
            "engagement": {
                "volume": volume,
                "liquidity": liquidity,
            },
            "relevance": round(relevance, 3),
            "why_relevant": f"Manifold: {probability*100:.0f}% probability",
            "metadata": {
                "probability": probability,
                "close_time": close_time,
            },
        })

    _source_log(f"Found {len(items)} Manifold markets")
    return items
