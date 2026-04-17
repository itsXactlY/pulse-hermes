"""Scoring engine for PULSE items.

Computes multi-signal scores: relevance, recency, engagement, source quality,
engagement velocity, retentive value, and cross-source confirmation.
"""

import hashlib
import math
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import dates, log
from .schema import SourceItem

# SQLite for retentive value tracking
CACHE_DIR = Path.home() / ".cache" / "pulse"
CACHE_DB = CACHE_DIR / "cache.db"
_ret_local = threading.local()


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


def _get_ret_conn() -> sqlite3.Connection:
    """Get thread-local SQLite connection for source_retention tracking."""
    if not hasattr(_ret_local, "conn") or _ret_local.conn is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _ret_local.conn = sqlite3.connect(str(CACHE_DB))
        _ret_local.conn.execute("PRAGMA journal_mode=WAL")
        _ret_local.conn.execute("PRAGMA synchronous=NORMAL")
        _ret_local.conn.execute("""
            CREATE TABLE IF NOT EXISTS source_retention (
                topic_hash TEXT NOT NULL,
                source TEXT NOT NULL,
                avg_score REAL DEFAULT 0.0,
                count INTEGER DEFAULT 0,
                updated_at REAL NOT NULL,
                PRIMARY KEY (topic_hash, source)
            )
        """)
        _ret_local.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sr_hash
            ON source_retention(topic_hash)
        """)
        _ret_local.conn.commit()
    return _ret_local.conn


def _topic_hash(topic: str) -> str:
    """Stable hash for a topic string."""
    return hashlib.sha256(topic.lower().strip().encode()).hexdigest()[:16]


def _update_retention(topic: str, source: str, score: float) -> None:
    """Update running average score for topic/source pair."""
    thash = _topic_hash(topic)
    import time
    now = time.time()
    conn = _get_ret_conn()
    try:
        conn.execute(
            """INSERT INTO source_retention (topic_hash, source, avg_score, count, updated_at)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(topic_hash, source) DO UPDATE SET
                 avg_score = (avg_score * count + excluded.avg_score) / (count + 1),
                 count = count + 1,
                 updated_at = excluded.updated_at""",
            (thash, source, score, now),
        )
        conn.commit()
    except sqlite3.Error:
        pass


def compute_retentive_value(item: SourceItem, topic: str) -> float:
    """Compute retentive value based on historical source performance for topic.

    Sources that consistently produce high-scoring content for a given topic
    get a boost. Returns 0.0-1.0.
    """
    thash = _topic_hash(topic)
    conn = _get_ret_conn()
    try:
        row = conn.execute(
            """SELECT avg_score, count FROM source_retention
               WHERE topic_hash = ? AND source = ?""",
            (thash, item.source),
        ).fetchone()
        if row is None:
            return 0.3  # Baseline for no history
        avg_score, count = row
        # Confidence grows with count (log scale), capped at 1.0
        confidence = min(1.0, math.log1p(count) / 5.0)
        # Blend: confidence * avg_score + (1 - confidence) * baseline
        return round(confidence * avg_score + (1 - confidence) * 0.3, 3)
    except sqlite3.Error:
        return 0.3


def compute_cross_source_confirmation(
    item: SourceItem, all_items: List[SourceItem], threshold: float = 0.6
) -> float:
    """Boost score if similar content appears in 3+ sources.

    Uses title token overlap to detect same-content appearances across sources.
    Returns 0.0-1.0 (1.0 if confirmed by 5+ sources).
    """
    from .relevance import token_overlap_relevance

    item_tokens = set(item.title.lower().split())
    if len(item_tokens) < 2:
        return 0.0

    confirming_sources = set()
    for other in all_items:
        if other.source == item.source:
            continue
        sim = token_overlap_relevance(item.title, other.title)
        if sim >= threshold:
            confirming_sources.add(other.source)

    count = len(confirming_sources)
    if count == 0:
        return 0.0
    if count == 1:
        return 0.3
    if count == 2:
        return 0.6
    # 3+ sources: strong signal
    return min(1.0, 0.6 + 0.2 * (count - 2))


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
    all_items: Optional[List[SourceItem]] = None,
) -> SourceItem:
    """Compute all scores for an item.

    Mutates and returns the item with score fields populated.
    Scoring weights:
      - Local Relevance: 25% — token overlap with topic
      - Freshness: 15% — recency within lookback
      - Engagement: 20% — platform metrics
      - Engagement Velocity: 10% — how fast engagement grows
      - Source Quality: 10% — baseline trust
      - Retentive Value: 10% — historical source performance for topic
      - Cross-Source Confirmation: 10% — same content in 3+ sources
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

    # Retentive value
    retentive = compute_retentive_value(item, topic)

    # Cross-source confirmation (requires batch context)
    if all_items is not None:
        cross_source = compute_cross_source_confirmation(item, all_items)
    else:
        cross_source = 0.0

    # Combined local rank score
    freshness_norm = item.freshness / 100.0
    item.local_rank_score = (
        0.25 * item.local_relevance +
        0.15 * freshness_norm +
        0.20 * item.engagement_score +
        0.10 * velocity +
        0.10 * item.source_quality +
        0.10 * retentive +
        0.10 * cross_source
    )

    # Update retention DB with this item's final score
    _update_retention(topic, item.source, item.local_rank_score)

    return item


def score_items(
    items: list[SourceItem],
    topic: str,
    from_date: str,
    to_date: str,
    max_days: int = 30,
) -> list[SourceItem]:
    """Score all items in a list.

    Passes all items as batch context for cross-source confirmation.
    """
    return [
        score_item(item, topic, from_date, to_date, max_days, all_items=items)
        for item in items
    ]
