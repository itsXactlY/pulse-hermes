"""Near-duplicate detection for last30days items."""
"""Near-duplicate detection for last30days items.

Three-pass deduplication:
1. URL exact match (always dedup)
2. Content hash (title + body fingerprint)
3. Cosine similarity on titles (catches reworded duplicates)
"""

import hashlib
import re
from typing import List, Set

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


def _title_similarity(title1: str, title2: str) -> float:
    """Compute cosine similarity between two titles."""
    return cosine_similarity(title1, title2)


def deduplicate(items: List[SourceItem], threshold: float = 0.65) -> List[SourceItem]:
    """Remove near-duplicate items using three-pass dedup.

    Pass 1: Exact URL match (always dedup)
    Pass 2: Content hash (title+body fingerprint)
    Pass 3: Cosine similarity on titles (catches reworded duplicates)

    Args:
        items: List of SourceItems (should already be scored)
        threshold: Cosine similarity threshold for dedup (0.0 - 1.0)

    Returns:
        Deduplicated list
    """
    if not items:
        return items

    # Pass 1: exact URL dedup
    seen_urls: Set[str] = set()
    url_deduped: List[SourceItem] = []

    for item in items:
        url = item.url.lower().rstrip("/")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(item)

    # Pass 2: content hash dedup
    seen_hashes: Set[str] = set()
    hash_deduped: List[SourceItem] = []

    for item in url_deduped:
        ch = _content_hash(item)
        if ch in seen_hashes:
            continue
        seen_hashes.add(ch)
        hash_deduped.append(item)

    # Pass 3: cosine similarity dedup
    if len(hash_deduped) <= 1:
        return hash_deduped

    # Sort by local_rank_score descending so we keep the best
    sorted_items = sorted(
        hash_deduped,
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

    total_deduped = len(items) - len(kept)
    if total_deduped > 0:
        _source_log(f"Deduped {total_deduped} items ({len(items)} -> {len(kept)}): "
                    f"{len(items) - len(url_deduped)} URL, "
                    f"{len(url_deduped) - len(hash_deduped)} content, "
                    f"{len(hash_deduped) - len(kept)} similar")

    return kept
