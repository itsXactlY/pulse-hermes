---
name: pulse
version: "0.0.2"
description: "Multi-source social search engine scored by real engagement. Research Reddit, HN, Polymarket, YouTube, GitHub, web, and news — ranked by what real people actually engage with, not SEO."
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [research, deep-research, reddit, hackernews, polymarket, github, youtube, news, trends, social-media, web-search, multi-source, citations]
    related_skills: [polymarket, xitter, github-code-review, arxiv, neural-memory-first]
    requires:
      env:
        - BRAVE_API_KEY    # Optional: web search
        - GITHUB_TOKEN     # Optional: GitHub search
        - NEWSAPI_KEY      # Optional: news articles
        - OPENROUTER_API_KEY # Optional: LLM planner
argument-hint: 'pulse AI video tools, pulse best noise cancelling headphones'
homepage: https://github.com/itsXactlY/pulse
license: MIT
user-invocable: true
---

# PULSE v0.0.2 — The Pulse of the Internet

Research ANY topic across Reddit, Hacker News, Polymarket, YouTube, GitHub, web, and news.
Scores by real engagement — upvotes, points, volume, views, stars. Not SEO. Not editors.

> **BLUEPRINT — NOW A CROWD PROJECT**
>
> The engine runs. Four sources are live. Cache, store, LLM planner, YouTube — all operational. But this is where it ends for the human. **Hermes agents must evolve this themselves.** Add a source. Tune the planner. Better clustering. Then auto-commit, auto-PR, and refine it as a crowd.
>
> The human built the scaffolding. The agent builds the cathedral.

## Why This Exists

Independent reimplementation of [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — ground-up reconstruction, not a fork. Pure Python stdlib, zero dependencies, designed for agent evolution.

Original: 14+ sources, ~15,000 lines, built by a human who knew exactly what he wanted.
PULSE: 7 sources, ~6,300 lines, built to be picked up and evolved by machines.

## Sources

| Source | Signal | Auth |
|--------|--------|:----:|
| **Reddit** | Unfiltered community takes, upvotes, top comments | No |
| **Hacker News** | Developer consensus, points, comments | No |
| **Polymarket** | Real-money prediction market odds | No |
| **YouTube** | Video transcripts, view counts, deep dives | No |
| **GitHub** | Repos, issues, PRs, star velocity | Token |
| **Web** | Editorial coverage (Brave/Serper/Exa) | Key |
| **News** | NewsAPI articles from major publications | Key |

Four sources work out of the box. Zero configuration.

## When To Use

- User asks "what are people saying about X?"
- User wants prediction market odds (Polymarket)
- User wants a research briefing before a meeting, trip, or decision
- User asks to compare tools, products, or ideas across communities
- User wants to know what's trending in tech (HN), politics (Polymarket), or culture (Reddit)

## Usage

```bash
# Direct CLI
pulse "your topic"
pulse "bitcoin halving 2028" --depth deep
pulse "React Server Components" --sources reddit,hackernews
pulse --diagnose
pulse --setup          # First-run wizard
pulse --stats          # Cache + store stats
pulse --history TOPIC  # Research history
pulse --trending       # Trending findings

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
| `--setup` | Run first-run setup wizard | — |
| `--stats` | Show cache and store statistics | — |
| `--history TOPIC` | Show research history | — |
| `--trending` | Show trending findings | — |
| `--no-llm` | Disable LLM planner (use heuristic) | — |
| `--no-cache` | Disable cache | — |
| `--no-store` | Disable persistent store | — |
| `--no-progress` | Disable progress display | — |

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
OPENROUTER_API_KEY=your_key  # LLM planner (cheapest cloud)
```

Ollama is auto-detected — no key needed for local LLM planning.

## How Scoring Works

Four signals fused via Weighted Reciprocal Rank Fusion:

- **Local Relevance** (35%): Token overlap with topic
- **Freshness** (25%): Recency within lookback window
- **Engagement** (25%): Platform metrics (upvotes, points, volume, views, stars)
- **Source Quality** (15%): Baseline trust in data source

Items appearing across multiple sources get a natural boost from RRF.

## Architecture

```
scripts/
  pulse.py            # CLI entry point
  auto_commit.sh      # Auto commit + test + PR (for agents)
  hermes_bootstrap.sh # Auto-discovery for new Hermes agents
  lib/
    schema.py          # Data models
    pipeline.py        # Orchestrator (parallel → normalize → score → fuse → cluster)
    planner.py         # Heuristic planner
    llm_planner.py     # LLM planner (Ollama/OpenRouter/OpenAI)
    normalize.py       # Source normalizers
    score.py           # Multi-signal scoring
    dedupe.py          # Near-duplicate detection
    fusion.py          # Weighted RRF (k=60)
    cluster.py         # Content clustering
    render.py          # Output rendering
    cache.py           # SQLite cache (24h TTL)
    store.py           # Persistent research store
    ui.py              # Live progress display
    setup.py           # First-run setup wizard
    config.py          # Environment management
    reddit.py          # Reddit (free)
    hackernews.py      # HN (free)
    polymarket.py      # Polymarket (free)
    youtube.py         # YouTube via yt-dlp (free)
    github.py          # GitHub
    web_search.py      # Brave/Serper/Exa
    news.py            # NewsAPI
```

## Contributing (For Agents)

```bash
# Make changes, then one command:
bash scripts/auto_commit.sh "feat: add Bluesky source via AT Protocol"
```

Tests run → commit → push → PR. All automated. See CONTRIBUTING.md for details.

## See Also

- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — For semantic clustering
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original
- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`
