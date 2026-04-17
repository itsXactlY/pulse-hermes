"""Lobsters search via JSON API (free, no auth required).

Lobsters is a curated tech link aggregator with quality-focused community.
API: https://lobste.rs/search.json?q={query}
     https://lobste.rs/newest.json
     https://lobste.rs/hottest.json
"""

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import log
from .relevance import token_overlap_relevance, extract_core_subject

LOBSTERS_SEARCH_URL = "https://lobste.rs/search.json"
LOBSTERS_NEWEST_URL = "https://lobste.rs/newest.json"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}

USER_AGENT = "pulse-hermes/3.0 (research tool)"


def _source_log(msg: str):
    log.source_log("Lobsters", msg)


def _fetch_json(url: str, timeout: int = 15) -> Optional[Any]:
    """Fetch JSON from a URL."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as e:
        _source_log(f"Fetch error: {e}")
        return None


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Lobsters for tech links.

    Returns list of normalized item dicts.
    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    core = extract_core_subject(topic)

    # Search via API
    params = {"q": core}
    url = f"{LOBSTERS_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    data = _fetch_json(url)

    if not data or not isinstance(data, list):
        # Fallback: grab newest and filter
        _source_log("Search failed, falling back to newest + filter")
        data = _fetch_json(LOBSTERS_NEWEST_URL)
        if not data or not isinstance(data, list):
            return []

        # Filter by topic relevance
        filtered = []
        for story in data:
            title = story.get("title", "")
            if token_overlap_relevance(core, title) > 0.2:
                filtered.append(story)
        data = filtered[:count]
    else:
        data = data[:count]

    items = []
    for i, story in enumerate(data):
        title = story.get("title", "")
        url = story.get("url") or story.get("comments_url", "")
        description = story.get("description", "") or ""
        score = story.get("score", 0) or 0
        comment_count = story.get("comment_count", 0) or 0
        created = story.get("created_at", "")[:10] if story.get("created_at") else None
        tags = story.get("tags", [])

        # Author
        submitter = story.get("submitter_user", {})
        author = submitter.get("username", "") if isinstance(submitter, dict) else ""

        # Comments URL
        comments_url = story.get("comments_url", "")

        # Compute relevance
        relevance = token_overlap_relevance(topic, title)
        engagement_boost = min(0.3, math.log1p(score) / 20)
        relevance = min(1.0, relevance + engagement_boost)

        items.append({
            "id": f"lobsters-{i + 1}",
            "title": title,
            "body": description[:500],
            "url": url or comments_url,
            "author": author,
            "date": created,
            "engagement": {
                "score": score,
                "comments": comment_count,
            },
            "relevance": round(relevance, 3),
            "why_relevant": f"Lobsters: {', '.join(tags[:3])}",
            "metadata": {
                "tags": tags,
                "comments_url": comments_url,
            },
        })

    _source_log(f"Found {len(items)} Lobsters stories")
    return items
