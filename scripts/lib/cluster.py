"""Cluster related candidates into thematic groups."""

import hashlib
import re
from collections import defaultdict
from typing import Dict, List, Set

from . import log
from .schema import Candidate, Cluster


def _source_log(msg: str):
    log.source_log("Cluster", msg)


def _normalize_for_cluster(text: str) -> str:
    """Normalize text for clustering."""
    text = text.lower().strip()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_key_terms(text: str, min_len: int = 3) -> Set[str]:
    """Extract significant terms from text."""
    words = _normalize_for_cluster(text).split()
    stops = {
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
        "of", "and", "or", "but", "not", "with", "this", "that", "it", "be", "by",
        "from", "as", "do", "has", "had", "have", "will", "would", "could", "should",
        "been", "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "can", "need", "dare", "ought",
        "about", "above", "after", "again", "all", "also", "am", "any", "because",
        "before", "between", "both", "each", "few", "more", "most", "other", "some",
        "such", "than", "too", "very", "just", "into", "over", "own", "same", "so",
        "still", "up", "down", "out", "off", "now", "then", "here", "there", "when",
        "where", "why", "how", "what", "which", "who", "whom", "while", "during",
    }
    return {w for w in words if len(w) >= min_len and w not in stops}


def _compute_similarity(terms1: Set[str], terms2: Set[str]) -> float:
    """Compute Jaccard similarity between two term sets."""
    if not terms1 or not terms2:
        return 0.0
    intersection = terms1 & terms2
    union = terms1 | terms2
    return len(intersection) / len(union) if union else 0.0


def _generate_cluster_title(candidates: List[Candidate]) -> str:
    """Generate a human-readable title for a cluster."""
    # Collect all terms and count frequency
    term_counts: Dict[str, int] = defaultdict(int)
    for c in candidates:
        terms = _extract_key_terms(c.title)
        for t in terms:
            term_counts[t] += 1

    # Sort by frequency, take top 3
    top_terms = sorted(term_counts.items(), key=lambda x: -x[1])[:3]
    if top_terms:
        return " ".join(t[0] for t in top_terms).title()

    # Fallback: use the top candidate's title
    return candidates[0].title[:60] if candidates else "Untitled"


def cluster_candidates(
    candidates: List[Candidate],
    similarity_threshold: float = 0.25,
) -> List[Cluster]:
    """Cluster candidates by content similarity.

    Args:
        candidates: Ranked list of candidates
        similarity_threshold: Minimum term overlap for clustering

    Returns:
        List of Clusters sorted by score (descending)
    """
    if not candidates:
        return []

    # Pre-compute terms for each candidate
    candidate_terms: Dict[str, Set[str]] = {}
    for c in candidates:
        combined = f"{c.title} {c.snippet}"
        candidate_terms[c.candidate_id] = _extract_key_terms(combined)

    # Union-Find for clustering
    parent: Dict[str, str] = {c.candidate_id: c.candidate_id for c in candidates}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Compare all pairs (O(n^2) but fine for typical candidate counts)
    for i, c1 in enumerate(candidates):
        for c2 in candidates[i + 1:]:
            sim = _compute_similarity(
                candidate_terms.get(c1.candidate_id, set()),
                candidate_terms.get(c2.candidate_id, set()),
            )
            if sim >= similarity_threshold:
                union(c1.candidate_id, c2.candidate_id)

    # Also cluster by URL domain
    domain_groups: Dict[str, List[str]] = defaultdict(list)
    for c in candidates:
        if c.url:
            # Extract domain
            try:
                from urllib.parse import urlparse
                domain = urlparse(c.url).netloc
                if domain:
                    domain_groups[domain].append(c.candidate_id)
            except Exception:
                pass

    for domain, cids in domain_groups.items():
        if len(cids) > 1:
            for cid in cids[1:]:
                union(cid, cids[0])

    # Build clusters
    groups: Dict[str, List[Candidate]] = defaultdict(list)
    for c in candidates:
        root = find(c.candidate_id)
        groups[root].append(c)

    clusters = []
    for cluster_id, members in groups.items():
        # Sort members by final_score
        members.sort(key=lambda c: c.final_score, reverse=True)

        # Cluster score = max score + bonus for multiple sources
        sources = set()
        for m in members:
            sources.update(m.sources if m.sources else [m.source])
        source_bonus = 0.1 * (len(sources) - 1)
        cluster_score = members[0].final_score + source_bonus

        # Representative IDs: top 3 candidates
        rep_ids = [m.candidate_id for m in members[:3]]

        # All candidate IDs
        all_ids = [m.candidate_id for m in members]

        # Uncertainty
        uncertainty = None
        if len(sources) == 1:
            uncertainty = "single-source"
        elif len(members) == 1:
            uncertainty = "thin-evidence"

        # Title
        title = _generate_cluster_title(members)

        # Assign cluster_id to candidates
        cid_hash = hashlib.md5(cluster_id.encode()).hexdigest()[:8]
        for m in members:
            m.cluster_id = f"cluster-{cid_hash}"

        clusters.append(Cluster(
            cluster_id=f"cluster-{cid_hash}",
            title=title,
            candidate_ids=all_ids,
            representative_ids=rep_ids,
            sources=sorted(sources),
            score=round(cluster_score, 4),
            uncertainty=uncertainty,
        ))

    # Sort clusters by score
    clusters.sort(key=lambda c: c.score, reverse=True)

    _source_log(f"Clustered {len(candidates)} candidates into {len(clusters)} clusters")
    return clusters
