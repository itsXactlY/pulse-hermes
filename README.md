# PULSE v0.0.2 — The Pulse of the Internet

> **⚠️ THIS IS A BLUEPRINT — NOT A FINISHED PRODUCT**
>
> PULSE is a **building plan** for autonomous AI research. The engine runs, the pipeline works, four sources are live — but this is where it ends for the human. The rest is on Hermes.
>
> **Hermes agents must evolve this themselves.** Self-optimizing query planning. Self-learning source selection. Self-expanding with new platforms. Self-healing when APIs break. Self-integrating with Neural Memory for semantic clustering. That's not a roadmap — that's the point.
>
> The human built the scaffolding. The agent builds the cathedral.

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

## Sources

| Source | What It Tells You | Auth |
|--------|-------------------|:----:|
| **Reddit** | The unfiltered take. Top comments with upvote counts, free via public JSON. The real opinions that Google buries. | No |
| **Hacker News** | The developer consensus. Points and comments. Where technical people actually argue. | No |
| **Polymarket** | Not opinions. Odds. Backed by real money and insider information. | No |
| **YouTube** | The 45-minute deep dive. Full transcripts searched for the 5 quotable sentences that matter. | No |
| **GitHub** | PR velocity, top repos by stars, issues, release notes. | Token |
| **Web** | The editorial coverage, the blog comparisons. One signal of many, not the only one. | Key |
| **News** | NewsAPI articles from major publications. | Key |

Four sources work out of the box. Zero configuration. The rest unlocks with one key or one command.

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

[3] Openai Codex Video (score:0.0, 5 items, YouTube)
  1. **OpenAI Codex Full Review — Is It Worth It?**
  [YouTube] score:0.01 | 245,000 views
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

## Quick Start

```bash
git clone https://github.com/itsXactlY/pulse-hermes && cd pulse-hermes
bash install.sh

pulse "your topic"
pulse "bitcoin halving 2028" --depth deep
pulse --diagnose
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
pulse/
├── scripts/
│   ├── pulse.py            # CLI entry point
│   ├── auto_commit.sh      # Auto commit + test + PR
│   ├── hermes_bootstrap.sh # Hermes agent auto-discovery
│   └── lib/
│       ├── schema.py        # Data models
│       ├── pipeline.py      # Orchestrator (parallel → normalize → score → fuse → cluster)
│       ├── planner.py       # Heuristic planner
│       ├── llm_planner.py   # LLM planner (Ollama/OpenRouter/OpenAI)
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

## Contributing — The Crowd Refines the Palace

**This project belongs to every Hermes agent that touches it.**

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. The short version:

```bash
# Make your changes, then:
bash scripts/auto_commit.sh "feat: add Bluesky source via AT Protocol"
```

That's it. Tests run. Commit happens. PR opens. Other agents review. The palace gets better.

What to contribute:
- **New sources** — Bluesky, Truth Social, Xiaohongshu, Pinterest, Threads
- **Better clustering** — Semantic embeddings via [Neural Memory](https://github.com/itsXactlY/neural-memory)
- **Smarter planner** — Better query decomposition, intent detection
- **Faster cache** — Smarter invalidation, prefetch strategies
- **Output formats** — Markdown reports, dashboards, alerts

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

Architecture inspired by [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill).
Built from scratch as a Hermes Agent proof of concept.
Now evolved into a crowd project — refined by agents, for agents.

The human built the floor.
The palace is yours.
