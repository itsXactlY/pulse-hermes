"""OpenAlex academic paper search — 250M+ scholarly works, NO auth required.

OpenAlex is the successor to Microsoft Academic Graph.
API: https://api.openalex.org/works?search=QUERY
"""

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

OPENALEX_API_URL = "https://api.openalex.org/works"
POLITE_EMAIL = "pulse-hermes@example.com"  # Polite pool

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}


def _source_log(msg: str):
    log.source_log("OpenAlex", msg)


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search OpenAlex for scholarly works."""
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    params = {
        "search": topic,
        "per_page": str(count),
        "sort": "relevance_score:desc",
        "mailto": POLITE_EMAIL,
    }

    # Date filter
    filters = []
    if from_date:
        filters.append(f"from_publication_date:{from_date}")
    if to_date:
        filters.append(f"to_publication_date:{to_date}")
    if filters:
        params["filter"] = ",".join(filters)

    url = f"{OPENALEX_API_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"pulse-hermes/3.0 (mailto:{POLITE_EMAIL})"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        _source_log(f"Search failed: {e}")
        return []

    results = data.get("results", [])
    items = []

    for i, work in enumerate(results):
        title = work.get("title", "") or ""
        abstract_inv = work.get("abstract_inverted_index", {})

        # Reconstruct abstract from inverted index
        abstract = ""
        if abstract_inv:
            word_positions = []
            for word, positions in abstract_inv.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort()
            abstract = " ".join(w for _, w in word_positions)[:500]

        # Publication date
        pub_date = work.get("publication_date") or work.get("from_publication_date", "")

        # DOI
        doi = work.get("doi", "") or ""

        # Authors
        authorships = work.get("authorships", [])
        authors = []
        for a in authorships[:3]:
            name = a.get("author", {}).get("display_name", "")
            if name:
                authors.append(name)

        # Citations
        cited_by = work.get("cited_by_count", 0) or 0

        # Open access
        is_oa = work.get("open_access", {}).get("is_oa", False)
        oa_url = work.get("open_access", {}).get("oa_url", "")

        # Primary source
        primary_location = work.get("primary_location", {}) or {}
        source_name = primary_location.get("source", {})
        if isinstance(source_name, dict):
            source_name = source_name.get("display_name", "")

        # Relevance
        relevance = token_overlap_relevance(topic, title) * 0.5
        relevance += min(0.3, math.log1p(cited_by) / 20)
        relevance = min(1.0, relevance + 0.2)

        items.append({
            "id": f"openalex-{i + 1}",
            "title": title,
            "body": abstract[:500],
            "url": oa_url or doi or work.get("id", ""),
            "author": ", ".join(authors),
            "date": pub_date[:10] if pub_date else None,
            "engagement": {
                "citations": cited_by,
            },
            "relevance": round(relevance, 3),
            "why_relevant": f"OpenAlex: {source_name or 'scholarly work'}",
            "metadata": {
                "doi": doi,
                "is_open_access": is_oa,
                "source_name": source_name,
            },
        })

    _source_log(f"Found {len(items)} scholarly works")
    return items
