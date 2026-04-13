---
name: pulse
version: "0.0.1"
description: "Multi-source social search engine scored by real engagement. Research Reddit, HN, Polymarket, GitHub, web, and news — ranked by what real people actually engage with, not SEO."
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [research, deep-research, reddit, hackernews, polymarket, github, news, trends, social-media, web-search, multi-source, citations]
    related_skills: [polymarket, xitter, github-code-review, arxiv, blogwatcher]
    requires:
      env:
        - BRAVE_API_KEY    # Optional: web search
        - GITHUB_TOKEN     # Optional: GitHub search
        - NEWSAPI_KEY      # Optional: news articles
argument-hint: 'pulse AI video tools, pulse best noise cancelling headphones'
homepage: https://github.com/itsXactlY/pulse
license: MIT
user-invocable: true
---

# PULSE v0.0.1 — The Pulse of the Internet

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
- User wants to know the current sentiment/discussion around a topic
- User asks about prediction market odds (Polymarket)
- User wants a research briefing before a meeting, trip, or decision
- User asks to compare tools, products, or ideas across communities
- User wants to know what's trending in tech (HN), politics (Polymarket), or culture (Reddit)

## How It Works

```
Topic → Planner (intent detection + source selection)
      → Parallel fetch (Reddit, HN, Polymarket, GitHub, Web, News)
      → Normalize (canonical SourceItem schema)
      → Score (relevance 35% + freshness 25% + engagement 25% + quality 15%)
      → Deduplicate (URL exact + title similarity)
      → RRF Fusion (weighted reciprocal rank fusion, k=60)
      → Cluster (content similarity grouping)
      → Render (compact / full / json / context)
```

## Usage

```bash
# Direct CLI
pulse "your topic"
pulse "bitcoin halving 2028" --depth deep
pulse "React Server Components" --sources reddit,hackernews
pulse --diagnose

# Hermes integration — context injection
pulse "your topic" --emit=context   # Compact snippet for other skills
pulse "your topic" --emit=json      # Machine-readable for programmatic use
pulse "your topic" --emit=full      # Save to disk or audit
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
| `--debug` | Enable debug logging | — |

## Setup

```bash
# Clone
git clone https://github.com/itsXactlY/pulse-hermes && cd pulse-hermes

# Install into Hermes
bash install.sh

# Or just run directly (no install needed)
python3 scripts/pulse.py "your topic"
```

### Optional API Keys

Add to `~/.config/pulse/.env` or export as env vars:

```bash
BRAVE_API_KEY=your_key       # Web search (free: 2000/mo)
GITHUB_TOKEN=your_token      # GitHub search
NEWSAPI_KEY=your_key         # News articles (free: 100/day)
```

## Embedding In Other Skills

```bash
# Get context snippet for injection into another agent/skill
pulse "your topic" --emit=context

# Get structured JSON for programmatic processing
pulse "your topic" --emit=json

# Save full report to disk
pulse "your topic" --save-dir ~/Documents/research/
```

## Scoring

Each item receives four signals fused via Weighted Reciprocal Rank Fusion:

- **Local Relevance** (35%): Token overlap with topic
- **Freshness** (25%): Recency within lookback window
- **Engagement** (25%): Platform metrics (upvotes, points, volume, stars)
- **Source Quality** (15%): Baseline trust in data source

Items appearing across multiple sources get a natural boost from RRF.

## See Also

- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — For semantic clustering and cross-session research history
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original that inspired PULSE
- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`
