"""Bluesky search via AT Protocol — fully open API, NO auth for public data.

API: https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

BLUESKY_SEARCH_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}


def _source_log(msg: str):
    log.source_log("Bluesky", msg)


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Bluesky posts."""
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    params = {
        "q": topic,
        "limit": str(min(count, 100)),  # API max is 100
    }

    url = f"{BLUESKY_SEARCH_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pulse-hermes/3.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        _source_log(f"Search failed: {e}")
        return []

    posts = data.get("posts", [])
    items = []

    for i, post_data in enumerate(posts[:count]):
        record = post_data.get("record", {})
        author = post_data.get("author", {})

        text = record.get("text", "") or ""
        created_at = record.get("createdAt", "")[:10] if record.get("createdAt") else None

        # Author info
        handle = author.get("handle", "")
        display_name = author.get("displayName", "") or handle

        # Engagement
        like_count = post_data.get("likeCount", 0) or 0
        repost_count = post_data.get("repostCount", 0) or 0
        reply_count = post_data.get("replyCount", 0) or 0

        # URL
        uri = post_data.get("uri", "")
        # Convert at:// URI to web URL
        post_url = ""
        if uri and "app.bsky.feed.post" in uri:
            rkey = uri.split("/")[-1]
            post_url = f"https://bsky.app/profile/{handle}/post/{rkey}"

        # Relevance
        relevance = token_overlap_relevance(topic, text) * 0.6
        engagement = like_count + repost_count * 2 + reply_count * 3
        relevance += min(0.3, (engagement / 100) * 0.3)
        relevance = min(1.0, relevance + 0.1)

        items.append({
            "id": f"bsky-{i + 1}",
            "title": text[:100] if text else f"Post by @{handle}",
            "body": text[:500],
            "url": post_url,
            "author": display_name,
            "date": created_at,
            "engagement": {
                "likes": like_count,
                "reposts": repost_count,
                "replies": reply_count,
            },
            "relevance": round(relevance, 3),
            "why_relevant": f"Bluesky: @{handle}",
            "metadata": {
                "handle": handle,
                "uri": uri,
            },
        })

    _source_log(f"Found {len(items)} Bluesky posts")
    return items
