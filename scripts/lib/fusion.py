"""Weighted Reciprocal Rank Fusion (RRF) for combining ranked lists.

Merges items from multiple sources/subqueries into a single ranked list.
"""

import hashlib
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from . import log
from .schema import Candidate, SourceItem


def _source_log(msg: str):
    log.source_log("Fusion", msg)


# RRF constant (default k=60 from original paper)
RRF_K = 60


def _item_key(item: SourceItem) -> str:
    """Generate a deduplication key for an item."""
    # Use URL if available, otherwise title+source
    if item.url:
        return item.url.lower().rstrip("/")
    return f"{item.source}:{item.title.lower()[:100]}"


def _make_candidate_id(item_key: str) -> str:
    """Generate a stable candidate ID."""
    return hashlib.md5(item_key.encode()).hexdigest()[:12]


def weighted_rrf(
    items_by_source_and_query: Dict[Tuple[str, str], List[SourceItem]],
    source_weights: Dict[str, float],
    subquery_weights: Dict[str, float] | None = None,
    rrf_k: int = RRF_K,
) -> List[Candidate]:
    """Combine ranked lists using weighted RRF.

    Args:
        items_by_source_and_query: Dict mapping (subquery_label, source_name) to ranked items
        source_weights: Weight for each source
        subquery_weights: Weight for each subquery (optional)
        rrf_k: RRF smoothing constant

    Returns:
        List of Candidates sorted by RRF score (descending)
    """
    if subquery_weights is None:
        subquery_weights = {}

    # Aggregate scores per unique item
    candidate_scores: Dict[str, float] = defaultdict(float)
    candidate_items: Dict[str, List[SourceItem]] = defaultdict(list)
    candidate_labels: Dict[str, List[str]] = defaultdict(list)
    candidate_native_ranks: Dict[str, Dict[str, int]] = defaultdict(dict)
    candidate_sources: Dict[str, set] = defaultdict(set)

    for (label, source), items in items_by_source_and_query.items():
        sw = source_weights.get(source, 0.5)
        qw = subquery_weights.get(label, 1.0)
        combined_weight = sw * qw

        for rank, item in enumerate(items, start=1):
            key = _item_key(item)
            cid = _make_candidate_id(key)

            # RRF formula: weight * 1 / (k + rank)
            rrf_contribution = combined_weight / (rrf_k + rank)
            candidate_scores[cid] += rrf_contribution

            candidate_items[cid].append(item)
            if label not in candidate_labels[cid]:
                candidate_labels[cid].append(label)
            candidate_native_ranks[cid][source] = rank
            candidate_sources[cid].add(source)

    # Build Candidate objects
    candidates = []
    for cid, rrf_score in candidate_scores.items():
        items = candidate_items[cid]
        # Use the first item as the primary representative
        primary = items[0]

        # Aggregate engagement across all instances
        total_engagement = 0
        for item in items:
            for val in item.engagement.values():
                if isinstance(val, (int, float)):
                    total_engagement += val

        # Best local_relevance, freshness, engagement_score across instances
        best_relevance = max((i.local_relevance or 0) for i in items)
        best_freshness = max((i.freshness or 0) for i in items)
        best_engagement = max((i.engagement_score or 0) for i in items)
        best_source_quality = max((i.source_quality or 0) for i in items)

        candidate = Candidate(
            candidate_id=cid,
            item_id=primary.item_id,
            source=primary.source,
            title=primary.title,
            url=primary.url,
            snippet=primary.snippet or primary.body[:200],
            subquery_labels=candidate_labels[cid],
            native_ranks=dict(candidate_native_ranks[cid]),
            local_relevance=best_relevance,
            freshness=best_freshness,
            engagement=total_engagement if total_engagement > 0 else best_engagement,
            source_quality=best_source_quality,
            rrf_score=round(rrf_score, 6),
            sources=list(candidate_sources[cid]),
            source_items=items,
            final_score=rrf_score,
        )
        candidates.append(candidate)

    # Sort by RRF score descending
    candidates.sort(key=lambda c: c.rrf_score, reverse=True)

    _source_log(f"RFF: {len(candidates)} candidates from {len(items_by_source_and_query)} streams")
    return candidates
