"""Persistent research store for PULSE.

Stores research runs, topics, and findings in SQLite.
Enables cross-run dedup, history browsing, and trend tracking.
"""

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import log
from .schema import Report, SourceItem

STORE_DIR = Path.home() / ".local" / "share" / "pulse"
STORE_DB = STORE_DIR / "store.db"

_local = threading.local()


def _source_log(msg: str):
    log.source_log("Store", msg)


def _get_conn() -> sqlite3.Connection:
    """Get thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(STORE_DB))
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _init_schema(_local.conn)
    return _local.conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if not exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            topic_hash TEXT NOT NULL UNIQUE,
            first_searched TEXT NOT NULL,
            last_searched TEXT NOT NULL,
            search_count INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT DEFAULT 'running',
            source_mode TEXT,
            depth TEXT DEFAULT 'default',
            lookback_days INTEGER DEFAULT 30,
            items_found INTEGER DEFAULT 0,
            clusters_found INTEGER DEFAULT 0,
            sources_used TEXT,
            errors TEXT,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        );

        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            run_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            title_hash TEXT NOT NULL,
            url TEXT,
            body TEXT,
            author TEXT,
            container TEXT,
            published_at TEXT,
            engagement_json TEXT,
            relevance REAL DEFAULT 0.0,
            freshness INTEGER DEFAULT 0,
            engagement_score REAL DEFAULT 0.0,
            source_quality REAL DEFAULT 0.0,
            local_rank_score REAL DEFAULT 0.0,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            seen_count INTEGER DEFAULT 1,
            FOREIGN KEY (topic_id) REFERENCES topics(id),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_findings_topic ON findings(topic_id);
        CREATE INDEX IF NOT EXISTS idx_findings_hash ON findings(title_hash);
        CREATE INDEX IF NOT EXISTS idx_findings_source ON findings(source);
        CREATE INDEX IF NOT EXISTS idx_topics_hash ON topics(topic_hash);
        CREATE INDEX IF NOT EXISTS idx_runs_topic ON runs(topic_id);
    """)
    conn.commit()


def _topic_hash(topic: str) -> str:
    """Hash topic for dedup."""
    return hashlib.md5(topic.lower().strip().encode()).hexdigest()


def _title_hash(source: str, title: str) -> str:
    """Hash title for cross-run dedup."""
    raw = f"{source}:{title.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_or_create_topic(topic: str) -> Dict[str, Any]:
    """Get existing topic or create new one."""
    conn = _get_conn()
    h = _topic_hash(topic)
    now = datetime.now(timezone.utc).isoformat()

    row = conn.execute(
        "SELECT id, topic, search_count FROM topics WHERE topic_hash = ?", (h,)
    ).fetchone()

    if row:
        topic_id, _, count = row
        conn.execute(
            "UPDATE topics SET last_searched = ?, search_count = ? WHERE id = ?",
            (now, count + 1, topic_id),
        )
        conn.commit()
        return {"id": topic_id, "topic": topic, "search_count": count + 1}

    cursor = conn.execute(
        "INSERT INTO topics (topic, topic_hash, first_searched, last_searched) VALUES (?, ?, ?, ?)",
        (topic, h, now, now),
    )
    conn.commit()
    return {"id": cursor.lastrowid, "topic": topic, "search_count": 1}


def start_run(
    topic_id: int,
    source_mode: str = "",
    depth: str = "default",
    lookback_days: int = 30,
) -> int:
    """Record a new research run. Returns run_id."""
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO runs (topic_id, started_at, source_mode, depth, lookback_days) VALUES (?, ?, ?, ?, ?)",
        (topic_id, now, source_mode, depth, lookback_days),
    )
    conn.commit()
    return cursor.lastrowid


def complete_run(
    run_id: int,
    items_found: int,
    clusters_found: int,
    sources_used: List[str],
    errors: Optional[Dict[str, str]] = None,
) -> None:
    """Mark a run as completed."""
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    errors_json = json.dumps(errors) if errors else None
    conn.execute(
        """UPDATE runs SET completed_at = ?, status = 'completed',
           items_found = ?, clusters_found = ?, sources_used = ?, errors = ?
           WHERE id = ?""",
        (now, items_found, clusters_found, ",".join(sources_used), errors_json, run_id),
    )
    conn.commit()


