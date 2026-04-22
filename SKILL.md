---
name: pulse
version: "4.0"
description: "Multi-source social search engine scored by real engagement. 18 sources: Reddit, HN, Polymarket, YouTube, GitHub, ArXiv, Lobsters, RSS, Bluesky, Dev.to, Lemmy, OpenAlex, Semantic Scholar, StackExchange, Manifold, Metaculus, Tickertick, News. 16 work without API keys."
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [research, deep-research, reddit, hackernews, polymarket, github, youtube, arxiv, lobsters, rss, news, trends, social-media, web-search, multi-source, citations, neural-memory, prediction-markets, bluesky, lemmy]
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

# PULSE v4.0 — The Pulse of the Internet

Research ANY topic across 18 sources. Scores by real engagement — not SEO, not editors.

> **6 UPGRADES FROM arXiv DEEP RESEARCH — ~93 papers analyzed**
>
> Query Router · Adaptive Lookback · 7-Signal Scoring · Iterative Retrieval · Trend Detection · Multi-Agent Research Crew
>
> "The human built the floor. The agents building the cathedral."

## CRITICAL: Project Path

**The project is at the clone directory (remote: `pulse-hermes.git`). Use `$(pwd)` or the agent's working directory — never hardcode paths.**

⚠️ **SYMLINK WARNING:** If a `lib` symlink exists at project root pointing to `scripts/lib`, REMOVE IT before spawning parallel agents. Agents using `write_file` on `lib/foo.py` will silently overwrite `scripts/lib/foo.py` through the symlink, and `git checkout` will destroy the work. Learned the hard way — 9 agents, 2 rounds, symlink ate everything.

## Why This Exists

