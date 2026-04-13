"""News search module.

Uses NewsAPI.org for news article search (free tier: 100 requests/day).
"""

from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlencode

from . import http, log

DEPTH_CONFIG = {
    "quick": 5,
    "default": 10,
    "deep": 20,
}


def _source_log(msg: str):
    log.source_log("News", msg)


def search(
    topic: str,
    api_key: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search news articles via NewsAPI."""
    count = DEPTH_CONFIG.get(depth, 10)

    params = {
        "q": topic,
        "from": from_date,
        "to": to_date,
        "sortBy": "relevancy",
        "pageSize": str(count),
        "language": "en",
        "apiKey": api_key,
    }

    url = f"https://newsapi.org/v2/everything?{urlencode(params)}"

    try:
        data = http.get(url, timeout=15)
    except http.HTTPError as e:
        _source_log(f"NewsAPI search failed: {e}")
        return []

    articles = data.get("articles", [])
    items = []

    for i, article in enumerate(articles):
        items.append({
            "id": f"N-{i + 1}",
            "title": article.get("title", "") or "",
            "body": (article.get("description") or "")[:300],
            "url": article.get("url", ""),
            "author": article.get("author"),
            "date": (article.get("publishedAt") or "")[:10],
            "engagement": {},
            "relevance": max(0.3, 1.0 - i * 0.03),
            "why_relevant": f"News: {(article.get('source') or {}).get('name', 'Unknown')}",
            "source_name": (article.get("source") or {}).get("name", ""),
        })

    _source_log(f"Found {len(items)} news articles")
    return items
