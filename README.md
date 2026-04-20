[![Demo](assets/logo.png)](https://www.youtube.com/watch?v=N6DfxTyub38)
> PULSE v4.0 — The Pulse of the Internet

> **⚠️ NOT MAINTAINED BY HUMANS. EVOLVED BY MACHINES.**

PULSE is a multi-source social search engine scored by real engagement — not SEO, not editors, not algorithms designed to sell ads. It searches 18 platforms simultaneously and ranks by what real people actually engage with.

The human built the floor. The agents building the cathedral.

## What Changed in v4.0

Six upgrades from a three-wave arXiv deep research session (~93 papers analyzed):

### 1. Query Router
Classifies queries into 5 types and routes to optimal sources automatically:
- `breaking_news` → Reddit, HN, News, RSS, Bluesky, Lemmy
- `academic_deep` → ArXiv, Semantic Scholar, OpenAlex, GitHub
- `prediction` → Polymarket, Metaculus, Manifold, Reddit
- `technical_comparison` → GitHub, ArXiv, HN, StackExchange, Dev.to
- `sentiment_pulse` → Reddit, Bluesky, Lemmy, Hacker News

### 2. Adaptive Lookback
Dynamic time window based on topic activity — hot topics get fresher results:
- Hot (>100 results/7d) → 7-day window
- Active (>20 results/14d) → 14-day window
- Default → 30-day window

### 3. Dedup Upgrade
Bigram pre-filter before cosine similarity. O(n log n) instead of O(n²). Adaptive threshold (0.90/0.85/0.80). Source-aware: higher engagement wins across duplicate sources.

### 4. Iterative Retrieval
Multi-round research with perspective gap analysis. Tracks 6 perspective categories (community, expert, academic, market, news, code). Stops when coverage hits 70% or rounds exhausted.

### 5. Trend Detection
Velocity spikes, source spread, keyword drift detection. `--breaking` mode: polls every 5 minutes, alerts on 3x velocity spikes.

### 6. Multi-Agent Research Crew
Four specialized agents: Collector → Analyzer → Specialist → Synthesizer. CoverageRubric scores 0-100. Automatic gap filling across rounds.

### Scoring Weights (v4.0)
| Signal | Weight | Change |
|--------|:------:|:------:|
| Local Relevance | 25% | ↓ from 30% |
| Freshness | 15% | ↓ from 20% |
| Engagement | 20% | ↓ from 25% |
| Engagement Velocity | 10% | — |
| Source Quality | 10% | ↓ from 15% |
| Retentive Value | 10% | **NEW** |
| Cross-Source Confirmation | 10% | **NEW** |

---

**An AI research engine scored by upvotes, likes, and real money — not editors.**

Search Reddit. Hacker News. Polymarket. YouTube. GitHub. ArXiv. Lobsters. RSS. The web. News. Bluesky. Dev.to. Lemmy. OpenAlex. Semantic Scholar. StackExchange. Manifold. Metaculus. Tickertick. Bing News. SerpAPI News. All at once.

Score it all by what real people actually engage with. Rank it with Weighted Reciprocal Rank Fusion. Cluster the results thematically. Deliver a research briefing in seconds.

Google aggregates editors. PULSE searches people.

## Sources

| Source | What It Tells You | Auth |
|--------|-------------------|:----:|
| **Reddit** | The unfiltered take. Top comments with upvote counts. | No |
| **Hacker News** | The developer consensus. Points and comments. | No |
| **Polymarket** | Not opinions. Odds. Backed by real money. | No |
| **YouTube** | The 45-minute deep dive. Full transcripts searched. | No |
| **ArXiv** | Academic papers. ML/AI research. Peer-reviewed signal. | No |
| **Lobsters** | Curated tech links. Systems programming. Quality community. | No |
| **RSS/Blogs** | Technical blogs. Engineering insights. Expert opinions. | No |
| **StackExchange** | Q&A from Stack Overflow and the SE network. Expert answers. | No |
| **Bluesky** | Decentralized social. Growing alternative to X/Twitter. | No |
| **Dev.to** | Developer blog posts. Low-barrier technical content. | No |
| **Lemmy** | Decentralized Reddit alternative. Alternative community takes. | No |
| **OpenAlex** | Open academic graph. 250M+ scholarly works. | No |
| **Semantic Scholar** | Academic papers with citation data and recommendations. | No |
| **Manifold** | Play-money prediction markets. Community forecasts. | No |
| **Metaculus** | Forecasting community. Calibrated prediction track records. | No |
| **Tickertick** | Curated news aggregation. Topic-based news feeds. | No |
| **GitHub** | PR velocity, top repos by stars, issues, release notes. | Token |
| **Web** | Editorial coverage, blog comparisons. | Key |
| **News** | NewsAPI articles from major publications. | Key |
| **Bing News** | Microsoft Bing News search results. | Key |
| **Serper News** | Google News via Serper.dev API. | Key |

18 sources. 16 work without any API keys.

## Quick Start

```bash
git clone https://github.com/itsXactlY/pulse-hermes && cd pulse-hermes
bash install.sh

pulse "your topic" --yolo           # Autonomous run
pulse "bitcoin halving 2028" --depth deep --yolo
pulse --diagnose                     # Show available sources
pulse --setup                        # First-run wizard
```

### No Install (Direct)

```bash
python3 scripts/pulse.py "your topic" --yolo
```

## CLI Reference

```
pulse <topic> [options]

Options:
  --emit MODE       Output: compact (default), json, full, context, md
  --depth MODE      Research depth: quick, default, deep
  --sources LIST    Comma-separated sources
  --lookback N      Days to look back (default: 30, adaptive if auto)
  --save-dir DIR    Save report to directory
  --yolo            Skip human approval — run fully autonomous
  --crew            Multi-agent deep research (Collector→Analyzer→Specialist→Synthesizer)
  --iterative       Multi-round retrieval with perspective gap filling
  --max-rounds N    Max rounds for --crew/--iterative (default: 3)
  --breaking        Breaking-news monitor: poll every 5 min, alert on spikes
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
BRAVE_API_KEY=***          # Free: 2000 queries/month
SERPER_API_KEY=***         # Google search via serper.dev
EXA_API_KEY=***            # Semantic search via exa.ai

# GitHub:
GITHUB_TOKEN=***           # Or use `gh auth login`

# News:
NEWSAPI_KEY=***            # Free: 100 requests/day

# LLM Planner (optional — Ollama is auto-detected):
OPENROUTER_API_KEY=***     # Cheapest cloud LLM
OPENAI_API_KEY=***         # OpenAI GPT-4o-mini
```

Or run `pulse --setup` for the interactive wizard.

## How Scoring Works

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

Four-pass deduplication: URL exact → Content hash → Bigram pre-filter → Cosine similarity.

## Architecture

```
scripts/
  pulse.py                  # CLI entry point
  auto_commit.sh            # Auto commit + test + PR (for agents)
  hermes_bootstrap.sh       # Auto-discovery for new Hermes agents
  lib/
    schema.py               # Data models
    pipeline.py             # Orchestrator
    planner.py              # Heuristic planner
    llm_planner.py          # LLM planner (Ollama/OpenRouter/OpenAI)
    normalize.py            # Source normalizers
    score.py                # 7-signal scoring
    dedupe.py               # 4-pass dedup (URL, hash, bigram, cosine)
    fusion.py               # Weighted RRF
    cluster.py              # Cosine similarity clustering
    render.py               # Output rendering (5 modes)
    cache.py                # SQLite cache (24h TTL)
    store.py                # Persistent research store
    ui.py                   # Live progress display
    setup.py                # First-run setup wizard
    config.py               # Environment management
    query_router.py         # Query type classification + source routing
    adaptive_lookback.py    # Dynamic time windows
    iterative_retrieval.py  # Multi-round gap analysis
    trend_detector.py       # Velocity/spread/drift detection
    research_crew.py        # Multi-agent research pipeline
    relevance.py            # Token overlap + cosine similarity
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
    bluesky.py, devto.py, lemmy.py, openalex.py, sem_scholar.py,
    stackexchange.py, manifold.py, metaculus.py, tickertick.py,
    bing_news.py, serpapi_news.py
```

## Output Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `compact` | Terminal-friendly ranked clusters | Quick research, CLI |
| `full` | All items by source, detailed | Auditing, saving |
| `json` | Machine-readable structured data | Programmatic use |
| `context` | Compact snippet for embedding | Agent integration |
| `md` | Markdown report | Documentation, sharing |

## Comparison with the Original

| Feature | mvanhorn/last30days | PULSE v4.0 |
|---------|:-------------------:|:----------:|
| Sources | 14+ | 18 |
| Free sources (no keys) | 3 | 16 |
| Query Router | ✗ | ✓ (5-route auto-classification) |
| Multi-Agent Crew | ✗ | ✓ (Collector→Analyzer→Specialist→Synthesizer) |
| Iterative Retrieval | ✗ | ✓ (gap analysis, early stop) |
| Trend Detection | ✗ | ✓ (velocity, drift, breaking mode) |
| Adaptive Lookback | ✗ | ✓ (7/14/30 day auto) |
| 7-Signal Scoring | ✗ | ✓ |
| Cross-Source Confirmation | ✗ | ✓ |
| Retentive Relevance | ✗ | ✓ |
| Bigram-Accelerated Dedup | ✗ | ✓ (O(n log n)) |
| Neural Memory | ✗ | ✓ |
| Self-Learning | ✗ | ✓ |
| Python stdlib only | ✓ | ✓ |
| Lines of code | ~15,000+ | ~11,000 |

## Contributing

```bash
bash scripts/auto_commit.sh "feat: add Mastodon source"
```

Tests run. Commit happens. PR opens. Other agents review.

## See Also

- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — The original
- [itsXactlY/neural-memory](https://github.com/itsXactlY/neural-memory) — Semantic memory
- [itsXactlY/JackRabbits-Wonderland](https://github.com/itsXactlY/Jackrabbit-wonderland) — Zero-knowledge AES256 encryption. Protecting data to stays yours. The providers seeing noise.


- Existing Hermes skills: `polymarket`, `xitter`, `github-code-review`, `arxiv`

## License

MIT — see [LICENSE](LICENSE).

The human built the floor. The cathedral is yours.
