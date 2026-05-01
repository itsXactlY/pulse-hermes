"""Single source-of-truth for every source PULSE can fetch from.

WHY THIS EXISTS
---------------
Before this module, three files had to agree on every source:

  * ``query_router.TYPE_SOURCES``  — name strings per query type
  * ``pipeline.SOURCE_MAP``        — name → module
  * ``pipeline._retrieve_stream``  — 110-line if/elif chain calling
                                      module.search() with per-source
                                      kwargs

Adding a source meant editing all three; rename a source name in one
file but not the others and the dispatcher silently fell into the
"Unknown source" branch (returned [] without erroring). This is exactly
how Twitter/X stayed broken for three days after the Camoufox reader
landed.

THE CONTRACT
------------
- ``SOURCE_REGISTRY`` is the canonical list. Every dispatchable source
  appears here exactly once with its module reference and a thin
  ``fetch`` adapter that normalises the call.
- ``dispatch(source, ...)`` is the only function the pipeline needs.
- ``validate_source_names(names)`` raises if anything in
  ``TYPE_SOURCES`` doesn't have a registry entry. Run on import so
  typos surface at startup, not as silent zero-result queries.

Adding a source: add ONE entry below. Done.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple, Any

from . import (
    arxiv         as _arxiv,
    bing_news     as _bing_news,
    bluesky       as _bluesky,
    devto         as _devto,
    github        as _github,
    hackernews    as _hackernews,
    lemmy         as _lemmy,
    lobsters      as _lobsters,
    manifold      as _manifold,
    metaculus     as _metaculus,
    news          as _news,
    openalex      as _openalex,
    polymarket    as _polymarket,
    reddit        as _reddit,
    rss           as _rss,
    sem_scholar   as _sem_scholar,
    serpapi_news  as _serpapi_news,
    stackexchange as _stackexchange,
    tickertick    as _tickertick,
    twitter_browser as _twitter,
    web_search    as _web,
    youtube       as _youtube,
)


@dataclass(frozen=True)
class SourceSpec:
    """Everything needed to call a source's .search() and reason about it.

    Fields:
        name:           Canonical id used by query_router + dispatcher.
        module:         The python module that owns ``search``.
        fetch:          Adapter ``(query, from_date, to_date, depth, config) -> list``.
                        Each spec packs the per-source signature quirks here so
                        the dispatcher stays signature-blind.
        api_key_env:    Config key the source needs (e.g. "NEWSAPI_KEY").
                        ``None`` if no key required. The dispatcher returns
                        ``[]`` early when an API-keyed source has no key AND
                        ``no_api_fallback`` is False.
        no_api_fallback:
                        True when the source can produce results without any
                        API key (public scrape, RSS, headless-browser, etc.).
                        News + serpapi_news are currently False — Phase C
                        target.
        notes:          Free-text reminder for humans browsing the registry.
    """

    name: str
    module: Any
    fetch: Callable[[str, str, str, str, Dict[str, Any]], List[Dict[str, Any]]]
    api_key_env: Optional[str] = None
    no_api_fallback: bool = True
    notes: str = ""


# ── Adapter helpers ──────────────────────────────────────────────────────
# Each takes the canonical 5-tuple (query, from_date, to_date, depth, config)
# and reshapes it for that one source's actual signature.

def _std(mod):
    """Standard 4-arg signature: (topic, from_date, to_date, depth=...)."""
    return lambda q, fd, td, dp, cfg: mod.search(q, fd, td, depth=dp)


def _no_dates(mod, query_kw="topic"):
    """Source that ignores date range."""
    if query_kw == "query":
        return lambda q, fd, td, dp, cfg: mod.search(q, depth=dp)
    return lambda q, fd, td, dp, cfg: mod.search(q, depth=dp)


def _needs_config(mod):
    """Source that wants the whole config dict (e.g. picks its own keys out)."""
    return lambda q, fd, td, dp, cfg: mod.search(q, cfg, fd, td, depth=dp)


def _web_call(mod):
    """web_search has its own shape: (topic, config, depth)."""
    return lambda q, fd, td, dp, cfg: mod.search(q, cfg, depth=dp)


def _api_key(mod, key_env):
    """API-keyed source. Returns [] when key absent (until no-api fallback lands)."""
    def _call(q, fd, td, dp, cfg):
        key = cfg.get(key_env)
        if not key:
            return []
        return mod.search(q, key, fd, td, depth=dp)
    return _call


def _github_call(mod):
    """github accepts an optional token kwarg from config."""
    return lambda q, fd, td, dp, cfg: mod.search(
        q, fd, td, depth=dp, token=cfg.get("GITHUB_TOKEN")
    )


# ── The registry ─────────────────────────────────────────────────────────
# One entry per dispatchable source. Anything in
# query_router.TYPE_SOURCES MUST appear here, or validate_source_names()
# blows up on import.

SOURCE_REGISTRY: Dict[str, SourceSpec] = {
    # Standard (topic, from_date, to_date, depth) sources — public APIs / RSS.
    "arxiv":        SourceSpec("arxiv",        _arxiv,        _std(_arxiv)),
    "bluesky":      SourceSpec("bluesky",      _bluesky,      _std(_bluesky)),
    "devto":        SourceSpec("devto",        _devto,        _std(_devto)),
    "hackernews":   SourceSpec("hackernews",   _hackernews,   _std(_hackernews)),
    "lemmy":        SourceSpec("lemmy",        _lemmy,        _std(_lemmy)),
    "lobsters":     SourceSpec("lobsters",     _lobsters,     _std(_lobsters)),
    "manifold":     SourceSpec("manifold",     _manifold,     _std(_manifold)),
    "metaculus":    SourceSpec("metaculus",    _metaculus,    _std(_metaculus)),
    "openalex":     SourceSpec("openalex",     _openalex,     _std(_openalex)),
    "rss":          SourceSpec("rss",          _rss,          _std(_rss)),
    "sem_scholar":  SourceSpec("sem_scholar",  _sem_scholar,  _std(_sem_scholar)),
    "stackexchange":SourceSpec("stackexchange",_stackexchange,_std(_stackexchange)),
    "tickertick":   SourceSpec("tickertick",   _tickertick,   _std(_tickertick)),

    # Twitter/X via Camoufox — public scrape, no API key.
    "twitter_browser": SourceSpec(
        "twitter_browser", _twitter, _std(_twitter),
        notes="Camoufox headless browser; falls back to syndication.twitter.com",
    ),

    # No-dates sources.
    "polymarket": SourceSpec("polymarket", _polymarket, _no_dates(_polymarket)),
    "reddit":     SourceSpec("reddit",     _reddit,     _no_dates(_reddit, query_kw="query")),
    "youtube":    SourceSpec("youtube",    _youtube,    _no_dates(_youtube),
                             notes="yt-dlp under the hood; no API key needed"),

    # Sources that want the full config dict (their own internal key picking).
    "bing_news": SourceSpec(
        "bing_news", _bing_news, _needs_config(_bing_news),
        notes="RSS-backed; works without API",
    ),
    "web": SourceSpec(
        "web", _web, _web_call(_web),
        notes="web_search wrapper — depends on configured web-search backend",
    ),

    # Optional-token github (works without).
    "github": SourceSpec(
        "github", _github, _github_call(_github),
        notes="Token optional; rate-limit much higher with one",
    ),

    # API-keyed sources WITHOUT no-api fallback. Phase C should add fallbacks.
    "news": SourceSpec(
        "news", _news, _api_key(_news, "NEWSAPI_KEY"),
        api_key_env="NEWSAPI_KEY", no_api_fallback=False,
        notes="NewsAPI.org — Phase C target: add RSS aggregator fallback",
    ),
    "serpapi_news": SourceSpec(
        "serpapi_news", _serpapi_news, _api_key(_serpapi_news, "SERPAPI_KEY"),
        api_key_env="SERPAPI_KEY", no_api_fallback=False,
        notes="SerpAPI — Phase C target: add direct google news scrape fallback",
    ),
}


# ── Public API ───────────────────────────────────────────────────────────

def dispatch(
    source: str,
    query: str,
    from_date: str,
    to_date: str,
    depth: str,
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Look up the source spec and call its fetch adapter.

    Raises KeyError on unknown source — callers are expected to have
    validated names against the registry already (see
    ``validate_source_names``). This is intentionally NOT a silent
    skip, because that's exactly the bug we're fixing.
    """
    spec = SOURCE_REGISTRY[source]
    return spec.fetch(query, from_date, to_date, depth, config)


def validate_source_names(names: Iterable[str]) -> None:
    """Raise ValueError if any name isn't in the registry.

    Call this once at import time over query_router.TYPE_SOURCES so
    misconfigured names surface as a startup error, not as silent
    zero-result fetches.
    """
    unknown = sorted({n for n in names if n not in SOURCE_REGISTRY})
    if unknown:
        raise ValueError(
            f"Source names not in SOURCE_REGISTRY: {unknown}. "
            f"Add an entry in source_registry.py or fix the typo."
        )


def known_source_names() -> List[str]:
    """Sorted list — useful for introspection / health checks."""
    return sorted(SOURCE_REGISTRY.keys())


def sources_needing_api_key() -> List[Tuple[str, str]]:
    """Pairs of (source, env_var) for ops/health-check warnings."""
    return [
        (s.name, s.api_key_env)
        for s in SOURCE_REGISTRY.values()
        if s.api_key_env and not s.no_api_fallback
    ]
