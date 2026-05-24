"""corroborate — multi-source signal boost.

After the worm finishes, walk every Candidate's body/snippet and count
how many DISTINCT source-types cite each URL. URLs cited by 2+ source
types are signal-rich (HN AND Reddit AND a blog all link to X = X is
load-bearing).

Apply that signal as a boost to the candidate whose own URL is the
boosted one:

    cand.final_score += CORROBORATION_BOOST * (cites - 1)
    cand.metadata["corroborated_by"] = [list of citing source-types]

Tunable via env:
    PULSE_CORROBORATE_BOOST=0.15
    PULSE_CORROBORATE_MIN=2          minimum distinct cites to count

Stdlib only.
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Iterable

_BOOST = float(os.environ.get("PULSE_CORROBORATE_BOOST", "0.15"))
_MIN   = int(os.environ.get("PULSE_CORROBORATE_MIN", "2"))


def _candidate_source_bucket(cand) -> str:
    """Classify a candidate's source for the corroboration vote.

    Worm candidates carry source='worm:r<n>:<type>' — we use the type
    suffix so a worm-found-reddit-link still corroborates as "reddit"
    and not "worm".
    """
    src = (getattr(cand, "source", "") or "").strip()
    if src.startswith("worm:"):
        # "worm:r1:reddit" → "reddit"
        parts = src.split(":")
        return parts[-1] if parts and parts[-1] else "worm"
    return src or "unknown"


def boost(candidates: Iterable) -> dict:
    """Mutate candidates in place. Returns a dict of stats:
        {"boosted_n": N, "max_cites": M, "by_url": {url: cite_count}}."""
    from lib import url_extract as _ue

    # Phase 1: tally citations
    cites_by_url: dict[str, set] = defaultdict(set)
    for cand in candidates:
        source_bucket = _candidate_source_bucket(cand)
        texts = [cand.snippet or "", cand.title or ""]
        for si in getattr(cand, "source_items", []) or []:
            texts.append(getattr(si, "body", "") or "")
        for txt in texts:
            for u in _ue.extract(txt):
                if u.is_followable:
                    cites_by_url[u.url].add(source_bucket)

    # Phase 2: apply boost to candidates whose own URL is corroborated
    stats = {"boosted_n": 0, "max_cites": 0,
             "by_url": {u: len(s) for u, s in cites_by_url.items()
                        if len(s) >= _MIN}}
    for cand in candidates:
        own = (cand.url or "").strip()
        if not own:
            continue
        citers = cites_by_url.get(own, set())
        n = len(citers)
        if n >= _MIN:
            extra = _BOOST * (n - 1)
            cand.final_score = float(cand.final_score or 0.0) + extra
            md = getattr(cand, "metadata", {}) or {}
            md["corroborated_by"] = sorted(citers)
            md["corroboration_boost"] = round(extra, 4)
            try:
                cand.metadata = md
            except Exception:
                pass
            stats["boosted_n"] += 1
            stats["max_cites"] = max(stats["max_cites"], n)

    return stats
