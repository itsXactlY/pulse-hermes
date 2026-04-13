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


# Map source names to normalizer functions
NORMALIZERS = {
    "reddit": normalize_reddit,
    "hackernews": normalize_hackernews,
    "polymarket": normalize_polymarket,
    "github": normalize_github,
    "youtube": normalize_youtube,
    "web": normalize_web,
    "news": normalize_news,
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
