#!/usr/bin/env python3
"""Basic integration tests for last30days."""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from lib import schema, dates, config, planner, normalize, score, dedupe, fusion, cluster, render, pipeline


def test_schema():
    """Test data model creation."""
    item = schema.SourceItem(
        item_id="test-1",
        source="reddit",
        title="Test post",
        body="Test body",
        url="https://reddit.com/r/test/1",
    )
    assert item.source == "reddit"
    assert item.title == "Test post"

    plan = schema.QueryPlan(
        intent="general",
        freshness_mode="relaxed",
        raw_topic="test",
        subqueries=[schema.SubQuery(label="primary", search_query="test", ranking_query="test", sources=["reddit"])],
        source_weights={"reddit": 1.0},
    )
    assert len(plan.subqueries) == 1
    print("  ✓ schema")


def test_dates():
    """Test date utilities."""
    from_date, to_date = dates.get_date_range(30)
    assert len(from_date) == 10
    assert len(to_date) == 10
    assert from_date < to_date

    # from_date is 30 days ago, so recency should be 0 (at the boundary)
    score = dates.recency_score(to_date, 30)
    assert score == 100  # Today should be 100

    score_old = dates.recency_score("2020-01-01", 30)
    assert score_old == 0

    print("  ✓ dates")


def test_config():
    """Test config loading."""
    cfg = config.get_config()
    assert isinstance(cfg, dict)
    available = config.available_sources(cfg)
    assert "reddit" in available
    assert "hackernews" in available
    assert "polymarket" in available
    print(f"  ✓ config (available: {', '.join(available)})")


def test_planner():
    """Test query planning."""
    plan = planner.plan_query(
        topic="OpenAI Codex",
        available_sources=["reddit", "hackernews", "polymarket", "github"],
        depth="default",
    )
    assert plan.intent in ("general", "product_research", "news_tracking")
    assert len(plan.subqueries) >= 1
    assert "reddit" in plan.source_weights
    print(f"  ✓ planner (intent={plan.intent}, {len(plan.subqueries)} subqueries)")


def test_normalize():
    """Test item normalization."""
    raw_items = [
        {"id": "1", "title": "Test", "body": "Body", "url": "https://example.com", "date": "2026-04-01", "engagement": {"score": 100}, "relevance": 0.8},
    ]
    items = normalize.normalize_items("reddit", raw_items, "2026-03-01", "2026-04-13")
    assert len(items) == 1
    assert items[0].source == "reddit"
    assert items[0].published_at == "2026-04-01"
    print("  ✓ normalize")


def test_score():
    """Test scoring engine."""
    item = schema.SourceItem(
        item_id="test", source="reddit", title="OpenAI Codex", body="Test body",
        url="https://example.com", engagement={"score": 500, "num_comments": 100},
        published_at="2026-04-10",
    )
    scored = score.score_item(item, "OpenAI Codex", "2026-03-01", "2026-04-13")
    assert scored.freshness is not None
    assert scored.engagement_score is not None
    assert scored.local_relevance is not None
    assert scored.local_rank_score is not None
    print(f"  ✓ score (relevance={scored.local_relevance}, engagement={scored.engagement_score:.3f}, rank={scored.local_rank_score:.3f})")


def test_dedupe():
    """Test deduplication."""
    items = [
        schema.SourceItem(item_id="1", source="reddit", title="Same Title", body="b", url="https://a.com"),
        schema.SourceItem(item_id="2", source="reddit", title="Same Title", body="b", url="https://a.com"),
        schema.SourceItem(item_id="3", source="reddit", title="Different", body="b", url="https://b.com"),
    ]
    deduped = dedupe.deduplicate(items)
    assert len(deduped) == 2
    print("  ✓ dedupe")


def test_fusion():
    """Test RRF fusion."""
    items_by_source = {
        ("primary", "reddit"): [
            schema.SourceItem(item_id="r1", source="reddit", title="Post A", body="", url="https://r1.com", local_relevance=0.8, freshness=90, engagement_score=0.7, source_quality=0.75),
        ],
        ("primary", "hackernews"): [
            schema.SourceItem(item_id="hn1", source="hackernews", title="Post A", body="", url="https://r1.com", local_relevance=0.9, freshness=80, engagement_score=0.6, source_quality=0.85),
        ],
    }
    candidates = fusion.weighted_rrf(items_by_source, {"reddit": 1.0, "hackernews": 0.9})
    assert len(candidates) >= 1
    print(f"  ✓ fusion ({len(candidates)} candidates)")


def test_render():
    """Test rendering."""
    plan = schema.QueryPlan(intent="general", freshness_mode="relaxed", raw_topic="test",
                           subqueries=[schema.SubQuery(label="p", search_query="test", ranking_query="test", sources=["reddit"])],
                           source_weights={"reddit": 1.0})
    report = schema.Report(
        topic="Test Topic", range_from="2026-03-01", range_to="2026-04-13",
        generated_at="2026-04-13T00:00:00Z", query_plan=plan,
        clusters=[], ranked_candidates=[], items_by_source={}, errors_by_source={},
    )

    compact = render.render_compact(report)
    assert "Test Topic" in compact

    full = render.render_full(report)
    assert "Test Topic" in full

    context = render.render_context(report)
    assert "Test Topic" in context

    import json
    j = render.render_json(report)
    parsed = json.loads(j)
    assert parsed["topic"] == "Test Topic"

    print("  ✓ render (compact, full, context, json)")


if __name__ == "__main__":
    print("Running last30days tests...\n")
    tests = [
        test_schema,
        test_dates,
        test_config,
        test_planner,
        test_normalize,
        test_score,
        test_dedupe,
        test_fusion,
        test_render,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("All tests passed!")
