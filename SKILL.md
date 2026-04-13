# last30days v3.0.0 - Hermes Edition

Research ANY topic across Reddit, Hacker News, Polymarket, GitHub, web, and news.
Surface what people are actually discussing, recommending, betting on, and debating right now.

## What It Does

Scores by real engagement: Reddit upvotes, HN points, Polymarket volume backed by real money, GitHub stars. Not SEO. Not editors. What people actually engage with.

| Source | What it tells you |
|--------|-------------------|
| **Reddit** | The unfiltered take. Top comments with upvote counts, free via public JSON. |
| **Hacker News** | Developer consensus. Points and comments. Where technical people argue. |
| **Polymarket** | Odds backed by real money. Not opinions, actual betting markets. |
| **GitHub** | PR velocity, top repos by stars, issues, releases. |
| **Web** | Editorial coverage, blog posts, news articles. |
| **News** | NewsAPI articles from major publications. |

## How To Use

Just ask: "last30days [topic]"

The engine automatically:
1. Detects your intent (prediction? comparison? person research?)
2. Selects the best sources for your topic
3. Searches all sources in parallel
4. Normalizes, scores, and deduplicates
5. Clusters related results
6. Ranks by weighted Reciprocal Rank Fusion
7. Renders a ranked briefing

## CLI Reference

```bash
python3 ~/.hermes/skills/last30days/scripts/last30days.py <topic> [options]

Options:
  --emit MODE     Output: compact (default), json, full, context
  --depth MODE    Depth: quick, default (default), deep
  --sources LIST  Comma-separated: reddit,hackernews,polymarket,github,web,news
  --lookback N    Days to look back (default: 30)
  --save-dir DIR  Save report to directory
  --diagnose      Show available sources and exit
  --debug         Enable debug logging
```

## Examples

```
last30days OpenAI Codex
last30days Kanye West --depth deep
last30days best noise cancelling headphones --sources reddit,web
last30days will Trump win 2028 --sources polymarket,reddit
last30days @steipete --depth deep
```

## Setup

### Required
Nothing! Reddit, Hacker News, and Polymarket work out of the box (free, no API keys).

### Optional API Keys
Add to `~/.config/last30days/.env` or export as environment variables:

```
# Web search (pick one):
BRAVE_API_KEY=your_key          # Free: 2000 queries/month at brave.com/search/api
SERPER_API_KEY=your_key         # Google search via serper.dev
EXA_API_KEY=your_key            # Semantic search via exa.ai

# GitHub (enables repo/issue/PR search):
GITHUB_TOKEN=your_token         # Or use `gh auth login`

# News (optional):
NEWSAPI_KEY=your_key            # Free: 100 requests/day at newsapi.org
```

### Check Available Sources
```bash
python3 ~/.hermes/skills/last30days/scripts/last30days.py --diagnose
```

## Architecture

```
scripts/
  last30days.py          # CLI entry point
  lib/
    __init__.py          # Package init
    schema.py            # Data models (SourceItem, Candidate, Cluster, Report)
    pipeline.py          # Orchestrator (parallel fetch -> normalize -> score -> fuse -> cluster)
    planner.py           # Intent detection + source selection + subquery generation
    normalize.py         # Source-specific normalizers to canonical SourceItem
    score.py             # Multi-signal scoring (relevance, recency, engagement, source quality)
    dedupe.py            # Near-duplicate detection (URL + title similarity)
    fusion.py            # Weighted Reciprocal Rank Fusion
    cluster.py           # Content-based clustering
    render.py            # Terminal-friendly output rendering
    config.py            # Environment and API key management
    dates.py             # Date range utilities
    http.py              # HTTP client with retry logic
    relevance.py         # Token overlap scoring
    log.py               # Logging utilities
    reddit.py            # Reddit public JSON search (free, no auth)
    hackernews.py        # HN Algolia API search (free, no auth)
    polymarket.py        # Polymarket Gamma API search (free, no auth)
    github.py            # GitHub search via gh CLI or API
    web_search.py        # Brave/Serper/Exa web search
    news.py              # NewsAPI search
```

## How Scoring Works

Each item gets four signals:
1. **Local Relevance** (35%): Token overlap with topic + source's own relevance hint
2. **Freshness** (25%): Recency within the lookback window
3. **Engagement** (25%): Platform-specific metrics (upvotes, points, volume, stars)
4. **Source Quality** (15%): Baseline trust in the source

Sources are then fused using Weighted Reciprocal Rank Fusion, which naturally rewards items that appear across multiple sources and subqueries.

## Output Modes

- **compact**: Terminal-friendly clusters with top items (default)
- **full**: All items by source, detailed (for saving/auditing)
- **json**: Machine-readable JSON for programmatic use
- **context**: Compact snippet for embedding in other skills/agents

## Embedding In Other Skills

```bash
# Get context snippet for injection
python3 ~/.hermes/skills/last30days/scripts/last30days.py "your topic" --emit=context

# Get JSON for programmatic use
python3 ~/.hermes/skills/last30days/scripts/last30days.py "your topic" --emit=json

# Save report to disk
python3 ~/.hermes/skills/last30days/scripts/last30days.py "your topic" --save-dir ~/Documents/research/
```
