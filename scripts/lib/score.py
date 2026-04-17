"""Scoring engine for last30days items.

Computes multi-signal scores: relevance, recency, engagement, source quality,
engagement velocity, and cross-source agreement bonus.
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
    "youtube": 0.70,
    "web": 0.60,
    "news": 0.65,
    "arxiv": 0.88,       # Peer-reviewed academic papers
    "lobsters": 0.78,    # Curated tech community
    "rss": 0.55,         # Varies wildly by feed
    "bluesky": 0.65,     # Growing platform
    "openalex": 0.89,    # 250M+ scholarly works
    "sem_scholar": 0.88, # AI-focused, TLDR summaries
    "manifold": 0.75,    # Play-money but 1M+ markets
    "metaculus": 0.83,   # Expert forecasting
    "stackexchange": 0.80, # Curated Q&A
    "lemmy": 0.62,       # Federated Reddit
    "devto": 0.68,       # Developer blogs
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

    # Web/News/RSS: no direct engagement
    else:
        score = 0.3  # Baseline

    return round(score, 3)


def compute_engagement_velocity(item: SourceItem) -> float:
    """Estimate how fast engagement is growing.

    Items published recently with high engagement are more interesting
    than old items with the same engagement. Returns 0.0-1.0.
    """
    eng = item.engagement
    if not eng or not item.published_at:
        return 0.0

    days = dates.days_ago(item.published_at)
    if days is None or days <= 0:
        days = 1

    # Get primary engagement metric
    primary = 0
    if item.source == "reddit":
        primary = (eng.get("score", 0) or 0) + (eng.get("num_comments", 0) or 0) * 2
    elif item.source == "hackernews":
        primary = (eng.get("points", 0) or 0) + (eng.get("comments", 0) or 0) * 2
    elif item.source == "polymarket":
        primary = eng.get("volume", 0) or 0
    elif item.source == "youtube":
        primary = eng.get("views", 0) or 0
    elif item.source == "github":
        primary = eng.get("stars", 0) or 0
    else:
        return 0.0

    if primary <= 0:
        return 0.0

    # Velocity = engagement per day (log-scaled)
    daily_rate = primary / days
    return min(1.0, math.log1p(daily_rate) / 8.0)


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
    Scoring weights:
      - Local Relevance: 30% (was 35%) — token overlap with topic
      - Freshness: 20% (was 25%) — recency within lookback
      - Engagement: 25% — platform metrics
      - Engagement Velocity: 10% (NEW) — how fast engagement grows
      - Source Quality: 15% — baseline trust
    """
    # Freshness (0-100)
    item.freshness = dates.recency_score(item.published_at, max_days)

    # Engagement score
    item.engagement_score = compute_engagement_score(item)

    # Engagement velocity (NEW)
    velocity = compute_engagement_velocity(item)

    # Local relevance
    item.local_relevance = compute_local_relevance(item, topic)

    # Source quality
    item.source_quality = compute_source_quality(item.source)

    # Combined local rank score
    freshness_norm = item.freshness / 100.0
    item.local_rank_score = (
        0.30 * item.local_relevance +
        0.20 * freshness_norm +
        0.25 * item.engagement_score +
        0.10 * velocity +
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
