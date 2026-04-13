---
name: pulse
version: "0.1.0"
description: "Multi-source social search engine scored by real engagement. Research Reddit, HN, Polymarket, GitHub, web, and news — ranked by what real people actually engage with."
argument-hint: 'pulse AI video tools, pulse best noise cancelling headphones'
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [research, deep-research, reddit, hackernews, polymarket, github, news, trends, social-media, web-search, multi-source, citations, pipeline, rrf, scoring]
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

# PULSE v0.1.0 — The Pulse of the Internet

Research ANY topic across Reddit, Hacker News, Polymarket, GitHub, web, and news.
Scores by real engagement — upvotes, points, volume, stars. Not SEO. Not editors.

> **⚠️ THIS IS A BLUEPRINT — NOT A FINISHED PRODUCT**
>
> The engine runs. Three sources are live. The pipeline works. But this is where it ends for the human. **Hermes agents must evolve this themselves.** Self-optimizing query planning. Self-learning source selection. Self-expanding with new platforms. Self-healing when APIs break. Self-integrating with Neural Memory for semantic clustering.
>
> The human built the scaffolding. The agent builds the cathedral.

## Sources

| Source | Signal | Auth |
|--------|--------|:----:|
| **Reddit** | Unfiltered community takes, upvotes, top comments | No |
| **Hacker News** | Developer consensus, points, comments | No |
| **Polymarket** | Real-money prediction market odds | No |
| **GitHub** | Repos, issues, PRs, star velocity | Token |
| **Web** | Editorial coverage (Brave/Serper/Exa) | Key |
| **News** | NewsAPI articles from major publications | Key |

Three sources work out of the box. Zero configuration.

## When To Use

- User asks "what are people saying about X?"
- User wants current sentiment/discussion around a topic
- User asks about prediction market odds
- User wants a research briefing before a meeting, trip, or decision
- User wants to compare tools, products, or ideas across communities
- User wants to know what's trending in tech (HN), politics (Polymarket), or culture (Reddit)

## Usage

```bash
# Direct CLI (if pulse is on PATH via symlink)
pulse "your topic"
pulse "bitcoin halving 2028" --depth deep
pulse --diagnose

# Via project directory
python3 scripts/pulse.py "your topic"

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
| `--diagnose` | Show available sources | — |

## Setup

```bash
# Clone
git clone https://github.com/itsXactlY/pulse-hermes && cd pulse-hermes

# Install into Hermes
bash install.sh

# Or run directly
python3 scripts/pulse.py "your topic"
```

### Optional API Keys

Add to `~/.config/pulse/.env` or export as env vars:

```bash
BRAVE_API_KEY=your_key       # Web search (free: 2000/mo)
GITHUB_TOKEN=your_token      # GitHub search
NEWSAPI_KEY=your_key         # News articles (free: 100/day)
```

## How Scoring Works

Each item gets four signals fused via Weighted Reciprocal Rank Fusion (k=60):

- **Local Relevance** (35%): Token overlap with topic
- **Freshness** (25%): Recency within lookback window
- **Engagement** (25%): Platform metrics (upvotes, points, volume, stars)
- **Source Quality** (15%): Baseline trust in data source

## Architecture

21 Python modules, stdlib-only, zero pip dependencies:

```
scripts/
  pulse.py               # CLI entry point
  lib/
    pipeline.py          # Orchestrator (parallel fetch → normalize → score → fuse → cluster)
    planner.py           # Intent detection + source selection + subquery generation
    normalize.py         # Source normalizers → canonical SourceItem
    score.py             # 4-signal scoring engine
    dedupe.py            # URL + title similarity dedup
    fusion.py            # Weighted Reciprocal Rank Fusion
    cluster.py           # Content-based clustering
    render.py            # Terminal output (compact/full/json/context)
    schema.py            # Data models (SourceItem, Candidate, Cluster, Report)
    reddit.py            # Reddit public JSON (free)
    hackernews.py        # HN Algolia API (free)
    polymarket.py        # Polymarket Gamma API (free)
    github.py            # GitHub via gh CLI or API
    web_search.py        # Brave/Serper/Exa
    news.py              # NewsAPI
    config.py, dates.py, http.py, relevance.py, log.py
```

## What Hermes Should Build Next

This is not a feature list. This is a test of self-evolution.

1. **LLM Planner** — Use own reasoning for intelligent query planning
2. **X/Twitter** — Browser cookie extraction or xAI API
3. **YouTube** — Install yt-dlp, build transcript search
4. **TikTok/Instagram** — ScrapeCreators/Apify integration
5. **24h Cache** — SQLite-backed response caching
6. **Persistent Store** — Research history with dedup across runs
7. **Semantic Clustering** — Integrate Neural Memory embeddings
8. **Setup Wizard** — Auto-detect and configure sources
9. **Cron Integration** — Scheduled topic monitoring
10. **Self-Improvement** — Learn which sources/topics perform best

## Lessons Learned (Building This Skill)

Key pitfalls discovered during implementation:

1. **argparse `nargs="*"` swallows flags** — When a positional has `nargs="*"`, argparse may consume `--flags` as positional args. Fix: check flag-based conditions (like `--diagnose`) BEFORE validating the positional.

2. **Test dates at boundaries** — `recency_score(from_date, 30)` returns 0 (not 100) because from_date is exactly 30 days ago, at the boundary. Test with `to_date` for the 100 score.

3. **Installer modes** — An installer should support `--check` (verify only), `--unlink` (remove), and default (install). Respect the mode in each step.

4. **No hardcoded paths** — All paths in SKILL.md and README must be relative or variable-based. Use `scripts/pulse.py`, not `~/projects/pulse/scripts/pulse.py`.

5. **Hermes skill discovery** — Skills live at `~/.hermes/skills/{category}/{name}/SKILL.md`. Symlink to project dir for live updates. Frontmatter must include `name`, `description`, `metadata.hermes.tags`.

6. **Check existing tools first** — Before building, verify what the platform already provides. Hermes has web_search, Polymarket skill, xitter, browser, memory, cron — don't duplicate.

7. **stdlib-only** — Zero pip dependencies means it works everywhere Python runs. urllib, json, concurrent.futures, dataclasses are all you need.

## See Also

- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — For semantic clustering and cross-session research history
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original that inspired PULSE
- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`