def store_findings(
    topic_id: int,
    run_id: int,
    items: List[SourceItem],
) -> Dict[str, int]:
    """Store findings, dedup against previous runs.

    Returns: {"new": N, "updated": N, "duplicate": N}
    """
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    counts = {"new": 0, "updated": 0, "duplicate": 0}

    for item in items:
        h = _title_hash(item.source, item.title)

        existing = conn.execute(
            "SELECT id, seen_count FROM findings WHERE title_hash = ?", (h,)
        ).fetchone()

        if existing:
            fid, seen = existing
            conn.execute(
                "UPDATE findings SET last_seen = ?, seen_count = ?, relevance = ? WHERE id = ?",
                (now, seen + 1, item.local_rank_score or 0, fid),
            )
            if seen > 1:
                counts["duplicate"] += 1
            else:
                counts["updated"] += 1
        else:
            conn.execute(
                """INSERT INTO findings
                   (topic_id, run_id, source, title, title_hash, url, body, author,
                    container, published_at, engagement_json, relevance, freshness,
                    engagement_score, source_quality, local_rank_score, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    topic_id, run_id, item.source, item.title, h,
                    item.url, item.body[:500], item.author, item.container,
                    item.published_at, json.dumps(item.engagement),
                    item.local_relevance or 0, item.freshness or 0,
                    item.engagement_score or 0, item.source_quality or 0,
                    item.local_rank_score or 0, now, now,
                ),
            )
            counts["new"] += 1

    conn.commit()
    return counts


def get_topic_history(topic: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get research history for a topic."""
    conn = _get_conn()
    h = _topic_hash(topic)

    topic_row = conn.execute(
        "SELECT id FROM topics WHERE topic_hash = ?", (h,)
    ).fetchone()

    if not topic_row:
        return []

    topic_id = topic_row[0]
    rows = conn.execute(
        """SELECT id, started_at, completed_at, status, items_found,
                  clusters_found, sources_used
           FROM runs WHERE topic_id = ? ORDER BY started_at DESC LIMIT ?""",
        (topic_id, limit),
    ).fetchall()

    return [
        {
            "run_id": r[0],
            "started_at": r[1],
            "completed_at": r[2],
            "status": r[3],
            "items_found": r[4],
            "clusters_found": r[5],
            "sources_used": r[6].split(",") if r[6] else [],
        }
        for r in rows
    ]


def get_trending_findings(
    source: Optional[str] = None,
    days: int = 7,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get most-seen findings across all topics."""
    conn = _get_conn()

    query = """
        SELECT f.source, f.title, f.url, f.seen_count, f.last_seen,
               f.engagement_json, f.container, t.topic
        FROM findings f
        JOIN topics t ON f.topic_id = t.id
        WHERE f.seen_count > 1
    """
    params: list = []

    if source:
        query += " AND f.source = ?"
        params.append(source)

    query += " ORDER BY f.seen_count DESC, f.last_seen DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [
        {
            "source": r[0],
            "title": r[1],
            "url": r[2],
            "seen_count": r[3],
            "last_seen": r[4],
            "engagement": json.loads(r[5]) if r[5] else {},
            "container": r[6],
            "topic": r[7],
        }
        for r in rows
    ]


def stats() -> Dict[str, Any]:
    """Get store statistics."""
    conn = _get_conn()
    try:
        topics = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        findings = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        by_source = dict(
            conn.execute(
                "SELECT source, COUNT(*) FROM findings GROUP BY source"
            ).fetchall()
        )
        db_size = STORE_DB.stat().st_size if STORE_DB.exists() else 0

        return {
            "topics_tracked": topics,
            "total_runs": runs,
            "total_findings": findings,
            "findings_by_source": by_source,
            "db_size_kb": round(db_size / 1024, 1),
        }
    except sqlite3.Error:
        return {"topics_tracked": 0}


def save_report(report: Report) -> Dict[str, int]:
    """Save a full report to the persistent store."""
    topic_row = get_or_create_topic(report.topic)
    topic_id = topic_row["id"]

    source_mode = ",".join(sorted(report.items_by_source.keys()))
    run_id = start_run(topic_id, source_mode=source_mode)

    all_items = []
    for items in report.items_by_source.values():
        all_items.extend(items)

    counts = store_findings(topic_id, run_id, all_items)

    complete_run(
        run_id,
        items_found=len(all_items),
        clusters_found=len(report.clusters),
        sources_used=list(report.items_by_source.keys()),
        errors=report.errors_by_source if report.errors_by_source else None,
    )

    _source_log(f"Saved report: {counts['new']} new, {counts['duplicate']} dupes")
    return counts


def close() -> None:
    """Close thread-local connection."""
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None
