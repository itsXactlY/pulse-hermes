"""v3 orchestration pipeline for PULSE.

Coordinates discovery, enrichment, normalization, scoring, deduplication,
fusion, clustering, and rendering. Now with caching, persistent store,
YouTube, LLM planner, and live progress UI.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import (
    adaptive_lookback as _adaptive_lb,
    arxiv as _arxiv,
    bing_news as _bing_news,
    bluesky as _bluesky,
    cache as _cache,
    cluster as _cluster,
    config as _config,
    dates as _dates,
    dedupe as _dedupe,
    devto as _devto,
    filter as _filter,
    fusion as _fusion,
    github as _github,
    hackernews as _hackernews,
    lemmy as _lemmy,
    lobsters as _lobsters,
    log,
    manifold as _manifold,
    metaculus as _metaculus,
    neural_memory as _neural_mem,
    news as _news,
    normalize as _normalize,
    openalex as _openalex,
    planner as _heuristic_planner,
    llm_planner as _llm_planner,
    polymarket as _polymarket,
    query_router as _query_router,
    reddit as _reddit,
    rss as _rss,
    score as _score,
    self_learn as _self_learn,
    sem_scholar as _sem_scholar,
    serpapi_news as _serpapi_news,
    stackexchange as _stackexchange,
    store as _store,
    tickertick as _tickertick,
    twitter_browser as _twitter,
    ui as _ui,
    web_search as _web,
    youtube as _youtube,
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

# Source dispatch map: source name -> module with .search()
SOURCE_MAP = {
    "reddit": _reddit,
    "hackernews": _hackernews,
    "polymarket": _polymarket,
    "github": _github,
    "web": _web,
    "news": _news,
    "youtube": _youtube,
    "arxiv": _arxiv,
    "lobsters": _lobsters,
    "rss": _rss,
    "openalex": _openalex,
    "sem_scholar": _sem_scholar,
    "manifold": _manifold,
    "metaculus": _metaculus,
    "bluesky": _bluesky,
    "stackexchange": _stackexchange,
    "lemmy": _lemmy,
    "devto": _devto,
    "tickertick": _tickertick,
    "twitter_browser": _twitter,
    "bing_news": _bing_news,
    "serpapi_news": _serpapi_news,
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
    """Retrieve items from a single source for a single subquery."""
    from_date, to_date = date_range

    # Check cache first
    cached = _cache.get(source, search_query, from_date, to_date)
    if cached is not None:
        return cached, None

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
        elif source == "youtube":
            items = _youtube.search(search_query, depth=depth)
        elif source == "arxiv":
            items = _arxiv.search(search_query, from_date, to_date, depth=depth)
        elif source == "lobsters":
            items = _lobsters.search(search_query, from_date, to_date, depth=depth)
        elif source == "rss":
            items = _rss.search(search_query, from_date, to_date, depth=depth)
        elif source == "openalex":
            items = _openalex.search(search_query, from_date, to_date, depth=depth)
        elif source == "sem_scholar":
            items = _sem_scholar.search(search_query, from_date, to_date, depth=depth)
        elif source == "manifold":
            items = _manifold.search(search_query, from_date, to_date, depth=depth)
        elif source == "metaculus":
            items = _metaculus.search(search_query, from_date, to_date, depth=depth)
        elif source == "bluesky":
            items = _bluesky.search(search_query, from_date, to_date, depth=depth)
        elif source == "stackexchange":
            items = _stackexchange.search(search_query, from_date, to_date, depth=depth)
        elif source == "lemmy":
            items = _lemmy.search(search_query, from_date, to_date, depth=depth)
        elif source == "devto":
            items = _devto.search(search_query, from_date, to_date, depth=depth)
        elif source == "tickertick":
            items = _tickertick.search(search_query, from_date, to_date, depth=depth)
        elif source == "twitter_browser":
            items = _twitter.search(search_query, from_date, to_date, depth=depth)
        elif source == "bing_news":
            items = _bing_news.search(search_query, config, from_date, to_date, depth=depth)
        elif source == "serpapi_news":
            key = config.get("SERPAPI_KEY")
            if key:
                items = _serpapi_news.search(search_query, key, from_date, to_date, depth=depth)
            else:
                items = []
        else:
            _source_log(f"Unknown source: {source}")
            items = []

        # Cache the results
        if items:
            _cache.put(source, search_query, items, from_date, to_date)

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
    items = _normalize.normalize_items(source, raw_items, from_date, to_date)
    items = _score.score_items(items, topic, from_date, to_date, max_days)
    items = _dedupe.deduplicate(items)
    items = _filter.filter_items(items)  # Filter out blocked content
    return items


def run(
    *,
    topic: str,
    config: Dict[str, Any],
    depth: str = "default",
    requested_sources: Optional[List[str]] = None,
    lookback_days: int = 30,
    use_llm: bool = True,
    use_cache: bool = True,
    use_store: bool = True,
    progress: bool = True,
) -> Report:
    """Run the full research pipeline.

    Args:
        topic: Research topic
        config: Configuration dict with API keys
        depth: Research depth ('quick', 'default', 'deep')
        requested_sources: Optional list of specific sources to search
        lookback_days: Number of days to look back (default 30)
        use_llm: Use LLM planner if available (default True)
        use_cache: Use SQLite cache (default True)
        use_store: Save to persistent store (default True)
        progress: Show progress UI (default True)

    Returns:
        Report with ranked clusters and candidates
    """
    settings = DEPTH_SETTINGS.get(depth, DEPTH_SETTINGS["default"])
    from_date, to_date = _dates.get_date_range(lookback_days)

    # Query router: classify and optimize source ordering
    router = _query_router.QueryRouter()
    lookback_tracker = _adaptive_lb.AdaptiveLookback()

    # Adaptive lookback: adjust window based on topic density
    adaptive_days = lookback_tracker.get_lookback(topic)
    if adaptive_days != lookback_days:
        _source_log(f"Adaptive lookback: {lookback_days}d -> {adaptive_days}d for topic density")
        from_date, to_date = _dates.get_date_range(adaptive_days)
        lookback_days = adaptive_days

    # Prune expired cache entries
    if use_cache:
        _cache.prune()

    # Determine available sources
    available = _config.available_sources(config)
    if requested_sources:
        available = [s for s in available if s in requested_sources]

    if not available:
        raise RuntimeError("No sources available. Check your API keys.")

    _source_log(f"Available sources: {', '.join(available)}")

    # Progress UI
    ui = _ui.ProgressDisplay(topic, show=progress)
    ui.start()

    # Neural memory: recall past context
    neural_context = _neural_mem.recall_context(topic, limit=3)
    if neural_context:
        _source_log(f"Neural memory: found {len(neural_context)} past memories")

    # Self-learning: boost sources that performed well in past searches
    past_performance = _self_learn.get_source_performance(topic)
    if past_performance:
        _source_log(f"Self-learning: found past performance data for {len(past_performance)} sources")

    # Generate query plan (LLM or heuristic)
    if use_llm:
        plan = _llm_planner.plan_query(
            topic=topic,
            available_sources=available,
            depth=depth,
            config=config,
            requested_sources=requested_sources,
        )
    else:
        plan = _heuristic_planner.plan_query(
            topic=topic,
            available_sources=available,
            depth=depth,
            requested_sources=requested_sources,
        )

    # Apply self-learning boost to source weights
    if past_performance:
        plan.source_weights = _self_learn.boost_weights(
            plan.source_weights, past_performance
        )

    # Query router: classify and boost routed sources by 15%
    query_type = router.classify(topic)
    _source_log(f"Query type: {query_type}")
    for source in plan.source_weights:
        plan.source_weights[source] = plan.source_weights[source] * 1.15

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
                ui.update_source(source, f"searching '{subquery.search_query[:30]}'...")

        for future in as_completed(futures):
            subquery, source = futures[future]
            try:
                raw_items, artifact = future.result()
                ui.source_done(source, len(raw_items))
            except Exception as e:
                bundle.errors_by_source[source] = str(e)
                ui.source_error(source, str(e))
                continue

            # Normalize, score, dedupe
            normalized = _normalize_score_dedupe(
                source, raw_items, from_date, to_date, topic, lookback_days,
            )
            normalized = normalized[:settings["per_stream_limit"]]
            bundle.add_items(subquery.label, source, normalized)

            # Record result density for adaptive lookback
            if normalized:
                lookback_tracker.record_result(topic, source)

    # Compute subquery weights
    subquery_weights = {sq.label: sq.weight for sq in plan.subqueries}

    # Fusion: weighted RRF
    candidates = _fusion.weighted_rrf(
        bundle.items_by_source_and_query,
        plan.source_weights,
        subquery_weights,
    )

    # Filter out blocked content after fusion
    candidates = _filter.filter_items(candidates)

    # Apply pool limit
    candidates = candidates[:settings["pool_limit"]]

    # Clustering
    clusters = _cluster.cluster_candidates(candidates)

    # Build report
    now = datetime.now(timezone.utc).isoformat()
    total_items = sum(len(items) for items in bundle.items_by_source.values())

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

    # Progress summary
    source_counts = {s: len(items) for s, items in bundle.items_by_source.items()}
    ui.show_complete(
        source_counts=source_counts,
        total_items=total_items,
        total_clusters=len(clusters),
    )

    # Save to persistent store
    new_findings = 0
    if use_store:
        try:
            counts = _store.save_report(report)
            new_findings = counts.get("new", 0)
        except Exception as e:
            _source_log(f"Store save failed: {e}")

    # Save to neural memory (top findings only)
    try:
        all_items = []
        for items in bundle.items_by_source.values():
            all_items.extend(items)
        neural_items = [
            {"title": item.title, "source": item.source, "url": item.url}
            for item in all_items[:15]
        ]
        _neural_mem.save_findings(topic, neural_items, limit=10)
    except Exception as e:
        _source_log(f"Neural memory save failed: {e}")

    _source_log(f"Pipeline complete: {total_items} items, {len(clusters)} clusters, {len(candidates)} candidates")

    return report
