"""dig_value — persistent per-source rolling quality score.

A source's `dig_value` answers: when we followed a URL of THIS source
type during a previous run, did the resulting deeper finding pan out
(non-trivial engagement, non-stale, distinct from parent)?

Higher score → prioritise this source in the next round. Lower (or
negative) score → deprioritise, optionally skip past a depth limit.

Storage: piggybacks on a sibling SQLite file (dig_values.db) next to
cache.db so concurrent writers in pulse share the same WAL discipline.
Table `dig_values`:

    source_type  TEXT PRIMARY KEY
    pulls        INTEGER NOT NULL   -- total follow attempts
    hits         INTEGER NOT NULL   -- pannings-out
    last_pull    INTEGER            -- epoch s
    raw_score    REAL    NOT NULL   -- exp-decay weighted hit rate
    updated_at   INTEGER NOT NULL

The score is a smoothed hit rate `hits / max(pulls, FLOOR_PULLS)` with
exponential decay on `(now - last_pull)` so a source that USED to be
good but stopped getting hit drifts back toward zero.

API is sync and idempotent. Concurrent writers serialised by WAL +
Python lock around the connection.
"""
from __future__ import annotations

import math
import os
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


_DB_PATH = _data_dir() / "dig_values.db"
_lock = Lock()
_conn: Optional[sqlite3.Connection] = None
_DECAY_HALF_LIFE_DAYS = 30.0
_FLOOR_PULLS = 5


def _get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10.0)
            _conn.execute("PRAGMA journal_mode = WAL")
            _conn.execute("PRAGMA synchronous = NORMAL")
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS dig_values (
                    source_type TEXT PRIMARY KEY,
                    pulls       INTEGER NOT NULL DEFAULT 0,
                    hits        INTEGER NOT NULL DEFAULT 0,
                    last_pull   INTEGER,
                    raw_score   REAL    NOT NULL DEFAULT 0.0,
                    updated_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            _conn.commit()
    return _conn


def record_pull(source_type: str, hit: bool) -> None:
    """Call once per follow attempt. `hit=True` if the deeper finding panned
    out (non-trivial engagement / new info / distinct from parent — the
    caller decides). Updates the rolling score atomically."""
    if not source_type:
        return
    conn = _get_conn()
    now = int(time.time())
    with _lock:
        row = conn.execute(
            "SELECT pulls, hits FROM dig_values WHERE source_type = ?",
            (source_type,),
        ).fetchone()
        if row is None:
            pulls, hits = 0, 0
        else:
            pulls, hits = int(row[0]), int(row[1])
        pulls += 1
        if hit:
            hits += 1
        raw = hits / max(pulls, _FLOOR_PULLS)
        conn.execute("""
            INSERT INTO dig_values(source_type, pulls, hits, last_pull, raw_score, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_type) DO UPDATE SET
                pulls=excluded.pulls,
                hits=excluded.hits,
                last_pull=excluded.last_pull,
                raw_score=excluded.raw_score,
                updated_at=excluded.updated_at
        """, (source_type, pulls, hits, now, raw, now))
        conn.commit()


def score(source_type: str, now: Optional[int] = None) -> float:
    """Decayed score in [0, 1]. Sources never pulled = 0."""
    if not source_type:
        return 0.0
    conn = _get_conn()
    now = now or int(time.time())
    with _lock:
        row = conn.execute(
            "SELECT raw_score, last_pull FROM dig_values WHERE source_type = ?",
            (source_type,),
        ).fetchone()
    if row is None:
        return 0.0
    raw, last_pull = float(row[0]), row[1]
    if not last_pull:
        return raw
    days = max(0.0, (now - int(last_pull)) / 86400.0)
    decay = math.pow(0.5, days / _DECAY_HALF_LIFE_DAYS)
    return raw * decay


def lookup_map(source_types: list[str]) -> dict[str, float]:
    """Bulk score for url_extract.rank_for_follow."""
    now = int(time.time())
    return {st: score(st, now) for st in set(source_types)}


def all_scores() -> list[dict]:
    """Operator-facing dump for `pulse --dig-values`. Sorted high→low."""
    conn = _get_conn()
    now = int(time.time())
    out = []
    with _lock:
        rows = conn.execute("""
            SELECT source_type, pulls, hits, last_pull, raw_score
            FROM dig_values ORDER BY raw_score DESC
        """).fetchall()
    for st, pulls, hits, last_pull, raw in rows:
        days = (now - int(last_pull or now)) / 86400.0
        decay = math.pow(0.5, days / _DECAY_HALF_LIFE_DAYS) if last_pull else 1.0
        out.append({
            "source_type": st,
            "pulls": int(pulls),
            "hits": int(hits),
            "raw_score": round(float(raw), 4),
            "decayed_score": round(float(raw) * decay, 4),
            "days_since_pull": round(days, 1),
        })
    return out


def reset() -> None:
    """Operator-callable: wipe all scores (debug / fresh start)."""
    conn = _get_conn()
    with _lock:
        conn.execute("DELETE FROM dig_values")
        conn.commit()
