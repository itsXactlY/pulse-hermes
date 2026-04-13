---
name: pulse
version: "0.0.1"
description: "Multi-source social search engine scored by real engagement. Research Reddit, HN, Polymarket, GitHub, web, and news - ranked by what people actually engage with."
argument-hint: 'pulse AI video tools, pulse best noise cancelling headphones'
homepage: https://github.com/itsXactlY/pulse
author: hermes-agent
license: MIT
user-invocable: true
metadata:
  hermes:
    tags:
      - research
      - deep-research
      - reddit
      - hackernews
      - polymarket
      - github
      - news
      - trends
      - social-media
      - analysis
      - web-search
      - multi-source
      - citations
---

# PULSE v0.0.1 — The Pulse of the Internet

Research ANY topic across Reddit, Hacker News, Polymarket, GitHub, web, and news.
Scores by real engagement — upvotes, points, volume, stars. Not SEO. Not editors.

> **⚠️ PROOF OF CONCEPT** — Hermes should evolve this into a fully autonomous research system. The core engine (pipeline, RRF fusion, clustering) is done. What's missing: LLM planner, X/Twitter, YouTube, caching, persistent store, semantic clustering with Neural Memory.

## Sources

| Source | What It Tells You | Auth Required |
|--------|-------------------|:-------------:|
| **Reddit** | Unfiltered community takes, top comments with upvote counts | No |
| **Hacker News** | Developer consensus, points and comments | No |
| **Polymarket** | Odds backed by real money and insider information | No |
| **GitHub** | Repos, issues, PRs, star velocity | Token (optional) |
| **Web** | Editorial coverage, blog posts (Brave/Serper/Exa) | API key |
| **News** | NewsAPI articles from major publications | API key |

## Usage

```bash
# Direct CLI
python3 ~/projects/pulse/scripts/pulse.py "your topic"
python3 ~/projects/pulse/scripts/pulse.py "bitcoin halving" --depth deep --sources reddit,polymarket
python3 ~/projects/pulse/scripts/pulse.py --diagnose

# Via symlink (after install.sh)
pulse "your topic"

# Hermes integration — context injection
python3 ~/projects/pulse/scripts/pulse.py "your topic" --emit=context
python3 ~/projects/pulse/scripts/pulse.py "your topic" --emit=json
```

## Options

```
--emit MODE       Output: compact (default), json, full, context
--depth MODE      Depth: quick, default (default), deep
--sources LIST    Comma-separated: reddit,hackernews,polymarket,github,web,news
--lookback N      Days to look back (default: 30)
--save-dir DIR    Save report to directory
--diagnose        Show available sources
--debug           Enable debug logging
```

## How Scoring Works

Each item gets four signals:
1. **Local Relevance** (35%): Token overlap with topic
2. **Freshness** (25%): Recency within lookback window
3. **Engagement** (25%): Platform metrics (upvotes, points, volume, stars)
4. **Source Quality** (15%): Baseline trust in data source

Fused via Weighted Reciprocal Rank Fusion (k=60). Items appearing across multiple sources get a natural boost.

## Setup

Three sources work with zero config (Reddit, HN, Polymarket).

Optional keys in `~/.config/pulse/.env`:
```
BRAVE_API_KEY=your_key       # Web search
GITHUB_TOKEN=your_token      # GitHub search
NEWSAPI_KEY=your_key         # News articles
```

## Hermes Built-in vs PULSE Unique Value

Before building features, check what Hermes already provides. This audit was done 2026-04-13:

| Capability | Hermes Built-in | PULSE Adds |
|-----------|:-:|:-:|
| Web Search | `web_search` (Exa/Firecrawl/Parallel/Tavily) | — |
| Browser | Camoufox (can scrape anything) | — |
| Polymarket | Dedicated skill (`skills/research/polymarket`) | — |
| X/Twitter | xitter skill (`skills/social-media/xitter`) | — |
| GitHub | Multiple skills (PR, Issues, Repo) | — |
| Memory | Built-in + 8 provider plugins | — |
| Cron Jobs | `cronjob` tool | — |
| Session Search | `session_search` tool | — |
| Reddit (public JSON) | **NO** | **YES** — no browser, no API key |
| HN Algolia Search | **NO** | **YES** — no browser, no API key |
| Multi-Source Pipeline | **NO** | **YES** — parallel fetch + normalize + score |
| RRF Fusion | **NO** | **YES** — cross-source ranking |
| Evidence Clustering | **NO** | **YES** — content similarity grouping |
| Engagement Scoring | **NO** | **YES** — platform-specific metrics |

**Rule of thumb**: If Hermes has a tool/skill for it, USE that. PULSE fills gaps, not duplicates.

## See Also

- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — Neural Memory for semantic clustering and cross-session research history
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original that inspired PULSE
