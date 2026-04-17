"""Neural Memory integration for PULSE.

Provides three integration points:
1. Pre-search: Recall past research context for the topic
2. Post-search: Save findings to neural memory
3. Clustering: Use neural memory for semantic grouping (future)

Uses the hermes neural_remember/neural_recall tools when available.
Falls back gracefully if neural memory is not installed.
"""

import json
import subprocess
from typing import Any, Dict, List, Optional

from . import log


def _source_log(msg: str):
    log.source_log("NeuralMem", msg)


def _check_neural_memory() -> bool:
    """Check if neural memory is available via hermes tools."""
    try:
        # Check if neural_memory module exists
        result = subprocess.run(
            ["python3", "-c", "import neural_memory; print('ok')"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def recall_context(topic: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search neural memory for past research context on this topic.

    Returns list of relevant memories that can inform the current search.
    """
    if not _check_neural_memory():
        return []

    try:
        # Use neural_memory CLI or Python API
        safe_topic = topic.replace('"', '\\"')
        script = (
            'import neural_memory, json\n'
            'nm = neural_memory.NeuralMemory()\n'
            f'results = nm.recall("{safe_topic}", limit={limit})\n'
            'for r in results:\n'
            '    print(json.dumps({"content": r.get("content", ""), '
            '"label": r.get("label", ""), "score": r.get("score", 0)}))'
        )

        result = subprocess.run(
            ["python3", "-c", script],
            capture_output=True, text=True, timeout=15
        )

        if result.returncode != 0:
            return []

        memories = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    memories.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        if memories:
            _source_log(f"Found {len(memories)} neural memories for '{topic}'")
        return memories

    except Exception as e:
        _source_log(f"Neural recall failed: {e}")
        return []


def save_findings(topic: str, findings: List[Dict[str, Any]], limit: int = 10) -> bool:
    """Save top findings to neural memory for future recall.

    Only saves the top N findings to avoid noise.
    """
    if not _check_neural_memory():
        return False

    try:
        # Prepare summary
        top_findings = findings[:limit]
        summary_lines = [f"PULSE Research: {topic}"]
        for i, f in enumerate(top_findings, 1):
            title = f.get("title", "")[:100]
            source = f.get("source", "unknown")
            url = f.get("url", "")
            summary_lines.append(f"{i}. [{source}] {title}")
            if url:
                summary_lines.append(f"   {url}")

        content = "\n".join(summary_lines)
        safe_content = content.replace('"', '\\"').replace('\n', '\\n')
        label = f"pulse-{topic[:50].replace(' ', '-')}"

        script = (
            'import neural_memory\n'
            'nm = neural_memory.NeuralMemory()\n'
            f'nm.remember(content="{safe_content}", label="{label}")\n'
            'print("ok")'
        )

        result = subprocess.run(
            ["python3", "-c", script],
            capture_output=True, text=True, timeout=15
        )

        if result.returncode == 0:
            _source_log(f"Saved {len(top_findings)} findings to neural memory")
            return True

    except Exception as e:
        _source_log(f"Neural save failed: {e}")

    return False


def enhance_context(topic: str, base_context: str) -> str:
    """Enhance a research context with neural memory insights.

    Returns the enhanced context string with neural memory findings prepended.
    """
    memories = recall_context(topic, limit=3)
    if not memories:
        return base_context

    lines = ["[Neural Memory — Past Research Context]"]
    for m in memories:
        content = m.get("content", "")[:200]
        if content:
            lines.append(f"- {content}")
    lines.append("")
    lines.append(base_context)

    return "\n".join(lines)
