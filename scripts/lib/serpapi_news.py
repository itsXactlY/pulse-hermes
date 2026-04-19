"""SerpAPI News Search — Google News via SerpAPI, requires SERPAPI_KEY.

SerpAPI scrapes Google search results including Google News.
API: https://serpapi.com/search?engine=google_news&q=QUERY

Free tier: 100 searches/month. Good for comprehensive Google News coverage.
Also supports Bing News and other search engines via SerpAPI.
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List
from urllib.parse import urlencode

from . import http, log
from .relevance import token_overlap_relevance

SERPAPI_BASE_URL = "https://serpapi.com/search"

DEPTH_CONFIG = {
    "quick": 8,
    "default": 15,
    "deep": 30,
}


def _source_log(msg: str):
    log.source_log("SerpAPI", msg)


def search(
    topic: str,
    api_key: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Google News via SerpAPI.

    Supports multiple SerpAPI engines:
    - google_news: Primary news search (recommended)
    - google: General search with news tab
    - bing_news: Bing News via SerpAPI proxy
    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    results: List[Dict[str, Any]] = []

    # Try Google News first (best for news-specific results)
    google_news_results = _search_google_news(topic, api_key, count, from_date, to_date)
    results.extend(google_news_results)

    # If we got few results, supplement with general Google search
    if len(results) < count // 2:
        google_results = _search_google(topic, api_key, count // 2, from_date, to_date)
        # Deduplicate by URL
        seen_urls = {r.get("url") for r in results}
        for item in google_results:
            if item.get("url") not in seen_urls:
                # Filter for news relevance
                title_lower = item.get("title", "").lower()
                is_news = any(kw in title_lower for kw in [
                    "news", "report", "breaking", "update", "analysis",
                    "review", "opinion", "editorial", "investigation",
                ])
                if is_news or item.get("relevance", 0) > 0.3:
                    results.append(item)
                    seen_urls.add(item.get("url"))

    # Sort by relevance
    results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    results = results[:count]

    _source_log(f"Found {len(results)} SerpAPI results")
    return results


def _search_google_news(
    topic: str,
    api_key: str,
    count: int,
    from_date: str = "",
    to_date: str = "",
) -> List[Dict[str, Any]]:
    """Search Google News engine via SerpAPI."""
    params = {
        "engine": "google_news",
        "q": topic,
        "api_key": api_key,
        "gl": "us",
        "hl": "en",
        "num": str(min(count, 100)),
    }

    # Date filtering via SerpAPI's tbs parameter
    if from_date:
        try:
            from datetime import datetime, timezone
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            now = datetime.now(timezone.utc)
            days_ago = (now - from_dt.replace(tzinfo=timezone.utc)).days
            if days_ago <= 1:
                params["tbs"] = "qdr:d"  # Past day
            elif days_ago <= 7:
                params["tbs"] = "qdr:w"  # Past week
            elif days_ago <= 30:
                params["tbs"] = "qdr:m"  # Past month
            elif days_ago <= 365:
                params["tbs"] = "qdr:y"  # Past year
        except ValueError:
            pass

    url = f"{SERPAPI_BASE_URL}?{urlencode(params)}"

    try:
        data = http.get(url, timeout=20)
    except http.HTTPError as e:
        _source_log(f"SerpAPI Google News error: {e}")
        return []

    # Parse Google News results
    news_results = data.get("news_results", [])
    items = []

    for i, result in enumerate(news_results[:count]):
        title = result.get("title", "")
        snippet = result.get("snippet", "") or result.get("description", "")
        url = result.get("link", "")
        source = result.get("source", "")
        date = result.get("date", "")

        # Parse date to standard format
        if date:
            # SerpAPI returns dates like "2 hours ago", "3 days ago", "Jan 15, 2024"
            date = _normalize_date(date)

        relevance = token_overlap_relevance(topic, f"{title} {snippet}")
        # Boost for being from Google News (pre-filtered for quality)
        relevance = max(relevance, 0.35 - (i * 0.02))

        items.append({
            "id": f"serp-gn-{i + 1}",
            "title": title,
            "body": snippet[:500] if snippet else "",
            "url": url,
            "author": source,
            "date": date,
            "engagement": {},
            "relevance": round(min(1.0, relevance), 3),
            "why_relevant": f"Google News: {source}",
            "metadata": {
                "position": i + 1,
                "source": source,
            },
        })

    return items


def _search_google(
    topic: str,
    api_key: str,
    count: int,
    from_date: str = "",
    to_date: str = "",
) -> List[Dict[str, Any]]:
    """Search general Google via SerpAPI (catches news not in Google News)."""
    params = {
        "engine": "google",
        "q": f"{topic} news",
        "api_key": api_key,
        "gl": "us",
        "hl": "en",
        "num": str(min(count, 100)),
    }

    url = f"{SERPAPI_BASE_URL}?{urlencode(params)}"

    try:
        data = http.get(url, timeout=20)
    except http.HTTPError as e:
        _source_log(f"SerpAPI Google error: {e}")
        return []

    organic = data.get("organic_results", [])
    items = []

    for i, result in enumerate(organic[:count]):
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("link", "")

        relevance = token_overlap_relevance(topic, f"{title} {snippet}")
        if relevance < 0.15:
            continue

        items.append({
            "id": f"serp-g-{i + 1}",
            "title": title,
            "body": snippet[:500] if snippet else "",
            "url": url,
            "author": None,
            "date": "",
            "engagement": {},
            "relevance": round(relevance, 3),
            "why_relevant": f"Google: {title[:60]}",
            "metadata": {"position": i + 1},
        })

    return items


def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD."""
    if not date_str:
        return ""

    date_str = date_str.strip()

    # Already in standard format
    if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
        return date_str

    # Relative dates: "2 hours ago", "3 days ago", "1 week ago"
    import re
    relative = re.match(r"(\d+)\s+(hour|day|week|month|year)s?\s+ago", date_str.lower())
    if relative:
        from datetime import datetime, timedelta, timezone
        num = int(relative.group(1))
        unit = relative.group(2)
        now = datetime.now(timezone.utc)
        if unit == "hour":
            dt = now - timedelta(hours=num)
        elif unit == "day":
            dt = now - timedelta(days=num)
        elif unit == "week":
            dt = now - timedelta(weeks=num)
        elif unit == "month":
            dt = now - timedelta(days=num * 30)
        else:  # year
            dt = now - timedelta(days=num * 365)
        return dt.strftime("%Y-%m-%d")

    # "Yesterday"
    if date_str.lower() == "yesterday":
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    # Try parsing common formats: "Jan 15, 2024", "January 15, 2024"
    for fmt in ["%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"]:
        try:
            from datetime import datetime
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str[:10] if len(date_str) >= 10 else ""
