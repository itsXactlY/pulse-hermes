"""Reddit public JSON search module.

Searches Reddit using free public JSON endpoints (no API key required).
Endpoints:
- Global: https://www.reddit.com/search.json?q={query}&sort=relevance&t=month&limit={limit}
- Subreddit: https://www.reddit.com/r/{sub}/search.json?q={query}&restrict_sr=on&sort=relevance&t=month
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Dict, List, Optional

from . import log

USER_AGENT = "last30days-hermes/3.0 (research tool)"

DEPTH_LIMITS = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}

ENRICH_LIMITS = {
    "quick": 3,
    "default": 5,
    "deep": 8,
}

MAX_RETRIES = 3
BASE_BACKOFF = 2.0


def _source_log(msg: str):
    log.source_log("Reddit", msg)


def _url_encode(text: str) -> str:
    return urllib.parse.quote_plus(text)


def _fetch_json(url: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
    """Fetch JSON from a URL with retry on 429."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "json" not in content_type and "text/html" in content_type:
                    _source_log(f"Anti-bot HTML response")
                    return None
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                delay = BASE_BACKOFF * (2 ** attempt)
                retry_after = None
                if hasattr(e, "headers"):
                    retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        pass
                _source_log(f"429 rate limited, retry {attempt + 1}/{MAX_RETRIES} after {delay:.1f}s")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                    continue
                return None
            elif e.code in (404, 403):
                return None
            else:
                return None
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            _source_log(f"Network error: {e}")
            return None
        except json.JSONDecodeError as e:
            _source_log(f"JSON decode error: {e}")
            return None
    return None


def _parse_posts(data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse Reddit listing JSON into normalized post dicts."""
    if not data:
        return []

    children = data.get("data", {}).get("children", [])
    posts = []

    for child in children:
        if child.get("kind") != "t3":
            continue
        post = child.get("data", {})
        permalink = str(post.get("permalink", "")).strip()
        if not permalink or "/comments/" not in permalink:
            continue

        score = int(post.get("score", 0) or 0)
        num_comments = int(post.get("num_comments", 0) or 0)
        selftext = str(post.get("selftext", ""))
        author = str(post.get("author", "[deleted]"))
        created_utc = post.get("created_utc")

        date_str = None
        if created_utc:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
                date_str = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError, OSError):
                pass

        posts.append({
            "id": "",
            "title": str(post.get("title", "")).strip(),
            "body": selftext[:500] if selftext else "",
            "url": f"https://www.reddit.com{permalink}",
            "score": score,
            "num_comments": num_comments,
            "subreddit": str(post.get("subreddit", "")).strip(),
            "author": author if author not in ("[deleted]", "[removed]") else "[deleted]",
            "date": date_str,
            "engagement": {
                "score": score,
                "num_comments": num_comments,
                "upvote_ratio": post.get("upvote_ratio"),
            },
            "relevance": _compute_relevance(score, num_comments),
            "why_relevant": f"Reddit post: {str(post.get('title', ''))[:80]}",
        })

    return posts


def _compute_relevance(score: int, num_comments: int) -> float:
    """Estimate relevance from engagement signals."""
    score_component = min(1.0, max(0.0, score / 500.0))
    comments_component = min(1.0, max(0.0, num_comments / 200.0))
    return round((score_component * 0.6) + (comments_component * 0.4), 3)


def _enrich_post(item: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
    """Enrich a single post with top comments."""
    try:
        thread_data = _fetch_json(f"{item['url']}.json", timeout=timeout)
        if not thread_data or not isinstance(thread_data, list) or len(thread_data) < 2:
            return item

        comments_data = thread_data[1].get("data", {}).get("children", [])
        top_comments = []
        comment_insights = []

        for c in comments_data[:5]:
            if c.get("kind") != "t1":
                continue
            cdata = c.get("data", {})
            body = str(cdata.get("body", ""))[:200]
            if body:
                top_comments.append({
                    "score": cdata.get("score", 0),
                    "excerpt": body,
                    "author": cdata.get("author", ""),
                })
                # First sentence as insight
                first_sentence = body.split(". ")[0].split("\n")[0][:150]
                if first_sentence and len(first_sentence) > 10:
                    comment_insights.append(first_sentence)

        item["top_comments"] = top_comments
        item["comment_insights"] = comment_insights
    except Exception:
        pass
    return item


def search(
    query: str,
    depth: str = "default",
    subreddit: Optional[str] = None,
    timeout: int = 15,
) -> List[Dict[str, Any]]:
    """Search Reddit via public JSON endpoint."""
    limit = DEPTH_LIMITS.get(depth, DEPTH_LIMITS["default"])
    encoded_query = _url_encode(query)

    if subreddit:
        sub = subreddit.lstrip("r/").strip()
        url = (
            f"https://www.reddit.com/r/{sub}/search.json"
            f"?q={encoded_query}&restrict_sr=on&sort=relevance&t=month&limit={limit}&raw_json=1"
        )
    else:
        url = (
            f"https://www.reddit.com/search.json"
            f"?q={encoded_query}&sort=relevance&t=month&limit={limit}&raw_json=1"
        )

    data = _fetch_json(url, timeout=timeout)
    posts = _parse_posts(data)

    # Dedupe by URL and assign IDs
    seen_urls = set()
    unique = []
    for post in posts:
        if post["url"] not in seen_urls:
            seen_urls.add(post["url"])
            unique.append(post)

    for i, post in enumerate(unique):
        post["id"] = f"R{i + 1}"

    result = unique[:limit]

    # Enrich top posts with comments
    enrich_limit = min(ENRICH_LIMITS.get(depth, 5), len(result))
    if enrich_limit > 0:
        by_score = sorted(range(len(result)), key=lambda i: result[i].get("score", 0), reverse=True)
        to_enrich = by_score[:enrich_limit]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(_enrich_post, result[idx]): idx
                for idx in to_enrich
            }
            for future in futures:
                try:
                    future.result(timeout=15)
                except Exception:
                    pass

    return result
