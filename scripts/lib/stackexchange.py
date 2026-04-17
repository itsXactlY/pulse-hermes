"""Stack Exchange API search — 170+ Q&A sites including StackOverflow.

API: https://api.stackexchange.com/2.3/search?order=desc&sort=relevance&intitle=QUERY&site=stackoverflow
"""

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

STACKEXCHANGE_URL = "https://api.stackexchange.com/2.3/search"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}

# Sites to search (order matters — most relevant first)
DEFAULT_SITES = ["stackoverflow", "serverfault", "superuser", "askubuntu", "devops"]


def _source_log(msg: str):
    log.source_log("StackEx", msg)


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Stack Exchange Q&A sites."""
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    items = []

    for site in DEFAULT_SITES:
        params = {
            "order": "desc",
            "sort": "relevance",
            "intitle": topic,
            "site": site,
            "pagesize": str(min(count, 30)),
            "filter": "default",
        }

        url = f"{STACKEXCHANGE_URL}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hermes-pulse/3.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            continue

        for q in data.get("items", []):
            title = q.get("title", "") or ""
            link = q.get("link", "") or ""
            score = q.get("score", 0) or 0
            answer_count = q.get("answer_count", 0) or 0
            view_count = q.get("view_count", 0) or 0
            is_answered = q.get("is_answered", False)
            tags = q.get("tags", [])
            owner = q.get("owner", {})
            author = owner.get("display_name", "") if owner else ""

            # Tags as body
            body = f"Tags: {', '.join(tags[:5])} | {answer_count} answers | {view_count:,} views"

            relevance = token_overlap_relevance(topic, title) * 0.6
            relevance += min(0.3, math.log1p(max(0, score)) / 10)
            relevance += 0.1 if is_answered else 0

            items.append({
                "id": f"se-{q.get('question_id', '')}",
                "title": title,
                "body": body[:500],
                "url": link,
                "author": author,
                "date": None,
                "engagement": {
                    "score": score,
                    "answers": answer_count,
                    "views": view_count,
                },
                "relevance": round(min(1.0, relevance), 3),
                "why_relevant": f"StackExchange ({site}): {', '.join(tags[:3])}",
                "metadata": {
                    "site": site,
                    "tags": tags,
                    "is_answered": is_answered,
                },
            })

    # Dedupe and sort
    seen = set()
    unique = []
    for item in items:
        key = item["url"]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    unique.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    result = unique[:count]

    _source_log(f"Found {len(result)} Stack Exchange Q&As")
    return result
