"""Terminal-friendly rendering for pulse reports."""

from __future__ import annotations

from collections import Counter
from typing import List

from . import dates, log
from .schema import Candidate, Cluster, Report, SourceItem


SOURCE_LABELS = {
    "reddit": "Reddit",
    "hackernews": "Hacker News",
    "polymarket": "Polymarket",
    "github": "GitHub",
    "youtube": "YouTube",
    "web": "Web",
    "news": "News",
    "arxiv": "ArXiv",
    "lobsters": "Lobsters",
    "rss": "RSS/Blogs",
    "openalex": "OpenAlex",
    "sem_scholar": "Semantic Scholar",
    "manifold": "Manifold",
    "metaculus": "Metaculus",
    "bluesky": "Bluesky",
    "stackexchange": "Stack Exchange",
    "lemmy": "Lemmy",
    "devto": "Dev.to",
}


def _source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source.title())


def _format_engagement(item: SourceItem) -> str:
    """Format engagement metrics for display."""
    eng = item.engagement
    if not eng:
        return ""
    parts = []
    for key in ["score", "points", "comments", "num_comments", "stars", "volume"]:
        val = eng.get(key)
        if val is not None and val != 0:
            if key == "volume":
                parts.append(f"${val:,.0f} vol")
            elif key == "stars":
                parts.append(f"{val:,} stars")
            elif key in ("score", "points"):
                parts.append(f"{val} pts")
            elif key in ("comments", "num_comments"):
                parts.append(f"{val} cmts")
    return ", ".join(parts) if parts else ""


def _format_item_engagement_full(item: SourceItem) -> str:
    """Format all engagement metrics for full dump."""
    eng = item.engagement
    if not eng:
        return ""
    parts = []
    for key, val in eng.items():
        if val is not None and val != 0:
            if key == "volume":
                parts.append(f"${val:,.0f} {key}")
            else:
                parts.append(f"{val:,} {key}")
    return ", ".join(parts) if parts else ""


def _render_candidate(candidate: Candidate, prefix: str = "") -> list[str]:
    """Render a single candidate for compact display."""
    lines = []
    src_label = _source_label(candidate.source)
    score_str = f"score:{candidate.final_score:.2f}"
    eng_str = ""

    # Get engagement from primary source item
    if candidate.source_items:
        eng_str = _format_engagement(candidate.source_items[0])

    parts = [f"{prefix} **{candidate.title}**"]
    detail = f"  [{src_label}] {score_str}"
    if eng_str:
        detail += f" | {eng_str}"
    lines.extend(parts)
    lines.append(detail)

    if candidate.url:
        lines.append(f"  {candidate.url}")

    # Snippet
    if candidate.snippet:
        snippet = candidate.snippet[:200]
        if len(candidate.snippet) > 200:
            snippet += "..."
        lines.append(f"  {snippet}")

    # Reddit top comments
    if candidate.source_items:
        for item in candidate.source_items:
            top_comments = item.metadata.get("top_comments", [])
            if top_comments:
                for tc in top_comments[:2]:
                    excerpt = tc.get("excerpt", tc.get("text", ""))[:150]
                    score_val = tc.get("score", "")
                    if excerpt:
                        lines.append(f"  > ({score_val} upvotes) {excerpt}")
                break

    # Polymarket odds
    if candidate.source == "polymarket" and candidate.source_items:
        prices = candidate.source_items[0].metadata.get("outcome_prices", [])
        if prices:
            odds_parts = []
            for name, price in prices[:4]:
                if isinstance(price, (int, float)) and price > 0:
                    label = name.split(": ", 1)[-1] if ": " in name else name
                    odds_parts.append(f"{label}: {price * 100:.0f}%")
            if odds_parts:
                lines.append(f"  Odds: {' | '.join(odds_parts)}")

    lines.append("")
    return lines


def render_compact(report: Report, cluster_limit: int = 8) -> str:
    """Render compact report for terminal display."""
    non_empty = [s for s, items in sorted(report.items_by_source.items()) if items]
    lines = [
        f"=== pulse: {report.topic} ===",
        f"Date range: {report.range_from} to {report.range_to}",
        f"Sources: {len(non_empty)} active ({', '.join(_source_label(s) for s in non_empty)})",
        "",
    ]

    if report.warnings:
        lines.append("[WARNINGS]")
        for w in report.warnings:
            lines.append(f"  ! {w}")
        lines.append("")

    lines.append("=== RANKED EVIDENCE CLUSTERS ===")
    lines.append("")

    candidate_by_id = {c.candidate_id: c for c in report.ranked_candidates}

    for index, cluster in enumerate(report.clusters[:cluster_limit], start=1):
        n_items = len(cluster.candidate_ids)
        src_labels = ", ".join(_source_label(s) for s in cluster.sources)
        lines.append(f"[{index}] {cluster.title} (score:{cluster.score:.1f}, {n_items} items, {src_labels})")

        if cluster.uncertainty:
            lines.append(f"  Uncertainty: {cluster.uncertainty}")

        for rep_i, cid in enumerate(cluster.representative_ids, start=1):
            candidate = candidate_by_id.get(cid)
            if not candidate:
                continue
            lines.extend(_render_candidate(candidate, prefix=f"  {rep_i}."))

    # Stats
    total_items = sum(len(items) for items in report.items_by_source.values())
    lines.append(f"---")
    lines.append(f"Total: {total_items} items across {len(non_empty)} sources")

    return "\n".join(lines).strip() + "\n"


