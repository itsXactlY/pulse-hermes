"""Normalize raw source items to SourceItem schema."""

import hashlib
from typing import Any, Dict, List

from . import dates, log
from .schema import SourceItem


def _source_log(msg: str):
    log.source_log("Normalize", msg)


def _make_id(source: str, url: str, title: str) -> str:
    """Generate a stable item ID from source+url+title."""
    raw = f"{source}:{url}:{title}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def normalize_reddit(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Reddit items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        engagement = item.get("engagement", {})
        snippet = item.get("body", "")[:300]

        # Add comment insights to snippet
        insights = item.get("comment_insights", [])
        if insights:
            snippet += "\nTop insight: " + "; ".join(insights[:2])

        metadata = {}
        if item.get("top_comments"):
            metadata["top_comments"] = item["top_comments"]
        if insights:
            metadata["comment_insights"] = insights

        normalized.append(SourceItem(
            item_id=_make_id("reddit", item.get("url", ""), item.get("title", "")),
            source="reddit",
            title=item.get("title", ""),
            body=snippet,
            url=item.get("url", ""),
            author=item.get("author"),
            container=item.get("subreddit"),
            published_at=date_str,
            date_confidence=confidence,
            engagement=engagement,
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=snippet[:200],
            metadata=metadata,
        ))
    return normalized


def normalize_hackernews(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize HN items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        engagement = item.get("engagement", {})

        metadata = {}
        if item.get("hn_url"):
            metadata["hn_url"] = item["hn_url"]
        if item.get("top_comments"):
            metadata["top_comments"] = item["top_comments"]
        if item.get("comment_insights"):
            metadata["comment_insights"] = item["comment_insights"]

        normalized.append(SourceItem(
            item_id=_make_id("hackernews", item.get("url", ""), item.get("title", "")),
            source="hackernews",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", "") or item.get("hn_url", ""),
            author=item.get("author"),
            container="Hacker News",
            published_at=date_str,
            date_confidence=confidence,
            engagement=engagement,
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("title", "")[:200],
            metadata=metadata,
        ))
    return normalized


def normalize_polymarket(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Polymarket items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        engagement = item.get("engagement", {})

        metadata = {}
        if item.get("outcome_prices"):
            metadata["outcome_prices"] = item["outcome_prices"]
        if item.get("end_date"):
            metadata["end_date"] = item["end_date"]

        normalized.append(SourceItem(
            item_id=_make_id("polymarket", item.get("url", ""), item.get("title", "")),
            source="polymarket",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", ""),
            author=None,
            container="Polymarket",
            published_at=date_str,
            date_confidence=confidence,
            engagement=engagement,
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200],
            metadata=metadata,
        ))
    return normalized


def normalize_github(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize GitHub items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        engagement = item.get("engagement", {})
        metadata = {}
        if item.get("language"):
            metadata["language"] = item["language"]
        if item.get("state"):
            metadata["state"] = item["state"]
        if item.get("repository"):
            metadata["repository"] = item["repository"]

        normalized.append(SourceItem(
            item_id=_make_id("github", item.get("url", ""), item.get("title", "")),
            source="github",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", ""),
            author=item.get("author"),
            container=item.get("repository"),
            published_at=date_str,
            date_confidence=confidence,
            engagement=engagement,
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200],
            metadata=metadata,
        ))
    return normalized


def normalize_web(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize web search items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        normalized.append(SourceItem(
            item_id=_make_id("web", item.get("url", ""), item.get("title", "")),
            source="web",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", ""),
            author=item.get("author"),
            container=None,
            published_at=date_str,
            date_confidence=confidence,
            engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200],
            metadata={},
        ))
    return normalized


def normalize_youtube(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize YouTube items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        engagement = item.get("engagement", {})
        metadata = {}
        if item.get("transcript_highlights"):
            metadata["transcript_highlights"] = item["transcript_highlights"]
        if item.get("transcript_snippet"):
            metadata["transcript_snippet"] = item["transcript_snippet"]

        normalized.append(SourceItem(
            item_id=_make_id("youtube", item.get("url", ""), item.get("title", "")),
            source="youtube",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", ""),
            author=item.get("author"),
            container="YouTube",
            published_at=date_str,
            date_confidence=confidence,
            engagement=engagement,
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200],
            metadata=metadata,
        ))
    return normalized


def normalize_news(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize news items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        metadata = {}
        if item.get("source_name"):
            metadata["source_name"] = item["source_name"]

        normalized.append(SourceItem(
            item_id=_make_id("news", item.get("url", ""), item.get("title", "")),
            source="news",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", ""),
            author=item.get("author"),
            container=item.get("source_name"),
            published_at=date_str,
            date_confidence=confidence,
            engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200],
            metadata=metadata,
        ))
    return normalized


def normalize_arxiv(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize ArXiv items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        metadata = {}
        if item.get("metadata", {}).get("categories"):
            metadata["categories"] = item["metadata"]["categories"]
        if item.get("metadata", {}).get("authors"):
            metadata["authors"] = item["metadata"]["authors"]

        normalized.append(SourceItem(
            item_id=_make_id("arxiv", item.get("url", ""), item.get("title", "")),
            source="arxiv",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", ""),
            author=item.get("author"),
            container="ArXiv",
            published_at=date_str,
            date_confidence=confidence,
            engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200],
            metadata=metadata,
        ))
    return normalized


def normalize_lobsters(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Lobsters items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        metadata = {}
        if item.get("metadata", {}).get("tags"):
            metadata["tags"] = item["metadata"]["tags"]
        if item.get("metadata", {}).get("comments_url"):
            metadata["comments_url"] = item["metadata"]["comments_url"]

        normalized.append(SourceItem(
            item_id=_make_id("lobsters", item.get("url", ""), item.get("title", "")),
            source="lobsters",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", ""),
            author=item.get("author"),
            container="Lobsters",
            published_at=date_str,
            date_confidence=confidence,
            engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200],
            metadata=metadata,
        ))
    return normalized


def normalize_rss(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize RSS items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)

        metadata = {}
        if item.get("metadata", {}).get("feed_url"):
            metadata["feed_url"] = item["metadata"]["feed_url"]
        if item.get("metadata", {}).get("feed_domain"):
            metadata["feed_domain"] = item["metadata"]["feed_domain"]

        normalized.append(SourceItem(
            item_id=_make_id("rss", item.get("url", ""), item.get("title", "")),
            source="rss",
            title=item.get("title", ""),
            body=item.get("body", ""),
            url=item.get("url", ""),
            author=item.get("author"),
            container=item.get("metadata", {}).get("feed_domain", ""),
            published_at=date_str,
            date_confidence=confidence,
            engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200],
            metadata=metadata,
        ))
    return normalized




