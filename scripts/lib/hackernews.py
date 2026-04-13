"""Hacker News search via Algolia API (free, no auth required)."""

import html
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
from urllib.parse import urlencode

from . import http, log
from .relevance import token_overlap_relevance, extract_core_subject

_HN_PREFIXES = re.compile(r"^(Tell HN|Show HN|Ask HN|Launch HN)\s*:\s*", re.IGNORECASE)

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items"

DEPTH_CONFIG = {
    "quick": 15,
    "default": 30,
    "deep": 60,
}

ENRICH_LIMITS = {
    "quick": 3,
    "default": 5,
    "deep": 10,
}


def _source_log(msg: str):
    log.source_log("HN", msg)


def _date_to_unix(date_str: str) -> int:
    """Convert YYYY-MM-DD to Unix timestamp (start of day UTC)."""
    import datetime
    parts = date_str.split("-")
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    dt = datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)
    return int(dt.timestamp())


def _unix_to_date(ts: int) -> str:
    """Convert Unix timestamp to YYYY-MM-DD."""
    import datetime
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _title_matches_query(title: str, query: str) -> bool:
    """Check if query terms appear in title after stripping HN prefixes."""
    if not query:
        return True
    stripped = _HN_PREFIXES.sub("", title).strip()
    check_text = stripped.lower()
    query_words = query.lower().split()
    for word in query_words:
        if word not in check_text:
            return False
    return True


def search(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Hacker News via Algolia API.

    Returns list of normalized item dicts.
    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    from_ts = _date_to_unix(from_date)
    to_ts = _date_to_unix(to_date) + 86400

    core = extract_core_subject(topic)
    _source_log(f"Searching for '{core}' (since {from_date}, count={count})")

    params = {
        "query": core,
        "tags": "story",
        "numericFilters": f"created_at_i>{from_ts},created_at_i<{to_ts},points>2",
        "hitsPerPage": str(count),
    }

    url = f"{ALGOLIA_SEARCH_URL}?{urlencode(params)}"

    try:
        response = http.get(url, timeout=30)
    except http.HTTPError as e:
        _source_log(f"Search failed: {e}")
        return []
    except Exception as e:
        _source_log(f"Search failed: {e}")
        return []

    hits = response.get("hits", [])

    # Post-filter: remove prefix-only matches
    if core:
        hits = [h for h in hits if _title_matches_query(h.get("title", ""), core)]

    items = []
    for i, hit in enumerate(hits):
        object_id = hit.get("objectID", "")
        points = hit.get("points") or 0
        num_comments = hit.get("num_comments") or 0
        created_at_i = hit.get("created_at_i")

        date_str = _unix_to_date(created_at_i) if created_at_i else None
        article_url = hit.get("url") or ""
        hn_url = f"https://news.ycombinator.com/item?id={object_id}"

        rank_score = max(0.3, 1.0 - (i * 0.02))
        engagement_boost = min(0.2, math.log1p(points) / 40)
        if core:
            content_score = token_overlap_relevance(core, hit.get("title", ""))
            relevance = min(1.0, 0.6 * rank_score + 0.4 * content_score + engagement_boost)
        else:
            relevance = min(1.0, rank_score * 0.7 + engagement_boost + 0.1)

        items.append({
            "id": object_id,
            "title": hit.get("title", ""),
            "body": "",
            "url": article_url or hn_url,
            "hn_url": hn_url,
            "author": hit.get("author", ""),
            "date": date_str,
            "engagement": {
                "points": points,
                "comments": num_comments,
            },
            "relevance": round(relevance, 2),
            "why_relevant": f"HN story: {hit.get('title', '')[:60]}",
        })

    # Enrich top stories with comments
    enrich_limit = min(ENRICH_LIMITS.get(depth, 5), len(items))
    if enrich_limit > 0:
        by_points = sorted(range(len(items)), key=lambda i: items[i].get("engagement", {}).get("points", 0), reverse=True)
        to_enrich = by_points[:enrich_limit]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for idx in to_enrich:
                futures[executor.submit(_fetch_comments, items[idx]["id"])] = idx

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result(timeout=15)
                    items[idx]["top_comments"] = result["comments"]
                    items[idx]["comment_insights"] = result["comment_insights"]
                except Exception:
                    items[idx]["top_comments"] = []
                    items[idx]["comment_insights"] = []

    _source_log(f"Found {len(items)} stories")
    return items


def _fetch_comments(object_id: str, max_comments: int = 5) -> Dict[str, Any]:
    """Fetch top-level comments for a story."""
    url = f"{ALGOLIA_ITEM_URL}/{object_id}"
    try:
        data = http.get(url, timeout=15)
    except Exception:
        return {"comments": [], "comment_insights": []}

    children = data.get("children", [])
    real_comments = [c for c in children if c.get("text") and c.get("author")]
    real_comments.sort(key=lambda c: c.get("points") or 0, reverse=True)

    comments = []
    insights = []
    for c in real_comments[:max_comments]:
        text = _strip_html(c.get("text", ""))
        excerpt = text[:300] + "..." if len(text) > 300 else text
        comments.append({
            "author": c.get("author", ""),
            "text": excerpt,
            "points": c.get("points") or 0,
        })
        first_sentence = text.split(". ")[0].split("\n")[0][:200]
        if first_sentence:
            insights.append(first_sentence)

    return {"comments": comments, "comment_insights": insights}
