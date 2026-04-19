"""Bing News Search — news articles via Bing API, requires API key.

Uses Bing News Search API v7 for comprehensive news coverage.
API: https://api.bing.microsoft.com/v7.0/news/search

Free tier: 1000 calls/month (Bing API key from Azure).
Also supports Bing News without API key via scraping fallback.
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlencode

from . import http, log
from .relevance import token_overlap_relevance

BING_NEWS_API_URL = "https://api.bing.microsoft.com/v7.0/news/search"
BING_NEWS_FREE_URL = "https://www.bing.com/news/search"  # Fallback: scrape

DEPTH_CONFIG = {
    "quick": 8,
    "default": 15,
    "deep": 30,
}

# News categories for topic boosting
NEWS_CATEGORIES = {
    "politics": ["politics", "government", "election", "congress", "senate", "parliament"],
    "business": ["business", "market", "stock", "economy", "finance", "company"],
    "technology": ["technology", "tech", "ai", "software", "startup", "digital"],
    "science": ["science", "research", "study", "discovery", "space", "climate"],
    "health": ["health", "medical", "vaccine", "disease", "hospital", "pharma"],
    "sports": ["sports", "football", "basketball", "soccer", "baseball", "olympics"],
    "entertainment": ["entertainment", "movie", "music", "celebrity", "streaming"],
    "world": ["world", "international", "global", "foreign", "war", "conflict"],
}


def _source_log(msg: str):
    log.source_log("BingNews", msg)


def _detect_category(topic: str) -> Optional[str]:
    """Detect news category from topic for better filtering."""
    topic_lower = topic.lower()
    for category, keywords in NEWS_CATEGORIES.items():
        if any(kw in topic_lower for kw in keywords):
            return category
    return None


def search(
    topic: str,
    config: Dict[str, Any],
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Bing News for articles.

    Supports two modes:
    1. API mode: Uses Bing News Search API (requires BING_API_KEY)
    2. Fallback: Uses web_search module if Bing API unavailable
    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    api_key = config.get("BING_API_KEY")

    if api_key:
        return _search_api(topic, api_key, count, from_date, to_date)
    else:
        return _search_fallback(topic, config, count, from_date, to_date)


def _search_api(
    topic: str,
    api_key: str,
    count: int,
    from_date: str = "",
    to_date: str = "",
) -> List[Dict[str, Any]]:
    """Search via Bing News Search API."""
    params = {
        "q": topic,
        "count": str(min(count, 100)),
        "mkt": "en-US",
        "safeSearch": "Moderate",
        "sortBy": "Relevance",
    }

    # Date filtering (Bing uses freshness parameter)
    if from_date:
        try:
            from datetime import datetime, timezone
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            now = datetime.now(timezone.utc)
            days_ago = (now - from_dt.replace(tzinfo=timezone.utc)).days
            if days_ago <= 1:
                params["freshness"] = "Day"
            elif days_ago <= 7:
                params["freshness"] = "Week"
            elif days_ago <= 30:
                params["freshness"] = "Month"
        except ValueError:
            pass

    # Category boost
    category = _detect_category(topic)
    if category:
        params["category"] = category

    url = f"{BING_NEWS_API_URL}?{urlencode(params)}"
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
    }

    try:
        data = http.get(url, headers=headers, timeout=15)
    except http.HTTPError as e:
        _source_log(f"Bing API error: {e}")
        return []

    articles = data.get("value", [])
    items = []

    for i, article in enumerate(articles[:count]):
        title = article.get("name", "")
        body = article.get("description", "")[:500]
        url = article.get("url", "")
        provider = article.get("provider", [{}])
        source_name = provider[0].get("name", "Bing News") if provider else "Bing News"
        date = (article.get("datePublished") or "")[:10]

        # Engagement from Bing (if available)
        engagement = {}
        if article.get("mentions"):
            engagement["mentions"] = article["mentions"]

        relevance = token_overlap_relevance(topic, f"{title} {body}")
        # Bing API results are pre-sorted by relevance
        relevance = max(relevance, 0.4 - (i * 0.02))

        items.append({
            "id": f"bing-{i + 1}",
            "title": title,
            "body": body,
            "url": url,
            "author": source_name,
            "date": date,
            "engagement": engagement,
            "relevance": round(min(1.0, relevance), 3),
            "why_relevant": f"Bing News: {source_name}",
            "metadata": {
                "source_provider": source_name,
                "category": category,
            },
        })

    _source_log(f"Found {len(items)} Bing News results (API)")
    return items


def _search_fallback(
    topic: str,
    config: Dict[str, Any],
    count: int,
    from_date: str = "",
    to_date: str = "",
) -> List[Dict[str, Any]]:
    """Fallback: use web_search module or direct scraping.

    If we have Brave/Serper/Exa keys, delegate to web_search.
    Otherwise, try a free Bing news scrape.
    """
    # Check if we can use web_search as proxy
    if config.get("BRAVE_API_KEY") or config.get("SERPER_API_KEY") or config.get("EXA_API_KEY"):
        _source_log("Using web_search as Bing News fallback")
        from . import web_search as _web
        # Search with news-specific query
        news_query = f"{topic} news"
        items = _web.search(news_query, config, depth="default")
        # Re-tag as Bing News source
        for item in items:
            item["why_relevant"] = f"Bing News (via web): {item.get('author', 'unknown')}"
            item["id"] = f"bing-{item.get('id', 'x')}"
        return items[:count]

    # Last resort: try free Bing news scrape (may be blocked)
    _source_log("Attempting free Bing News scrape (no API key)")
    return _scrape_bing_news(topic, count)


def _scrape_bing_news(topic: str, count: int) -> List[Dict[str, Any]]:
    """Scrape Bing News search page (no API key, may be blocked)."""
    url = f"https://www.bing.com/news/search?q={quote_plus(topic)}&FORM=HDRSC6"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        _source_log(f"Bing scrape failed: {e}")
        return []

    # Basic HTML parsing to extract news items
    items = []
    import re

    # Extract news cards - Bing uses <div class="news-card">
    # Look for title + URL patterns
    card_pattern = r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]{10,200})</a>'
    matches = re.findall(card_pattern, html)

    seen_urls = set()
    for url, title in matches:
        if len(items) >= count:
            break
        # Filter out Bing internal links
        if "bing.com" in url or url in seen_urls:
            continue
        if len(title.strip()) < 10:
            continue
        seen_urls.add(url)

        relevance = token_overlap_relevance(topic, title)
        if relevance < 0.1:
            continue

        items.append({
            "id": f"bing-scrape-{len(items) + 1}",
            "title": title.strip(),
            "body": "",
            "url": url,
            "author": None,
            "date": "",
            "engagement": {},
            "relevance": round(relevance, 3),
            "why_relevant": "Bing News (scraped)",
            "metadata": {"scraped": True},
        })

    _source_log(f"Scraped {len(items)} Bing News results")
    return items
