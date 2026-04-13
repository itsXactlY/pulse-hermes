"""Near-duplicate detection for last30days items."""

import re
from typing import List, Set

from . import log
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


def _title_similarity(title1: str, title2: str) -> float:
    """Compute token-based similarity between two titles."""
    t1 = set(_normalize_text(title1).split())
    t2 = set(_normalize_text(title2).split())

    if not t1 or not t2:
        return 0.0

    # Remove stop words
    stops = {"the", "a", "an", "is", "are", "was", "in", "on", "at", "to", "for", "of", "and", "or", "but"}
    t1 -= stops
    t2 -= stops

    if not t1 or not t2:
        return 0.0

    intersection = t1 & t2
    union = t1 | t2

    return len(intersection) / len(union) if union else 0.0


def deduplicate(items: List[SourceItem], threshold: float = 0.7) -> List[SourceItem]:
    """Remove near-duplicate items.

    Items with the same URL are always deduped.
    Items with title similarity above threshold are deduped (keeps the higher-scoring one).

    Args:
        items: List of SourceItems (should already be scored)
        threshold: Similarity threshold for dedup (0.0 - 1.0)

    Returns:
        Deduplicated list
    """
    if not items:
        return items

    # First pass: exact URL dedup
    seen_urls: Set[str] = set()
    url_deduped: List[SourceItem] = []

    for item in items:
        url = item.url.lower().rstrip("/")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(item)

    # Second pass: title similarity dedup
    if len(url_deduped) <= 1:
        return url_deduped

    # Sort by local_rank_score descending so we keep the best
    sorted_items = sorted(
        url_deduped,
        key=lambda x: x.local_rank_score or 0,
        reverse=True,
    )

    kept: List[SourceItem] = []
    for item in sorted_items:
        is_dup = False
        for existing in kept:
            sim = _title_similarity(item.title, existing.title)
            if sim >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(item)

    deduped_count = len(url_deduped) - len(kept)
    if deduped_count > 0:
        _source_log(f"Deduped {deduped_count} items ({len(url_deduped)} -> {len(kept)})")

    return kept
