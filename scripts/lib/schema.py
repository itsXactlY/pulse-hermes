"""Core data model for the last30days pipeline."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal


def _drop_none(value: Any) -> Any:
    """Recursively remove None values from dataclass-derived structures."""
    if is_dataclass(value):
        return _drop_none(asdict(value))
    if isinstance(value, dict):
        return {key: _drop_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


@dataclass(frozen=True)
class SubQuery:
    """Planner-emitted retrieval unit."""
    label: str
    search_query: str
    ranking_query: str
    sources: list[str]
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError("SubQuery must have at least one source")
        if self.weight <= 0:
            raise ValueError(f"SubQuery weight must be positive, got {self.weight}")


@dataclass
class QueryPlan:
    """Planner output."""
    intent: str
    freshness_mode: str
    raw_topic: str
    subqueries: list[SubQuery]
    source_weights: dict[str, float]
    notes: list[str] = field(default_factory=list)


@dataclass
class SourceItem:
    """Generic normalized evidence item."""
    item_id: str
    source: str
    title: str
    body: str
    url: str
    author: str | None = None
    container: str | None = None  # subreddit, channel, etc.
    published_at: str | None = None
    date_confidence: Literal["high", "med", "low"] = "low"
    engagement: dict[str, float | int] = field(default_factory=dict)
    relevance_hint: float = 0.5
    why_relevant: str = ""
    snippet: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Signal fields
    local_relevance: float | None = None
    freshness: int | None = None
    engagement_score: float | None = None
    source_quality: float | None = None
    local_rank_score: float | None = None


@dataclass
class Candidate:
    """Global candidate after fusion and reranking."""
    candidate_id: str
    item_id: str
    source: str
    title: str
    url: str
    snippet: str
    subquery_labels: list[str]
    native_ranks: dict[str, int]
    local_relevance: float
    freshness: int
    engagement: int | float | None
    source_quality: float
    rrf_score: float
    sources: list[str] = field(default_factory=list)
    source_items: list[SourceItem] = field(default_factory=list)
    rerank_score: float | None = None
    final_score: float = 0.0
    explanation: str | None = None
    cluster_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Cluster:
    """Ranked cluster of related candidates."""
    cluster_id: str
    title: str
    candidate_ids: list[str]
    representative_ids: list[str]
    sources: list[str]
    score: float
    uncertainty: Literal["single-source", "thin-evidence"] | None = None


@dataclass
class Report:
    """Final pipeline output."""
    topic: str
    range_from: str
    range_to: str
    generated_at: str
    query_plan: QueryPlan
    clusters: list[Cluster]
    ranked_candidates: list[Candidate]
    items_by_source: dict[str, list[SourceItem]]
    errors_by_source: dict[str, str]
    warnings: list[str] = field(default_factory=list)


@dataclass
class RetrievalBundle:
    """Structured retrieval output before global ranking."""
    items_by_source_and_query: dict[tuple[str, str], list[SourceItem]] = field(default_factory=dict)
    items_by_source: dict[str, list[SourceItem]] = field(default_factory=dict)
    errors_by_source: dict[str, str] = field(default_factory=dict)

    def add_items(self, label: str, source: str, items: list[SourceItem]) -> None:
        self.items_by_source_and_query.setdefault((label, source), []).extend(items)
        self.items_by_source.setdefault(source, []).extend(items)


def to_dict(value: Any) -> Any:
    """Serialize dataclasses and nested containers."""
    return _drop_none(value)


def slugify(value: str) -> str:
    """Convert a topic to a filename-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "last30days"
