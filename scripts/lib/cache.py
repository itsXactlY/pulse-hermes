"""SQLite-backed cache with 24h TTL for PULSE.

Stores API responses keyed by (source, query, from_date, to_date).
Auto-prunes expired entries. Thread-safe.
"""

import hashlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import log, raw_filter

CACHE_DIR = Path.home() / ".cache" / "pulse"
CACHE_DB = CACHE_DIR / "cache.db"
DEFAULT_TTL = 86400  # 24 hours

_local = threading.local()


def _source_log(msg: str):
    log.source_log("Cache", msg)


def _get_conn() -> sqlite3.Connection:
    """Get thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(CACHE_DB))
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                query TEXT NOT NULL,
                from_date TEXT,
                to_date TEXT,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                hit_count INTEGER DEFAULT 0
            )
        """)
        _local.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)
        """)
        _local.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source ON cache(source)
        """)
        _local.conn.commit()
    return _local.conn


def _make_key(source: str, query: str, from_date: str = "", to_date: str = "") -> str:
    """Generate cache key from parameters."""
    raw = f"{source}|{query}|{from_date}|{to_date}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get(
    source: str,
    query: str,
    from_date: str = "",
    to_date: str = "",
) -> Optional[list]:
    """Get cached results. Returns None if miss or expired."""
    key = _make_key(source, query, from_date, to_date)
    conn = _get_conn()
    now = time.time()

    try:
        row = conn.execute(
            "SELECT data, expires_at FROM cache WHERE key = ?", (key,)
        ).fetchone()

        if row is None:
            return None

        data_str, expires_at = row
        if now > expires_at:
            # Expired — delete
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            return None

        # Hit — increment counter
        conn.execute(
            "UPDATE cache SET hit_count = hit_count + 1 WHERE key = ?", (key,)
        )
        conn.commit()

        _source_log(f"Cache HIT: {source}/{query[:30]}")
        data = json.loads(data_str)
        # Filter out blocked content from cached data
        return raw_filter.filter_raw_items(data)

    except (sqlite3.Error, json.JSONDecodeError) as e:
        _source_log(f"Cache read error: {e}")
        return None


def put(
    source: str,
    query: str,
    data: list,
    from_date: str = "",
    to_date: str = "",
    ttl: int = DEFAULT_TTL,
) -> None:
    """Store results in cache."""
    key = _make_key(source, query, from_date, to_date)
    conn = _get_conn()
    now = time.time()

    try:
        data_str = json.dumps(data, ensure_ascii=False)
        conn.execute(
            """INSERT OR REPLACE INTO cache
               (key, source, query, from_date, to_date, data, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (key, source, query, from_date, to_date, data_str, now, now + ttl),
        )
        conn.commit()
        _source_log(f"Cache PUT: {source}/{query[:30]} ({len(data)} items, TTL {ttl}s)")
    except (sqlite3.Error, TypeError) as e:
        _source_log(f"Cache write error: {e}")


def prune() -> int:
    """Remove expired entries. Returns count removed."""
    conn = _get_conn()
    now = time.time()
    try:
        cursor = conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
        conn.commit()
        removed = cursor.rowcount
        if removed > 0:
            _source_log(f"Pruned {removed} expired entries")
        return removed
    except sqlite3.Error:
        return 0


def stats() -> Dict[str, Any]:
    """Get cache statistics."""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        expired = conn.execute(
            "SELECT COUNT(*) FROM cache WHERE expires_at < ?", (time.time(),)
        ).fetchone()[0]
        by_source = dict(
            conn.execute(
                "SELECT source, COUNT(*) FROM cache GROUP BY source"
            ).fetchall()
        )
        total_hits = conn.execute(
            "SELECT COALESCE(SUM(hit_count), 0) FROM cache"
        ).fetchone()[0]

        db_size = CACHE_DB.stat().st_size if CACHE_DB.exists() else 0

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "by_source": by_source,
            "total_hits": total_hits,
            "db_size_kb": round(db_size / 1024, 1),
        }
    except sqlite3.Error:
        return {"total_entries": 0}


def clear() -> int:
    """Clear all cache entries."""
    conn = _get_conn()
    try:
        cursor = conn.execute("DELETE FROM cache")
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error:
        return 0


def close() -> None:
    """Close thread-local connection."""
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None
