"""Iterative retrieval with perspective-based coverage tracking for PULSE.

Runs multiple rounds of retrieval, identifies gaps in perspective coverage,
and generates targeted queries for underrepresented source categories.
"""

from typing import Any, Dict, List, Optional

from . import log
from .schema import Candidate, SourceItem


def _source_log(msg: str):
    log.source_log("IterativeRetrieval", msg)


# Perspective groupings: each perspective maps to a set of source names
PERSPECTIVES: Dict[str, List[str]] = {
    "community": ["reddit", "bluesky", "lemmy"],
    "expert": ["hackernews", "lobsters"],
    "academic": ["arxiv", "sem_scholar", "openalex"],
    "market": ["polymarket", "manifold", "metaculus"],
    "news": ["news", "rss"],
    "code": ["github", "stackexchange", "devto"],
}


class CoverageTracker:
    """Track which perspectives have been covered across retrieval rounds."""

    PERSPECTIVES = PERSPECTIVES

    def __init__(self):
        # Counts results per perspective across all rounds
        self._counts: Dict[str, int] = {p: 0 for p in PERSPECTIVES}

    def record_round(self, results: List[SourceItem]) -> None:
        """Count results per perspective from a list of SourceItems."""
        source_to_perspective: Dict[str, str] = {}
        for perspective, sources in PERSPECTIVES.items():
            for src in sources:
                source_to_perspective[src] = perspective

        for item in results:
            persp = source_to_perspective.get(item.source)
            if persp:
                self._counts[persp] += 1

    def identify_gaps(self) -> List[str]:
        """Return list of perspectives with fewer than 2 results."""
        return [p for p, count in self._counts.items() if count < 2]

    def coverage_score(self) -> int:
        """Return 0-100 based on perspective coverage.

        Score = (number of perspectives with >= 2 results) / total * 100.
        """
        covered = sum(1 for c in self._counts.values() if c >= 2)
        return int((covered / len(PERSPECTIVES)) * 100)

    def summary(self) -> Dict[str, int]:
        """Return dict with all perspective counts."""
        return dict(self._counts)


# Query modifiers to target specific perspectives
_GAP_QUERIES: Dict[str, str] = {
    "community": "community discussion opinion",
    "expert": "expert analysis technical deep dive",
    "academic": "research paper study academic",
    "market": "prediction forecast market odds",
    "news": "news announcement update",
    "code": "code repository implementation open source",
}


