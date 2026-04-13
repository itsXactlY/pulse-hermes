#!/usr/bin/env python3
"""last30days v3.0.0 - Hermes Agent edition.

Research any topic across Reddit, Hacker News, Polymarket, GitHub, web, and news.
Scores by real engagement metrics - upvotes, points, volume, stars.

Usage:
    python3 last30days.py <topic> [options]

Options:
    --emit MODE     Output: compact (default), json, md, full, context
    --depth MODE    Depth: quick, default (default), deep
    --sources LIST  Comma-separated sources: reddit,hackernews,polymarket,github,web,news
    --lookback N    Days to look back (default: 30)
    --save-dir DIR  Save report to directory
    --debug         Enable debug logging
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

from lib import config, log, pipeline, render
from lib.schema import slugify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research any topic across Reddit, HN, Polymarket, GitHub, web, and news."
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
                        help="Print available sources and exit")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    return parser


def save_output(report, emit: str, save_dir: str) -> Path:
    """Save report to disk."""
    path = Path(save_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    slug = slugify(report.topic)
    extension = "json" if emit == "json" else "md"

    out_path = path / f"{slug}-last30days.{extension}"

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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"
        log.DEBUG = True

    # Load config
    cfg = config.get_config()

    # Diagnose mode - check before topic validation
    if args.diagnose:
        available = config.available_sources(cfg)
        print(json.dumps({
            "available_sources": available,
            "has_brave": bool(cfg.get("BRAVE_API_KEY")),
            "has_serper": bool(cfg.get("SERPER_API_KEY")),
            "has_exa": bool(cfg.get("EXA_API_KEY")),
            "has_github": bool(cfg.get("GITHUB_TOKEN")),
            "has_newsapi": bool(cfg.get("NEWSAPI_KEY")),
        }, indent=2))
        return 0

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
    elif args.emit == "full" or args.emit == "md":
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
