"""Scoring engine for last30days items.

Computes multi-signal scores: relevance, recency, engagement, source quality.
"""

import math
from typing import Any, Dict, Optional

from . import dates, log
from .schema import SourceItem


def _source_log(msg: str):
    log.source_log("Score", msg)


# Source quality baselines (0.0 - 1.0)
SOURCE_QUALITY = {
    "reddit": 0.75,
    "hackernews": 0.85,
    "polymarket": 0.90,  # Money-backed signals
    "github": 0.80,
    "web": 0.60,
    "news": 0.65,
}


def compute_engagement_score(item: SourceItem) -> float:
    """Compute engagement score from item's engagement metrics."""
    eng = item.engagement
    if not eng:
        return 0.0

    score = 0.0

    # Reddit: score + comments
    if item.source == "reddit":
        s = eng.get("score", 0) or 0
        c = eng.get("num_comments", 0) or 0
        score = min(1.0, (math.log1p(s) / 8.0) * 0.6 + (math.log1p(c) / 6.0) * 0.4)

    # HN: points + comments
    elif item.source == "hackernews":
        p = eng.get("points", 0) or 0
        c = eng.get("comments", 0) or 0
        score = min(1.0, (math.log1p(p) / 7.0) * 0.6 + (math.log1p(c) / 5.0) * 0.4)

    # Polymarket: volume
    elif item.source == "polymarket":
        v = eng.get("volume", 0) or 0
        score = min(1.0, math.log1p(v) / 15.0)

    # GitHub: stars
    elif item.source == "github":
        s = eng.get("stars", 0) or 0
        score = min(1.0, math.log1p(s) / 10.0)

    # YouTube: views
    elif item.source == "youtube":
        v = eng.get("views", 0) or 0
        score = min(1.0, math.log1p(v) / 15.0)

    # Web/News: no direct engagement
    else:
        score = 0.3  # Baseline

    return round(score, 3)


def compute_local_relevance(item: SourceItem, topic: str) -> float:
    """Compute local relevance score using token overlap and existing hint."""
    from .relevance import token_overlap_relevance

    # Use existing relevance_hint if available
    hint = item.relevance_hint

    # Compute token overlap with title and body
    title_overlap = token_overlap_relevance(topic, item.title)
    body_overlap = token_overlap_relevance(topic, item.body[:200]) if item.body else 0

    # Weighted combination
    relevance = 0.4 * hint + 0.4 * title_overlap + 0.2 * body_overlap
    return round(min(1.0, max(0.0, relevance)), 3)


def compute_source_quality(source: str) -> float:
    """Get source quality score."""
    return SOURCE_QUALITY.get(source, 0.5)


def score_item(
    item: SourceItem,
    topic: str,
    from_date: str,
    to_date: str,
    max_days: int = 30,
) -> SourceItem:
    """Compute all scores for an item.

    Mutates and returns the item with score fields populated.
    """
    # Freshness (0-100)
    item.freshness = dates.recency_score(item.published_at, max_days)

    # Engagement score
    item.engagement_score = compute_engagement_score(item)

    # Local relevance
    item.local_relevance = compute_local_relevance(item, topic)

    # Source quality
    item.source_quality = compute_source_quality(item.source)

    # Combined local rank score
    freshness_norm = item.freshness / 100.0
    item.local_rank_score = (
        0.35 * item.local_relevance +
        0.25 * freshness_norm +
        0.25 * item.engagement_score +
        0.15 * item.source_quality
    )

    return item


def score_items(
    items: list[SourceItem],
    topic: str,
    from_date: str,
    to_date: str,
    max_days: int = 30,
) -> list[SourceItem]:
    """Score all items in a list."""
    return [score_item(item, topic, from_date, to_date, max_days) for item in items]