def normalize_openalex(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize OpenAlex items to SourceItem."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)
        metadata = item.get("metadata", {})
        normalized.append(SourceItem(
            item_id=_make_id("openalex", item.get("url", ""), item.get("title", "")),
            source="openalex", title=item.get("title", ""), body=item.get("body", ""),
            url=item.get("url", ""), author=item.get("author"), container="OpenAlex",
            published_at=date_str, date_confidence=confidence, engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5), why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200], metadata=metadata,
        ))
    return normalized

def normalize_sem_scholar(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Semantic Scholar items."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)
        metadata = item.get("metadata", {})
        normalized.append(SourceItem(
            item_id=_make_id("sem_scholar", item.get("url", ""), item.get("title", "")),
            source="sem_scholar", title=item.get("title", ""), body=item.get("body", ""),
            url=item.get("url", ""), author=item.get("author"), container="Semantic Scholar",
            published_at=date_str, date_confidence=confidence, engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5), why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200], metadata=metadata,
        ))
    return normalized

def normalize_manifold(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Manifold Markets items."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)
        metadata = item.get("metadata", {})
        normalized.append(SourceItem(
            item_id=_make_id("manifold", item.get("url", ""), item.get("title", "")),
            source="manifold", title=item.get("title", ""), body=item.get("body", ""),
            url=item.get("url", ""), author=item.get("author"), container="Manifold",
            published_at=date_str, date_confidence=confidence, engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5), why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200], metadata=metadata,
        ))
    return normalized

