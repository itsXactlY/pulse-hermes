"""GitHub search module.

Searches GitHub for repos, issues, PRs, releases, and user activity.
Uses the GitHub API via gh CLI or GITHUB_TOKEN.
"""

import json
import os
import subprocess
from typing import Any, Dict, List, Optional

from . import log

DEPTH_CONFIG = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}


def _source_log(msg: str):
    log.source_log("GitHub", msg)


def _run_gh(args: List[str], token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Run a gh CLI command and return parsed JSON."""
    cmd = ["gh"] + args + ["--json", "title,body,url,createdAt,author,repository,labels,state"]
    env = os.environ.copy()
    if token:
        env["GITHUB_TOKEN"] = token

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        if result.returncode != 0:
            # Try without --json for non-list commands
            cmd_json = ["gh"] + args + ["--json"]
            result = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=30, env=env)
            if result.returncode != 0:
                _source_log(f"gh command failed: {result.stderr[:200]}")
                return None
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"text": result.stdout.strip()}
        return json.loads(result.stdout) if result.stdout.strip() else None
    except subprocess.TimeoutExpired:
        _source_log("gh command timed out")
        return None
    except FileNotFoundError:
        _source_log("gh CLI not found")
        return None
    except Exception as e:
        _source_log(f"gh error: {e}")
        return None


def _run_gh_search(query: str, search_type: str = "repos", limit: int = 25, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """Run gh search and return results."""
    cmd = ["gh", "search", search_type, query, "--limit", str(limit), "--json"]
    env = os.environ.copy()
    if token:
        env["GITHUB_TOKEN"] = token

    # Different search types need different JSON fields
    field_map = {
        "repos": "fullName,description,url,stargazersCount,updatedAt,language",
        "issues": "title,body,url,createdAt,repository,state,author",
        "prs": "title,body,url,createdAt,repository,state,author",
        "commits": "message,url,author,repository",
    }
    fields = field_map.get(search_type, "title,url")

    try:
        result = subprocess.run(
            cmd + [fields],
            capture_output=True, text=True, timeout=30, env=env
        )
        if result.returncode != 0:
            _source_log(f"gh search {search_type} failed: {result.stderr[:200]}")
            return []
        return json.loads(result.stdout) if result.stdout.strip() else []
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        _source_log(f"gh search error: {e}")
        return []


def search(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search GitHub for repos, issues, and PRs related to a topic.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        depth: 'quick', 'default', or 'deep'
        token: GitHub token (optional, uses gh CLI auth if not provided)

    Returns:
        List of normalized item dicts.
    """
    limit = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    items = []
    seen_urls = set()

    # Search repos
    repos = _run_gh_search(topic, "repos", min(limit, 10), token)
    for i, repo in enumerate(repos):
        url = repo.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        items.append({
            "id": f"GH-R{i + 1}",
            "title": repo.get("fullName", ""),
            "body": repo.get("description", "") or "",
            "url": url,
            "author": None,
            "date": (repo.get("updatedAt") or "")[:10],
            "engagement": {
                "stars": repo.get("stargazersCount", 0) or 0,
            },
            "relevance": min(1.0, 0.5 + (repo.get("stargazersCount", 0) or 0) / 10000),
            "why_relevant": f"GitHub repo: {repo.get('description', '')[:80]}",
            "language": repo.get("language", ""),
        })

    # Search issues
    issues = _run_gh_search(topic, "issues", min(limit, 10), token)
    for i, issue in enumerate(issues):
        url = issue.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        repo_name = issue.get("repository", "")
        if isinstance(repo_name, dict):
            repo_name = repo_name.get("fullName", "")

        items.append({
            "id": f"GH-I{i + 1}",
            "title": issue.get("title", ""),
            "body": (issue.get("body") or "")[:300],
            "url": url,
            "author": issue.get("author", ""),
            "date": (issue.get("createdAt") or "")[:10],
            "engagement": {},
            "relevance": 0.5,
            "why_relevant": f"GitHub issue in {repo_name}",
            "state": issue.get("state", ""),
            "repository": repo_name,
        })

    # Search PRs
    prs = _run_gh_search(topic, "prs", min(limit, 10), token)
    for i, pr in enumerate(prs):
        url = pr.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        repo_name = pr.get("repository", "")
        if isinstance(repo_name, dict):
            repo_name = repo_name.get("fullName", "")

        items.append({
            "id": f"GH-P{i + 1}",
            "title": pr.get("title", ""),
            "body": (pr.get("body") or "")[:300],
            "url": url,
            "author": pr.get("author", ""),
            "date": (pr.get("createdAt") or "")[:10],
            "engagement": {},
            "relevance": 0.6,
            "why_relevant": f"GitHub PR in {repo_name}",
            "state": pr.get("state", ""),
            "repository": repo_name,
        })

    _source_log(f"Found {len(items)} GitHub items")
    return items
