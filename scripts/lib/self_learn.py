"""Self-learning source selection for PULSE planner.

Analyzes past research runs from the store to learn which sources
perform best for different topic types. Feeds back into planner weights.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import Counter

from . import log

STORE_DB = Path.home() / ".local" / "share" / "pulse" / "store.db"


def _source_log(msg: str):
    log.source_log("SelfLearn", msg)


def get_source_performance(topic: str, limit_runs: int = 10) -> Dict[str, float]:
    """Analyze which sources performed best for past searches on this topic.

    Returns dict of source_name -> performance_score (0.0-1.0).
    Performance = findings_count / total_findings for that source.
    """
    if not STORE_DB.exists():
        return {}

    try:
        conn = sqlite3.connect(str(STORE_DB))

        # Find past runs for this topic (or similar topics)
        import hashlib
        topic_hash = hashlib.md5(topic.lower().strip().encode()).hexdigest()

        # Get topic ID
        row = conn.execute(
            "SELECT id FROM topics WHERE topic_hash = ?", (topic_hash,)
        ).fetchone()

        if not row:
            conn.close()
            return {}

        topic_id = row[0]

        # Get recent runs
        runs = conn.execute(
            """SELECT id, sources_used FROM runs
               WHERE topic_id = ? AND status = 'completed'
               ORDER BY started_at DESC LIMIT ?""",
            (topic_id, limit_runs)
        ).fetchall()

        if not runs:
            conn.close()
            return {}

        # Count findings per source across all runs
        source_counts: Dict[str, int] = {}
        total = 0

        for run_id, sources_used in runs:
            findings = conn.execute(
                """SELECT source, COUNT(*) FROM findings
                   WHERE run_id = ? GROUP BY source""",
                (run_id,)
            ).fetchall()

            for source, count in findings:
                source_counts[source] = source_counts.get(source, 0) + count
                total += count

        conn.close()

        if total == 0:
            return {}

        # Normalize to 0.0-1.0
        performance = {}
        for source, count in source_counts.items():
            performance[source] = round(count / total, 3)

        _source_log(f"Source performance for '{topic}': {performance}")
        return performance

    except Exception as e:
        _source_log(f"Self-learning query failed: {e}")
        return {}


def boost_weights(
    base_weights: Dict[str, float],
    performance: Dict[str, float],
    boost_factor: float = 0.2,
) -> Dict[str, float]:
    """Boost source weights based on past performance.

    Sources that had more findings in the past get a boost.
    The boost is proportional to their past performance share.

    Args:
        base_weights: Original source weights from planner
        performance: Past performance dict (source -> 0.0-1.0)
        boost_factor: How much to boost (0.2 = 20% max boost)

    Returns:
        Adjusted source weights
    """
    if not performance:
        return base_weights

    adjusted = dict(base_weights)

    for source, perf in performance.items():
        if source in adjusted:
            # Boost proportional to past performance
            boost = 1.0 + (perf * boost_factor)
            adjusted[source] = round(adjusted[source] * boost, 3)

    return adjusted
