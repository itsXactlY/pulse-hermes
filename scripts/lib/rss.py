"""RSS/Atom feed search and parsing.

Parses RSS 2.0 and Atom feeds from user-configured feed URLs.
No external dependencies — uses xml.etree.ElementTree.
Configure feeds in ~/.config/pulse/feeds.txt (one URL per line).
"""

import hashlib
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import log
from .relevance import token_overlap_relevance

FEEDS_FILE = Path.home() / ".config" / "pulse" / "feeds.txt"

DEPTH_CONFIG = {
    "quick": 5,
    "default": 15,
    "deep": 30,
}

USER_AGENT = "pulse-hermes/3.0 (research tool)"

# Default quality feeds if no config exists
DEFAULT_FEEDS = [
    "https://blog.pragmaticengineer.com/rss/",
    "https://simonwillison.net/atom/everything/",
    "https://lucumr.pocoo.org/feed.atom",
    "https://jvns.ca/atom.xml",
    "https://rachelbythebay.com/w/atom.xml",
    "https://blog.research.google/feeds/posts/default?alt=rss",
    "https://openai.com/blog/rss.xml",
    "https://www.anthropic.com/rss.xml",
]


def _source_log(msg: str):
    log.source_log("RSS", msg)


def _load_feeds() -> List[str]:
    """Load feed URLs from config file or defaults."""
    if FEEDS_FILE.exists():
        feeds = []
        with open(FEEDS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    feeds.append(line)
        if feeds:
            return feeds
    return DEFAULT_FEEDS


def _fetch_feed(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch feed XML from URL."""
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _parse_rss(xml_text: str, feed_url: str) -> List[Dict[str, Any]]:
    """Parse RSS 2.0 feed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date = item.findtext("pubDate") or ""

        # Clean description
        desc = re.sub(r"<[^>]+>", "", desc)[:500]

        # Parse date (RFC 2822 format)
        date_str = None
        if pub_date:
            try:
                # Try common formats
                for fmt in [
                    "%a, %d %b %Y %H:%M:%S %z",
                    "%a, %d %b %Y %H:%M:%S %Z",
                    "%Y-%m-%dT%H:%M:%S%z",
                ]:
                    try:
                        dt = datetime.strptime(pub_date.strip(), fmt)
                        date_str = dt.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        if title and link:
            items.append({
                "title": title,
                "url": link,
                "body": desc,
                "date": date_str,
            })

    return items


def _parse_atom(xml_text: str, feed_url: str) -> List[Dict[str, Any]]:
    """Parse Atom feed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    ns = "{http://www.w3.org/2005/Atom}"
    items = []

    for entry in root.findall(f"{ns}entry"):
        title = (entry.findtext(f"{ns}title") or "").strip()
        summary = (entry.findtext(f"{ns}summary") or entry.findtext(f"{ns}content") or "").strip()
        summary = re.sub(r"<[^>]+>", "", summary)[:500]
        published = entry.findtext(f"{ns}published") or entry.findtext(f"{ns}updated") or ""

        # Get link
        link = ""
        for elink in entry.findall(f"{ns}link"):
            if elink.get("rel", "alternate") == "alternate" or not link:
                link = elink.get("href", "")

        date_str = published[:10] if len(published) >= 10 else None

        if title and link:
            items.append({
                "title": title,
                "url": link,
                "body": summary,
                "date": date_str,
            })

    return items


def _parse_feed(xml_text: str, feed_url: str) -> List[Dict[str, Any]]:
    """Parse feed — auto-detect RSS vs Atom."""
    # Try RSS first
    items = _parse_rss(xml_text, feed_url)
    if items:
        return items

    # Try Atom
    items = _parse_atom(xml_text, feed_url)
    if items:
        return items

    return []


def _fetch_single_feed(url: str) -> List[Dict[str, Any]]:
    """Fetch and parse a single feed."""
    xml_text = _fetch_feed(url)
    if not xml_text:
        return []

    items = _parse_feed(xml_text, url)

    # Add feed source metadata
    domain = urllib.parse.urlparse(url).netloc
    for item in items:
        item["feed_url"] = url
        item["feed_domain"] = domain

    return items


def search(
    topic: str,
    from_date: str = "",
    to_date: str = "",
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search RSS/Atom feeds for items matching topic.

    Fetches all configured feeds in parallel, then filters by relevance.
    Returns list of normalized item dicts.
    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    feeds = _load_feeds()

    _source_log(f"Searching {len(feeds)} feeds for '{topic}'")

    # Fetch all feeds in parallel
    all_items: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_single_feed, url): url for url in feeds}
        for future in as_completed(futures):
            try:
                items = future.result(timeout=20)
                all_items.extend(items)
            except Exception:
                pass

    _source_log(f"Fetched {len(all_items)} total items from {len(feeds)} feeds")

    # Score and filter by topic relevance
    scored = []
    for item in all_items:
        relevance = token_overlap_relevance(topic, f"{item.get('title', '')} {item.get('body', '')}")
        if relevance > 0.15:
            item["relevance"] = round(relevance, 3)
            scored.append(item)

    # Sort by relevance
    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:count]

    # Normalize
    items = []
    for i, item in enumerate(scored):
        items.append({
            "id": f"rss-{i + 1}",
            "title": item.get("title", ""),
            "body": item.get("body", ""),
            "url": item.get("url", ""),
            "author": None,
            "date": item.get("date"),
            "engagement": {},
            "relevance": item.get("relevance", 0.3),
            "why_relevant": f"RSS: {item.get('feed_domain', 'unknown')}",
            "metadata": {
                "feed_url": item.get("feed_url", ""),
                "feed_domain": item.get("feed_domain", ""),
            },
        })

    _source_log(f"Found {len(items)} relevant RSS items")
    return items
