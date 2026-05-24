"""worm — recursive crawler that turns a flat pulse Report into a
multi-round dig.

INPUT: a Report produced by `pipeline.run(depth='default')` (the seed).
OUTPUT: new Candidates (the seed PLUS every deeper finding the worm
followed across N rounds) — caller appends them to its bundle.

ALGORITHM (one round):

    1. Collect URLs from every existing Candidate's body / snippet /
       source-item bodies.
    2. Filter to followable (not images/trackers), drop already-seen,
       drop self-links to the parent's own URL.
    3. Rank by url_extract.rank_for_follow (context length + parent
       engagement × 0.1 + dig_value score).
    4. Take top-K (max_per_round, default 50) and fan out parallel
       sub-fetches via ThreadPoolExecutor.
    5. Each sub-fetch returns title + description + first-2000-chars
       plaintext (or None on 403/429/timeout — recorded as a dig_value
       miss for that source bucket).
    6. Build a new Candidate per successful fetch (synthetic source =
       'worm:<round>:<source_type>'), inherit a fraction of parent
       engagement, attach lineage metadata.
    7. Add to bundle. Loop with the new candidates as the new frontier.

CAPS:
    - max_fetches      hard ceiling across all rounds (default 500)
    - max_rounds       depth cap (default 3)
    - max_per_round    breadth cap per round (default 50)
    - concurrency      simultaneous fetches (default 8)

Phase 1 limitations (addressed in phase 2):
    - Single fetch path per URL; no bypass chain
    - No per-host rate limiting beyond global concurrency
    - No corroboration boost (URL seen on N sources)
    - Lineage lives in Candidate.metadata only, not yet in SQLite
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from html import unescape
from typing import Optional

logger = logging.getLogger(__name__)


DEFAULTS = {
    "max_rounds":         int(os.environ.get("PULSE_WORM_MAX_ROUNDS", "3")),
    "max_fetches":        int(os.environ.get("PULSE_WORM_MAX_FETCHES", "500")),
    "max_per_round":      int(os.environ.get("PULSE_WORM_MAX_PER_ROUND", "50")),
    "concurrency":        int(os.environ.get("PULSE_WORM_CONCURRENCY", "8")),
    "min_context":        int(os.environ.get("PULSE_WORM_MIN_CONTEXT", "8")),
    "engagement_inherit": float(os.environ.get("PULSE_WORM_ENG_INHERIT", "0.15")),
}


@dataclass
class WormStats:
    rounds_completed: int = 0
    urls_extracted: int = 0
    fetches_attempted: int = 0
    fetches_succeeded: int = 0
    fetches_failed: int = 0
    fetches_skipped_capped: int = 0
    new_candidates: int = 0
    dig_value_hits: int = 0
    dig_value_misses: int = 0
    elapsed_seconds: float = 0.0


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META_DESC_RE = re.compile(
    r"""<meta\s+[^>]*?
        (?:name|property)\s*=\s*["'](?:description|og:description)["']
        [^>]*?content\s*=\s*["']([^"']+)["']
        [^>]*?>""",
    re.I | re.X,
)
_SCRIPT_STYLE_RE = re.compile(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(html: str, body_chars: int = 2000) -> str:
    if not html:
        return ""
    cleaned = _SCRIPT_STYLE_RE.sub(" ", html)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned[:body_chars]


@dataclass
class _DeepFetch:
    url: str
    source_type: str
    title: str = ""
    description: str = ""
    body: str = ""
    ok: bool = False
    error: Optional[str] = None
    fetched_at: float = field(default_factory=time.time)


def _fetch_one(url: str, source_type: str, timeout: int = 15) -> _DeepFetch:
    """Single-path fetch + parse. Phase 2 will wrap this with a bypass chain."""
    from lib import http as _http
    try:
        html = _http.get_text(url, timeout=timeout)
    except Exception as exc:
        return _DeepFetch(url=url, source_type=source_type, ok=False, error=str(exc)[:200])
    title_m = _TITLE_RE.search(html)
    desc_m  = _META_DESC_RE.search(html)
    return _DeepFetch(
        url=url,
        source_type=source_type,
        title=(_strip_html(title_m.group(1), 200) if title_m else "").strip(),
        description=(unescape(desc_m.group(1)) if desc_m else "")[:500],
        body=_strip_html(html, 2000),
        ok=True,
    )


def _make_synthetic_candidate(fetched: _DeepFetch, *,
                              parent_candidate, round_idx: int,
                              inherit_score: float):
    from lib.schema import SourceItem, Candidate

    item_id = "worm-" + hashlib.sha256(fetched.url.encode()).hexdigest()[:16]
    cid     = "worm-cid-" + hashlib.sha256(fetched.url.encode()).hexdigest()[:16]
    src     = f"worm:r{round_idx}:{fetched.source_type or 'unknown'}"

    snippet = fetched.description or fetched.body[:400]
    snippet = snippet.strip() or "(no body)"

    source_item = SourceItem(
        item_id=item_id,
        source=src,
        title=fetched.title or fetched.url,
        body=fetched.body,
        url=fetched.url,
        published_at=None,
        date_confidence="low",
        engagement={},
        metadata={
            "worm_round": round_idx,
            "worm_parent_id": getattr(parent_candidate, "candidate_id", ""),
            "worm_parent_url": getattr(parent_candidate, "url", ""),
            "worm_follow_reason": "extracted-from-parent-content",
        },
    )

    cand = Candidate(
        candidate_id=cid,
        item_id=item_id,
        source=src,
        title=fetched.title or fetched.url,
        url=fetched.url,
        snippet=snippet,
        subquery_labels=list(getattr(parent_candidate, "subquery_labels", []) or []),
        native_ranks={},
        local_relevance=getattr(parent_candidate, "local_relevance", 0.0) * 0.6,
        freshness=getattr(parent_candidate, "freshness", 0) or 0,
        engagement=inherit_score,
        source_quality=0.5,
        rrf_score=getattr(parent_candidate, "rrf_score", 0.0) * 0.5,
        sources=[src],
        source_items=[source_item],
        final_score=getattr(parent_candidate, "final_score", 0.0) * 0.5,
        explanation=f"worm follow from {getattr(parent_candidate, 'url', '?')} (round {round_idx})",
        metadata={
            "worm_round": round_idx,
            "worm_parent_id": getattr(parent_candidate, "candidate_id", ""),
            "worm_parent_url": getattr(parent_candidate, "url", ""),
            "worm_source_type": fetched.source_type,
        },
    )
    return cand


class WormCrawler:
    def __init__(
        self,
        *,
        max_rounds: int = DEFAULTS["max_rounds"],
        max_fetches: int = DEFAULTS["max_fetches"],
        max_per_round: int = DEFAULTS["max_per_round"],
        concurrency: int = DEFAULTS["concurrency"],
        min_context: int = DEFAULTS["min_context"],
        engagement_inherit: float = DEFAULTS["engagement_inherit"],
        progress=None,
    ):
        self.max_rounds = max(1, int(max_rounds))
        self.max_fetches = max(1, int(max_fetches))
        self.max_per_round = max(1, int(max_per_round))
        self.concurrency = max(1, int(concurrency))
        self.min_context = max(0, int(min_context))
        self.engagement_inherit = float(engagement_inherit)
        self.progress = progress
        self.stats = WormStats()
        self._seen_urls: set[str] = set()

    def _log(self, msg: str) -> None:
        logger.info("[worm] %s", msg)
        if self.progress is not None and hasattr(self.progress, "log"):
            try: self.progress.log(f"[worm] {msg}")
            except Exception: pass

    def _harvest_urls(self, candidate) -> list:
        from lib import url_extract as _ue, dig_value as _dv
        bag = []
        for txt in (candidate.snippet or "", candidate.title or ""):
            bag.extend(_ue.extract(txt))
        for si in getattr(candidate, "source_items", []) or []:
            bag.extend(_ue.extract(getattr(si, "body", "") or ""))
        seen_here: set[str] = set()
        unique = []
        for u in bag:
            if u.url in seen_here:
                continue
            seen_here.add(u.url)
            unique.append(u)
        parent_url = (candidate.url or "").strip()
        unique = [
            u for u in unique
            if u.url != parent_url
            and u.url not in self._seen_urls
            and u.context_chars >= self.min_context
        ]
        dv_lookup = _dv.lookup_map([u.source_type for u in unique])
        parent_eng = float(candidate.engagement or 0) if candidate.engagement else 0.0
        return _ue.rank_for_follow(unique, parent_engagement=parent_eng,
                                   dig_value_lookup=dv_lookup)

    def _fetch_round(self, candidates: list, round_idx: int) -> list:
        from lib import dig_value as _dv
        work: list = []
        for cand in candidates:
            ranked = self._harvest_urls(cand)
            for u in ranked:
                work.append((u.url, u.source_type, cand))
                self._seen_urls.add(u.url)
            self.stats.urls_extracted += len(ranked)
        work.sort(key=lambda w: _dv.score(w[1]) + (w[2].engagement or 0) * 0.001, reverse=True)
        budget = max(0, self.max_fetches - self.stats.fetches_attempted)
        capped = min(self.max_per_round, budget)
        if len(work) > capped:
            self.stats.fetches_skipped_capped += (len(work) - capped)
            work = work[:capped]
        if not work:
            return []

        self._log(f"round {round_idx}: fetching {len(work)} urls (budget remaining: {budget})")

        new_candidates: list = []
        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            futures = {ex.submit(_fetch_one, url, st): (url, st, parent)
                       for (url, st, parent) in work}
            for fut in as_completed(futures):
                url, st, parent = futures[fut]
                self.stats.fetches_attempted += 1
                try:
                    fetched = fut.result()
                except Exception as exc:
                    fetched = _DeepFetch(url=url, source_type=st, ok=False,
                                          error=str(exc)[:200])
                if not fetched.ok:
                    self.stats.fetches_failed += 1
                    self.stats.dig_value_misses += 1
                    _dv.record_pull(st, hit=False)
                    continue
                hit = bool(fetched.body) and len(fetched.body) > 120 and (
                    bool(fetched.title) or bool(fetched.description)
                )
                _dv.record_pull(st, hit=hit)
                if hit:
                    self.stats.dig_value_hits += 1
                else:
                    self.stats.dig_value_misses += 1
                self.stats.fetches_succeeded += 1
                inherit = (parent.engagement or 0.0) * self.engagement_inherit
                new_cand = _make_synthetic_candidate(
                    fetched, parent_candidate=parent,
                    round_idx=round_idx, inherit_score=inherit,
                )
                new_candidates.append(new_cand)
                self.stats.new_candidates += 1
        self._log(f"round {round_idx}: +{len(new_candidates)} new candidates "
                  f"({self.stats.fetches_succeeded}/{self.stats.fetches_attempted} ok)")
        return new_candidates

    def crawl(self, seed_candidates: list):
        t0 = time.time()
        for c in seed_candidates:
            if c.url:
                self._seen_urls.add(c.url)
        all_new: list = []
        frontier = list(seed_candidates)
        for r in range(1, self.max_rounds + 1):
            if self.stats.fetches_attempted >= self.max_fetches:
                self._log(f"hard cap reached ({self.max_fetches} fetches) — stopping")
                break
            new = self._fetch_round(frontier, round_idx=r)
            if not new:
                self._log(f"round {r}: empty frontier — stopping")
                break
            all_new.extend(new)
            frontier = new
            self.stats.rounds_completed = r
        self.stats.elapsed_seconds = round(time.time() - t0, 2)
        return all_new, self.stats