Independent reimplementation of [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — ground-up reconstruction, not a fork. Pure Python stdlib, zero dependencies, designed for agent evolution.

Original: 14+ sources, ~15,000 lines, built by a human who knew exactly what he wanted.
PULSE: 10 sources, ~9,370 lines, built to be picked up and evolved by machines.

## Sources (18 total — 16 work WITHOUT any API keys)

| Source | Signal | Auth |
|--------|--------|:----:|
| **Reddit** | Unfiltered community takes, upvotes, top comments | No |
| **Hacker News** | Developer consensus, points, comments | No |
| **Polymarket** | Real-money prediction market odds | No |
| **YouTube** | Video transcripts, view counts, deep dives | No |
| **ArXiv** | Academic papers, ML/AI research, peer-reviewed signal | No |
| **Lobsters** | Curated tech links, systems programming, quality community | No |
| **RSS/Blogs** | Technical blogs, engineering insights, expert opinions | No |
| **GitHub** | Repos, issues, PRs, star velocity | Token |
| **Bluesky** | Decentralized social, growing alternative to X/Twitter | No |
| **Dev.to** | Developer blog posts, low-barrier technical content | No |
| **Lemmy** | Decentralized Reddit alternative, alternative community takes | No |
| **StackExchange** | Q&A from Stack Overflow and the SE network, expert answers | No |
| **OpenAlex** | Open academic graph, 250M+ scholarly works | No |
| **Semantic Scholar** | Academic papers with citation data and recommendations | No |
| **Manifold** | Play-money prediction markets, community forecasts | No |
| **Metaculus** | Forecasting community, calibrated prediction track records | No |
| **Tickertick** | Curated news aggregation, topic-based news feeds | No |
| **News** | NewsAPI articles from major publications | Key |

## When To Use

- User asks "what are people saying about X?"
- User wants prediction market odds (Polymarket, Manifold, Metaculus)
- User wants a research briefing before a meeting, trip, or decision
- User wants to compare tools, products, or ideas across communities
- User wants to know what's trending in tech (HN), politics (Polymarket), culture (Reddit), or research (ArXiv)
- User wants deep multi-round research with gap analysis (--crew or --iterative)
- User wants breaking news monitoring with velocity alerts (--breaking)

## Usage
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

# Advanced
pulse "topic" --crew --iterative --max-rounds 3  # Multi-agent research
pulse "topic" --breaking                            # Breaking news monitor
pulse "topic" --yolo                               # Skip approval, run fully autonomous

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
| `--yolo` | Skip human approval — run fully autonomous | — |
| `--crew` | Multi-agent deep research (Collector→Analyzer→Specialist→Synthesizer) | — |
| `--iterative` | Multi-round retrieval with perspective gap filling | — |
| `--max-rounds N` | Max rounds for --crew/--iterative | 3 |
| `--breaking` | Breaking-news monitor: poll every 5 min, alert on spikes | — |
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
OPENROUTER_API_KEY=your_key  # LLM planner (cheapest cloud)
```

Ollama is auto-detected — no key needed for local LLM planning.

## How Scoring Works (v0.0.3)
## How Scoring Works (v4.0)

Seven signals fused via Weighted Reciprocal Rank Fusion (RRF, k=60):

| Signal | Weight | What It Measures |
|--------|:------:|------------------|
| **Local Relevance** | 25% | Token overlap with topic (bigram/trigram weighted) |
| **Freshness** | 15% | Recency within the lookback window |
| **Engagement** | 20% | Platform metrics (upvotes, points, volume, views, stars) |
| **Engagement Velocity** | 10% | How fast engagement grows per day |
| **Source Quality** | 10% | Baseline trust + self-learning weights |
| **Retentive Value** | 10% | Did this source help with similar topics before? |
| **Cross-Source Confirmation** | 10% | Same content from 3+ sources = higher trust |

Four-pass deduplication: URL exact → Content hash → Bigram pre-filter → Cosine similarity (O(n log n)).

## Architecture
```
scripts/
  pulse.py                  # CLI entry point
  auto_commit.sh            # Auto commit + test + PR (for agents)
  hermes_bootstrap.sh       # Auto-discovery for new Hermes agents
  polymarket_deep_scan.py   # Deep Polymarket keyword scanner
  lib/
    schema.py               # Data models
    pipeline.py             # Orchestrator
    planner.py              # Heuristic planner
    llm_planner.py          # LLM planner (Ollama/OpenRouter/OpenAI)
    normalize.py            # Source normalizers
    score.py                # 7-signal scoring (v4.0)
    dedupe.py               # 4-pass dedup (URL, hash, bigram, cosine)
    fusion.py               # Weighted RRF (k=60)
    cluster.py              # Cosine similarity clustering
    render.py               # Output rendering (5 modes: compact/json/full/md/context)
    cache.py                # SQLite cache (24h TTL)
    store.py                # Persistent research store
    ui.py                   # Live progress display
    setup.py                # First-run setup wizard
    config.py               # Environment management
    query_router.py         # Query type classification + source routing (v4.0)
    adaptive_lookback.py    # Dynamic time windows (v4.0)
    iterative_retrieval.py  # Multi-round gap analysis (v4.0)
    trend_detector.py       # Velocity/spread/drift detection (v4.0)
    research_crew.py        # Multi-agent research pipeline (v4.0)
    relevance.py             # Token overlap + cosine similarity
    self_learn.py           # Self-learning source weights
    neural_memory.py        # Neural memory integration
    filter.py               # Result filtering
    raw_filter.py           # Raw data pre-filtering
    http.py                 # HTTP client utilities
    log.py                  # Structured logging
    dates.py                # Date/time helpers
    # Sources (18):
    reddit.py, hackernews.py, polymarket.py, youtube.py,
    github.py, web_search.py, news.py, arxiv.py, lobsters.py, rss.py,
    bluesky.py, devto.py, lemmy.py, stackexchange.py, openalex.py,
    sem_scholar.py, manifold.py, metaculus.py, tickertick.py,
    bing_news.py, serpapi_news.py
```

## Contributing (For Agents)

```bash
# Make changes, then one command:
bash scripts/auto_commit.sh "feat: add Bluesky source via AT Protocol"
```

Tests run -> commit -> push -> PR. All automated. See CONTRIBUTING.md for details.

## Limitations & Fallback Strategies

PULSE works best for English/tech topics. For German niche products, specialized research, or when PULSE returns few results:

### When PULSE Fails
1. **German pet products** — PULSE rarely finds relevant results. Direct scraping needed.
2. **Niche consumer products** — Limited Reddit/HN coverage. Try manufacturer sites + retailers.
3. **Non-English content** — Search engines may not index well.

### Fallback Approaches

**German Pet Products:**
- **Zooplus.de** — Good product details, composition, prices (Shopify-based, scrapable)
- **Amazon.de** — May not carry all products; search with exact product name
- **AniForte.de** — Shopify store, but direct product URLs may fail (try `/search?q=product`)
- **German forums** — hundeforum.de, hunde.de (SSL issues common, may need browser)

**Scientific Validation:**
- **PubMed** — Search for herb/ingredient effectiveness studies
- **NCBI PMC** — Full-text articles on antiparasitic properties
- **Google Scholar** — Academic papers on specific ingredients

**Product Analysis:**
1. Extract composition/ingredients from retailer sites
2. Search PubMed for each ingredient's effectiveness
3. Check for clinical studies on the specific product
4. Compare price per kg to alternatives
5. Look for veterinary opinions (tierarzt.de, vetline.de)

### Example Workflow (German Product Research)
```python
# 1. Try PULSE first
pulse "AniForte WermiX Hund" --depth deep

# 2. If insufficient, scrape retailer sites
# Zooplus often has German pet products
curl -s "https://www.zooplus.de/search?q=product+name"

# 3. Extract ingredients from product page
# Look for: Zusammensetzung, Inhaltsstoffe, Zutaten

# 4. Validate ingredients scientifically
# PubMed: "ingredient name antiparasitic dogs"
```

## See Also

- [itsXactlY/pulse-hermes](https://github.com/itsXactlY/pulse-hermes) — Main repo
- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — For semantic clustering
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original
- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`
