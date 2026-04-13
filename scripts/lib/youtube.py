"""YouTube search and transcript extraction via yt-dlp.

Uses yt-dlp for search and subtitle extraction.
No API key needed — works with public YouTube data.
"""

import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from . import log

DEPTH_CONFIG = {
    "quick": 5,
    "default": 15,
    "deep": 30,
}

TRANSCRIPT_LIMITS = {
    "quick": 2,
    "default": 5,
    "deep": 10,
}


def _source_log(msg: str):
    log.source_log("YouTube", msg)


def _check_ytdlp() -> bool:
    """Check if yt-dlp is installed."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _install_ytdlp() -> bool:
    """Try to install yt-dlp."""
    _source_log("yt-dlp not found, attempting install...")
    try:
        result = subprocess.run(
            ["pip", "install", "yt-dlp"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            _source_log("yt-dlp installed successfully")
            return True
        _source_log(f"pip install failed: {result.stderr[:200]}")
        return False
    except Exception as e:
        _source_log(f"Install failed: {e}")
        return False


def search_videos(
    query: str,
    max_results: int = 15,
) -> List[Dict[str, Any]]:
    """Search YouTube for videos using yt-dlp.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        List of video metadata dicts.
    """
    if not _check_ytdlp():
        if not _install_ytdlp():
            _source_log("yt-dlp not available")
            return []

    # yt-dlp search: ytsearchN:query
    cmd = [
        "yt-dlp",
        f"ytsearch{max_results}:{query}",
        "--flat-playlist",
        "--dump-json",
        "--no-download",
        "--no-warnings",
        "--quiet",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        _source_log("yt-dlp search timed out")
        return []
    except Exception as e:
        _source_log(f"yt-dlp error: {e}")
        return []

    if result.returncode != 0:
        _source_log(f"yt-dlp returned {result.returncode}: {result.stderr[:200]}")
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            video = {
                "id": data.get("id", ""),
                "title": data.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
                "channel": data.get("channel", data.get("uploader", "")),
                "duration": data.get("duration"),
                "view_count": data.get("view_count", 0),
                "upload_date": data.get("upload_date", ""),
                "description": (data.get("description") or "")[:300],
            }
            # Format upload date
            if video["upload_date"] and len(video["upload_date"]) == 8:
                d = video["upload_date"]
                video["upload_date"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            videos.append(video)
        except json.JSONDecodeError:
            continue

    _source_log(f"Found {len(videos)} videos")
    return videos


def _extract_transcript(video_url: str, timeout: int = 15) -> Optional[str]:
    """Extract transcript/subtitles from a video."""
    cmd = [
        "yt-dlp",
        video_url,
        "--write-auto-sub",
        "--write-sub",
        "--sub-lang", "en",
        "--sub-format", "vtt",
        "--skip-download",
        "--quiet",
        "--no-warnings",
        "-o", "%(id)s.%(ext)s",
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd.extend(["--paths", tmpdir])
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None

        # Find the subtitle file
        for f in os.listdir(tmpdir):
            if f.endswith((".vtt", ".srt")):
                try:
                    with open(os.path.join(tmpdir, f), "r", encoding="utf-8") as fh:
                        raw = fh.read()
                    # Strip VTT formatting
                    text = re.sub(r"WEBVTT.*?\n\n", "", raw, flags=re.DOTALL)
                    text = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3} --> .*?\n", "", text)
                    text = re.sub(r"<[^>]+>", "", text)
                    text = re.sub(r"\n{3,}", "\n\n", text)
                    return text.strip()[:5000]
                except Exception:
                    pass

    return None


def _extract_highlights(transcript: str, query: str, max_highlights: int = 5) -> List[str]:
    """Extract relevant highlights from transcript based on query."""
    if not transcript:
        return []

    query_words = set(query.lower().split())
    sentences = re.split(r"[.!?]\s+", transcript)

    scored = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 20 or len(sent) > 300:
            continue
        words = set(sent.lower().split())
        overlap = len(query_words & words)
        if overlap > 0:
            scored.append((overlap, sent))

    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:max_highlights]]


def search(
    topic: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search YouTube for videos related to topic.

    Returns normalized items with engagement metrics and transcript highlights.
    """
    if not _check_ytdlp() and not _install_ytdlp():
        _source_log("yt-dlp not available, skipping YouTube search")
        return []

    count = DEPTH_CONFIG.get(depth, 15)
    videos = search_videos(topic, count)

    if not videos:
        return []

    items = []
    for i, video in enumerate(videos):
        view_count = video.get("view_count", 0) or 0
        relevance = min(1.0, 0.3 + (min(view_count, 1000000) / 1000000) * 0.5)
        # Boost for recency
        if video.get("upload_date"):
            from . import dates
            days = dates.days_ago(video["upload_date"])
            if days is not None and days <= 7:
                relevance = min(1.0, relevance + 0.2)

        items.append({
            "id": f"YT-{i + 1}",
            "title": video["title"],
            "body": video.get("description", ""),
            "url": video["url"],
            "author": video.get("channel"),
            "date": video.get("upload_date"),
            "engagement": {
                "views": view_count,
                "duration": video.get("duration", 0),
            },
            "relevance": round(relevance, 3),
            "why_relevant": f"YouTube: {video.get('channel', 'Unknown')}",
            "transcript_highlights": [],
            "transcript_snippet": "",
        })

    # Extract transcripts for top videos
    transcript_limit = min(TRANSCRIPT_LIMITS.get(depth, 5), len(items))
    if transcript_limit > 0:
        by_views = sorted(
            range(len(items)),
            key=lambda i: items[i].get("engagement", {}).get("views", 0),
            reverse=True,
        )
        to_extract = by_views[:transcript_limit]

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for idx in to_extract:
                url = items[idx]["url"]
                futures[executor.submit(_extract_transcript, url)] = idx

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    transcript = future.result(timeout=20)
                    if transcript:
                        items[idx]["transcript_snippet"] = transcript[:2000]
                        highlights = _extract_highlights(transcript, topic)
                        items[idx]["transcript_highlights"] = highlights
                        # Boost relevance if transcript matches topic
                        if highlights:
                            items[idx]["relevance"] = min(
                                1.0, items[idx]["relevance"] + 0.15
                            )
                except Exception:
                    pass

    _source_log(f"Processed {len(items)} YouTube videos ({transcript_limit} with transcripts)")
    return items
