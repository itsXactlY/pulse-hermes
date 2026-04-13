# pulse v0.0.1 — Hermes Edition

> **⚠️ PROOF OF CONCEPT — CLONE WARNING**
>
> This is an independent reimplementation of [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill), built from scratch for the Hermes Agent ecosystem. It is *not* a fork — it's a ground-up reconstruction of the architecture and concepts.
>
> **This PoC validates the core engine.** Hermes should evolve this into a fully autonomous, self-improving research system with memory, learning, and zero-config setup. The hard part — the multi-source pipeline, RRF fusion, clustering — is done. The rest is iteration.

---

**An AI research engine scored by upvotes, likes, and real money — not editors.**

Search Reddit. Hacker News. Polymarket prediction markets. GitHub. The web. News.
Score it all by what real people actually engage with.
Rank it with Weighted Reciprocal Rank Fusion.
Cluster the results thematically.
Deliver a research briefing in seconds.

Google aggregates editors. pulse searches people.

## What This Does

```
$ pulse "OpenAI Codex"

=== pulse: OpenAI Codex ===
Date range: 2026-03-14 to 2026-04-13
Sources: 3 active (Hacker News, Polymarket, Reddit)

=== RANKED EVIDENCE CLUSTERS ===

[1] Codex Openai Limits (score:0.0, 6 items, Reddit)
  1. **Thanks to the leaked source code for Claude Code...**
  [Reddit] score:0.02 | 2733 pts, 232 cmts
  ...

[2] Pricing Codex Openai (score:0.0, 1 items, Hacker News)
  1. **OpenAI Codex Moves to API Usage-Based Pricing**
  [Hacker News] score:0.01 | 6 pts, 5 cmts
  ...

[5] Openai Ipo Closing (score:0.0, 4 items, Polymarket)
  1. **OpenAI IPO closing market cap above ___ ?**
  [Polymarket] score:0.01 | $1,370,841 vol
  ...
```

## Sources

| Source | What It Tells You | Auth Required |
|--------|-------------------|:-------------:|
| **Reddit** | Unfiltered community takes, top comments with upvote counts | No |
| **Hacker News** | Developer consensus, points and comments | No |
| **Polymarket** | Odds backed by real money and insider information | No |
| **GitHub** | Repos, issues, PRs, star velocity | Token (optional) |
| **Web** | Editorial coverage, blog posts | API key |
| **News** | NewsAPI articles from major publications | API key |

Three sources work out of the box with zero configuration.

## Quick Start

```bash
# Clone and install
git clone <repo-url> ~/projects/pulse
cd ~/projects/pulse
bash install.sh

# Run it
pulse "your topic"
pulse "bitcoin halving 2028" --depth deep
pulse "React Server Components" --sources reddit,hackernews
pulse --diagnose
```

### No Install (Direct)

```bash
python3 ~/projects/pulse/scripts/pulse.py "your topic"
```

## CLI Reference

```
pulse <topic> [options]

Options:
  --emit MODE       Output mode: compact (default), json, full, context
  --depth MODE      Research depth: quick, default (default), deep
  --sources LIST    Comma-separated: reddit,hackernews,polymarket,github,web,news
  --lookback N      Days to look back (default: 30)
  --save-dir DIR    Save report to directory
  --diagnose        Show available sources and exit
  --debug           Enable debug logging
```

## Configuration

Optional API keys go in `~/.config/pulse/.env`:

```bash
# Web search (pick one):
BRAVE_API_KEY=your_key          # Free: 2000 queries/month at brave.com/search/api
SERPER_API_KEY=your_key         # Google search via serper.dev
EXA_API_KEY=your_key            # Semantic search via exa.ai

# GitHub:
GITHUB_TOKEN=your_token         # Or use `gh auth login`

# News:
NEWSAPI_KEY=your_key            # Free: 100 requests/day at newsapi.org
```

Or set them as environment variables.

## How Scoring Works

Each item receives four signals:

| Signal | Weight | Description |
|--------|:------:|-------------|
| **Local Relevance** | 35% | Token overlap with topic + source relevance hint |
| **Freshness** | 25% | Recency within the lookback window |
| **Engagement** | 25% | Platform-specific metrics (upvotes, points, volume, stars) |
| **Source Quality** | 15% | Baseline trust in the data source |

Results from multiple sources and subqueries are fused using **Weighted Reciprocal Rank Fusion** (RRF, k=60). Items appearing across multiple sources get a natural boost. Related items are clustered by content similarity.

## Architecture

