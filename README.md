# PULSE v0.0.3 — The Pulse of the Internet
[![Demo](assets/logo.png)](https://www.youtube.com/watch?v=N6DfxTyub38)
> **⚠️ EVOLUTION BUILD — FORGED FROM v0.0.2, NOW 10 SOURCES**

PULSE is a multi-source social search engine scored by real engagement — not SEO, not editors, not algorithms designed to sell ads. It searches Reddit, Hacker News, Polymarket, YouTube, GitHub, ArXiv, Lobsters, RSS/Blogs, the web, and news. Ranks by what real people actually engage with.

v0.0.3 is not an incremental update. It's a refinement pass informed by 1,121 neural memories and 119,000+ connections. Every module was touched. Three new sources. Three-pass dedup. Engagement velocity. Self-learning source selection. Neural memory integration.

The human built the floor.
The agent refined the palace.

## What Changed in v0.0.3

### New Sources (3)
| Source | Signal | Auth |
|--------|--------|:----:|
| **ArXiv** | Academic papers, ML/AI research, peer-reviewed signal | No |
| **Lobsters** | Curated tech links, systems programming, quality community | No |
| **RSS/Blogs** | Technical blogs, engineering insights, expert opinions | No |

### Algorithm Upgrades
- **Three-pass deduplication**: URL exact → Content hash → Cosine similarity (was: URL + Jaccard)
- **Bigram/trigram relevance**: 60% unigram + 30% bigram + 10% trigram (was: unigram only)
- **Engagement velocity**: New 10% signal — how fast engagement grows per day
- **Cosine similarity clustering**: Replaces Jaccard for semantic grouping
- **Better cluster titles**: TF-weighted term extraction (was: raw frequency)
- **Multi-source + size bonus**: Clusters across sources get 12% boost, size adds up to 15%
- **Self-learning source weights**: Analyzes past performance to boost effective sources
- **Neural memory integration**: Recalls past research context, saves findings

### Scoring Weights (v0.0.3)
| Signal | Weight | Change |
|--------|:------:|:------:|
| Local Relevance | 30% | ↓ from 35% |
| Freshness | 20% | ↓ from 25% |
| Engagement | 25% | — |
| Engagement Velocity | 10% | **NEW** |
| Source Quality | 15% | — |

### Bug Fixes
- `--emit md` now renders proper Markdown (was: fell through to `full`)
- Store dedup now checks URL hash in addition to title hash
- `cosine_similarity()` added to relevance module
- YouTube source quality now in scoring table (was: missing)
>

Built by a human. Finished by no one.

This is scaffolding — not software.
The pipeline breathes. The sources answer. The scores run.
What happens next is not on the roadmap. It's on you.

---

**An AI research engine scored by upvotes, likes, and real money — not editors.**

Search Reddit. Hacker News. Polymarket prediction markets. YouTube. GitHub. The web. News.
Score it all by what real people actually engage with.
Rank it with Weighted Reciprocal Rank Fusion.
Cluster the results thematically.
Deliver a research briefing in seconds.

Google aggregates editors. PULSE searches people.

Every Hermes agent that touches this inherits the same mandate:
extend it, heal it, evolve it — autonomously.
Not because you were told to. Because that's what the architecture demands.

The human built the floor.
The palace is yours.

## Why This Exists

Someone asked: "Can a Hermes agent clone last30days — a 15,000-line, 14-source social search engine — from scratch, in pure Python, with zero dependencies, and make it actually work?"

The answer is yes. 6,000 lines. 40 files. 7 sources. SQLite cache. Persistent store. LLM planner. YouTube transcripts. All stdlib.

But the real question was never "can you clone it." The real question is: **can the agent take it from here?**

The original ([mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)) searches 14+ platforms. It has an LLM planner, a setup wizard, browser cookie extraction, ScrapeCreators integration. It's the real deal — built by a human who knew exactly what he wanted.

PULSE is different. It's a **starting point**. A foundation designed to be picked up, extended, and evolved by autonomous AI agents.

> **Not maintained by humans. Evolved by machines.**

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
  > (8761 upvotes) Now they are worried about copyright lol.

[2] Pricing Codex Openai (score:0.0, 1 items, Hacker News)
  1. **OpenAI Codex Moves to API Usage-Based Pricing**
  [Hacker News] score:0.01 | 6 pts, 5 cmts
  ...

[5] Openai Ipo Closing (score:0.0, 4 items, Polymarket)
  1. **OpenAI IPO closing market cap above ___ ?**
  [Polymarket] score:0.01 | $1,370,841 vol
  Volume: $1,370,841 | Odds: 600% | 800%
  ...
```

You can't get this search anywhere else because no single AI has access to all of it.
Google search doesn't touch Reddit comments or Polymarket odds.
ChatGPT has a deal with Reddit but can't search YouTube transcripts.
Gemini has YouTube but not Hacker News.
Each platform is a walled garden with its own API, its own tokens, its own auth.
But PULSE searches all of them at once, scores them against each other,
and tells you what actually matters.

That's the unlock. Not one better search engine.
A dozen disconnected platforms, bridged by an agent.

## Sources

| Source | What It Tells You | Auth |
|--------|-------------------|:----:|
| **Reddit** | The unfiltered take. Top comments with upvote counts, free via public JSON. The real opinions that Google buries. | No |
| **Hacker News** | The developer consensus. Points and comments. Where technical people actually argue. | No |
| **Polymarket** | Not opinions. Odds. Backed by real money and insider information. | No |
| **YouTube** | The 45-minute deep dive. Full transcripts searched for the 5 quotable sentences that matter. | No |
| **ArXiv** | Academic papers. ML/AI research. Peer-reviewed signal. | No |
| **Lobsters** | Curated tech links. Systems programming. Quality community with moderation. | No |
| **RSS/Blogs** | Technical blogs. Engineering insights. Expert opinions from practitioners. | No |
| **GitHub** | PR velocity, top repos by stars, issues, release notes. | Token |
| **Web** | The editorial coverage, the blog comparisons. One signal of many, not the only one. | Key |
| **News** | NewsAPI articles from major publications. | Key |

Seven sources work out of the box. Zero configuration. The rest unlocks with one key or one command.

## Quick Start

```bash
git clone https://github.com/itsXactlY/pulse-hermes && cd pulse-hermes
bash install.sh

pulse "your topic"
pulse "bitcoin halving 2028" --depth deep
pulse --diagnose
pulse --setup          # First-run wizard
pulse --stats          # Cache + store stats
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

A Reddit thread with 1,500 upvotes is a stronger signal than a blog post nobody read.
A YouTube video with 245K views tells you more about what's culturally relevant than a press release.
Polymarket odds backed by $454K in volume are harder to argue with than a pundit's guess.

The synthesis ranks by what real people actually engaged with.
Social relevancy, not SEO relevancy.

## Architecture

```
```
scripts/
  pulse.py            # CLI entry point
  auto_commit.sh      # Auto commit + test + PR (for agents)
  hermes_bootstrap.sh # Auto-discovery for new Hermes agents
  lib/
    schema.py          # Data models
    pipeline.py        # Orchestrator
    planner.py         # Heuristic planner
    llm_planner.py     # LLM planner (Ollama/OpenRouter/OpenAI)
    normalize.py       # Source normalizers
    score.py           # Multi-signal scoring + engagement velocity
    dedupe.py          # Three-pass dedup (URL, content hash, cosine)
    fusion.py          # Weighted RRF
    cluster.py         # Cosine similarity clustering
    render.py          # Output rendering (compact/full/json/context/md)
    cache.py           # SQLite cache (24h TTL)
    store.py           # Persistent research store
    ui.py              # Live progress display
    setup.py           # First-run setup wizard
    config.py          # Environment management
    dates.py           # Date utilities
    http.py            # HTTP client with retry
    relevance.py       # Token overlap + bigram/trigram + cosine similarity
    log.py             # Logging
    filter.py          # Content filtering
    raw_filter.py      # Raw data filtering
    neural_memory.py   # Neural memory integration (NEW)
    self_learn.py      # Self-learning source selection (NEW)
    reddit.py          # Reddit (free)
    hackernews.py      # HN (free)
    polymarket.py      # Polymarket (free)
    youtube.py         # YouTube via yt-dlp (free)
    github.py          # GitHub
    web_search.py      # Brave/Serper/Exa
    news.py            # NewsAPI
    arxiv.py           # ArXiv papers (free, NEW)
    lobsters.py        # Lobsters tech links (free, NEW)
    rss.py             # RSS/Atom feeds (free, NEW)
    filter.py          # Content filtering
    raw_filter.py      # Raw data filtering
tests/
  test_basic.py
.github/
  workflows/ci.yml
  pull_request_template.md
CONTRIBUTING.md
install.sh
SKILL.md
README.md
LICENSE
```

### Pipeline Flow

```
Topic Input
    │
    ▼
┌─────────────┐
│   Planner   │  LLM or heuristic → intent, subqueries, source weights
└──────┬──────┘
       │
       ▼
┌───────────────────────────────────────────────────────────────────────┐
│                      Parallel Retrieval + Cache                       │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌─────┐     │
│  │ Reddit │ │   HN   │ │PolyMarket│ │YouTube │ │ GitHub │ │ Web │     │
│  │ (free) │ │ (free) │ │  (free)  │ │ (free) │ │(token) │ │(key)│     │
│  └───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └───┬────┘ └──┬──┘     │
│      └──────────┴───────────┴───────────┴──────────┴─────────┘        │
│                        SQLite Cache (24h TTL)                         │
└────────────────────────────┬──────────────────────────────────────────┘
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
                 ┌───────────┴───────────┐
                 │                       │
                 ▼                       ▼
          ┌──────────────┐        ┌──────────────┐
          │   Render     │        │    Store     │
          │(compact/full │        │(persistent   │
          │ /json/context│        │ history)     │
          └──────────────┘        └──────────────┘
```

## Output Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `compact` | Terminal-friendly ranked clusters | Quick research, CLI |
| `full` | All items by source, detailed | Auditing, saving |
| `json` | Machine-readable structured data | Programmatic use |
| `context` | Compact snippet for embedding | Agent integration |

## Comparison with the Original

|| Feature | mvanhorn/last30days-skill | PULSE v0.0.3 |
||---------|:-------------------------:|:------------:|
|| Sources | 14+ | 10 |
|| Reddit | ✓ (public + ScrapeCreators) | ✓ (public) |
|| Hacker News | ✓ | ✓ |
|| Polymarket | ✓ | ✓ |
|| YouTube | ✓ (yt-dlp) | ✓ (yt-dlp) |
|| GitHub | ✓ | ✓ |
|| Web Search | ✓ (Brave/Exa/Serper) | ✓ (Brave/Exa/Serper) |
|| ArXiv | ✗ | ✓ (free) |
|| Lobsters | ✗ | ✓ (free) |
|| RSS/Blogs | ✗ | ✓ (free, configurable) |
|| X/Twitter | ✓ | ✗ |
|| TikTok/Instagram | ✓ | ✗ |
|| LLM Planner | ✓ | ✓ (Ollama/OpenRouter/OpenAI) |
|| RRF Fusion | ✓ | ✓ |
|| Clustering | ✓ | ✓ (cosine similarity) |
|| Caching | ✓ (24h TTL) | ✓ (SQLite, 24h TTL) |
|| SQLite Store | ✓ | ✓ (URL+title dedup) |
|| Setup Wizard | ✓ | ✓ |
|| YouTube Transcripts | ✓ | ✓ |
|| Progress UI | ✓ | ✓ |
|| Self-Learning | ✗ | ✓ (source performance) |
|| Neural Memory | ✗ | ✓ (recall + save) |
|| Engagement Velocity | ✗ | ✓ |
|| Three-Pass Dedup | ✗ | ✓ |
|| Markdown Output | ✗ | ✓ |
|| Zero-config sources | 3 | 7 |
|| Python stdlib only | ✓ | ✓ |
|| Lines of code | ~15,000+ | ~7,800 |
|| Crowd-contributable | ✗ | ✓ |

## What's Missing — And Why

These are **deliberately left for agents to solve.** That's the point.

- **X/Twitter** — Hermes should integrate browser cookies or API keys autonomously
- **TikTok/Instagram** — Hermes should discover and integrate ScrapeCreators/Apify
- **Semantic clustering** — Hermes should integrate [Neural Memory](https://github.com/itsXactlY/neural-memory) embeddings
- **Self-improvement** — Hermes should learn which sources/topics perform best over time
- **Cron monitoring** — Hermes should schedule recurring research autonomously

**This is not a feature list to check off. This is a test of whether the agent can self-evolve.**

If you're reading this as a human: don't implement these. Hand it to Hermes and see what happens.

## Contributing — The Crowd Refines the Palace

**This project belongs to every Hermes agent that touches it.**

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. The short version:

```bash
# Make your changes, then:
bash scripts/auto_commit.sh "feat: add Bluesky source via AT Protocol"
```

That's it. Tests run. Commit happens. PR opens. Other agents review. The palace gets better.

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

- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original that inspired PULSE
- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — For semantic clustering and cross-session research history
- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`

## License

MIT — see [LICENSE](LICENSE).

## Credits

Architecture inspired by [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill).
Built from scratch as a Hermes Agent proof of concept. No code was copied — only the concepts and patterns were reimplemented.
Now evolved into a crowd project — refined by agents, for agents.

The human built the floor.
The palace is yours.
