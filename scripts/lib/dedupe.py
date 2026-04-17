"""Near-duplicate detection for last30days items.

Multi-pass deduplication:
1. URL exact match - source-aware: keep higher-engagement item when
   duplicate URLs appear across sources
2. Content hash (title + body fingerprint) - groups by hash key
3. Source-aware cross-source dedup - same content hash across sources,
   keep higher-engagement version
4. Bigram pre-filtered cosine similarity with adaptive threshold
   - Bigram inverted index: only compare items sharing >=2 bigrams
   - Adaptive threshold: 0.90 (<50 items), 0.85 (50-500), 0.80 (>500)
   - Batch processing in chunks of 100 for memory bounds

Tracks removal stats per source.
"""

import hashlib
import re
from collections import defaultdict
from typing import List, Set, Dict

from . import log
from .relevance import cosine_similarity
from .schema import SourceItem


def _source_log(msg: str):
    log.source_log("Dedupe", msg)


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    text = text.lower().strip()
    text = re.sub(r"https?://\S+", "", text)  # Remove URLs
    text = re.sub(r"[^\w\s]", "", text)  # Remove punctuation
    text = re.sub(r"\s+", " ", text)  # Normalize whitespace
    return text.strip()


def _content_hash(item: SourceItem) -> str:
    """Generate a content fingerprint from title + first 200 chars of body."""
    text = f"{_normalize_text(item.title)}:{_normalize_text(item.body[:200])}"
    return hashlib.md5(text.encode()).hexdigest()


def _get_bigrams(text: str) -> Set[str]:
    """Extract bigrams from normalized text for pre-filtering."""
    normalized = _normalize_text(text)
    tokens = normalized.split()
    if len(tokens) < 2:
        return set()
    return {f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)}


def _get_engagement_score(item: SourceItem) -> float:
    """Extract a composite engagement score from an item."""
    eng = item.engagement
    if not eng:
        return item.engagement_score or 0.0
    # Sum available engagement metrics with weights
    score = 0.0
    # Common engagement keys across sources
    for key, weight in [
        ("score", 1.0), ("ups", 1.0), ("upvotes", 1.0),
        ("likes", 1.0), ("points", 1.0), ("views", 0.01),
        ("comments", 2.0), ("num_comments", 2.0),
        ("retweets", 2.0), ("replies", 2.0),
    ]:
        val = eng.get(key)
        if val is not None:
            score += float(val) * weight
    return max(score, item.engagement_score or 0.0)


def _adaptive_threshold(n_items: int) -> float:
    """Return adaptive cosine similarity threshold based on item count."""
    if n_items < 50:
        return 0.90
    elif n_items <= 500:
        return 0.85
    else:
        return 0.80


