"""News search module.

Uses NewsAPI.org for news article search (free tier: 100 requests/day).
"""

from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlencode

from . import http, log

DEPTH_CONFIG = {
    "quick": 5,
    "default": 10,
    "deep": 20,
}


def _source_log(msg: str):
    log.source_log("News", msg)


def search(
    topic: str,
    api_key: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search news articles via NewsAPI."""
    count = DEPTH_CONFIG.get(depth, 10)

    params = {
        "q": topic,
        "from": from_date,
        "to": to_date,
        "sortBy": "relevancy",
        "pageSize": str(count),
        "language": "en",
        "apiKey": api_key,
    }

    url = f"https://newsapi.org/v2/everything?{urlencode(params)}"

    try:
        data = http.get(url, timeout=15)
    except http.HTTPError as e:
        _source_log(f"NewsAPI search failed: {e}")
        return []

    articles = data.get("articles", [])
    items = []

    for i, article in enumerate(articles):
        items.append({
            "id": f"N-{i + 1}",
            "title": article.get("title", "") or "",
            "body": (article.get("description") or "")[:300],
            "url": article.get("url", ""),
            "author": article.get("author"),
            "date": (article.get("publishedAt") or "")[:10],
            "engagement": {},
            "relevance": max(0.3, 1.0 - i * 0.03),
            "why_relevant": f"News: {(article.get('source') or {}).get('name', 'Unknown')}",
            "source_name": (article.get("source") or {}).get("name", ""),
        })

    _source_log(f"Found {len(items)} news articles")
    return items


# ─────────────────────────────────────────────────────────────────────────
# Wurm-mode fallback: when NewsAPI key is missing or fails, pull from a
# curated set of major-outlet RSS feeds + Google News RSS. No API key,
# no rate-limit-budget burn, just public XML.
# ─────────────────────────────────────────────────────────────────────────

# Major news outlets with stable, public, no-auth RSS endpoints.
# Mix of EN + DE so we don't pretend the world is anglophone.
_RSS_OUTLETS = [
    ("BBC",          "http://feeds.bbci.co.uk/news/rss.xml"),
    ("Reuters World","http://feeds.reuters.com/Reuters/worldNews"),
    ("Guardian",     "https://www.theguardian.com/world/rss"),
    ("AP",           "https://apnews.com/index.rss"),
    ("Al Jazeera",   "https://www.aljazeera.com/xml/rss/all.xml"),
    ("DW",           "https://rss.dw.com/rdf/rss-en-all"),
    ("NPR World",    "https://feeds.npr.org/1004/rss.xml"),
    ("Tagesschau",   "https://www.tagesschau.de/xml/rss2/"),
    ("ZEIT",         "https://newsfeed.zeit.de/index"),
    ("Spiegel",      "https://www.spiegel.de/international/index.rss"),
    ("Heise",        "https://www.heise.de/rss/heise.rdf"),
    ("FAZ",          "https://www.faz.net/rss/aktuell/"),
]


def _google_news_rss_url(topic: str, hl: str = "en-US", gl: str = "US") -> str:
    """Build a Google News RSS URL for a topic. Public endpoint, no key needed.

    Google News exposes any search query as RSS: news.google.com/rss/search?q=…
    Returns up to ~100 items per query. Combined with the outlet feeds
    this is the closest no-API equivalent to NewsAPI.
    """
    return (
        f"https://news.google.com/rss/search?q={quote_plus(topic)}"
        f"&hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}"
    )


def _parse_rss(xml_text: str, source_name: str, topic: str,
               max_items: int) -> List[Dict[str, Any]]:
    """Tiny RSS/Atom parser that pulls title / link / pubDate / description.

    Stays stdlib-only (xml.etree). Filters items where neither title nor
    description mentions the topic — keeps the worm honest by rejecting
    obvious off-topic hits from broad outlet feeds.
    """
    import xml.etree.ElementTree as ET
    import re as _re
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # Strip XML namespaces so we can use simple element names.
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]

    items_xml = root.findall(".//item") or root.findall(".//entry")
    topic_tokens = {t.lower() for t in _re.findall(r"\w+", topic) if len(t) > 2}

    out = []
    for i, it in enumerate(items_xml):
        if len(out) >= max_items:
            break
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not link:
            link_el = it.find("link")
            if link_el is not None:
                link = link_el.get("href", "").strip()
        body = (it.findtext("description") or it.findtext("summary") or "").strip()
        date = (it.findtext("pubDate") or it.findtext("published") or "")[:10]

        # Soft topic filter: if neither title nor body has any topic token,
        # skip — outlet feeds are firehose-broad.
        haystack = f"{title} {body}".lower()
        if topic_tokens and not any(t in haystack for t in topic_tokens):
            continue

        out.append({
            "id": f"NRSS-{source_name}-{i + 1}",
            "title": title,
            "body": body[:300],
            "url": link,
            "author": None,
            "date": date,
            "engagement": {},
            "relevance": max(0.3, 1.0 - i * 0.02),
            "why_relevant": f"News (RSS): {source_name}",
            "source_name": source_name,
        })
    return out


def search_rss_aggregator(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """No-API fallback: aggregate Google News RSS + curated outlet feeds.

    Tries Google News RSS first (best topic-targeted yield), then sweeps
    a fixed set of major outlets in parallel and fuses results. Topic
    filter inside _parse_rss keeps the firehose feeds honest.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    count = DEPTH_CONFIG.get(depth, 10)
    per_outlet_max = max(2, count // 4)

    items: List[Dict[str, Any]] = []
    seen_urls = set()

    # 1) Google News RSS — topic-targeted, biggest single-source yield.
    try:
        gn_xml = http.get_text(_google_news_rss_url(topic), timeout=10)
        for it in _parse_rss(gn_xml, "Google News", topic, count):
            if it["url"] and it["url"] not in seen_urls:
                items.append(it)
                seen_urls.add(it["url"])
    except Exception as exc:
        _source_log(f"google news rss path failed: {exc}")

    if len(items) >= count:
        _source_log(f"RSS fallback: Google News covered the depth ({len(items)})")
        return items[:count]

    # 2) Major outlet feeds in parallel — broad firehose, topic-filtered.
    def _pull(outlet):
        name, url = outlet
        try:
            xml = http.get_text(url, timeout=8)
            return _parse_rss(xml, name, topic, per_outlet_max)
        except Exception as exc:
            _source_log(f"{name} RSS path failed: {exc}")
            return []

    with ThreadPoolExecutor(max_workers=6) as ex:
        for fut in as_completed(ex.submit(_pull, o) for o in _RSS_OUTLETS):
            for it in fut.result():
                if it["url"] and it["url"] not in seen_urls:
                    items.append(it)
                    seen_urls.add(it["url"])
                    if len(items) >= count:
                        break

    _source_log(f"RSS fallback total: {len(items)} items from {len(_RSS_OUTLETS)+1} feeds")
    return items[:count]