def render_full(report: Report) -> str:
    """Render full report with all items by source."""
    non_empty = [s for s, items in sorted(report.items_by_source.items()) if items]
    lines = [
        f"=== pulse FULL REPORT: {report.topic} ===",
        f"Date range: {report.range_from} to {report.range_to}",
        f"Sources: {len(non_empty)} active ({', '.join(_source_label(s) for s in non_empty)})",
        "",
    ]

    if report.warnings:
        lines.append("[WARNINGS]")
        for w in report.warnings:
            lines.append(f"  ! {w}")
        lines.append("")

    # Clusters section
    lines.append("=== RANKED EVIDENCE CLUSTERS ===")
    lines.append("")
    candidate_by_id = {c.candidate_id: c for c in report.ranked_candidates}

    for index, cluster in enumerate(report.clusters, start=1):
        n_items = len(cluster.candidate_ids)
        src_labels = ", ".join(_source_label(s) for s in cluster.sources)
        lines.append(f"[{index}] {cluster.title} (score:{cluster.score:.1f}, {n_items} items, {src_labels})")

        for rep_i, cid in enumerate(cluster.representative_ids, start=1):
            candidate = candidate_by_id.get(cid)
            if not candidate:
                continue
            lines.extend(_render_candidate(candidate, prefix=f"  {rep_i}."))
        lines.append("")

    # All items by source
    lines.append("=== ALL ITEMS BY SOURCE ===")
    lines.append("")

    source_order = ["reddit", "hackernews", "polymarket", "github", "youtube", "arxiv", "openalex", "sem_scholar", "manifold", "metaculus", "lobsters", "stackexchange", "bluesky", "lemmy", "devto", "rss", "web", "news"]
    for source in source_order:
        items = report.items_by_source.get(source, [])
        if not items:
            continue
        lines.append(f"--- {_source_label(source)} ({len(items)} items) ---")
        lines.append("")
        for item in items:
            score = item.local_rank_score if item.local_rank_score is not None else 0
            eng_str = _format_item_engagement_full(item)
            lines.append(f"{item.item_id} (score:{score:.2f}) {item.author or ''} ({item.published_at or 'date unknown'}) [{eng_str}]")
            lines.append(f"  {item.title}")
            if item.url:
                lines.append(f"  {item.url}")
            if item.container:
                lines.append(f"  in {item.container}")
            if item.snippet:
                lines.append(f"  {item.snippet[:300]}")

            # Top comments
            top_comments = item.metadata.get("top_comments", [])
            if top_comments:
                for tc in top_comments[:3]:
                    excerpt = tc.get("excerpt", tc.get("text", ""))[:200]
                    tc_score = tc.get("score", "")
                    if excerpt:
                        lines.append(f"  > ({tc_score}) {excerpt}")

            # Comment insights
            insights = item.metadata.get("comment_insights", [])
            if insights:
                for ins in insights[:3]:
                    lines.append(f"  Insight: {ins[:200]}")

            # Polymarket odds
            prices = item.metadata.get("outcome_prices", [])
            if prices and item.source == "polymarket":
                odds_parts = []
                for name, price in prices[:6]:
                    if isinstance(price, (int, float)) and price > 0:
                        label = name.split(": ", 1)[-1] if ": " in name else name
                        odds_parts.append(f"{label}: {price * 100:.0f}%")
                if odds_parts:
                    lines.append(f"  Odds: {' | '.join(odds_parts)}")

            lines.append("")

    # Stats
    total_items = sum(len(items) for items in report.items_by_source.values())
    lines.append(f"=== STATS ===")
    lines.append(f"Total: {total_items} items across {len(non_empty)} sources")
    for source in source_order:
        count = len(report.items_by_source.get(source, []))
        if count:
            lines.append(f"  {_source_label(source)}: {count}")
    if report.errors_by_source:
        lines.append(f"Errors:")
        for source, error in report.errors_by_source.items():
            lines.append(f"  {_source_label(source)}: {error}")

    return "\n".join(lines).strip() + "\n"


