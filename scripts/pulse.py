#!/usr/bin/env python3
"""PULSE v0.0.1 — The Pulse of the Internet.

Research any topic across Reddit, Hacker News, Polymarket, GitHub, YouTube, web, and news.
Scores by real engagement metrics - upvotes, points, volume, stars.

Usage:
    python3 pulse.py <topic> [options]
    python3 pulse.py --setup          # First-run setup wizard
    python3 pulse.py --diagnose       # Show available sources
    python3 pulse.py --stats          # Show cache & store statistics
    python3 pulse.py --history TOPIC  # Show research history for topic
    python3 pulse.py --trending       # Show trending findings across topics
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the scripts directory is on the path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib import cache, config, log, pipeline, render, store, ui
from lib.schema import slugify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PULSE — Research any topic across Reddit, HN, Polymarket, GitHub, YouTube, web, and news."
    )
    parser.add_argument("topic", nargs="*", default=[], help="Research topic")
    parser.add_argument("--emit", default="compact",
                        choices=["compact", "json", "full", "context", "md"],
                        help="Output mode (default: compact)")
    parser.add_argument("--depth", default="default",
                        choices=["quick", "default", "deep"],
                        help="Research depth (default: default)")
    parser.add_argument("--sources", help="Comma-separated sources to search")
    parser.add_argument("--lookback", type=int, default=30,
                        help="Days to look back (default: 30)")
    parser.add_argument("--save-dir", help="Directory to save report")
    parser.add_argument("--diagnose", action="store_true",
                        help="Show available sources and exit")
    parser.add_argument("--setup", action="store_true",
                        help="Run first-run setup wizard")
    parser.add_argument("--stats", action="store_true",
                        help="Show cache and store statistics")
    parser.add_argument("--history", metavar="TOPIC",
                        help="Show research history for a topic")
    parser.add_argument("--trending", action="store_true",
                        help="Show trending findings across topics")
    parser.add_argument("--no-llm", action="store_true",
                        help="Disable LLM planner (use heuristic)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable cache (always fetch fresh)")
    parser.add_argument("--no-store", action="store_true",
                        help="Disable persistent store")
    parser.add_argument("--no-progress", action="store_true",
                        help="Disable progress display")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    return parser


def save_output(report, emit: str, save_dir: str) -> Path:
    """Save report to disk."""
    path = Path(save_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    slug = slugify(report.topic)
    extension = "json" if emit == "json" else "md"
    out_path = path / f"{slug}-pulse.{extension}"

    if emit == "json":
        content = render.render_json(report)
    elif emit == "full":
        content = render.render_full(report)
    elif emit == "context":
        content = render.render_context(report)
    else:
        content = render.render_compact(report)

    out_path.write_text(content)
    return out_path


def cmd_diagnose() -> int:
    """Show available sources and environment."""
    from lib.setup import detect_environment, get_available_sources, has_llm
    env = detect_environment()
    env["available_sources"] = get_available_sources(env)
    env["has_llm"] = has_llm(env)

    # Add cache stats
    env["cache_stats"] = cache.stats()
    env["store_stats"] = store.stats()

    print(json.dumps(env, indent=2, default=str))
    return 0


def cmd_setup() -> int:
    """Run the interactive setup wizard."""
    from lib.setup import run_setup
    run_setup()
    return 0


def cmd_stats() -> int:
    """Show cache and store statistics."""
    print("\nPULSE Statistics\n")

    cs = cache.stats()
    print(f"  Cache:")
    print(f"    Active entries: {cs.get('active_entries', 0)}")
    print(f"    Total hits: {cs.get('total_hits', 0)}")
    print(f"    DB size: {cs.get('db_size_kb', 0)} KB")
    if cs.get("by_source"):
        print(f"    By source: {json.dumps(cs['by_source'])}")

    ss = store.stats()
    print(f"\n  Store:")
    print(f"    Topics tracked: {ss.get('topics_tracked', 0)}")
    print(f"    Total runs: {ss.get('total_runs', 0)}")
    print(f"    Total findings: {ss.get('total_findings', 0)}")
    print(f"    DB size: {ss.get('db_size_kb', 0)} KB")
    if ss.get("findings_by_source"):
        print(f"    By source: {json.dumps(ss['findings_by_source'])}")

    print()
    return 0


def cmd_history(topic: str) -> int:
    """Show research history for a topic."""
    history = store.get_topic_history(topic)
    if not history:
        print(f"No history found for: {topic}")
        return 0

    print(f"\nResearch history for: {topic}\n")
    for run in history:
        status_icon = "✓" if run["status"] == "completed" else "⋯"
        print(f"  {status_icon} {run['started_at'][:16]} | "
              f"{run['items_found']} items, {run['clusters_found']} clusters | "
              f"sources: {', '.join(run['sources_used'])}")
    print()
    return 0


def cmd_trending() -> int:
    """Show trending findings."""
    findings = store.get_trending_findings(limit=20)
    if not findings:
        print("No trending findings yet. Run some research first!")
        return 0

    print("\nTrending Findings (seen across multiple runs)\n")
    for f in findings:
        print(f"  [{f['source']}] {f['seen_count']}x | {f['title'][:80]}")
        if f.get("url"):
            print(f"    {f['url']}")
    print()
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.debug:
        os.environ["PULSE_DEBUG"] = "1"
        log.DEBUG = True

    # Load config early for subcommands that need it
    cfg = config.get_config()

    # Subcommands (no topic needed)
    if args.setup:
        return cmd_setup()

    if args.diagnose:
        return cmd_diagnose()

    if args.stats:
        return cmd_stats()

    if args.history:
        return cmd_history(args.history)

    if args.trending:
        return cmd_trending()

    # Main research command
    topic = " ".join(args.topic).strip()
    if not topic:
        parser.print_usage(sys.stderr)
        return 2

    # Parse requested sources
    requested = None
    if args.sources:
        requested = [s.strip().lower() for s in args.sources.split(",") if s.strip()]

    # Run pipeline
    try:
        report = pipeline.run(
            topic=topic,
            config=cfg,
            depth=args.depth,
            requested_sources=requested,
            lookback_days=args.lookback,
            use_llm=not args.no_llm,
            use_cache=not args.no_cache,
            use_store=not args.no_store,
            progress=not args.no_progress,
        )
    except RuntimeError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Pipeline error: {e}\n")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

    # Render output
    if args.emit == "json":
        output = render.render_json(report)
    elif args.emit in ("full", "md"):
        output = render.render_full(report)
    elif args.emit == "context":
        output = render.render_context(report)
    else:
        output = render.render_compact(report)

    print(output)

    # Save if requested
    if args.save_dir:
        out_path = save_output(report, args.emit, args.save_dir)
        sys.stderr.write(f"Saved to: {out_path}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
