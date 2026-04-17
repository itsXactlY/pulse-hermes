"""Semantic Scholar search — AI-focused papers with TLDR summaries.

Free API: https://api.semanticscholar.org/graph/v1/paper/search
"""

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from . import log
from .relevance import token_overlap_relevance

SEMSCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}

FIELDS = "title,abstract,year,citationCount,url,openAccessPdf,authors,tldr,externalIds"


def _source_log(msg: str):
    log.source_log("SemScholar", msg)


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Semantic Scholar for papers."""
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    params = {
        "query": topic,
        "limit": str(count),
        "fields": FIELDS,
    }

    # Year filter
    if from_date and len(from_date) >= 4:
        params["year"] = f"{from_date[:4]}-"
    if to_date and len(to_date) >= 4:
        if "year" in params:
            params["year"] = f"{from_date[:4]}-{to_date[:4]}"
        else:
            params["year"] = f"-{to_date[:4]}"

    url = f"{SEMSCHOLAR_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pulse-hermes/3.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        _source_log(f"Search failed: {e}")
        return []

    papers = data.get("data", [])
    items = []

    for i, paper in enumerate(papers):
        title = paper.get("title", "") or ""
        abstract = paper.get("abstract", "") or ""
        year = paper.get("year")
        cited_by = paper.get("citationCount", 0) or 0
        url = paper.get("url", "") or ""
        oa_pdf = paper.get("openAccessPdf", {})
        pdf_url = oa_pdf.get("url", "") if oa_pdf else ""

        # Authors
        authors = []
        for a in (paper.get("authors") or [])[:3]:
            name = a.get("name", "")
            if name:
                authors.append(name)

        # TLDR
        tldr_data = paper.get("tldr", {})
        tldr = ""
        if tldr_data and isinstance(tldr_data, dict):
            tldr = tldr_data.get("text", "") or ""

        # External IDs
        ext_ids = paper.get("externalIds", {}) or {}
        arxiv_id = ext_ids.get("ArXiv", "")
        doi = ext_ids.get("DOI", "")

        # Use TLDR if available, otherwise abstract
        body = tldr if tldr else abstract[:500]

        # Relevance
        relevance = token_overlap_relevance(topic, title) * 0.4
        relevance += token_overlap_relevance(topic, body[:200]) * 0.2
        relevance += min(0.3, math.log1p(cited_by) / 20)
        relevance = min(1.0, relevance + 0.1)

        items.append({
            "id": f"sem-{i + 1}",
            "title": title,
            "body": body[:500],
            "url": pdf_url or url,
            "author": ", ".join(authors),
            "date": str(year) if year else None,
            "engagement": {
                "citations": cited_by,
            },
            "relevance": round(relevance, 3),
            "why_relevant": f"Semantic Scholar: {tldr[:60] if tldr else 'paper'}",
            "metadata": {
                "arxiv_id": arxiv_id,
                "doi": doi,
                "tldr": tldr,
                "has_pdf": bool(pdf_url),
            },
        })

    _source_log(f"Found {len(items)} papers")
    return items
