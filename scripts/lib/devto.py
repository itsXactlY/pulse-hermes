"""Dev.to search — developer blog content, NO auth required.

API: https://dev.to/api/articles?per_page=N&q=QUERY
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

DEVTO_SEARCH_URL = "https://dev.to/api/articles"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}


def _source_log(msg: str):
    log.source_log("Dev.to", msg)


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Dev.to for developer articles."""
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    params = {
        "per_page": str(min(count, 30)),
        "top": "30",  # Top articles in last 30 days
    }

    # Dev.to search uses ?q= for article search
    url = f"https://dev.to/api/articles?per_page={min(count, 30)}&tag={urllib.parse.quote(topic.split()[0]) if topic.split() else topic}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pulse-hermes/3.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        _source_log(f"Search failed: {e}")
        return []

    if not isinstance(data, list):
        return []

    items = []
    for i, article in enumerate(data[:count]):
        title = article.get("title", "") or ""
        description = article.get("description", "") or ""
        url = article.get("url", "") or ""
        published = article.get("readable_publish_date", "") or ""
        author = article.get("user", {}).get("name", "") if article.get("user") else ""
        tags = article.get("tag_list", [])
        reactions = article.get("public_reactions_count", 0) or 0
        comments = article.get("comments_count", 0) or 0
        reading_time = article.get("reading_time_minutes", 0) or 0
        cover_image = article.get("cover_image", "") or ""

        # Filter by topic relevance
        relevance = token_overlap_relevance(topic, f"{title} {description}")
        if relevance < 0.15:
            continue

        relevance += min(0.3, (reactions / 100) * 0.3)
        relevance = min(1.0, relevance + 0.1)

        items.append({
            "id": f"devto-{article.get('id', i)}",
            "title": title,
            "body": description[:500],
            "url": url,
            "author": author,
            "date": published,
            "engagement": {
                "reactions": reactions,
                "comments": comments,
            },
            "relevance": round(relevance, 3),
            "why_relevant": f"Dev.to: {', '.join(tags[:3])}",
            "metadata": {
                "tags": tags,
                "reading_time": reading_time,
            },
        })

    _source_log(f"Found {len(items)} Dev.to articles")
    return items
