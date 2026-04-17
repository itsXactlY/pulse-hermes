"""ArXiv academic paper search via Atom API (free, no auth required).

ArXiv provides an Atom feed API for searching papers.
Endpoint: http://export.arxiv.org/api/query
"""

import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from . import log
from .relevance import token_overlap_relevance, extract_core_subject

ARXIV_API_URL = "http://export.arxiv.org/api/query"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _source_log(msg: str):
    log.source_log("ArXiv", msg)


def _strip_html(text: str) -> str:
    """Strip HTML tags."""
    return re.sub(r"<[^>]+>", "", text).strip()


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search ArXiv for academic papers.

    Returns list of normalized item dicts.
    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    core = extract_core_subject(topic)

    # Build search query — search in title and abstract
    query_parts = []
    words = core.split()
    for word in words:
        if len(word) > 2:
            query_parts.append(f'all:"{word}"')

    if not query_parts:
        query_parts = [f'all:"{core}"']

    search_query = "+AND+".join(query_parts)

    params = {
        "search_query": search_query,
        "start": "0",
        "max_results": str(count),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pulse-hermes/3.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        _source_log(f"Search failed: {e}")
        return []

    # Parse Atom XML
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        _source_log(f"XML parse error: {e}")
        return []

    items = []
    entries = root.findall(f"{ATOM_NS}entry")

    for i, entry in enumerate(entries):
        title_el = entry.find(f"{ATOM_NS}title")
        summary_el = entry.find(f"{ATOM_NS}summary")
        published_el = entry.find(f"{ATOM_NS}published")

        title = _strip_html(title_el.text) if title_el is not None and title_el.text else ""
        abstract = _strip_html(summary_el.text) if summary_el is not None and summary_el.text else ""
        published = published_el.text[:10] if published_el is not None and published_el.text else None

        # Get URL
        url = ""
        for link in entry.findall(f"{ATOM_NS}link"):
            if link.get("title") == "pdf" or link.get("rel") == "alternate":
                url = link.get("href", "")
                break

        # Get authors
        authors = []
        for author in entry.findall(f"{ATOM_NS}author"):
            name_el = author.find(f"{ATOM_NS}name")
            if name_el is not None and name_el.text:
                authors.append(name_el.text)

        # Get categories
        categories = []
        for cat in entry.findall(f"{ATOM_NS}category"):
            term = cat.get("term", "")
            if term:
                categories.append(term)

        # Compute relevance
        relevance = token_overlap_relevance(topic, title) * 0.5
        relevance += token_overlap_relevance(topic, abstract[:300]) * 0.3
        relevance += 0.2  # Base score for academic papers

        items.append({
            "id": f"arxiv-{i + 1}",
            "title": title,
            "body": abstract[:500],
            "url": url,
            "author": ", ".join(authors[:3]),
            "date": published,
            "engagement": {
                "citations": 0,  # ArXiv API doesn't provide citation count
            },
            "relevance": round(min(1.0, relevance), 3),
            "why_relevant": f"ArXiv paper: {', '.join(categories[:3])}",
            "metadata": {
                "categories": categories,
                "authors": authors,
            },
        })

    _source_log(f"Found {len(items)} ArXiv papers")
    return items
