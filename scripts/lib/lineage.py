"""lineage — persistent record of the worm's dig trail.

Stores parent→child URL relationships across runs so the operator can
ask "WHY did pulse follow this finding?" and get the chain back to the
original seed query.

Schema (~/.config/pulse/lineage.db):

    runs
      run_id     TEXT PRIMARY KEY  -- 16-char hex, generated per pipeline run
      topic      TEXT NOT NULL
      depth      TEXT NOT NULL     -- 'default' | 'wurm' | etc
      started_at INTEGER NOT NULL  -- epoch s
      ended_at   INTEGER

    edges
      id            INTEGER PRIMARY KEY AUTOINCREMENT
      run_id        TEXT NOT NULL REFERENCES runs(run_id)
      parent_url    TEXT NOT NULL
      child_url     TEXT NOT NULL
      round         INTEGER NOT NULL
      source_type   TEXT
      strategy_used TEXT             -- which bypass strategy succeeded
      created_at    INTEGER NOT NULL DEFAULT (strftime('%s','now'))
      UNIQUE(run_id, child_url)      -- one parent per child per run

Public API:
    new_run(topic, depth) -> run_id
    record_edge(run_id, parent_url, child_url, round, source_type, strategy)
    end_run(run_id)
    trail_for(child_url, *, run_id=None) -> [{parent, child, round, ...}]
    runs_for_topic(topic, limit=20) -> [{run_id, topic, started_at, edges_n}]
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Optional


def _data_dir() -> Path:
    d = os.environ.get("PULSE_CACHE_DIR")
    if d:
        return Path(d)
    return Path.home() / ".config" / "pulse"


_DB_PATH = _data_dir() / "lineage.db"
_lock = Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10.0)
            _conn.execute("PRAGMA journal_mode = WAL")
            _conn.execute("PRAGMA synchronous = NORMAL")
            _conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id     TEXT PRIMARY KEY,
                    topic      TEXT NOT NULL,
                    depth      TEXT NOT NULL,
                    started_at INTEGER NOT NULL,
                    ended_at   INTEGER
                );
                CREATE TABLE IF NOT EXISTS edges (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id        TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                    parent_url    TEXT NOT NULL,
                    child_url     TEXT NOT NULL,
                    round         INTEGER NOT NULL,
                    source_type   TEXT,
                    strategy_used TEXT,
                    created_at    INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uniq_edges_run_child
                    ON edges(run_id, child_url);
                CREATE INDEX IF NOT EXISTS idx_edges_parent
                    ON edges(parent_url);
                CREATE INDEX IF NOT EXISTS idx_edges_child
                    ON edges(child_url);
                CREATE INDEX IF NOT EXISTS idx_runs_topic
                    ON runs(topic);
            """)
            _conn.commit()
    return _conn


def new_run(topic: str, depth: str) -> str:
    rid = secrets.token_hex(8)
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO runs(run_id, topic, depth, started_at) VALUES (?, ?, ?, ?)",
            (rid, topic, depth, int(time.time())),
        )
        conn.commit()
    return rid


def record_edge(run_id: str, *, parent_url: str, child_url: str,
                round_: int, source_type: str = "",
                strategy_used: str = "") -> None:
    if not run_id or not child_url:
        return
    conn = _get_conn()
    with _lock:
        try:
            conn.execute(
                "INSERT INTO edges(run_id, parent_url, child_url, round, "
                "                  source_type, strategy_used) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, parent_url or "", child_url, int(round_),
                 source_type or "", strategy_used or ""),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Same (run_id, child_url) already exists — not an error, just
            # means the same URL was reachable from two different parents in
            # the same round. First-wins is fine for the trail.
            pass


def end_run(run_id: str) -> None:
    if not run_id:
        return
    conn = _get_conn()
    with _lock:
        conn.execute(
            "UPDATE runs SET ended_at = ? WHERE run_id = ?",
            (int(time.time()), run_id),
        )
        conn.commit()


def trail_for(child_url: str, *, run_id: Optional[str] = None) -> list[dict]:
    """Walk backwards from `child_url` to the seed. Returns a list ordered
    seed → ... → child. If run_id is given, restrict to that run."""
    if not child_url:
        return []
    conn = _get_conn()
    trail = []
    cursor_url = child_url
    seen: set[str] = set()
    for _ in range(20):  # hard cycle guard
        if cursor_url in seen:
            break
        seen.add(cursor_url)
        if run_id:
            row = conn.execute(
                "SELECT parent_url, round, source_type, strategy_used "
                "FROM edges WHERE child_url = ? AND run_id = ? LIMIT 1",
                (cursor_url, run_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT parent_url, round, source_type, strategy_used "
                "FROM edges WHERE child_url = ? ORDER BY id DESC LIMIT 1",
                (cursor_url,),
            ).fetchone()
        if not row:
            break
        trail.append({
            "parent_url": row[0],
            "child_url": cursor_url,
            "round": int(row[1]),
            "source_type": row[2] or "",
            "strategy_used": row[3] or "",
        })
        if not row[0]:
            break
        cursor_url = row[0]
    return list(reversed(trail))   # seed-first


def runs_for_topic(topic: str, limit: int = 20) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT r.run_id, r.topic, r.depth, r.started_at, r.ended_at,
               (SELECT COUNT(*) FROM edges e WHERE e.run_id = r.run_id) AS edges_n
        FROM runs r
        WHERE r.topic = ?
        ORDER BY r.started_at DESC LIMIT ?
    """, (topic, int(limit))).fetchall()
    return [{
        "run_id": r[0], "topic": r[1], "depth": r[2],
        "started_at": int(r[3]),
        "ended_at": int(r[4]) if r[4] else None,
        "edges_n": int(r[5] or 0),
    } for r in rows]


def edges_for_run(run_id: str, limit: int = 1000) -> list[dict]:
    """Flat dump of every (parent, child) edge in a run — for the
    'watch it dig' panel."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT parent_url, child_url, round, source_type, strategy_used,
               created_at
        FROM edges WHERE run_id = ? ORDER BY id LIMIT ?
    """, (run_id, int(limit))).fetchall()
    return [{
        "parent_url": r[0], "child_url": r[1], "round": int(r[2]),
        "source_type": r[3] or "", "strategy_used": r[4] or "",
        "created_at": int(r[5]),
    } for r in rows]


def recent_runs(limit: int = 30) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT r.run_id, r.topic, r.depth, r.started_at, r.ended_at,
               (SELECT COUNT(*) FROM edges e WHERE e.run_id = r.run_id) AS edges_n
        FROM runs r
        ORDER BY r.started_at DESC LIMIT ?
    """, (int(limit),)).fetchall()
    return [{
        "run_id": r[0], "topic": r[1], "depth": r[2],
        "started_at": int(r[3]),
        "ended_at": int(r[4]) if r[4] else None,
        "edges_n": int(r[5] or 0),
    } for r in rows]
