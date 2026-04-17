"""Metaculus search — expert forecasting community, NO auth for public data.

API: https://www.metaculus.com/api/posts/
"""

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

METACULUS_API_URL = "https://www.metaculus.com/api/posts/"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 20,
    "deep": 40,
}


def _source_log(msg: str):
    log.source_log("Metaculus", msg)


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Metaculus for forecast questions."""
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    params = {
        "search": topic,
        "limit": str(count),
        "order_by": "-popularity",
    }

    url = f"{METACULUS_API_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pulse-hermes/3.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        _source_log(f"Search failed: {e}")
        return []

    results = data.get("results", [])
    if not isinstance(results, list):
        results = []

    items = []

    for i, post in enumerate(results[:count]):
        title = post.get("title", "") or ""
        question_data = post.get("question", {}) or {}
        q_title = question_data.get("title", "") or title

        # Forecast values
        forecasts = post.get("forecasts", {}) or {}
        pred = forecasts.get("agg_cdf", {}) or {}
        community_prediction = pred.get("latest", None)

        # Stats
        stats = post.get("stats", {}) or {}
        num_forecasters = stats.get("num_forecasters", 0) or 0
        num_comments = stats.get("num_comments", 0) or 0

        # URL
        post_id = post.get("id", "")
        url = f"https://www.metaculus.com/questions/{post_id}/" if post_id else ""

        # Date
        published = post.get("published_at", "")[:10] if post.get("published_at") else None

        # Tags
        tags = post.get("tags", [])

        # Body
        body_parts = []
        if community_prediction is not None:
            body_parts.append(f"Community prediction: {community_prediction}")
        body_parts.append(f"Forecasters: {num_forecasters}")
        if tags:
            body_parts.append(f"Tags: {', '.join(tags[:5])}")
        body = " | ".join(body_parts)

        # Relevance
        relevance = token_overlap_relevance(topic, q_title) * 0.7
        engagement_boost = min(0.2, math.log1p(num_forecasters) / 15)
        relevance = min(1.0, relevance + engagement_boost + 0.1)

        items.append({
            "id": f"metaculus-{post_id}",
            "title": q_title[:200],
            "body": body[:500],
            "url": url,
            "author": None,
            "date": published,
            "engagement": {
                "forecasters": num_forecasters,
                "comments": num_comments,
            },
            "relevance": round(relevance, 3),
            "why_relevant": f"Metaculus: {num_forecasters} forecasters",
            "metadata": {
                "community_prediction": community_prediction,
                "tags": tags,
            },
        })

    _source_log(f"Found {len(items)} Metaculus forecasts")
    return items