class IterativeRetriever:
    """Multi-round retriever that fills perspective gaps."""

    def __init__(self, pipeline_module, config: Dict[str, Any]):
        """
        Args:
            pipeline_module: The pipeline module (from . import pipeline).
            config: Configuration dict with API keys.
        """
        self._pipeline = pipeline_module
        self._config = config

    def retrieve_deep(
        self,
        query: str,
        max_rounds: int = 3,
        depth: str = "default",
        lookback_days: int = 30,
        requested_sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run iterative retrieval with perspective-based gap filling.

        Args:
            query: Research topic.
            max_rounds: Maximum retrieval rounds (default 3).
            depth: Research depth ('quick', 'default', 'deep').
            lookback_days: Number of days to look back.
            requested_sources: Optional list of specific sources.

        Returns:
            Dict with keys:
                results: List of merged, deduped SourceItem objects.
                rounds_info: List of per-round metadata dicts.
                coverage_score: Final coverage score (0-100).
        """
        tracker = CoverageTracker()
        all_results: List[SourceItem] = []
        seen_urls: set = set()
        rounds_info: List[Dict[str, Any]] = []

        # --- Round 1: full pipeline run ---
        _source_log(f"Round 1: full retrieval for '{query}'")
        report = self._pipeline.run(
            topic=query,
            config=self._config,
            depth=depth,
            requested_sources=requested_sources,
            lookback_days=lookback_days,
            use_llm=True,
            use_cache=True,
            use_store=False,
            progress=False,
        )

        round1_items = self._extract_items(report)
        new_items = self._dedup_items(round1_items, seen_urls)
        all_results.extend(new_items)
        tracker.record_round(round1_items)

        rounds_info.append({
            "round": 1,
            "query": query,
            "new_items": len(new_items),
            "coverage_score": tracker.coverage_score(),
            "gaps": tracker.identify_gaps(),
            "summary": tracker.summary(),
        })
        _source_log(
            f"Round 1 complete: {len(new_items)} items, "
            f"coverage={tracker.coverage_score()}%"
        )

        # Early exit if coverage is already good
        if tracker.coverage_score() >= 70:
            _source_log("Coverage >= 70%, stopping after round 1")
            return {
                "results": all_results,
                "rounds_info": rounds_info,
                "coverage_score": tracker.coverage_score(),
            }

        # --- Rounds 2+: targeted gap filling ---
        for round_num in range(2, max_rounds + 1):
            gaps = tracker.identify_gaps()
            if not gaps:
                _source_log(f"Round {round_num}: no gaps, stopping early")
                break

            _source_log(
                f"Round {round_num}: filling gaps in {', '.join(gaps)}"
            )

            # Build targeted query and source list for gap perspectives
            gap_sources = []
            for gap_persp in gaps:
                persp_sources = PERSPECTIVES[gap_persp]
                if requested_sources:
                    # Respect user's source filter
                    gap_sources.extend(
                        s for s in persp_sources if s in requested_sources
                    )
                else:
                    gap_sources.extend(persp_sources)

            # Deduplicate source list
            gap_sources = list(dict.fromkeys(gap_sources))

            if not gap_sources:
                _source_log(f"Round {round_num}: no available gap sources, stopping")
                break

            # Generate gap-targeted query
            gap_query = self._build_gap_query(query, gaps)

            _source_log(
                f"Round {round_num}: query='{gap_query}', sources={gap_sources}"
            )

            report = self._pipeline.run(
                topic=gap_query,
                config=self._config,
                depth=depth,
                requested_sources=gap_sources,
                lookback_days=lookback_days,
                use_llm=False,  # heuristic planner for speed
                use_cache=True,
                use_store=False,
                progress=False,
            )

            round_items = self._extract_items(report)
            new_items = self._dedup_items(round_items, seen_urls)
            all_results.extend(new_items)
            tracker.record_round(round_items)

            rounds_info.append({
                "round": round_num,
                "query": gap_query,
                "gaps_targeted": gaps,
                "sources_used": gap_sources,
                "new_items": len(new_items),
                "coverage_score": tracker.coverage_score(),
                "gaps_remaining": tracker.identify_gaps(),
                "summary": tracker.summary(),
            })
            _source_log(
                f"Round {round_num} complete: {len(new_items)} new items, "
                f"coverage={tracker.coverage_score()}%"
            )

            if tracker.coverage_score() >= 70:
                _source_log("Coverage >= 70%, stopping early")
                break

        # Re-score all merged results
        from . import score as _score
        from . import dates as _dates

        from_date, to_date = _dates.get_date_range(lookback_days)
        all_results = _score.score_items(all_results, query, from_date, to_date, lookback_days)

        final_score = tracker.coverage_score()
        _source_log(
            f"Iterative retrieval complete: {len(all_results)} total items, "
            f"coverage={final_score}%, rounds={len(rounds_info)}"
        )

        return {
            "results": all_results,
            "rounds_info": rounds_info,
            "coverage_score": final_score,
        }

    @staticmethod
    def _extract_items(report) -> List[SourceItem]:
        """Extract all SourceItems from a Report."""
        items = []
        for source_items in report.items_by_source.values():
            items.extend(source_items)
        return items

    @staticmethod
    def _dedup_items(
        items: List[SourceItem], seen_urls: set
    ) -> List[SourceItem]:
        """Return only items whose URL hasn't been seen yet."""
        new_items = []
        for item in items:
            url_key = item.url.strip().lower() if item.url else ""
            if url_key and url_key not in seen_urls:
                seen_urls.add(url_key)
                new_items.append(item)
        return new_items

    @staticmethod
    def _build_gap_query(original_query: str, gaps: List[str]) -> str:
        """Build a query that targets gap perspectives."""
        modifiers = []
        for gap in gaps:
            mod = _GAP_QUERIES.get(gap)
            if mod:
                modifiers.append(mod)
        if modifiers:
            return f"{original_query} {' '.join(modifiers)}"
        return original_query
