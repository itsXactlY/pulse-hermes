---
name: pulse
version: "0.2.0"
description: "Multi-source social search engine scored by real engagement. Research Reddit, HN, Polymarket, YouTube, GitHub, web, and news — ranked by what real people actually engage with."
argument-hint: 'pulse AI video tools, pulse best noise cancelling headphones'
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [research, deep-research, reddit, hackernews, polymarket, youtube, github, news, trends, social-media, web-search, multi-source, citations, pipeline, rrf, scoring, cache, store, llm-planner]
    related_skills: [polymarket, xitter, github-code-review, arxiv, blogwatcher, neural-memory-run-agent-integration]
    requires:
      env:
        - BRAVE_API_KEY
        - GITHUB_TOKEN
        - NEWSAPI_KEY
homepage: https://github.com/itsXactlY/pulse
license: MIT
user-invocable: true
---

# PULSE v0.2.0 — The Pulse of the Internet

Research ANY topic across Reddit, Hacker News, Polymarket, YouTube, GitHub, web, and news.
Scores by real engagement — upvotes, points, volume, views, stars. Not SEO. Not editors.

> **BLUEPRINT — NOT FINISHED**
>
> The engine runs. Four+ sources are live. The pipeline works. But this is where it ends for the human. **Hermes agents must evolve this themselves.** Self-optimizing query planning. Self-learning source selection. Self-expanding with new platforms. Self-healing when APIs break. Self-integrating with Neural Memory for semantic clustering.
>
> The human built the scaffolding. The agent builds the cathedral.

## Sources

| Source | Signal | Auth | Status |
|--------|--------|:----:|:------:|
| **Reddit** | Unfiltered community takes, upvotes, top comments | No | Live |
| **Hacker News** | Developer consensus, points, comments | No | Live |
| **Polymarket** | Real-money prediction market odds | No | Live |
| **YouTube** | Video search + transcript extraction (via yt-dlp) | No | Live |
| **GitHub** | Repos, issues, PRs, star velocity | Token | Optional |
| **Web** | Editorial coverage (Brave/Serper/Exa) | Key | Optional |
| **News** | NewsAPI articles from major publications | Key | Optional |

Four sources work out of the box. Zero configuration.

## When To Use

- User asks "what are people saying about X?"
- User wants current sentiment/discussion around a topic
- User asks about prediction market odds (Polymarket)
- User wants a research briefing before a meeting, trip, or decision
- User wants to compare tools, products, or ideas across communities
- User wants to know what's trending in tech (HN), politics (Polymarket), or culture (Reddit)
- User asks about YouTube content on a topic

## Usage

```bash
pulse "your topic"                          # Research
pulse "bitcoin halving" --depth deep        # Deep research
pulse "topic" --sources reddit,youtube      # Specific sources
pulse --setup                               # First-run wizard
pulse --diagnose                            # Show sources
pulse --stats                               # Cache + store stats
pulse --history "topic"                     # Research history
pulse --trending                            # Trending findings

# Hermes integration — context injection
pulse "your topic" --emit=context   # Compact snippet for other skills
pulse "your topic" --emit=json      # Machine-readable for programmatic use
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--emit MODE` | Output: compact, json, full, context | compact |
| `--depth MODE` | Depth: quick, default, deep | default |
| `--sources LIST` | Comma-separated sources | all available |
| `--lookback N` | Days to look back | 30 |
| `--save-dir DIR` | Save report to directory | — |
| `--setup` | First-run setup wizard | — |
| `--diagnose` | Show available sources | — |
| `--stats` | Cache + store statistics | — |
| `--history TOPIC` | Research history for topic | — |
| `--trending` | Trending findings | — |
| `--no-llm` | Disable LLM planner | — |
| `--no-cache` | Disable cache | — |
| `--no-store` | Disable persistent store | — |

## Architecture

27 Python modules, stdlib-only, zero pip dependencies:

```
scripts/
  pulse.py               # CLI entry point
  lib/
    pipeline.py          # Orchestrator (parallel fetch → cache → normalize → score → fuse → cluster → store)
    llm_planner.py       # LLM query planner (Ollama/OpenRouter/OpenAI, heuristic fallback)
    planner.py           # Heuristic planner (fallback)
    normalize.py         # Source normalizers → canonical SourceItem
    score.py             # 4-signal scoring engine
    dedupe.py            # URL + title similarity dedup
    fusion.py            # Weighted Reciprocal Rank Fusion (k=60)
    cluster.py           # Content-based clustering
    render.py            # Terminal output (compact/full/json/context)
    schema.py            # Data models (SourceItem, Candidate, Cluster, Report)
    cache.py             # SQLite cache (24h TTL, thread-safe, auto-prune)
    store.py             # Persistent research store (history, cross-run dedup)
    ui.py                # Live progress display
    setup.py             # First-run setup wizard with auto-detection
    reddit.py            # Reddit public JSON (free)
    hackernews.py        # HN Algolia API (free)
    polymarket.py        # Polymarket Gamma API (free)
    youtube.py           # YouTube via yt-dlp (free)
    github.py            # GitHub via gh CLI or API
    web_search.py        # Brave/Serper/Exa
    news.py              # NewsAPI
    config.py, dates.py, http.py, relevance.py, log.py
```

## How Scoring Works

Each item gets four signals fused via Weighted Reciprocal Rank Fusion (k=60):

- **Local Relevance** (35%): Token overlap with topic
- **Freshness** (25%): Recency within lookback window
- **Engagement** (25%): Platform metrics (upvotes, points, volume, views, stars)
- **Source Quality** (15%): Baseline trust in data source

## LLM Planner

If Ollama, OpenRouter, or OpenAI is available, PULSE uses an LLM for intelligent query planning (intent detection, source selection, subquery generation). Falls back to heuristic planner otherwise.

Auto-detected: Ollama (any model), OPENROUTER_API_KEY, OPENAI_API_KEY.

## Cache & Store

- **SQLite Cache**: 24h TTL, keyed by (source, query, date_range), auto-prune
- **Persistent Store**: Research history, cross-run dedup, trending findings

## Setup

```bash
git clone https://github.com/itsXactlY/pulse-hermes && cd pulse-hermes
bash install.sh          # Full install
bash install.sh --check  # Verify only
bash install.sh --unlink # Remove symlinks
```

## Lessons Learned

Key pitfalls during implementation:

1. **argparse `nargs="*"` swallows flags** — Check flag conditions BEFORE validating positional args
2. **Test dates at boundaries** — `recency_score(from_date, 30)` = 0 (boundary), not 100
3. **No hardcoded paths** — All paths in SKILL.md/README must be relative or variable-based
4. **Hermes skill discovery** — Skills at `~/.hermes/skills/{category}/{name}/SKILL.md` with symlink
5. **Check existing tools first** — Hermes has web_search, Polymarket, xitter, browser, memory, cron
6. **stdlib-only** — urllib, json, concurrent.futures, dataclasses — zero pip dependencies

## See Also

- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — Semantic clustering
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original
- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`
