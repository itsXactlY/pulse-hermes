"""Query router for PULSE.

Classifies queries into types and selects optimal ordered source lists
per type. Supports depth-based source prioritization.
"""

import re
from typing import Dict, List

from . import log


def _source_log(msg: str):
    log.source_log("QueryRouter", msg)


# Query type classification patterns (order matters: first match wins)
_TYPE_PATTERNS = [
    (r"(breaking|just ?now|live|urgent|just ?in|developing|real.?time)\b", "breaking_news"),
    (r"(paper|arxiv|peer.?review|journal|doi|abstract|methodology|dataset|benchmark)\b", "academic_deep"),
    (r"(predict|odds|forecast|chance|probability|will\b.*\bwin|bet|market|outcome)\b", "prediction"),
    (r"(vs\b|versus|compare|comparison|better|best\b.*\bwhich|alternative|stack\b|benchmark|review)\b", "technical_comparison"),
    (r"(opinion|sentiment|feel|community|vibe|mood|reaction|hot.?take|controversy)\b", "sentiment_pulse"),
    # Additional hints that may not match above but still map well
    (r"(news|announce|release|update|latest|trending)\b", "breaking_news"),
    (r"(research|study|academic|scholar|model|training|fine.?tun)\b", "academic_deep"),
    (r"(code|repo|github|api|sdk|library|framework|tool)\b", "technical_comparison"),
]

# Optimal ordered source lists per query type
TYPE_SOURCES: Dict[str, List[str]] = {
    "breaking_news": [
        "news", "hackernews", "reddit", "bluesky", "web", "rss", "bing_news", "serpapi_news",
        "polymarket", "github", "youtube", "lobsters", "stackexchange",
        "devto", "lemmy", "arxiv", "openalex", "sem_scholar",
        "manifold", "metaculus", "tickertick",
    ],
    "academic_deep": [
        "arxiv", "openalex", "sem_scholar", "hackernews", "reddit",
        "web", "youtube", "news", "github", "stackexchange",
        "lobsters", "rss", "devto", "bluesky", "polymarket",
        "manifold", "metaculus", "lemmy",
    ],
    "prediction": [
        "polymarket", "manifold", "metaculus", "reddit", "hackernews",
        "web", "news", "bluesky", "arxiv", "openalex", "sem_scholar",
        "github", "youtube", "stackexchange", "lobsters", "rss",
        "devto", "lemmy", "tickertick", "bing_news", "serpapi_news",
    ],
    "technical_comparison": [
        "hackernews", "github", "stackoverflow", "reddit", "lobsters",
        "web", "devto", "rss", "youtube", "arxiv", "openalex",
        "sem_scholar", "news", "bluesky", "stackexchange",
        "polymarket", "manifold", "metaculus", "lemmy",
    ],
    "sentiment_pulse": [
        "reddit", "bluesky", "hackernews", "news", "web",
        "youtube", "lobsters", "lemmy", "devto", "rss", "bing_news", "serpapi_news",
        "polymarket", "manifold", "metaculus", "github",
        "stackexchange", "arxiv", "openalex", "sem_scholar", "tickertick",
    ],
}

# Fast probe sources per depth (subset of overall; these are quick to check)
_PROBE_SOURCES = {
    "quick": ["hackernews", "reddit", "news", "bluesky"],
    "default": ["hackernews", "reddit", "news", "polymarket", "web", "bluesky", "devto"],
    "deep": ["hackernews", "reddit", "news", "polymarket", "web", "arxiv", "github", "bluesky", "devto", "stackexchange"],
}


class QueryRouter:
    """Routes queries to optimal source orderings based on type and depth."""

    def classify(self, query: str) -> str:
        """Classify a query string into one of the 5 query types.

        Returns:
            One of: breaking_news, academic_deep, prediction,
                    technical_comparison, sentiment_pulse
        """
        q = query.lower().strip()
        for pattern, qtype in _TYPE_PATTERNS:
            if re.search(pattern, q):
                _source_log(f"Classified '{query[:50]}' -> {qtype}")
                return qtype

        _source_log(f"No pattern match for '{query[:50]}' -> sentiment_pulse (default)")
        return "sentiment_pulse"

    def probe_first(self, depth: str = "default") -> List[str]:
        """Return fast sources to check first for a given depth.

        These are sources that typically respond quickly and are useful
        for early signal detection before deeper sources finish.
        """
        return list(_PROBE_SOURCES.get(depth, _PROBE_SOURCES["default"]))

    def prioritize(self, sources: List[str], depth: str = "default") -> List[str]:
        """Reorder source list by depth priority.

        - quick: only fast sources (up to 6)
        - default: balanced mix (up to 10)
        - deep: all sources, fast-first then rest
        """
        if depth == "quick":
            fast = [s for s in sources if s in _PROBE_SOURCES["quick"]]
            return fast[:6]

        if depth == "deep":
            fast = [s for s in sources if s in _PROBE_SOURCES["deep"]]
            rest = [s for s in sources if s not in fast]
            return fast + rest

        # default
        fast = [s for s in sources if s in _PROBE_SOURCES["default"]]
        rest = [s for s in sources if s not in fast]
        return (fast + rest)[:10]

    def get_optimal_sources(
        self, query_type: str, available: List[str]
    ) -> List[str]:
        """Get sources ordered by relevance for the query type, filtered to available.

        Args:
            query_type: One of the 5 query types.
            available: List of available source names.

        Returns:
            Ordered list of available sources optimal for this query type.
        """
        optimal = TYPE_SOURCES.get(query_type, TYPE_SOURCES["sentiment_pulse"])
        result = [s for s in optimal if s in available]
        # Append any remaining available sources not in the optimal list
        for s in available:
            if s not in result:
                result.append(s)
        return result