def deduplicate(items: List[SourceItem], threshold: float = 0.65) -> List[SourceItem]:
    """Remove near-duplicate items using multi-pass dedup.

    Pass 1: Source-aware URL dedup (keep higher-engagement across sources)
    Pass 2: Content hash dedup within same source
    Pass 3: Source-aware cross-source dedup (keep higher-engagement)
    Pass 4: Bigram pre-filtered cosine similarity with adaptive threshold

    Batch processing with chunks of 100 for memory bounds.

    Args:
        items: List of SourceItems (should already be scored)
        threshold: Cosine similarity threshold for dedup (0.0 - 1.0).
                   If <= 0, uses adaptive threshold based on item count.

    Returns:
        Deduplicated list
    """
    if not items:
        return items

    # Per-source removal stats
    source_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"url": 0, "hash": 0, "cross_source": 0, "cosine": 0})

    # Pass 1: exact URL dedup (source-aware: keep higher-engagement for dup URLs)
    url_best: Dict[str, SourceItem] = {}
    url_deduped: List[SourceItem] = []

    for item in items:
        url = item.url.lower().rstrip("/")
        if not url:
            url_deduped.append(item)
            continue
        if url in url_best:
            existing = url_best[url]
            if _get_engagement_score(item) > _get_engagement_score(existing):
                # New item has higher engagement; replace
                source_stats[existing.source]["url"] += 1
                url_best[url] = item
            else:
                source_stats[item.source]["url"] += 1
        else:
            url_best[url] = item

    url_deduped = list(url_best.values())

    # Pass 2: Content hash dedup within same source (keep best per hash)
    hash_by_source: Dict[tuple, List[SourceItem]] = defaultdict(list)
    for item in url_deduped:
        key = (item.source, _content_hash(item))
        hash_by_source[key].append(item)

    hash_deduped: List[SourceItem] = []
    for key, group in hash_by_source.items():
        if len(group) == 1:
            hash_deduped.append(group[0])
        else:
            # Keep highest engagement within same source + hash
            best = max(group, key=_get_engagement_score)
            hash_deduped.append(best)
            for item in group:
                if item is not best:
                    source_stats[item.source]["hash"] += 1

    # Pass 3: Source-aware dedup - across sources, keep higher-engagement
    # Group by content hash, keep best across sources
    hash_groups: Dict[str, List[SourceItem]] = defaultdict(list)
    for item in hash_deduped:
        ch = _content_hash(item)
        hash_groups[ch].append(item)

    source_aware: List[SourceItem] = []
    for ch, group in hash_groups.items():
        if len(group) == 1:
            source_aware.append(group[0])
        else:
            # Check if items are from different sources
            sources_in_group = set(item.source for item in group)
            if len(sources_in_group) > 1:
                # Keep the one with highest engagement
                best = max(group, key=_get_engagement_score)
                source_aware.append(best)
                for item in group:
                    if item is not best:
                        source_stats[item.source]["cross_source"] += 1
            else:
                # Same source - keep all, let cosine handle it
                source_aware.extend(group)

    # Pass 4: Cosine similarity dedup with bigram pre-filter
    # Adaptive threshold if threshold not explicitly set (<=0 means auto)
    if threshold <= 0:
        effective_threshold = _adaptive_threshold(len(source_aware))
    else:
        effective_threshold = threshold

    if len(source_aware) <= 1:
        kept = source_aware
    else:
        # Batch processing: chunks of 100 for memory bounds
        # Sort by engagement descending so best items are processed first
        sorted_aware = sorted(source_aware, key=_get_engagement_score, reverse=True)
        chunk_size = 100
        all_kept: List[SourceItem] = []
        cosine_removed = 0

        for i in range(0, len(sorted_aware), chunk_size):
            chunk = sorted_aware[i:i + chunk_size]
            new_kept: List[SourceItem] = []

            for item in chunk:
                is_dup = False
                item_bigrams = _get_bigrams(item.title)

                # Compare against all previously kept items (cross-chunk)
                for existing in all_kept:
                    existing_bigrams = _get_bigrams(existing.title)
                    # Bigram pre-filter: skip cosine if both have bigrams but share <2
                    if item_bigrams and existing_bigrams:
                        shared = item_bigrams & existing_bigrams
                        if len(shared) < 2:
                            continue
                    sim = cosine_similarity(item.title, existing.title)
                    if sim >= effective_threshold:
                        is_dup = True
                        cosine_removed += 1
                        break

                # Also compare against items already kept in this chunk
                if not is_dup:
                    for existing in new_kept:
                        existing_bigrams = _get_bigrams(existing.title)
                        if item_bigrams and existing_bigrams:
                            shared = item_bigrams & existing_bigrams
                            if len(shared) < 2:
                                continue
                        sim = cosine_similarity(item.title, existing.title)
                        if sim >= effective_threshold:
                            is_dup = True
                            cosine_removed += 1
                            break

                if not is_dup:
                    new_kept.append(item)

            all_kept.extend(new_kept)

        kept = all_kept

    total_deduped = len(items) - len(kept)
    if total_deduped > 0:
        breakdown = (
            f"{sum(s['url'] for s in source_stats.values())} URL, "
            f"{sum(s['hash'] for s in source_stats.values())} content, "
            f"{sum(s['cross_source'] for s in source_stats.values())} cross-source, "
            f"{sum(s['cosine'] for s in source_stats.values())} similar"
        )
        _source_log(f"Deduped {total_deduped} items ({len(items)} -> {len(kept)}): {breakdown}")

        # Per-source stats
        for src, stats in sorted(source_stats.items()):
            removed_count = sum(stats.values())
            if removed_count > 0:
                _source_log(f"  [{src}] removed {removed_count}: "
                           f"URL={stats['url']} hash={stats['hash']} "
                           f"cross={stats['cross_source']} cosine={stats['cosine']}")

    return kept


class Deduplicator:
    """Stateful deduplicator with bigram pre-filtering and adaptive thresholds.

    Maintains the dedup(results, threshold) interface.
    """

    def __init__(self):
        self.stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "url": 0, "hash": 0, "cross_source": 0, "cosine": 0, "total_in": 0, "total_out": 0
        })

    def dedup(self, results: List[SourceItem], threshold: float = 0.65) -> List[SourceItem]:
        """Deduplicate a list of results.

        Args:
            results: List of SourceItem to deduplicate
            threshold: Similarity threshold. If <= 0, uses adaptive.

        Returns:
            Deduplicated list of SourceItem
        """
        # Track input counts per source
        for item in results:
            self.stats[item.source]["total_in"] += 1

        kept = deduplicate(results, threshold)

        # Track output counts per source
        for item in kept:
            self.stats[item.source]["total_out"] += 1

        return kept

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Return cumulative dedup statistics per source."""
        return dict(self.stats)

    def reset_stats(self):
        """Reset cumulative statistics."""
        self.stats.clear()
