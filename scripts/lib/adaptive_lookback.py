"""Adaptive lookback window for PULSE.

Tracks topic density in SQLite and dynamically adjusts the lookback window:
- Hot (>100 results in 7 days)  -> 7 days
- Active (>20 results in 14 days) -> 14 days
- Default -> 30 days
"""

import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from . import log
from .trend_detector import TrendDetector

CACHE_DIR = Path.home() / ".cache" / "pulse"
CACHE_DB = CACHE_DIR / "cache.db"

_local = threading.local()


def _source_log(msg: str):
    log.source_log("AdaptiveLookback", msg)


def _topic_hash(topic: str) -> str:
    """Stable hash for a topic string."""
    return hashlib.sha256(topic.lower().strip().encode()).hexdigest()[:16]


def _get_conn() -> sqlite3.Connection:
    """Get thread-local SQLite connection (shares cache.db)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(CACHE_DB))
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS topic_density (
                topic_hash TEXT NOT NULL,
                source TEXT NOT NULL,
                date TEXT NOT NULL,
                item_count INTEGER DEFAULT 0,
                recorded_at REAL NOT NULL,
                PRIMARY KEY (topic_hash, source, date)
            )
        """)
        _local.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_td_hash_date
            ON topic_density(topic_hash, date)
        """)
        _local.conn.commit()
    return _local.conn


class AdaptiveLookback:
    """Dynamically adjusts the lookback window based on topic activity."""

    def __init__(self) -> None:
        self._trend = TrendDetector()

    def record_result(self, topic: str, source: str) -> None:
        """Record that a result was found for a topic.

        Increments today's density counter for this topic/source pair.
        """
        thash = _topic_hash(topic)
        today = datetime.now(timezone.utc).date().isoformat()
        conn = _get_conn()
        now = datetime.now(timezone.utc).timestamp()

        try:
            conn.execute(
                """INSERT INTO topic_density (topic_hash, source, date, item_count, recorded_at)
                   VALUES (?, ?, ?, 1, ?)
                   ON CONFLICT(topic_hash, source, date)
                   DO UPDATE SET item_count = item_count + 1,
                                 recorded_at = excluded.recorded_at""",
                (thash, source, today, now),
            )
            conn.commit()
        except sqlite3.Error as e:
            _source_log(f"record_result error: {e}")

    def get_lookback(self, topic: str) -> int:
        """Get the adaptive lookback window in days for a topic.

        Returns:
            7 for hot topics (>100 results in last 7 days),
            14 for active topics (>20 results in last 14 days),
            30 otherwise.
        """
        thash = _topic_hash(topic)
        conn = _get_conn()
        today = datetime.now(timezone.utc).date()

        try:
            # Check 7-day window first (hot)
            date_7 = (today - timedelta(days=7)).isoformat()
            row = conn.execute(
                """SELECT COALESCE(SUM(item_count), 0) FROM topic_density
                   WHERE topic_hash = ? AND date >= ?""",
                (thash, date_7),
            ).fetchone()
            count_7 = row[0] if row else 0

            if count_7 > 100:
                _source_log(f"Topic hot (7d count={count_7}): lookback=7")
                return 7

            # Check 14-day window (active)
            date_14 = (today - timedelta(days=14)).isoformat()
            row = conn.execute(
                """SELECT COALESCE(SUM(item_count), 0) FROM topic_density
                   WHERE topic_hash = ? AND date >= ?""",
                (thash, date_14),
            ).fetchone()
            count_14 = row[0] if row else 0

            if count_14 > 20:
                _source_log(f"Topic active (14d count={count_14}): lookback=14")
                return 14

            # Default
            default_lookback = 30

            # --- Trend detection override ---
            # If the trend detector says strength > 0.7, use a shorter window
            try:
                signal = self._trend.detect_trend(topic)
                if signal.trend_strength > 0.7:
                    _source_log(
                        f"Trend override: strength={signal.trend_strength:.2f} "
                        f"-> lookback={signal.recommended_lookback}"
                    )
                    return signal.recommended_lookback
            except Exception as e:
                _source_log(f"Trend detection error (non-fatal): {e}")

            _source_log(f"Topic default (7d={count_7}, 14d={count_14}): lookback=30")
            return default_lookback

        except sqlite3.Error as e:
            _source_log(f"get_lookback error: {e}")
            return 30

    def get_density(self, topic: str) -> dict:
        """Get raw density stats for a topic (for diagnostics)."""
        thash = _topic_hash(topic)
        conn = _get_conn()
        today = datetime.now(timezone.utc).date()

        try:
            date_7 = (today - timedelta(days=7)).isoformat()
            date_14 = (today - timedelta(days=14)).isoformat()
            date_30 = (today - timedelta(days=30)).isoformat()

            def _sum(since: str) -> int:
                row = conn.execute(
                    """SELECT COALESCE(SUM(item_count), 0) FROM topic_density
                       WHERE topic_hash = ? AND date >= ?""",
                    (thash, since),
                ).fetchone()
                return row[0] if row else 0

            return {
                "topic_hash": thash,
                "count_7d": _sum(date_7),
                "count_14d": _sum(date_14),
                "count_30d": _sum(date_30),
                "lookback": self.get_lookback(topic),
            }
        except sqlite3.Error:
            return {"topic_hash": thash, "count_7d": 0, "count_14d": 0, "count_30d": 0, "lookback": 30}