def normalize_metaculus(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Metaculus items."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)
        metadata = item.get("metadata", {})
        normalized.append(SourceItem(
            item_id=_make_id("metaculus", item.get("url", ""), item.get("title", "")),
            source="metaculus", title=item.get("title", ""), body=item.get("body", ""),
            url=item.get("url", ""), author=item.get("author"), container="Metaculus",
            published_at=date_str, date_confidence=confidence, engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5), why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200], metadata=metadata,
        ))
    return normalized

def normalize_bluesky(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Bluesky items."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)
        metadata = item.get("metadata", {})
        normalized.append(SourceItem(
            item_id=_make_id("bluesky", item.get("url", ""), item.get("title", "")),
            source="bluesky", title=item.get("title", ""), body=item.get("body", ""),
            url=item.get("url", ""), author=item.get("author"), container="Bluesky",
            published_at=date_str, date_confidence=confidence, engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5), why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200], metadata=metadata,
        ))
    return normalized

def normalize_stackexchange(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Stack Exchange items."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)
        metadata = item.get("metadata", {})
        normalized.append(SourceItem(
            item_id=_make_id("stackexchange", item.get("url", ""), item.get("title", "")),
            source="stackexchange", title=item.get("title", ""), body=item.get("body", ""),
            url=item.get("url", ""), author=item.get("author"), container=metadata.get("site", "StackExchange"),
            published_at=date_str, date_confidence=confidence, engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5), why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200], metadata=metadata,
        ))
    return normalized

def normalize_lemmy(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Lemmy items."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)
        metadata = item.get("metadata", {})
        normalized.append(SourceItem(
            item_id=_make_id("lemmy", item.get("url", ""), item.get("title", "")),
            source="lemmy", title=item.get("title", ""), body=item.get("body", ""),
            url=item.get("url", ""), author=item.get("author"),
            container=f"{metadata.get('community', '')}@{metadata.get('instance', '')}",
            published_at=date_str, date_confidence=confidence, engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5), why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200], metadata=metadata,
        ))
    return normalized

def normalize_devto(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[SourceItem]:
    """Normalize Dev.to items."""
    normalized = []
    for item in items:
        date_str = item.get("date")
        confidence = dates.get_date_confidence(date_str, from_date, to_date)
        metadata = item.get("metadata", {})
        normalized.append(SourceItem(
            item_id=_make_id("devto", item.get("url", ""), item.get("title", "")),
            source="devto", title=item.get("title", ""), body=item.get("body", ""),
            url=item.get("url", ""), author=item.get("author"), container="Dev.to",
            published_at=date_str, date_confidence=confidence, engagement=item.get("engagement", {}),
            relevance_hint=item.get("relevance", 0.5), why_relevant=item.get("why_relevant", ""),
            snippet=item.get("body", "")[:200], metadata=metadata,
        ))
    return normalized


# Map source names to normalizer functions
NORMALIZERS = {
    "reddit": normalize_reddit,
    "hackernews": normalize_hackernews,
    "polymarket": normalize_polymarket,
    "github": normalize_github,
    "youtube": normalize_youtube,
    "web": normalize_web,
    "news": normalize_news,
    "arxiv": normalize_arxiv,
    "lobsters": normalize_lobsters,
    "rss": normalize_rss,
    "openalex": normalize_openalex,
    "sem_scholar": normalize_sem_scholar,
    "manifold": normalize_manifold,
    "metaculus": normalize_metaculus,
    "bluesky": normalize_bluesky,
    "stackexchange": normalize_stackexchange,
    "lemmy": normalize_lemmy,
    "devto": normalize_devto,
}



def normalize_items(
    source: str,
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[SourceItem]:
    """Normalize items from any source."""
    normalizer = NORMALIZERS.get(source)
    if not normalizer:
        _source_log(f"No normalizer for source: {source}")
        return []
    return normalizer(items, from_date, to_date)
