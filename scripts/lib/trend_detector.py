"""Concept drift and trend detection for PULSE.

Tracks topic velocity, source spread, and keyword drift in SQLite.
Surfaces TrendSignal when a topic is heating up or evolving.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import log

CACHE_DIR = Path.home() / ".cache" / "pulse"
CACHE_DB = CACHE_DIR / "cache.db"

_local = threading.local()

STOPWORDS = frozenset(
    "a an the and or but in on at to for of is it by with from as this that "
    "these those be was were are been has have had do does did will would shall "
    "should may might can could not no nor so if then than too very just about "
    "also into over after before between under above up out all each every both "
    "few more most other some such only own same here there when where which who "
    "whom what how new latest update week day year".split()
)


@dataclass
class TrendSignal:
    """Output of trend detection for a single topic."""
    is_trending: bool
    trend_strength: float        # 0.0 - 1.0
    recommended_lookback: int    # days
    hot_subtopics: list          # keywords that are spiking
    velocity: float              # results / day (recent 24h)
    source_spread: int           # unique sources contributing
    drift_detected: bool         # keyword composition shifted


def _source_log(msg: str):
    log.source_log("TrendDetector", msg)


def _get_conn() -> sqlite3.Connection:
    """Get thread-local SQLite connection, creating trend_snapshots table."""
    if not hasattr(_local, "conn") or _local.conn is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(CACHE_DB))
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS trend_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_hash TEXT NOT NULL,
                topic TEXT NOT NULL,
                snapshot_time REAL NOT NULL,
                result_count INTEGER NOT NULL,
                sources TEXT NOT NULL,          -- JSON list of source names
                keywords TEXT NOT NULL          -- JSON list of keywords
            )
        """)
        _local.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ts_hash_time
            ON trend_snapshots(topic_hash, snapshot_time)
        """)
        _local.conn.commit()
    return _local.conn


def _topic_hash(topic: str) -> str:
    """Stable short hash for a topic string."""
    import hashlib
    return hashlib.sha256(topic.lower().strip().encode()).hexdigest()[:16]


def _extract_keywords(texts: Sequence[str]) -> List[str]:
    """Extract meaningful keywords from a list of title/snippet strings."""
    words: list[str] = []
    for text in texts:
        tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
        words.extend(t for t in tokens if t not in STOPWORDS)
    return words


def _hours_between(t1: float, t2: float) -> float:
    return abs(t2 - t1) / 3600.0


class TrendDetector:
    """Detects concept drift and trending topics from pipeline results."""

    # ------------------------------------------------------------------
    # Recording snapshots
    # ------------------------------------------------------------------

    def record_snapshot(self, topic: str, results: List[Dict[str, Any]]) -> None:
        """Store a snapshot of results in SQLite for later trend analysis.

        Each result dict is expected to have at least 'title' (str) and
        'source' (str).  Optional 'snippet' and 'keywords' keys are used
        when present.
        """
        thash = _topic_hash(topic)
        now = time.time()

        sources: list[str] = []
        titles: list[str] = []
        for r in results:
            src = r.get("source", "unknown")
            sources.append(src)
            titles.append(r.get("title", "") + " " + r.get("snippet", ""))

        keywords = _extract_keywords(titles)

        conn = _get_conn()
        try:
            conn.execute(
                """INSERT INTO trend_snapshots
                   (topic_hash, topic, snapshot_time, result_count, sources, keywords)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (thash, topic, now, len(results),
                 json.dumps(sources), json.dumps(keywords)),
            )
            conn.commit()
            _source_log(f"Recorded snapshot: {topic} ({len(results)} results)")
        except sqlite3.Error as e:
            _source_log(f"record_snapshot error: {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_snapshots(
        self, topic: str, hours: float = 168.0
    ) -> List[Dict[str, Any]]:
        """Retrieve snapshots for a topic within the last *hours* hours."""
        thash = _topic_hash(topic)
        cutoff = time.time() - hours * 3600
        conn = _get_conn()
        try:
            rows = conn.execute(
                """SELECT snapshot_time, result_count, sources, keywords
                   FROM trend_snapshots
                   WHERE topic_hash = ? AND snapshot_time >= ?
                   ORDER BY snapshot_time ASC""",
                (thash, cutoff),
            ).fetchall()
            return [
                {
                    "time": r[0],
                    "count": r[1],
                    "sources": json.loads(r[2]),
                    "keywords": json.loads(r[3]),
                }
                for r in rows
            ]
        except sqlite3.Error:
            return []

    # ------------------------------------------------------------------
    # Velocity spike detection
    # ------------------------------------------------------------------

    def check_velocity_spike(
        self, topic: str, current_count: int, baseline_window_days: int = 7
    ) -> bool:
        """Return True if current_count exceeds the rolling average by 3x."""
        snapshots = self._get_snapshots(topic, hours=baseline_window_days * 24)
        if not snapshots:
            return current_count > 0  # first run — anything is a spike

        # Average result count per snapshot in the baseline window
        total = sum(s["count"] for s in snapshots)
        avg = total / len(snapshots) if snapshots else 0

        if avg <= 0:
            return current_count > 0
        return current_count > avg * 3

    # ------------------------------------------------------------------
    # Main detection entry point
    # ------------------------------------------------------------------

    def detect_trend(
        self, topic: str, current_results: Optional[List[Dict[str, Any]]] = None
    ) -> TrendSignal:
        """Analyse a topic and return a TrendSignal.

        If *current_results* is provided they are first recorded as a
        snapshot so the analysis includes the freshest data.
        """
        if current_results is not None:
            self.record_snapshot(topic, current_results)

        snapshots_7d = self._get_snapshots(topic, hours=168)   # 7 days
        snapshots_1d = self._get_snapshots(topic, hours=24)    # last 24h

        # ---- velocity (results/day in last 24h vs 7d average) ----
        recent_count = sum(s["count"] for s in snapshots_1d)
        if snapshots_7d:
            total_7d = sum(s["count"] for s in snapshots_7d)
            days_with_data = max(
                1, len(set(int(s["time"] // 86400) for s in snapshots_7d))
            )
            baseline_daily = total_7d / days_with_data
        else:
            baseline_daily = 0

        velocity = float(recent_count)
        if baseline_daily > 0:
            velocity_ratio = velocity / baseline_daily
        else:
            velocity_ratio = 5.0 if velocity > 0 else 1.0

        # ---- source spread ----
        all_recent_sources: list[str] = []
        for s in snapshots_1d:
            all_recent_sources.extend(s["sources"])
        source_spread = len(set(all_recent_sources))

        # ---- keyword drift (recent vs older keywords) ----
        mid = len(snapshots_7d) // 2
        older_kw: Counter = Counter()
        newer_kw: Counter = Counter()
        for i, s in enumerate(snapshots_7d):
            (newer_kw if i >= mid else older_kw).update(s["keywords"])

        # Normalise: keep top 50 keywords per window
        older_top = set(dict(older_kw.most_common(50)).keys())
        newer_top = set(dict(newer_kw.most_common(50)).keys())

        if older_top:
            new_keywords = newer_top - older_top
            drift_ratio = len(new_keywords) / max(1, len(older_top))
        else:
            new_keywords = set()
            drift_ratio = 0.0

        drift_detected = drift_ratio > 0.3

        # ---- hot subtopics (recent high-frequency keywords) ----
        recent_kw: Counter = Counter()
        for s in snapshots_1d:
            recent_kw.update(s["keywords"])
        hot_subtopics = [w for w, _ in recent_kw.most_common(10)]

        # ---- composite trend strength (0-1) ----
        strength = min(
            1.0,
            (
                0.4 * min(velocity_ratio / 5.0, 1.0)
                + 0.3 * min(source_spread / 6.0, 1.0)
                + 0.3 * min(drift_ratio / 0.5, 1.0)
            ),
        )

        is_trending = strength > 0.5

        # Recommended lookback: shorter when trending strongly
        if strength > 0.7:
            recommended_lookback = 7
        elif strength > 0.4:
            recommended_lookback = 14
        else:
            recommended_lookback = 30

        signal = TrendSignal(
            is_trending=is_trending,
            trend_strength=round(strength, 3),
            recommended_lookback=recommended_lookback,
            hot_subtopics=hot_subtopics,
            velocity=velocity,
            source_spread=source_spread,
            drift_detected=drift_detected,
        )
        _source_log(
            f"Trend {topic}: strength={signal.trend_strength:.2f} "
            f"velocity={velocity:.1f}/d sources={source_spread} "
            f"drift={drift_detected} trending={is_trending}"
        )
        return signal