```
pulse/
├── scripts/
│   ├── pulse.py        # CLI entry point
│   └── lib/
│       ├── __init__.py
│       ├── schema.py        # Data models (SourceItem, Candidate, Cluster, Report)
│       ├── pipeline.py      # Orchestrator (parallel fetch → normalize → score → fuse → cluster)
│       ├── planner.py       # Intent detection + source selection + subquery generation
│       ├── normalize.py     # Source-specific normalizers to canonical SourceItem
│       ├── score.py         # Multi-signal scoring engine
│       ├── dedupe.py        # Near-duplicate detection (URL + title similarity)
│       ├── fusion.py        # Weighted Reciprocal Rank Fusion
│       ├── cluster.py       # Content-based clustering
│       ├── render.py        # Terminal-friendly output rendering
│       ├── config.py        # Environment and API key management
│       ├── dates.py         # Date range utilities
│       ├── http.py          # HTTP client with retry + backoff
│       ├── relevance.py     # Token overlap scoring
│       ├── log.py           # Logging utilities
│       ├── reddit.py        # Reddit public JSON search (free)
│       ├── hackernews.py    # HN Algolia API search (free)
│       ├── polymarket.py    # Polymarket Gamma API search (free)
│       ├── github.py        # GitHub search via gh CLI or API
│       ├── web_search.py    # Brave/Serper/Exa web search
│       └── news.py          # NewsAPI search
├── tests/
├── docs/
├── fixtures/
├── install.sh
├── pyproject.toml
├── LICENSE
└── README.md
```

### Pipeline Flow

```
Topic Input
    │
    ▼
┌─────────────┐
│   Planner   │  Detects intent, selects sources, generates subqueries
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                    Parallel Retrieval                        │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌─────┐       │
│  │ Reddit │ │   HN   │ │PolyMarket│ │ GitHub │ │ Web │       │
│  └───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └──┬──┘       │
│      └──────────┴───────────┴────────────┴─────────┘         │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Normalize  │  → canonical SourceItem
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Score    │  relevance + freshness + engagement + quality
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Dedupe    │  URL exact + title similarity
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  RRF Fusion │  weighted reciprocal rank fusion
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Cluster    │  content similarity grouping
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Render    │  compact / full / json / context
                    └─────────────┘
```

## Output Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `compact` | Terminal-friendly ranked clusters | Quick research, CLI |
| `full` | All items by source, detailed | Auditing, saving |
| `json` | Machine-readable structured data | Programmatic use |
| `context` | Compact snippet for embedding | Agent integration |

## Embedding In Other Tools

```bash
# Inject as context for another agent/skill
pulse "your topic" --emit=context

# Get structured JSON
pulse "your topic" --emit=json

# Save to disk
pulse "your topic" --save-dir ~/Documents/research/
```

## Known Limitations (PoC)

- **No LLM planner** — uses heuristic intent detection instead of LLM-based query planning
- **No X/Twitter** — requires browser cookies or xAI API key (not implemented in PoC)
- **No YouTube** — requires yt-dlp (not implemented in PoC)
- **No TikTok/Instagram** — requires ScrapeCreators API key
- **No setup wizard** — manual config only
- **No caching** — fresh fetch every run
- **No SQLite store** — no persistent history
- **Basic clustering** — token-overlap only, no semantic embeddings

All of these are straightforward extensions. The hard part — the pipeline architecture, RRF fusion, multi-source normalization — is done.

## Comparison with Original

| Feature | mvanhorn/last30days-skill | This PoC |
|---------|:-------------------------:|:--------:|
| Sources | 14+ | 6 |
| Reddit | ✓ (public + ScrapeCreators) | ✓ (public) |
| Hacker News | ✓ | ✓ |
| Polymarket | ✓ | ✓ |
| GitHub | ✓ | ✓ |
| Web Search | ✓ (Brave/Exa/Serper) | ✓ (Brave/Exa/Serper) |
| X/Twitter | ✓ | ✗ |
| YouTube | ✓ | ✗ |
| TikTok/Instagram | ✓ | ✗ |
| LLM Planner | ✓ | ✗ (heuristic) |
| RRF Fusion | ✓ | ✓ |
| Clustering | ✓ | ✓ |
| Caching | ✓ (24h TTL) | ✗ |
| SQLite Store | ✓ | ✗ |
| Setup Wizard | ✓ | ✗ |
| Zero-config sources | 3 | 3 |
| Python stdlib only | ✓ | ✓ |
| Lines of code | ~15,000+ | ~3,300 |

## Roadmap for Hermes

1. **LLM Planner** — Use Hermes's own LLM for intelligent query planning
2. **X/Twitter** — Browser cookie extraction or xAI API integration
3. **YouTube** — yt-dlp transcript search
4. **TikTok/Instagram** — ScrapeCreators or Apify integration
5. **24h Cache** — SQLite-backed response caching
6. **Persistent Store** — Research history with dedup across runs
7. **Semantic Clustering** — Use Neural Memory embeddings for clustering
8. **Setup Wizard** — Auto-detect and configure available sources
9. **Cron Integration** — Scheduled topic monitoring
10. **Self-Improvement** — Hermes learns which sources/topics perform best

## License

MIT — see [LICENSE](LICENSE).

## Credits

Architecture inspired by [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill). Built from scratch as a Hermes Agent proof of concept. No code was copied — only the concepts and patterns were reimplemented.
