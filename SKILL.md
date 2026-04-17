---
name: pulse
version: "0.0.4"
description: "Multi-source social search engine scored by real engagement. 15 sources: Reddit, HN, Polymarket, YouTube, GitHub, ArXiv, Lobsters, RSS, web, news, Bluesky, Dev.to, Lemmy, OpenAlex, Semantic Scholar, StackExchange, Manifold, Metaculus."
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [research, deep-research, reddit, hackernews, polymarket, github, youtube, arxiv, lobsters, rss, news, trends, social-media, web-search, multi-source, citations, neural-memory]
    related_skills: [polymarket, xitter, github-code-review, arxiv, neural-memory-first]
    requires:
      env:
        - BRAVE_API_KEY    # Optional: web search
        - GITHUB_TOKEN     # Optional: GitHub search
        - NEWSAPI_KEY      # Optional: news articles
        - OPENROUTER_API_KEY # Optional: LLM planner
argument-hint: 'pulse AI video tools, pulse best noise cancelling headphones'
homepage: https://github.com/itsXactlY/pulse-hermes
license: MIT
user-invocable: true
---

# PULSE v0.0.4 — The Pulse of the Internet

Research ANY topic across 15 sources. Scores by real engagement — not SEO, not editors.

> **EVOLUTION BUILD — FORGED FROM v0.0.3, NOW 15 SOURCES + 6 MAJOR UPGRADES**
>
> v0.0.4: Query Router, Adaptive Lookback, 7-Signal Scoring, Iterative Retrieval, Trend Detection, Multi-Agent Research Crew. 1,430 new lines.
>
> The human built the scaffolding. The agent builds the cathedral.

## CRITICAL: Project Path

**The project is at `~/projects/pulse` (remote: `pulse-hermes.git`).**

⚠️ **SYMLINK WARNING:** If a `lib` symlink exists at project root pointing to `scripts/lib`, REMOVE IT before spawning parallel agents. Agents using `write_file` on `lib/foo.py` will silently overwrite `scripts/lib/foo.py` through the symlink, and `git checkout` will destroy the work. Learned the hard way — 9 agents, 2 rounds, symlink ate everything.

## Why This Exists

Independent reimplementation of [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — ground-up reconstruction, not a fork. Pure Python stdlib, zero dependencies, designed for agent evolution.

Original: 14+ sources, ~15,000 lines, built by a human who knew exactly what he wanted.
PULSE: 10 sources, ~9,370 lines, built to be picked up and evolved by machines.

## Sources

| Source | Signal | Auth |
|--------|--------|:----:|
| **Reddit** | Unfiltered community takes, upvotes, top comments | No |
| **Hacker News** | Developer consensus, points, comments | No |
| **Polymarket** | Real-money prediction market odds | No |
| **YouTube** | Video transcripts, view counts, deep dives | No |
| **GitHub** | Repos, issues, PRs, star velocity | Token |
| **ArXiv** | Academic papers, ML/AI research, peer-reviewed signal | No |
| **Lobsters** | Curated tech links, systems programming, quality community | No |
| **RSS/Blogs** | Technical blogs, engineering insights, expert opinions | No |
| **Web** | Editorial coverage (Brave/Serper/Exa) | Key |
| **News** | NewsAPI articles from major publications | Key |

## When To Use

- User asks "what are people saying about X?"
- User wants prediction market odds (Polymarket)
- User wants a research briefing before a meeting, trip, or decision
- User asks to compare tools, products, or ideas across communities
- User wants to know what's trending in tech (HN), politics (Polymarket), culture (Reddit), or research (ArXiv)

## Usage

```bash
# Direct CLI
pulse "your topic"
pulse "bitcoin halving 2028" --depth deep
pulse "React Server Components" --sources reddit,hackernews,arxiv
pulse --diagnose
pulse --setup          # First-run wizard
pulse --stats          # Cache + store stats
pulse --history TOPIC  # Research history
pulse --trending       # Trending findings

# Hermes integration — context injection
pulse "your topic" --emit=context   # Compact snippet for other skills
pulse "your topic" --emit=json      # Machine-readable for programmatic use
pulse "your topic" --emit=full      # Save to disk or audit
pulse "your topic" --emit=md        # Markdown report
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--emit MODE` | Output: compact, json, full, md, context | compact |
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

## How Scoring Works (v0.0.3)

Five signals fused via Weighted Reciprocal Rank Fusion:

- **Local Relevance** (30%): Bigram/trigram token overlap with topic
- **Freshness** (20%): Recency within lookback window
- **Engagement** (25%): Platform metrics (upvotes, points, volume, views, stars)
- **Engagement Velocity** (10%): How fast engagement grows per day
- **Source Quality** (15%): Baseline trust in data source + self-learning weights

Three-pass deduplication: URL exact -> Content hash -> Cosine similarity.

## Architecture

```
scripts/
  pulse.py            # CLI entry point
  auto_commit.sh      # Auto commit + test + PR (for agents)
  hermes_bootstrap.sh # Auto-discovery for new Hermes agents
  polymarket_deep_scan.py # Deep Polymarket keyword scanner
  lib/
    schema.py          # Data models
    pipeline.py        # Orchestrator
    planner.py         # Heuristic planner
    llm_planner.py     # LLM planner (Ollama/OpenRouter/OpenAI)
    normalize.py       # Source normalizers
    score.py           # Multi-signal scoring (v0.0.3)
    dedupe.py          # Three-pass deduplication
    fusion.py          # Weighted RRF (k=60)
    cluster.py         # Cosine similarity clustering
    render.py          # Output rendering (compact/json/full/md)
    cache.py           # SQLite cache (24h TTL)
    store.py           # Persistent research store
    ui.py              # Live progress display
    setup.py           # First-run setup wizard
    config.py          # Environment management
    relevance.py       # Bigram/trigram relevance + cosine similarity
    self_learn.py      # Self-learning source weights
    neural_memory.py   # Neural memory integration
    filter.py          # Content filtering
    raw_filter.py      # Raw content filtering
    log.py             # Logging
    dates.py           # Date utilities
    http.py            # HTTP client
    # Sources (10):
    reddit.py, hackernews.py, polymarket.py, youtube.py,
    github.py, web_search.py, news.py,
    arxiv.py, lobsters.py, rss.py
    # Extended sources (optional):
    bluesky.py, devto.py, lemmy.py, manifold.py,
    metaculus.py, openalex.py, sem_scholar.py, stackexchange.py
```

## Contributing (For Agents)

```bash
# Make changes, then one command:
bash scripts/auto_commit.sh "feat: add Bluesky source via AT Protocol"
```

Tests run -> commit -> push -> PR. All automated. See CONTRIBUTING.md for details.

## See Also

- [itsXactlY/pulse-hermes](https://github.com/itsXactlY/pulse-hermes) — Main repo
- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — For semantic clustering
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original
- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`
