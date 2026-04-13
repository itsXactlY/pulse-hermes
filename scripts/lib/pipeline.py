"""v3 orchestration pipeline for last30days.

Coordinates discovery, enrichment, normalization, scoring, deduplication,
fusion, clustering, and rendering.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import (
    cluster as _cluster,
    config as _config,
    dates as _dates,
    dedupe as _dedupe,
    fusion as _fusion,
    github as _github,
    hackernews as _hackernews,
    log,
    news as _news,
    normalize as _normalize,
    planner as _planner,
    polymarket as _polymarket,
    reddit as _reddit,
    score as _score,
    web_search as _web,
)
from .schema import (
    Candidate,
    QueryPlan,
    Report,
    RetrievalBundle,
    SourceItem,
)

DEPTH_SETTINGS = {
    "quick": {"per_stream_limit": 6, "pool_limit": 15},
    "default": {"per_stream_limit": 12, "pool_limit": 40},
    "deep": {"per_stream_limit": 20, "pool_limit": 60},
}


def _source_log(msg: str):
    log.source_log("Pipeline", msg)


def _retrieve_stream(
    topic: str,
    subquery_label: str,
    search_query: str,
    source: str,
    config: Dict[str, Any],
    depth: str,
    date_range: Tuple[str, str],
) -> Tuple[List[Dict[str, Any]], None]:
    """Retrieve items from a single source for a single subquery.

    Returns (raw_items, artifact).
    """
    from_date, to_date = date_range

    _source_log(f"Fetching {source} for '{search_query}'")

    try:
        if source == "reddit":
            items = _reddit.search(search_query, depth=depth)
        elif source == "hackernews":
            items = _hackernews.search(search_query, from_date, to_date, depth=depth)
        elif source == "polymarket":
            items = _polymarket.search(search_query, depth=depth)
        elif source == "github":
            items = _github.search(search_query, from_date, to_date, depth=depth,
                                   token=config.get("GITHUB_TOKEN"))
        elif source == "web":
            items = _web.search(search_query, config, depth=depth)
        elif source == "news":
            key = config.get("NEWSAPI_KEY")
            if key:
                items = _news.search(search_query, key, from_date, to_date, depth=depth)
            else:
                items = []
        else:
            _source_log(f"Unknown source: {source}")
            items = []

        return items, None

    except Exception as e:
        _source_log(f"Error fetching {source}: {e}")
        raise


def _normalize_score_dedupe(
    source: str,
    raw_items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
    topic: str,
    max_days: int = 30,
) -> List[SourceItem]:
    """Normalize, score, and deduplicate items from a single source."""
    # Normalize
    items = _normalize.normalize_items(source, raw_items, from_date, to_date)

    # Score
    items = _score.score_items(items, topic, from_date, to_date, max_days)

    # Deduplicate
    items = _dedupe.deduplicate(items)

    return items


def run(
    *,
    topic: str,
    config: Dict[str, Any],
    depth: str = "default",
    requested_sources: Optional[List[str]] = None,
    lookback_days: int = 30,
) -> Report:
    """Run the full research pipeline.

    Args:
        topic: Research topic
        config: Configuration dict with API keys
        depth: Research depth ('quick', 'default', 'deep')
        requested_sources: Optional list of specific sources to search
        lookback_days: Number of days to look back (default 30)

    Returns:
        Report with ranked clusters and candidates
    """
    settings = DEPTH_SETTINGS.get(depth, DEPTH_SETTINGS["default"])
    from_date, to_date = _dates.get_date_range(lookback_days)

    # Determine available sources
    available = _config.available_sources(config)
    if requested_sources:
        available = [s for s in available if s in requested_sources]

    if not available:
        raise RuntimeError("No sources available. Check your API keys.")

    _source_log(f"Available sources: {', '.join(available)}")

    # Generate query plan
    plan = _planner.plan_query(
        topic=topic,
        available_sources=available,
        depth=depth,
        requested_sources=requested_sources,
    )

    # Retrieval bundle
    bundle = RetrievalBundle()

    # Execute subqueries in parallel
    futures = {}
    stream_count = sum(
        1 for sq in plan.subqueries for source in sq.sources if source in available
    )
    max_workers = max(4, min(16, stream_count or 1))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for subquery in plan.subqueries:
            for source in subquery.sources:
                if source not in available:
                    continue
                futures[executor.submit(
                    _retrieve_stream,
                    topic=topic,
                    subquery_label=subquery.label,
                    search_query=subquery.search_query,
                    source=source,
                    config=config,
                    depth=depth,
                    date_range=(from_date, to_date),
                )] = (subquery, source)

        for future in as_completed(futures):
            subquery, source = futures[future]
            try:
                raw_items, artifact = future.result()
            except Exception as e:
                bundle.errors_by_source[source] = str(e)
                continue

            # Normalize, score, dedupe
            normalized = _normalize_score_dedupe(
                source, raw_items, from_date, to_date, topic, lookback_days,
            )
            # Limit per stream
            normalized = normalized[:settings["per_stream_limit"]]
            bundle.add_items(subquery.label, source, normalized)

    # Compute subquery weights
    subquery_weights = {sq.label: sq.weight for sq in plan.subqueries}

    # Fusion: weighted RRF
    candidates = _fusion.weighted_rrf(
        bundle.items_by_source_and_query,
        plan.source_weights,
        subquery_weights,
    )

    # Apply pool limit
    candidates = candidates[:settings["pool_limit"]]

    # Clustering
    clusters = _cluster.cluster_candidates(candidates)

    # Build report
    now = datetime.now(timezone.utc).isoformat()

    report = Report(
        topic=topic,
        range_from=from_date,
        range_to=to_date,
        generated_at=now,
        query_plan=plan,
        clusters=clusters,
        ranked_candidates=candidates,
        items_by_source=bundle.items_by_source,
        errors_by_source=bundle.errors_by_source,
    )

    total = sum(len(items) for items in bundle.items_by_source.values())
    _source_log(f"Pipeline complete: {total} items, {len(clusters)} clusters, {len(candidates)} candidates")

    return report
