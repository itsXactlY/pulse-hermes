"""Web search module.

Supports multiple backends: Brave Search, Serper (Google), and Exa.
All require API keys but offer free tiers.
"""

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, quote_plus

from . import http, log

DEPTH_CONFIG = {
    "quick": 5,
    "default": 10,
    "deep": 20,
}


def _source_log(msg: str):
    log.source_log("Web", msg)


def search_brave(
    topic: str,
    api_key: str,
    count: int = 10,
) -> List[Dict[str, Any]]:
    """Search using Brave Search API."""
    url = f"https://api.search.brave.com/res/v1/web/search?q={quote_plus(topic)}&count={count}"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    try:
        data = http.get(url, headers=headers, timeout=15)
    except http.HTTPError as e:
        _source_log(f"Brave search failed: {e}")
        return []

    results = data.get("web", {}).get("results", [])
    items = []
    for i, result in enumerate(results):
        items.append({
            "id": f"W-{i + 1}",
            "title": result.get("title", ""),
            "body": result.get("description", "") or "",
            "url": result.get("url", ""),
            "author": None,
            "date": (result.get("page_age") or "")[:10] if result.get("page_age") else None,
            "engagement": {},
            "relevance": max(0.3, 1.0 - i * 0.05),
            "why_relevant": f"Web result: {result.get('title', '')[:60]}",
        })

    return items


def search_serper(
    topic: str,
    api_key: str,
    count: int = 10,
) -> List[Dict[str, Any]]:
    """Search using Serper (Google) API."""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    data = {"q": topic, "num": count}

    try:
        result = http.post(url, json_data=data, headers=headers, timeout=15)
    except http.HTTPError as e:
        _source_log(f"Serper search failed: {e}")
        return []

    organic = result.get("organic", [])
    items = []
    for i, item in enumerate(organic):
        items.append({
            "id": f"W-{i + 1}",
            "title": item.get("title", ""),
            "body": item.get("snippet", "") or "",
            "url": item.get("link", ""),
            "author": None,
            "date": None,
            "engagement": {},
            "relevance": max(0.3, 1.0 - i * 0.05),
            "why_relevant": f"Web result: {item.get('title', '')[:60]}",
        })

    return items


def search_exa(
    topic: str,
    api_key: str,
    count: int = 10,
) -> List[Dict[str, Any]]:
    """Search using Exa (formerly Metaphor) API."""
    url = "https://api.exa.ai/search"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    data = {
        "query": topic,
        "numResults": count,
        "type": "auto",
    }

    try:
        result = http.post(url, json_data=data, headers=headers, timeout=15)
    except http.HTTPError as e:
        _source_log(f"Exa search failed: {e}")
        return []

    results = result.get("results", [])
    items = []
    for i, item in enumerate(results):
        items.append({
            "id": f"W-{i + 1}",
            "title": item.get("title", ""),
            "body": (item.get("text") or item.get("snippet") or "")[:300],
            "url": item.get("url", ""),
            "author": item.get("author"),
            "date": (item.get("publishedDate") or "")[:10] if item.get("publishedDate") else None,
            "engagement": {},
            "relevance": max(0.3, 1.0 - i * 0.05),
            "why_relevant": f"Web result: {item.get('title', '')[:60]}",
        })

    return items


def search(
    topic: str,
    config: Dict[str, Any],
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search the web using the best available backend."""
    count = DEPTH_CONFIG.get(depth, 10)

    # Try backends in order
    if config.get("BRAVE_API_KEY"):
        _source_log("Using Brave Search")
        return search_brave(topic, config["BRAVE_API_KEY"], count)

    if config.get("SERPER_API_KEY"):
        _source_log("Using Serper (Google)")
        return search_serper(topic, config["SERPER_API_KEY"], count)

    if config.get("EXA_API_KEY"):
        _source_log("Using Exa")
        return search_exa(topic, config["EXA_API_KEY"], count)

    _source_log("No web search backend configured")
    return []
