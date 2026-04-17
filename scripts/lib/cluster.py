"""Cluster related candidates into thematic groups.

Uses cosine similarity instead of Jaccard for better semantic matching.
Generates meaningful cluster titles using TF-IDF-like term extraction.
"""

import hashlib
import re
from collections import Counter, defaultdict
from typing import Dict, List, Set

from . import log
from .relevance import cosine_similarity, _tokenize
from .schema import Candidate, Cluster


def _source_log(msg: str):
    log.source_log("Cluster", msg)


def _extract_key_terms(text: str, top_n: int = 5) -> List[str]:
    """Extract significant terms using TF-like scoring.

    Returns the top_n most informative terms (excluding stop words).
    """
    tokens = _tokenize(text)
    if not tokens:
        return []

    # Count term frequencies
    freq = Counter(tokens)

    # Score: raw frequency * word length bonus (longer words are more specific)
    scored = []
    for word, count in freq.items():
        # Skip very short or very common words
        if len(word) < 3:
            continue
        # Length bonus: longer words are more specific
        length_bonus = min(2.0, len(word) / 5.0)
        score = count * length_bonus
        scored.append((score, word))

    scored.sort(reverse=True)
    return [word for _, word in scored[:top_n]]


def _generate_cluster_title(candidates: List[Candidate]) -> str:
    """Generate a meaningful cluster title from top terms.

    Uses TF-weighted term extraction + concatenation of top 3-4 terms.
    Falls back to the top candidate's title if no good terms found.
    """
    # Collect all text
    all_text = []
    for c in candidates:
        all_text.append(c.title)
        if c.snippet:
            all_text.append(c.snippet[:100])

    combined = " ".join(all_text)
    terms = _extract_key_terms(combined, top_n=6)

    if terms:
        # Use top 3-4 terms, title-cased
        title_terms = terms[:4]
        return " ".join(t.capitalize() for t in title_terms)

    # Fallback: use the top candidate's title (truncated)
    return candidates[0].title[:60] if candidates else "Untitled"


def cluster_candidates(
    candidates: List[Candidate],
    similarity_threshold: float = 0.20,
) -> List[Cluster]:
    """Cluster candidates by content similarity using cosine similarity.

    Args:
        candidates: Ranked list of candidates
        similarity_threshold: Minimum cosine similarity for clustering

    Returns:
        List of Clusters sorted by score (descending)
    """
    if not candidates:
        return []

    # Pre-compute text representations
    candidate_texts: Dict[str, str] = {}
    for c in candidates:
        candidate_texts[c.candidate_id] = f"{c.title} {c.snippet}"

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

    # Compare all pairs using cosine similarity
    for i, c1 in enumerate(candidates):
        for c2 in candidates[i + 1:]:
            text1 = candidate_texts.get(c1.candidate_id, "")
            text2 = candidate_texts.get(c2.candidate_id, "")
            sim = cosine_similarity(text1, text2)
            if sim >= similarity_threshold:
                union(c1.candidate_id, c2.candidate_id)

    # Also cluster by URL domain (same article from different sources)
    domain_groups: Dict[str, List[str]] = defaultdict(list)
    for c in candidates:
        if c.url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(c.url).netloc
                # Skip generic domains
                if domain and domain not in ("www.youtube.com", "youtu.be", "github.com"):
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

        # Collect sources
        sources = set()
        for m in members:
            sources.update(m.sources if m.sources else [m.source])

        # Multi-source boost: items appearing across sources are more important
        source_bonus = 0.12 * (len(sources) - 1)

        # Size bonus: clusters with more items are more significant
        size_bonus = min(0.15, 0.03 * (len(members) - 1))

        cluster_score = members[0].final_score + source_bonus + size_bonus

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