def render_json(report: Report) -> str:
    """Render report as JSON."""
    import json
    from .schema import to_dict
    return json.dumps(to_dict(report), indent=2, sort_keys=True, default=str)


def render_markdown(report: Report, cluster_limit: int = 10) -> str:
    """Render report as Markdown — suitable for saving, sharing, or posting."""
    candidate_by_id = {c.candidate_id: c for c in report.ranked_candidates}
    non_empty = [s for s, items in sorted(report.items_by_source.items()) if items]

    lines = [
        f"# PULSE Research: {report.topic}",
        "",
        f"**Date range:** {report.range_from} to {report.range_to}  ",
        f"**Sources:** {len(non_empty)} active ({', '.join(_source_label(s) for s in non_empty)})  ",
        f"**Generated:** {report.generated_at[:19]}",
        "",
    ]

    if report.warnings:
        lines.append("> **Warnings:**")
        for w in report.warnings:
            lines.append(f"> - {w}")
        lines.append("")

    lines.append("## Evidence Clusters")
    lines.append("")

    for index, cluster in enumerate(report.clusters[:cluster_limit], start=1):
        n_items = len(cluster.candidate_ids)
        src_labels = ", ".join(_source_label(s) for s in cluster.sources)
        lines.append(f"### {index}. {cluster.title}")
        lines.append(f"*Score: {cluster.score:.2f} | {n_items} items | {src_labels}*")
        if cluster.uncertainty:
            lines.append(f"*⚠️ Uncertainty: {cluster.uncertainty}*")
        lines.append("")

        for rep_i, cid in enumerate(cluster.representative_ids[:3], start=1):
            candidate = candidate_by_id.get(cid)
            if not candidate:
                continue
            src_label = _source_label(candidate.source)
            eng_str = ""
            if candidate.source_items:
                eng_str = _format_engagement(candidate.source_items[0])

            lines.append(f"**{rep_i}. {candidate.title}**")
            detail_parts = [f"[{src_label}]"]
            if eng_str:
                detail_parts.append(eng_str)
            lines.append(f"*{' | '.join(detail_parts)}*")
            if candidate.url:
                lines.append(f"[Link]({candidate.url})")
            if candidate.snippet:
                lines.append(f"> {candidate.snippet[:300]}")

            # Top comments
            if candidate.source_items:
                for item in candidate.source_items:
                    top_comments = item.metadata.get("top_comments", [])
                    if top_comments:
                        for tc in top_comments[:2]:
                            excerpt = tc.get("excerpt", tc.get("text", ""))[:200]
                            score_val = tc.get("score", "")
                            if excerpt:
                                lines.append(f"> *({score_val} upvotes)* {excerpt}")
                        break

            # Polymarket odds
            if candidate.source == "polymarket" and candidate.source_items:
                prices = candidate.source_items[0].metadata.get("outcome_prices", [])
                if prices:
                    odds_parts = []
                    for name, price in prices[:4]:
                        if isinstance(price, (int, float)) and price > 0:
                            label = name.split(": ", 1)[-1] if ": " in name else name
                            odds_parts.append(f"{label}: {price * 100:.0f}%")
                    if odds_parts:
                        lines.append(f"**Odds:** {' | '.join(odds_parts)}")

            lines.append("")

    # Source summary
    total_items = sum(len(items) for items in report.items_by_source.values())
    lines.append("---")
    lines.append(f"**Total:** {total_items} items across {len(non_empty)} sources")

    if report.errors_by_source:
        lines.append("")
        lines.append("### Errors")
        for source, error in report.errors_by_source.items():
            lines.append(f"- **{_source_label(source)}:** {error}")

    return "\n".join(lines).strip() + "\n"


def render_context(report: Report, cluster_limit: int = 6) -> str:
    """Render compact context snippet for embedding in other tools."""
    candidate_by_id = {c.candidate_id: c for c in report.ranked_candidates}
    lines = [
        f"Topic: {report.topic}",
        f"Intent: {report.query_plan.intent}",
        f"Range: {report.range_from} to {report.range_to}",
        "",
        "Top clusters:",
    ]

    for cluster in report.clusters[:cluster_limit]:
        src_labels = ", ".join(_source_label(s) for s in cluster.sources)
        lines.append(f"- {cluster.title} [{src_labels}]")
        for cid in cluster.representative_ids[:2]:
            candidate = candidate_by_id.get(cid)
            if not candidate:
                continue
            lines.append(f"  * {_source_label(candidate.source)}: {candidate.title}")
            if candidate.snippet:
                lines.append(f"    {candidate.snippet[:150]}")

    return "\n".join(lines).strip() + "\n"
