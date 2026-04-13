"""Polymarket prediction market search via Gamma API (free, no auth required)."""

import json
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
from urllib.parse import quote_plus, urlencode

from . import http, log
from .relevance import token_overlap_relevance, extract_core_subject

GAMMA_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"

DEPTH_CONFIG = {
    "quick": 1,
    "default": 3,
    "deep": 4,
}

RESULT_CAP = {
    "quick": 5,
    "default": 15,
    "deep": 25,
}

_NOISE_WORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "of", "for", "and", "or", "to", "is", "are",
    "was", "were", "will", "be", "by", "with", "from", "as", "it", "its", "not", "no",
    "but", "if", "so", "do", "has", "had", "have", "this", "that", "what", "who",
    "west", "east", "north", "south", "central", "team", "game", "match", "season",
    "market", "odds", "prediction", "forecast", "chance", "probability",
})


def _source_log(msg: str):
    log.source_log("PM", msg)


def _expand_queries(topic: str) -> List[str]:
    """Generate search queries to cast a wider net."""
    core = extract_core_subject(topic)
    queries = [core]

    words = core.split()
    if len(words) >= 2:
        for word in words:
            if len(word) > 1 and word.lower() not in _NOISE_WORDS:
                queries.append(word)

    if topic.lower().strip() != core.lower():
        queries.append(topic.strip())

    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique.append(q.strip())
    return unique[:6]


def _passes_topic_filter(topic: str, event_title: str) -> bool:
    """Check if event title contains enough informative words from the topic."""
    core = extract_core_subject(topic).lower()
    core_words = [w for w in re.sub(r"[^\w\s]", " ", core).split() if len(w) > 1]

    if not core_words:
        return True

    informative = [w for w in core_words if w not in _NOISE_WORDS]
    if not informative:
        return True

    title_lower = " ".join(re.sub(r"[^\w\s]", " ", event_title.lower()).split())
    title_words = set(title_lower.split())

    match_count = 0
    for word in informative:
        if word in title_words:
            match_count += 1
        elif len(word) >= 4 and word in title_lower:
            match_count += 1

    min_matches = 2 if len(informative) >= 3 else 1
    return match_count >= min_matches


def _search_single_query(query: str, page: int = 0) -> List[Dict[str, Any]]:
    """Search Polymarket for a single query."""
    params = {"q": query, "page": str(page)}
    url = f"{GAMMA_SEARCH_URL}?{urlencode(params)}"

    try:
        data = http.get(url, timeout=15)
    except Exception as e:
        _source_log(f"Search failed for '{query}': {e}")
        return []

    events = data if isinstance(data, list) else data.get("events", [])
    if not isinstance(events, list):
        events = []

    results = []
    for event in events:
        if isinstance(event, dict):
            results.append(event)

    return results


def _event_to_item(event: Dict[str, Any], topic: str, rank: int) -> Dict[str, Any]:
    """Convert a Polymarket event to a normalized item dict."""
    title = event.get("title", "") or event.get("question", "")
    description = event.get("description", "") or ""

    # Extract market details
    markets = event.get("markets", []) or []
    outcome_prices = []
    total_volume = 0

    for market in markets[:3]:
        question = market.get("question", "")
        outcomes = market.get("outcomes", []) or []
        prices = market.get("outcomePrices", []) or []

        for i, outcome in enumerate(outcomes):
            price = 0
            if i < len(prices):
                try:
                    price = float(prices[i])
                except (ValueError, TypeError):
                    pass
            outcome_prices.append((f"{question}: {outcome}", price))

        try:
            vol = float(market.get("volume", 0) or 0)
            total_volume += vol
        except (ValueError, TypeError):
            pass

    # Compute relevance
    relevance = token_overlap_relevance(topic, title) * 0.6
    relevance += min(0.3, math.log1p(total_volume) / 50)
    relevance = min(1.0, relevance + 0.1)

    # Format odds for body
    odds_parts = []
    for name, price in outcome_prices[:6]:
        if isinstance(price, (int, float)) and price > 0:
            pct = f"{price * 100:.0f}%"
            odds_parts.append(f"{name.split(': ', 1)[-1]}: {pct}")

    body = f"Volume: ${total_volume:,.0f}"
    if odds_parts:
        body += f" | {' | '.join(odds_parts)}"

    return {
        "id": f"PM-{rank}",
        "title": title[:200],
        "body": body,
        "url": event.get("url", "") or f"https://polymarket.com/event/{event.get('slug', '')}",
        "author": None,
        "date": event.get("endDate", "")[:10] if event.get("endDate") else None,
        "engagement": {
            "volume": total_volume,
            "markets": len(markets),
        },
        "relevance": round(relevance, 3),
        "why_relevant": f"Prediction market: {title[:80]}",
        "outcome_prices": outcome_prices,
        "end_date": (event.get("endDate") or "")[:10] if event.get("endDate") else None,
    }


def search(
    topic: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search Polymarket prediction markets."""
    queries = _expand_queries(topic)
    result_cap = RESULT_CAP.get(depth, 15)
    pages_per_query = DEPTH_CONFIG.get(depth, 3)

    all_events: List[Dict[str, Any]] = []
    seen_ids = set()

    for query in queries:
        for page in range(pages_per_query):
            events = _search_single_query(query, page)
            for event in events:
                eid = event.get("id") or event.get("slug") or ""
                if eid and eid not in seen_ids:
                    if _passes_topic_filter(topic, event.get("title", "") or ""):
                        seen_ids.add(eid)
                        all_events.append(event)

    # Convert to items
    items = []
    for i, event in enumerate(all_events[:result_cap]):
        item = _event_to_item(event, topic, i + 1)
        items.append(item)

    _source_log(f"Found {len(items)} prediction markets")
    return items
