"""Query planner for last30days.

Generates subqueries and source selection based on topic analysis.
Can use an LLM for intelligent planning or fall back to heuristic planning.
"""

import re
from typing import Any, Dict, List, Optional

from . import log
from .schema import QueryPlan, SubQuery

# Source capabilities - what each source can search for
SOURCE_CAPABILITIES = {
    "reddit": {"types": ["discussions", "opinions", "questions", "news", "communities"]},
    "hackernews": {"types": ["tech", "startups", "programming", "science", "news"]},
    "polymarket": {"types": ["predictions", "events", "outcomes", "politics", "crypto", "sports"]},
    "github": {"types": ["code", "repos", "issues", "pulls", "releases", "developers"]},
    "youtube": {"types": ["videos", "tutorials", "interviews", "reviews", "deep-dives"]},
    "web": {"types": ["everything"]},
    "news": {"types": ["news", "events", "coverage"]},
}

# Topic patterns that map to preferred sources
TOPIC_PATTERNS = {
    r"(predict|odds|forecast|chance|probability|will .* win|bet)": ["polymarket", "reddit", "web"],
    r"(code|repo|github|programming|developer|open.?source)": ["github", "hackernews", "reddit"],
    r"(startup|launch|product|show HN)": ["hackernews", "reddit", "web"],
    r"(politic|election|government|president|congress)": ["polymarket", "news", "reddit"],
    r"(crypto|bitcoin|ethereum|blockchain|defi)": ["polymarket", "reddit", "hackernews"],
    r"(review|recommend|best|top|compare|vs)": ["reddit", "web", "news"],
    r"(news|announce|release|update|breaking)": ["news", "reddit", "hackernews", "web"],
}

SOURCE_WEIGHTS = {
    "reddit": 1.0,
    "hackernews": 0.9,
    "polymarket": 0.85,
    "github": 0.8,
    "web": 0.7,
    "news": 0.75,
}


def _source_log(msg: str):
    log.source_log("Planner", msg)


def _detect_intent(topic: str) -> str:
    """Detect the user's research intent."""
    topic_lower = topic.lower()

    if re.search(r"(predict|odds|forecast|will .* win|chance|probability)", topic_lower):
        return "prediction"
    if re.search(r"(vs|versus|compare|comparison|better|best|which)", topic_lower):
        return "comparison"
    if re.search(r"(how to|tutorial|guide|learn|explain)", topic_lower):
        return "learning"
    if re.search(r"(news|update|latest|recent|announce|release)", topic_lower):
        return "news_tracking"
    if re.search(r"(person|ceo|founder|developer|engineer|@)", topic_lower):
        return "person_research"
    if re.search(r"(company|startup|product|tool|service)", topic_lower):
        return "product_research"
    return "general"


def _select_sources(topic: str, available: List[str]) -> List[str]:
    """Select appropriate sources based on topic analysis."""
    topic_lower = topic.lower()
    selected = []

    for pattern, preferred in TOPIC_PATTERNS.items():
        if re.search(pattern, topic_lower):
            for source in preferred:
                if source in available and source not in selected:
                    selected.append(source)

    # Always include core free sources if not already selected
    core_sources = ["reddit", "hackernews", "polymarket"]
    for source in core_sources:
        if source in available and source not in selected:
            selected.append(source)

    # Add remaining available sources
    for source in available:
        if source not in selected:
            selected.append(source)

    return selected


def _generate_subqueries(topic: str, sources: List[str], depth: str) -> List[SubQuery]:
    """Generate subqueries for the topic."""
    queries = []

    # Primary query - exact topic
    queries.append(SubQuery(
        label="primary",
        search_query=topic,
        ranking_query=topic,
        sources=sources,
        weight=1.0,
    ))

    # For deeper searches, add variations
    if depth in ("default", "deep"):
        # Extract core subject
        core = topic
        prefixes_to_strip = [
            r"^last \d+ days?\s+",
            r"^what(?:'s| is| are) .+?\s+",
            r"^how (?:is|are)\s+",
            r"^tell me about\s+",
            r"^research\s+",
        ]
        for prefix in prefixes_to_strip:
            core = re.sub(prefix, "", core, flags=re.IGNORECASE).strip()

        if core != topic and core:
            queries.append(SubQuery(
                label="core",
                search_query=core,
                ranking_query=topic,
                sources=sources,
                weight=0.8,
            ))

        # For person research, try with and without @
        if re.search(r"@\w+", topic):
            handle = re.search(r"@(\w+)", topic).group(1)
            queries.append(SubQuery(
                label="handle",
                search_query=handle,
                ranking_query=topic,
                sources=["reddit", "hackernews", "github"],
                weight=0.7,
            ))

    if depth == "deep":
        # Add individual word queries for broad coverage
        words = [w for w in topic.split() if len(w) > 2]
        if len(words) >= 2:
            queries.append(SubQuery(
                label="broad",
                search_query=" ".join(words),
                ranking_query=topic,
                sources=["reddit", "hackernews", "web"],
                weight=0.5,
            ))

    return queries


def plan_query(
    topic: str,
    available_sources: List[str],
    depth: str = "default",
    requested_sources: Optional[List[str]] = None,
) -> QueryPlan:
    """Generate a query plan for the given topic.

    Args:
        topic: Research topic
        available_sources: List of available source names
        depth: Research depth ('quick', 'default', 'deep')
        requested_sources: User-requested specific sources

    Returns:
        QueryPlan with subqueries and source selection
    """
    intent = _detect_intent(topic)
    _source_log(f"Detected intent: {intent}")

    # Filter to requested sources if specified
    if requested_sources:
        sources = [s for s in requested_sources if s in available_sources]
    else:
        sources = _select_sources(topic, available_sources)

    if not sources:
        sources = available_sources  # Fallback to all available

    # Generate subqueries
    subqueries = _generate_subqueries(topic, sources, depth)

    # Compute source weights
    source_weights = {}
    for source in sources:
        source_weights[source] = SOURCE_WEIGHTS.get(source, 0.5)

    # Adjust for detected intent
    if intent == "prediction":
        source_weights["polymarket"] = source_weights.get("polymarket", 0.85) * 1.3
    elif intent == "person_research":
        source_weights["github"] = source_weights.get("github", 0.8) * 1.2
        source_weights["reddit"] = source_weights.get("reddit", 1.0) * 1.1
    elif intent == "product_research":
        source_weights["hackernews"] = source_weights.get("hackernews", 0.9) * 1.2

    freshness_mode = "strict" if intent == "news_tracking" else "relaxed"

    _source_log(f"Plan: {len(subqueries)} subqueries, sources: {', '.join(sources)}")

    return QueryPlan(
        intent=intent,
        freshness_mode=freshness_mode,
        raw_topic=topic,
        subqueries=subqueries,
        source_weights=source_weights,
    )
