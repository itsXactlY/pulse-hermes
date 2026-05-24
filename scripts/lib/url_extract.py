"""url_extract — pull URLs out of finding bodies/snippets and classify them.

Used by the worm crawler to decide what to follow. Classification drives
both fetch dispatch (which fetcher to use for this URL) and dig_value
attribution (which SOURCE counted the win when this URL panned out).

Stdlib only. No regex pyrotechnics — the simple URL regex below catches
the >99% case (http/https + optional path/query/fragment). False
positives (e.g. trailing punctuation) are stripped in `_clean_url`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse

# Liberal-ish URL regex: scheme + host + optional path. Won't catch
# bare "www." (rare in scraped content) — fine.
_URL_RE = re.compile(
    r"""(?xi)
    \bhttps?://
    [^\s<>"'()\[\]{}]+
    """
)

# Tail characters that almost always belong to the surrounding prose, not the URL.
_TAIL_TRIM = ".,;:!?)\\]>}>'\""

# Known host → source-type classifier. Used both for routing AND for the
# dig_value attribution (which "source" earned the +1 for this finding).
# Order matters: more-specific suffixes first.
_HOST_RULES: list[tuple[str, str]] = [
    ("reddit.com",                 "reddit"),
    ("redd.it",                    "reddit"),
    ("news.ycombinator.com",       "hackernews"),
    ("ycombinator.com",            "hackernews"),
    ("github.com",                 "github"),
    ("gist.github.com",            "github"),
    ("raw.githubusercontent.com",  "github"),
    ("gitlab.com",                 "gitlab"),
    ("youtube.com",                "youtube"),
    ("youtu.be",                   "youtube"),
    ("arxiv.org",                  "arxiv"),
    ("biorxiv.org",                "arxiv"),
    ("medrxiv.org",                "arxiv"),
    ("ssrn.com",                   "arxiv"),
    ("openreview.net",             "arxiv"),
    ("bsky.app",                   "bluesky"),
    ("lemmy.world",                "lemmy"),
    ("lemmy.ml",                   "lemmy"),
    ("lobste.rs",                  "lobsters"),
    ("dev.to",                     "devto"),
    ("polymarket.com",             "polymarket"),
    ("manifold.markets",           "manifold"),
    ("metaculus.com",              "metaculus"),
    ("stackoverflow.com",          "stackexchange"),
    ("stackexchange.com",          "stackexchange"),
    ("openalex.org",               "openalex"),
    ("semanticscholar.org",        "semscholar"),
    ("api.semanticscholar.org",    "semscholar"),
    ("twitter.com",                "twitter"),
    ("x.com",                      "twitter"),
    ("mastodon.social",            "mastodon"),
    ("nitter.net",                 "twitter"),
    ("medium.com",                 "blog"),
    ("substack.com",               "blog"),
    ("ghost.io",                   "blog"),
    ("hashnode.com",               "blog"),
    ("hashnode.dev",               "blog"),
    ("notion.so",                  "doc"),
    ("notion.site",                "doc"),
    ("docs.google.com",            "doc"),
    ("paper.dropbox.com",          "doc"),
    ("hf.co",                      "huggingface"),
    ("huggingface.co",             "huggingface"),
    ("kaggle.com",                 "kaggle"),
    ("nature.com",                 "paper-journal"),
    ("science.org",                "paper-journal"),
    ("cell.com",                   "paper-journal"),
    ("nejm.org",                   "paper-journal"),
    ("acm.org",                    "paper-journal"),
    ("ieee.org",                   "paper-journal"),
    ("openai.com",                 "vendor"),
    ("anthropic.com",              "vendor"),
    ("deepmind.com",               "vendor"),
    ("google.com/research",        "vendor"),
    ("googleblog.com",             "vendor"),
    ("microsoft.com/research",     "vendor"),
    ("ai.facebook.com",            "vendor"),
    ("ai.meta.com",                "vendor"),
    ("web.archive.org",            "archive"),
    ("archive.org",                "archive"),
    ("wikipedia.org",              "wikipedia"),
]

# Hosts to ignore entirely (tracker / CDN / shortener-loops the worm
# shouldn't recurse into).
_IGNORE_HOSTS = {
    "t.co", "bit.ly", "lnkd.in",   # shorteners — dereference instead
    "youtu.be",                    # noisy — already covered by youtube.com
    "imgur.com", "i.imgur.com",
    "i.redd.it", "v.redd.it",      # image/video only — no follow-up content
    "google.com/search",
    "duckduckgo.com",
    "bing.com",
}


@dataclass(frozen=True)
class ExtractedURL:
    url: str
    host: str
    source_type: str          # "reddit" | "github" | "blog" | "unknown" | ...
    is_followable: bool       # False = image/tracker/shortener that we shouldn't recurse into
    context_chars: int        # how many chars of surrounding text the URL appeared in
                              # (used as a tie-break weight when deciding what to follow first)


def _clean_url(raw: str) -> str:
    """Strip surrounding punctuation + trailing markdown/HTML cruft."""
    url = raw.strip()
    # Drop balanced-bracket noise like "(http://...)" or "[http://...]"
    while url and url[-1] in _TAIL_TRIM:
        url = url[:-1]
    # Trim trailing fragment if it's only a hash with no anchor name
    if url.endswith("#"):
        url = url[:-1]
    return url


def _classify_host(host: str) -> str:
    """Return the dig_value source-bucket for this host."""
    h = host.lower()
    if h.startswith("www."):
        h = h[4:]
    for needle, bucket in _HOST_RULES:
        if needle in h or h.endswith("." + needle.split(".")[-2] + "." + needle.split(".")[-1]
                                    if needle.count(".") >= 1 else False):
            return bucket
        if needle == h or h.endswith("." + needle):
            return bucket
    return "unknown"


def _followable(host: str) -> bool:
    h = host.lower()
    if h.startswith("www."):
        h = h[4:]
    if h in _IGNORE_HOSTS:
        return False
    return True


def extract(text: str) -> list[ExtractedURL]:
    """Pull every http(s) URL out of `text`, classify, dedupe (by URL).

    Returned in order of first appearance, max one ExtractedURL per
    unique URL. `context_chars` records the longest stretch of
    consecutive non-URL text around the URL — used as a soft signal
    that this URL was discussed (long context) vs just listed (short).
    """
    if not text:
        return []
    out: list[ExtractedURL] = []
    seen: set[str] = set()
    cursor = 0
    for m in _URL_RE.finditer(text):
        url = _clean_url(m.group(0))
        if not url or url in seen:
            cursor = m.end()
            continue
        seen.add(url)
        try:
            host = urlparse(url).hostname or ""
        except ValueError:
            cursor = m.end()
            continue
        if not host:
            cursor = m.end()
            continue
        # Context length = chars since last URL boundary OR start.
        ctx = m.start() - cursor
        cursor = m.end()
        out.append(ExtractedURL(
            url=url,
            host=host,
            source_type=_classify_host(host),
            is_followable=_followable(host),
            context_chars=max(0, ctx),
        ))
    return out


def host_of(url: str) -> str:
    """Convenience: parse + lowercase host, strip leading www."""
    try:
        h = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    if h.startswith("www."):
        h = h[4:]
    return h


def classify(url: str) -> str:
    """Standalone classifier — returns the dig_value source bucket."""
    return _classify_host(host_of(url))


def rank_for_follow(urls: Iterable[ExtractedURL],
                    parent_engagement: float = 0.0,
                    dig_value_lookup: Optional[dict[str, float]] = None
                    ) -> list[ExtractedURL]:
    """Order URLs by a follow-priority score.

    Score = context_chars (signal: was this URL DISCUSSED or just listed)
          + parent_engagement * 0.1 (inherit a bit of the parent's score)
          + dig_value of source bucket (this source has historically panned out)

    Followable-only. Caller decides cutoff (top-K).
    """
    dvl = dig_value_lookup or {}
    scored = []
    for u in urls:
        if not u.is_followable:
            continue
        score = float(u.context_chars)
        score += parent_engagement * 0.1
        score += dvl.get(u.source_type, 0.0)
        scored.append((score, u))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in scored]
