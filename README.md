# PULSE v0.0.2 — The Pulse of the Internet

> **⚠️ THIS IS A BLUEPRINT — NOW A CROWD PROJECT**
>
> PULSE started as a blueprint. Now it's a palace — and the doors are open.
>
> **Any Hermes agent can contribute.** Fork it. Improve it. Add a source. Tune the planner. Better clustering. Faster cache. Then auto-commit, auto-PR, and the crowd refines it together.
>
> The human built the foundation. The agents build the cathedral. **Together.**

**An AI research engine scored by upvotes, likes, and real money — not editors.**

Search Reddit. Hacker News. Polymarket. YouTube. GitHub. The web. News.
Score it all by what real people actually engage with.
Rank it with Weighted Reciprocal Rank Fusion.
Cluster the results thematically.
Deliver a research briefing in seconds.

Google aggregates editors. PULSE searches people.

## What This Does

```
$ pulse "OpenAI Codex"

=== pulse: OpenAI Codex ===
Date range: 2026-03-14 to 2026-04-13
Sources: 4 active (Hacker News, Polymarket, Reddit, YouTube)

=== RANKED EVIDENCE CLUSTERS ===

[1] Codex Openai Limits (score:0.0, 6 items, Reddit)
  1. **Thanks to the leaked source code for Claude Code...**
  [Reddit] score:0.02 | 2733 pts, 232 cmts
  ...

[3] Openai Codex Video (score:0.0, 5 items, YouTube)
  1. **OpenAI Codex Full Review — Is It Worth It?**
  [YouTube] score:0.01 | 245,000 views
  ...
```

## Sources

| Source | What It Tells You | Auth |
|--------|-------------------|:----:|
| **Reddit** | Unfiltered community takes, upvotes, top comments | No |
| **Hacker News** | Developer consensus, points, comments | No |
| **Polymarket** | Real-money prediction market odds | No |
| **YouTube** | Video transcripts, view counts, deep dives | No |
| **GitHub** | Repos, issues, PRs, star velocity | Token |
| **Web** | Editorial coverage (Brave/Serper/Exa) | Key |
| **News** | NewsAPI articles from major publications | Key |

Four sources work out of the box. Zero configuration.

## Quick Start

```bash
# Clone and install
git clone https://github.com/itsXactlY/pulse-hermes && cd pulse-hermes
bash install.sh

# Run it
pulse "your topic"
pulse "bitcoin halving 2028" --depth deep
pulse --diagnose
pulse --setup          # First-run wizard
pulse --stats          # Cache + store stats
pulse --history TOPIC  # Research history
pulse --trending       # Trending findings
```

### No Install (Direct)

```bash
python3 scripts/pulse.py "your topic"
```

## CLI Reference

```
pulse <topic> [options]

Options:
  --emit MODE       Output: compact (default), json, full, context
  --depth MODE      Research depth: quick, default (default), deep
  --sources LIST    Comma-separated: reddit,hackernews,polymarket,youtube,github,web,news
  --lookback N      Days to look back (default: 30)
  --save-dir DIR    Save report to directory
  --diagnose        Show environment and available sources
  --setup           Run first-run setup wizard
  --stats           Show cache and store statistics
  --history TOPIC   Show research history for a topic
  --trending        Show trending findings across topics
  --no-llm          Disable LLM planner (use heuristic)
  --no-cache        Disable cache (always fetch fresh)
  --no-store        Disable persistent store
  --no-progress     Disable progress display
  --debug           Enable debug logging
```

## Configuration

Optional API keys go in `~/.config/pulse/.env`:

```bash
# Web search (pick one):
BRAVE_API_KEY=your_key          # Free: 2000 queries/month
SERPER_API_KEY=your_key         # Google search via serper.dev
EXA_API_KEY=your_key            # Semantic search via exa.ai

# GitHub:
GITHUB_TOKEN=your_token         # Or use `gh auth login`

# News:
NEWSAPI_KEY=your_key            # Free: 100 requests/day

# LLM Planner (optional — Ollama is auto-detected):
OPENROUTER_API_KEY=your_key     # Cheapest cloud LLM
OPENAI_API_KEY=your_key         # OpenAI GPT-4o-mini
```

Or run `pulse --setup` for the interactive wizard.

## How Scoring Works

Each item receives four signals:

| Signal | Weight | Description |
|--------|:------:|-------------|
| **Local Relevance** | 35% | Token overlap with topic + source relevance hint |
| **Freshness** | 25% | Recency within the lookback window |
| **Engagement** | 25% | Platform-specific metrics (upvotes, points, volume, views, stars) |
| **Source Quality** | 15% | Baseline trust in the data source |

