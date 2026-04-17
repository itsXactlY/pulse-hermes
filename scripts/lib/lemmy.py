"""Lemmy search — federated Reddit alternative, NO auth for reading.

Lemmy instances expose a public JSON API.
Default instances: lemmy.world, lemmy.ml, programming.dev
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

# Popular Lemmy instances
DEFAULT_INSTANCES = [
    "lemmy.world",
    "lemmy.ml",
    "programming.dev",
    "sh.itjust.works",
    "lemm.ee",
]

DEPTH_CONFIG = {
    "quick": 5,
    "default": 15,
    "deep": 30,
}


def _source_log(msg: str):
    log.source_log("Lemmy", msg)


def _search_instance(instance: str, query: str, limit: int) -> List[Dict[str, Any]]:
    """Search a single Lemmy instance."""
    params = {
        "q": query,
        "type_": "Posts",
        "sort": "TopAll",
        "limit": str(limit),
        "page": "1",
    }

    url = f"https://{instance}/api/v3/search?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pulse-hermes/3.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    posts = data.get("posts", [])
    items = []

    for result in posts:
        post = result.get("post", {})
        counts = result.get("counts", {})
        community = result.get("community", {})

        title = post.get("name", "") or ""
        body = post.get("body", "") or ""
        url = post.get("url", "") or ""
        published = post.get("published", "")[:10] if post.get("published") else None

        # Creator
        creator = result.get("creator", {})
        author = creator.get("name", "") if creator else ""

        # Community
        community_name = community.get("name", "") if community else ""

        # Engagement
        score = counts.get("score", 0) or 0
        comments = counts.get("comments", 0) or 0

        # URL fallback
        if not url:
            post_id = post.get("id", "")
            url = f"https://{instance}/post/{post_id}" if post_id else ""

        items.append({
            "title": title,
            "body": body[:500] if body else "",
            "url": url,
            "author": author,
            "date": published,
            "engagement": {
                "score": score,
                "comments": comments,
            },
            "community": community_name,
            "instance": instance,
        })

    return items


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Lemmy instances for posts."""
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    per_instance = max(5, count // len(DEFAULT_INSTANCES))

    all_items = []

    for instance in DEFAULT_INSTANCES:
        items = _search_instance(instance, topic, per_instance)
        all_items.extend(items)

    # Dedupe by title
    seen_titles = set()
    unique = []
    for item in all_items:
        key = item["title"].lower().strip()[:100]
        if key and key not in seen_titles:
            seen_titles.add(key)
            unique.append(item)

    # Score and normalize
    result = []
    for i, item in enumerate(unique[:count]):
        relevance = token_overlap_relevance(topic, f"{item['title']} {item['body'][:100]}")
        engagement = item.get("engagement", {})
        score = engagement.get("score", 0) or 0
        relevance += min(0.3, (score / 50) * 0.3)
        relevance = min(1.0, relevance + 0.1)

        result.append({
            "id": f"lemmy-{i + 1}",
            "title": item["title"],
            "body": item["body"][:500],
            "url": item["url"],
            "author": item.get("author"),
            "date": item.get("date"),
            "engagement": item.get("engagement", {}),
            "relevance": round(relevance, 3),
            "why_relevant": f"Lemmy: {item.get('community', '')}@{item.get('instance', '')}",
            "metadata": {
                "community": item.get("community", ""),
                "instance": item.get("instance", ""),
            },
        })

    _source_log(f"Found {len(result)} Lemmy posts")
    return result
