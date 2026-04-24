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


def _memory_slug(value: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "pulse"


def _memory_entities(text: str, limit: int = 12) -> list[str]:
    import re
    candidates = []
    for tok in re.findall(r"\b[A-Za-z][A-Za-z0-9_\-]{2,}\b", text or ""):
        if tok[0].isupper() or any(ch.isdigit() for ch in tok) or re.search(r"[a-z][A-Z]", tok):
            candidates.append(tok)
    for phrase in re.findall(r"['\"]([^'\"]{3,80})['\"]", text or ""):
        candidates.append(phrase.strip())
    seen, out = set(), []
    for ent in candidates:
        key = ent.lower()
        if key not in seen:
            seen.add(key)
            out.append(ent)
        if len(out) >= limit:
            break
    return out


def _candidate_memory_payload(candidate: Candidate) -> dict:
    evidence = []
    urls = []
    engagements = []
    for item in candidate.source_items[:5]:
        if item.url:
            urls.append(item.url)
        engagements.append(item.engagement or {})
        evidence.append({
            "source": item.source,
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at,
            "container": item.container,
            "snippet": (item.snippet or item.body or "")[:500],
            "engagement": item.engagement,
        })
    text = "\n".join([candidate.title or "", candidate.snippet or ""] + [e.get("snippet", "") for e in evidence])
    dedup_src = "|".join([candidate.url or "", candidate.title or "", candidate.source or ""])
    import hashlib
    dedup_key = hashlib.sha256(dedup_src.encode("utf-8", "ignore")).hexdigest()[:24]
    salience = min(2.0, max(0.4, 0.75 + float(candidate.final_score or 0.0) * 0.15 + min(len(set(candidate.sources or [])), 5) * 0.08))
    return {
        "kind": "finding",
        "dedup_key": f"pulse:{dedup_key}",
        "label": f"pulse:{_memory_slug(candidate.source)}:{dedup_key[:10]}",
        "title": candidate.title,
        "content": (
            f"PULSE finding: {candidate.title}\n"
            f"Source: {candidate.source}\n"
            f"URL: {candidate.url}\n"
            f"Summary: {(candidate.snippet or '')[:700]}"
        ).strip(),
        "salience": round(salience, 3),
        "entities": _memory_entities(text),
        "source_urls": list(dict.fromkeys(urls or ([candidate.url] if candidate.url else []))),
        "evidence": evidence,
        "metadata": {
            "candidate_id": candidate.candidate_id,
            "source": candidate.source,
            "sources": candidate.sources,
            "final_score": candidate.final_score,
            "engagement": candidate.engagement,
            "engagements": engagements,
            "cluster_id": candidate.cluster_id,
        },
    }


def render_for_memory(report: Report, cluster_limit: int = 12, candidate_limit: int = 40) -> str:
    """Render compact JSON designed for neural memory ingestion.

    Shape is intentionally stable, dedup-friendly, and free of presentation text:
    each memory has content, label, dedup_key, salience hints, entities, URLs,
    and evidence metadata.
    """
    import hashlib
    import json
    candidate_by_id = {c.candidate_id: c for c in report.ranked_candidates}
    memories = []

    for cluster in report.clusters[:cluster_limit]:
        candidates = [candidate_by_id[cid] for cid in cluster.representative_ids if cid in candidate_by_id]
        source_urls = []
        snippets = []
        for c in candidates[:4]:
            if c.url:
                source_urls.append(c.url)
            if c.snippet:
                snippets.append(c.snippet[:300])
        dedup_src = "|".join([report.topic, cluster.title, ",".join(sorted(cluster.sources))])
        digest = hashlib.sha256(dedup_src.encode("utf-8", "ignore")).hexdigest()[:24]
        content = (
            f"PULSE cluster for {report.topic}: {cluster.title}\n"
            f"Sources: {', '.join(cluster.sources)}\n"
            f"Score: {cluster.score:.3f}\n"
            f"Evidence: {' | '.join(snippets[:4])}"
        ).strip()
        memories.append({
            "kind": "cluster",
            "dedup_key": f"pulse:{digest}",
            "label": f"pulse:{_memory_slug(report.topic)}:cluster:{digest[:10]}",
            "title": cluster.title,
            "content": content,
            "salience": round(min(2.0, max(0.5, 0.8 + cluster.score * 0.12 + len(cluster.sources) * 0.08)), 3),
            "entities": _memory_entities(content),
            "source_urls": list(dict.fromkeys(source_urls)),
            "metadata": {
                "cluster_id": cluster.cluster_id,
                "candidate_ids": cluster.candidate_ids,
                "representative_ids": cluster.representative_ids,
                "sources": cluster.sources,
                "score": cluster.score,
                "uncertainty": cluster.uncertainty,
            },
        })

    for candidate in report.ranked_candidates[:candidate_limit]:
        memories.append(_candidate_memory_payload(candidate))

    payload = {
        "schema": "pulse.for-memory.v1",
        "source": "pulse-hermes",
        "topic": report.topic,
        "generated_at": report.generated_at,
        "range_from": report.range_from,
        "range_to": report.range_to,
        "intent": getattr(report.query_plan, "intent", ""),
        "topic_dedup_key": "pulse-topic:" + hashlib.sha256((report.topic or "").lower().encode()).hexdigest()[:16],
        "counts": {
            "clusters": len(report.clusters),
            "ranked_candidates": len(report.ranked_candidates),
            "memories": len(memories),
        },
        "memories": memories,
        "errors_by_source": report.errors_by_source,
        "warnings": report.warnings,
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


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