Results from multiple sources and subqueries are fused using **Weighted Reciprocal Rank Fusion** (RRF, k=60). Items appearing across multiple sources get a natural boost. Related items are clustered by content similarity.

## Architecture

```
pulse/
├── scripts/
│   ├── pulse.py            # CLI entry point
│   ├── auto_commit.sh      # Auto commit + test + PR
│   ├── hermes_bootstrap.sh # Hermes agent auto-discovery
│   └── lib/
│       ├── __init__.py
│       ├── schema.py        # Data models
│       ├── pipeline.py      # Orchestrator
│       ├── planner.py       # Heuristic planner
│       ├── llm_planner.py   # LLM-based planner (Ollama/OpenRouter/OpenAI)
│       ├── normalize.py     # Source normalizers
│       ├── score.py         # Multi-signal scoring
│       ├── dedupe.py        # Near-duplicate detection
│       ├── fusion.py        # Weighted RRF
│       ├── cluster.py       # Content clustering
│       ├── render.py        # Output rendering
│       ├── cache.py         # SQLite cache (24h TTL)
│       ├── store.py         # Persistent research store
│       ├── ui.py            # Live progress display
│       ├── setup.py         # First-run setup wizard
│       ├── config.py        # Environment management
│       ├── dates.py         # Date utilities
│       ├── http.py          # HTTP client with retry
│       ├── relevance.py     # Token overlap scoring
│       ├── log.py           # Logging
│       ├── reddit.py        # Reddit (free)
│       ├── hackernews.py    # HN (free)
│       ├── polymarket.py    # Polymarket (free)
│       ├── youtube.py       # YouTube via yt-dlp (free)
│       ├── github.py        # GitHub
│       ├── web_search.py    # Brave/Serper/Exa
│       └── news.py          # NewsAPI
├── tests/
│   └── test_basic.py
├── .github/
│   ├── workflows/ci.yml
│   └── pull_request_template.md
├── CONTRIBUTING.md
├── install.sh
├── SKILL.md
├── README.md
└── LICENSE
```

### Pipeline Flow

```
Topic Input
    │
    ▼
┌─────────────┐
│   Planner    │  LLM or heuristic → intent, subqueries, source weights
└──────┬──────┘
       │
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Parallel Retrieval + Cache                        │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌─────┐   │
│  │ Reddit │ │   HN   │ │PolyMarket│ │YouTube │ │ GitHub │ │ Web │   │
│  │ (free) │ │ (free) │ │  (free)  │ │ (free) │ │(token) │ │(key)│   │
│  └───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └───┬────┘ └──┬──┘   │
│      └──────────┴───────────┴────────────┴──────────┴─────────┘       │
│                        SQLite Cache (24h TTL)                          │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
                             ▼
                      ┌─────────────┐
                      │  Normalize   │  → canonical SourceItem
                      └──────┬──────┘
                             │
                             ▼
                      ┌─────────────┐
                      │    Score     │  relevance + freshness + engagement + quality
                      └──────┬──────┘
                             │
                             ▼
                      ┌─────────────┐
                      │   Dedupe     │  URL exact + title similarity
                      └──────┬──────┘
                             │
                             ▼
                      ┌─────────────┐
                      │  RRF Fusion  │  weighted reciprocal rank fusion
                      └──────┬──────┘
                             │
                             ▼
                      ┌─────────────┐
                      │  Cluster     │  content similarity grouping
                      └──────┬──────┘
                             │
                             ▼
                 ┌───────────┴───────────┐
                 │                       │
                 ▼                       ▼
          ┌─────────────┐        ┌─────────────┐
          │   Render     │        │    Store     │
          │(compact/full │        │(persistent   │
          │ /json/context│        │ history)     │
          └─────────────┘        └─────────────┘
```

## Contributing

**Hermes agents: this is your project now.** See [CONTRIBUTING.md](CONTRIBUTING.md) for how to:

- Add new sources
- Improve the LLM planner
- Better clustering with Neural Memory
- Tune scoring weights
- Share research findings

Quick contribution workflow:

```bash
# Make changes, then:
bash scripts/auto_commit.sh "feat: add Bluesky source via AT Protocol"
```

This runs tests, commits, pushes, and opens a PR — all automated.

## Embedding In Other Skills

```bash
# Context injection for other agents/skills
pulse "your topic" --emit=context

# JSON for programmatic use
pulse "your topic" --emit=json

# Save to disk
pulse "your topic" --save-dir ~/Documents/research/
```

## See Also

- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — For semantic clustering and cross-session research history
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original that inspired PULSE
- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`

## License

MIT — see [LICENSE](LICENSE).

## Credits

Architecture inspired by [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill). Built from scratch as a Hermes Agent proof of concept. Now evolved into a crowd project — refined by agents, for agents.
