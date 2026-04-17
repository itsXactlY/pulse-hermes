"""Multi-Agent Research Crew for PULSE.

Orchestrates multiple rounds of research using specialized agents:
- Collector: full pipeline run across all sources
- Analyzer: coverage assessment via CoverageRubric
- Specialist: targeted queries for missing categories
- Synthesizer: merge, dedup, generate markdown report
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from . import log, pipeline, render
from .schema import Candidate, Cluster, Report, SourceItem, slugify


def _source_log(msg: str):
    log.source_log("ResearchCrew", msg)


# ---------------------------------------------------------------------------
# CoverageRubric
# ---------------------------------------------------------------------------

class CoverageRubric:
    """Assesses research coverage against a structured rubric."""

    SOURCE_CATEGORIES: Dict[str, List[str]] = {
        "social": ["reddit", "bluesky", "lemmy", "hackernews"],
        "academic": ["arxiv", "openalex", "sem_scholar"],
        "market": ["polymarket", "manifold", "metaculus"],
        "news": ["news", "rss", "devto"],
        "code": ["github", "stackexchange", "lobsters"],
        "media": ["youtube", "web"],
    }

    # Reverse lookup: source -> category
    _SOURCE_TO_CATEGORY: Dict[str, str] = {}
    for _cat, _sources in SOURCE_CATEGORIES.items():
        for _s in _sources:
            _SOURCE_TO_CATEGORY[_s] = _cat

    def _categorize_sources(self, items_by_source: Dict[str, List]) -> Dict[str, Set[str]]:
        """Group sources that returned results by category."""
        by_cat: Dict[str, Set[str]] = {}
        for source, items in items_by_source.items():
            if not items:
                continue
            cat = self._SOURCE_TO_CATEGORY.get(source, "other")
            by_cat.setdefault(cat, set()).add(source)
        return by_cat

    def _find_url_overlaps(self, items_by_source: Dict[str, List[SourceItem]]) -> List[Dict[str, str]]:
        """Detect same URLs appearing across multiple sources."""
        url_sources: Dict[str, List[str]] = {}
        for source, items in items_by_source.items():
            for item in items:
                if item.url:
                    url_sources.setdefault(item.url, []).append(source)
        overlaps = []
        for url, sources in url_sources.items():
            if len(sources) >= 2:
                overlaps.append({"url": url, "sources": sources})
        return overlaps

    def _detect_market_contradictions(
        self,
        items_by_source: Dict[str, List[SourceItem]],
    ) -> List[Dict[str, Any]]:
        """Detect contradictory predictions across market sources."""
        contradictions = []
        market_sources = self.SOURCE_CATEGORIES["market"]
        market_items = []
        for src in market_sources:
            for item in items_by_source.get(src, []):
                market_items.append(item)

        # Check for conflicting odds on similar topics
        for i, a in enumerate(market_items):
            for b in market_items[i + 1:]:
                if a.source == b.source:
                    continue
                # Simple heuristic: similar titles but different sources
                a_tokens = set(a.title.lower().split())
                b_tokens = set(b.title.lower().split())
                if len(a_tokens) < 2 or len(b_tokens) < 2:
                    continue
                overlap = len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))
                if overlap > 0.5:
                    # Check if odds/prices diverge significantly
                    a_prices = a.metadata.get("outcome_prices", [])
                    b_prices = b.metadata.get("outcome_prices", [])
                    if a_prices and b_prices:
                        a_prob = self._extract_primary_prob(a_prices)
                        b_prob = self._extract_primary_prob(b_prices)
                        if a_prob is not None and b_prob is not None:
                            if abs(a_prob - b_prob) > 0.3:
                                contradictions.append({
                                    "item_a": a.title,
                                    "source_a": a.source,
                                    "prob_a": a_prob,
                                    "item_b": b.title,
                                    "source_b": b.source,
                                    "prob_b": b_prob,
                                    "divergence": abs(a_prob - b_prob),
                                })
        return contradictions

    @staticmethod
    def _extract_primary_prob(prices: Any) -> Optional[float]:
        """Extract the first probability from outcome_prices."""
        if not prices:
            return None
        for entry in prices[:2]:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                p = entry[1]
                if isinstance(p, (int, float)) and 0 <= p <= 1:
                    return float(p)
            elif isinstance(entry, (int, float)) and 0 <= entry <= 1:
                return float(entry)
        return None

    def assess(
        self,
        report: Report,
        query: str,
    ) -> Dict[str, Any]:
        """Assess research coverage.

        Returns dict with keys: score (0-100), gaps, contradictions, recommendations.
        """
        items_by_source = report.items_by_source
        categories = self._categorize_sources(items_by_source)

        score = 0
        gaps: List[str] = []
        contradictions: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        # --- Check 1: at least 3 source categories represented ---
        cat_count = len(categories)
        if cat_count >= 5:
            score += 30
        elif cat_count >= 3:
            score += 20
        elif cat_count >= 1:
            score += 10
        else:
            score += 0
        if cat_count < 3:
            missing_cats = [c for c in self.SOURCE_CATEGORIES if c not in categories]
            gaps.append(f"Only {cat_count}/6 source categories covered")
            if missing_cats:
                recommendations.append(
                    f"Add sources from: {', '.join(missing_cats)}"
                )

        # --- Check 2: no category has 0 results ---
        zero_cats = []
        for cat, sources in self.SOURCE_CATEGORIES.items():
            has_results = any(items_by_source.get(s) for s in sources)
            if not has_results:
                zero_cats.append(cat)
        if not zero_cats:
            score += 25
        else:
            score += max(0, 25 - 5 * len(zero_cats))
            for cat in zero_cats:
                gaps.append(f"Category '{cat}' has zero results")
                srcs = self.SOURCE_CATEGORIES[cat]
                recommendations.append(f"Try sources: {', '.join(srcs)} for '{cat}' coverage")

        # --- Check 3: cross-source URL confirmation ---
        url_overlaps = self._find_url_overlaps(items_by_source)
        if len(url_overlaps) >= 5:
            score += 25
        elif len(url_overlaps) >= 2:
            score += 15
        elif len(url_overlaps) >= 1:
            score += 5
        else:
            score += 0
            gaps.append("No cross-source URL confirmation found")
            recommendations.append("Broaden query to find shared content across sources")

        # --- Check 4: market contradiction detection ---
        market_contradictions = self._detect_market_contradictions(items_by_source)
        if not market_contradictions:
            score += 20
        else:
            score += 5
            contradictions.extend(market_contradictions)
            recommendations.append(
                f"Found {len(market_contradictions)} market contradiction(s) - investigate divergence"
            )

        # Cap at 100
        score = min(100, score)

        # Bonus for total item volume
        total = sum(len(v) for v in items_by_source.values())
        if total >= 100:
            score = min(100, score + 5)

        return {
            "score": score,
            "gaps": gaps,
            "contradictions": contradictions,
            "recommendations": recommendations,
            "categories_covered": sorted(categories.keys()),
            "url_confirmations": len(url_overlaps),
            "total_items": total if (total := sum(len(v) for v in items_by_source.values())) else 0,
        }


# ---------------------------------------------------------------------------
# ResearchCrew
# ---------------------------------------------------------------------------

class ResearchCrew:
    """Multi-round research orchestrator."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rubric = CoverageRubric()

    def _run_pipeline(
        self,
        topic: str,
        depth: str = "deep",
        lookback_days: int = 30,
        use_llm: bool = True,
        requested_sources: Optional[List[str]] = None,
    ) -> Report:
        """Run a single pipeline pass."""
        return pipeline.run(
            topic=topic,
            config=self.config,
            depth=depth,
            requested_sources=requested_sources,
            lookback_days=lookback_days,
            use_llm=use_llm,
            use_cache=True,
            use_store=False,  # We save at the end only
            progress=False,
        )

    def _generate_gap_queries(self, gaps: List[str], query: str) -> List[str]:
        """Generate targeted queries for missing categories."""
        gap_queries = []
        for gap in gaps:
            # Extract category name from gap messages
            match = re.search(r"Category '(\w+)'", gap)
            if match:
                cat = match.group(1)
                gap_queries.append(f"{query} {cat} research")
            else:
                # Generic gap query
                gap_queries.append(f"{query} latest developments")
        # Ensure we have at least the original query
        if not gap_queries:
            gap_queries.append(query)
        return gap_queries

    def _merge_reports(self, reports: List[Report]) -> Report:
        """Merge multiple reports into one consolidated report."""
        if not reports:
            raise ValueError("No reports to merge")
        if len(reports) == 1:
            return reports[0]

        primary = reports[0]

        # Merge items_by_source
        merged_items: Dict[str, List[SourceItem]] = {}
        seen_urls: Set[str] = set()

        for report in reports:
            for source, items in report.items_by_source.items():
                for item in items:
                    if item.url and item.url in seen_urls:
                        continue
                    if item.url:
                        seen_urls.add(item.url)
                    merged_items.setdefault(source, []).append(item)

        # Merge all candidates, deduplicate by URL
        all_candidates: List[Candidate] = []
        seen_cand_urls: Set[str] = set()
        for report in reports:
            for cand in report.ranked_candidates:
                if cand.url and cand.url in seen_cand_urls:
                    continue
                if cand.url:
                    seen_cand_urls.add(cand.url)
                all_candidates.append(cand)

        # Re-sort by final_score
        all_candidates.sort(key=lambda c: c.final_score, reverse=True)

        # Merge clusters (keep unique by title)
        all_clusters: List[Cluster] = []
        seen_cluster_titles: Set[str] = set()
        for report in reports:
            for cluster in report.clusters:
                key = cluster.title.lower().strip()
                if key in seen_cluster_titles:
                    continue
                seen_cluster_titles.add(key)
                all_clusters.append(cluster)
        all_clusters.sort(key=lambda c: c.score, reverse=True)

        # Merge errors
        merged_errors: Dict[str, str] = {}
        for report in reports:
            merged_errors.update(report.errors_by_source)

        # Merge warnings
        all_warnings: List[str] = []
        seen_warnings: Set[str] = set()
        for report in reports:
            for w in report.warnings:
                if w not in seen_warnings:
                    seen_warnings.add(w)
                    all_warnings.append(w)

        return Report(
            topic=primary.topic,
            range_from=primary.range_from,
            range_to=primary.range_to,
            generated_at=datetime.now(timezone.utc).isoformat(),
            query_plan=primary.query_plan,
            clusters=all_clusters[:50],
            ranked_candidates=all_candidates[:100],
            items_by_source=merged_items,
            errors_by_source=merged_errors,
            warnings=all_warnings,
        )

    def _generate_synthesis_report(
        self,
        report: Report,
        assessment: Dict[str, Any],
        round_summaries: List[Dict[str, Any]],
    ) -> str:
        """Generate a markdown synthesis report."""
        lines = [
            f"# PULSE Deep Research: {report.topic}",
            "",
            f"**Generated:** {report.generated_at[:19]}",
            f"**Coverage Score:** {assessment['score']}/100",
            f"**Rounds completed:** {len(round_summaries)}",
            f"**Total items:** {assessment['total_items']}",
            "",
        ]

        # Coverage assessment
        lines.append("## Coverage Assessment")
        lines.append("")
        lines.append(f"Categories covered: {', '.join(assessment['categories_covered'])}")
        lines.append(f"Cross-source confirmations: {assessment['url_confirmations']}")
        lines.append("")

        if assessment["gaps"]:
            lines.append("### Gaps")
            for gap in assessment["gaps"]:
                lines.append(f"- {gap}")
            lines.append("")

        if assessment["contradictions"]:
            lines.append("### Contradictions")
            for c in assessment["contradictions"]:
                lines.append(
                    f"- {c['source_a']}: {c['item_a']} ({c['prob_a']:.0%}) "
                    f"vs {c['source_b']}: {c['item_b']} ({c['prob_b']:.0%}) "
                    f"[divergence: {c['divergence']:.0%}]"
                )
            lines.append("")

        if assessment["recommendations"]:
            lines.append("### Recommendations")
            for rec in assessment["recommendations"]:
                lines.append(f"- {rec}")
            lines.append("")

        # Round summaries
        lines.append("## Research Rounds")
        lines.append("")
        for i, rs in enumerate(round_summaries, 1):
            lines.append(f"### Round {i}: {rs['role']}")
            lines.append(f"- Query: `{rs['query']}`")
            lines.append(f"- Items found: {rs['items']}")
            lines.append(f"- Sources active: {rs['sources']}")
            lines.append("")

        # Main evidence (render via existing markdown renderer)
        lines.append("## Evidence")
        lines.append("")
        evidence_md = render.render_markdown(report)
        # Strip the header from render_markdown output to avoid duplication
        evidence_lines = evidence_md.split("\n")
        start_idx = 0
        for idx, line in enumerate(evidence_lines):
            if line.startswith("## Evidence Clusters"):
                start_idx = idx
                break
        lines.extend(evidence_lines[start_idx:])

        return "\n".join(lines)

    def deep_research(
        self,
        query: str,
        max_rounds: int = 3,
    ) -> Dict[str, Any]:
        """Run multi-round deep research.

        Args:
            query: Research topic
            max_rounds: Maximum research rounds (default 3)

        Returns:
            Dict with keys:
                - report: merged Report object
                - assessment: CoverageRubric assessment dict
                - synthesis: markdown synthesis string
                - rounds: list of round summary dicts
        """
        _source_log(f"Starting deep research: '{query}' (max_rounds={max_rounds})")
        all_reports: List[Report] = []
        round_summaries: List[Dict[str, Any]] = []

        # ---------------------------------------------------------------
        # Round 1: Collector - full pipeline across all sources
        # ---------------------------------------------------------------
        _source_log("Round 1: Collector - full pipeline run")
        try:
            report_1 = self._run_pipeline(query, depth="deep")
            all_reports.append(report_1)
            round_summaries.append({
                "role": "Collector",
                "query": query,
                "items": sum(len(v) for v in report_1.items_by_source.values()),
                "sources": len([s for s, v in report_1.items_by_source.items() if v]),
            })
        except Exception as e:
            _source_log(f"Collector round failed: {e}")
            round_summaries.append({
                "role": "Collector",
                "query": query,
                "items": 0,
                "sources": 0,
                "error": str(e),
            })

        if not all_reports:
            _source_log("No reports collected, returning empty result")
            return {
                "report": None,
                "assessment": {"score": 0, "gaps": ["All rounds failed"], "contradictions": [], "recommendations": ["Retry with different parameters"]},
                "synthesis": "# Research failed\n\nNo data could be collected.",
                "rounds": round_summaries,
            }

        merged = self._merge_reports(all_reports)

        # ---------------------------------------------------------------
        # Round 2: Analyzer - CoverageRubric assessment
        # ---------------------------------------------------------------
        if max_rounds >= 2:
            _source_log("Round 2: Analyzer - coverage assessment")
            assessment = self.rubric.assess(merged, query)
            _source_log(f"Coverage score: {assessment['score']}/100, gaps: {len(assessment['gaps'])}")

            round_summaries.append({
                "role": "Analyzer",
                "query": f"Assessment of '{query}'",
                "items": assessment["total_items"],
                "sources": len(assessment["categories_covered"]),
                "coverage_score": assessment["score"],
            })

            # ---------------------------------------------------------------
            # Round 3: Specialist - targeted queries for missing categories
            # ---------------------------------------------------------------
            if max_rounds >= 3 and assessment["score"] < 80:
                _source_log("Round 3: Specialist - targeted gap-filling")
                gap_queries = self._generate_gap_queries(assessment["gaps"], query)

                for gq in gap_queries[:3]:  # Cap at 3 gap queries
                    try:
                        _source_log(f"Specialist query: '{gq}'")
                        report_g = self._run_pipeline(gq, depth="default")
                        all_reports.append(report_g)
                        round_summaries.append({
                            "role": "Specialist",
                            "query": gq,
                            "items": sum(len(v) for v in report_g.items_by_source.values()),
                            "sources": len([s for s, v in report_g.items_by_source.items() if v]),
                        })
                    except Exception as e:
                        _source_log(f"Specialist query failed: {e}")
                        round_summaries.append({
                            "role": "Specialist",
                            "query": gq,
                            "items": 0,
                            "sources": 0,
                            "error": str(e),
                        })

                # Re-merge with specialist results
                merged = self._merge_reports(all_reports)
        else:
            assessment = self.rubric.assess(merged, query)

        # ---------------------------------------------------------------
        # Final: Synthesizer - generate final report
        # ---------------------------------------------------------------
        _source_log("Synthesizer: generating final report")

        # Re-assess after all rounds
        final_assessment = self.rubric.assess(merged, query)
        synthesis = self._generate_synthesis_report(
            merged, final_assessment, round_summaries
        )

        _source_log(
            f"Deep research complete: {final_assessment['total_items']} items, "
            f"score {final_assessment['score']}/100, {len(round_summaries)} rounds"
        )

        return {
            "report": merged,
            "assessment": final_assessment,
            "synthesis": synthesis,
            "rounds": round_summaries,
        }
