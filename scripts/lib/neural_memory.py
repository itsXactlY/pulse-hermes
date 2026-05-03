"""Neural Memory integration for PULSE — via MCP socket (post-rebrand).

Provides three integration points:
  1. recall_context  — pre-search context lookup
  2. save_findings   — post-search persistence
  3. enhance_context — convenience wrapper that prepends recalled context

Talks to mazemaker via the MCP server at ~/.neural_memory/mcp.sock
(see /home/alca/projects/neural-memory-mcp/mcp_local.py — Phase F dual-
listener). Falls back to spawning mcp_local.py over stdio if the socket
is missing.

Replaces the previous subprocess-spawned approach which broke after the
neural-memory-adapter → mazemaker rebrand (the `neural_memory` Python
module no longer exists; `mazemaker` is the new name).
"""

from typing import Any, Dict, List

from . import log
from ._mcp_client import MCPClient


def _source_log(msg: str):
    log.source_log("NeuralMem", msg)


def _try_mcp(callable_, *args, **kwargs):
    """Run an MCP-backed call, returning a default on any failure.

    Pulse must never crash because memory is unreachable — this is a
    nice-to-have layer. Errors get logged once, the user-visible flow
    continues with empty results.
    """
    try:
        with MCPClient(spawn_fallback=True) as mcp:
            return callable_(mcp, *args, **kwargs)
    except Exception as e:
        _source_log(f"MCP call failed: {e}")
        return None


def recall_context(topic: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search neural memory for past research context on this topic.

    Returns list of relevant memories that can inform the current search.
    """
    def _do(mcp: MCPClient, t: str, n: int):
        return mcp.call("neural_recall", {"query": t, "limit": n})

    result = _try_mcp(_do, topic, limit)
    if not result:
        return []

    # Server returns either a list directly or a dict with 'memories'/'results' key
    # Handle plain string responses (malformed MCP returns) gracefully
    if isinstance(result, str):
        _source_log(f"Neural memory returned string, not a dict/list: {result[:50]}")
        return []
    memories = result if isinstance(result, list) else \
               result.get("memories") or result.get("results") or []
    out: List[Dict[str, Any]] = []
    for m in memories:
        if isinstance(m, dict):
            out.append({
                "content": m.get("content", ""),
                "label": m.get("label", ""),
                "score": m.get("similarity", m.get("score", 0)),
            })
    if out:
        _source_log(f"Found {len(out)} neural memories for '{topic}'")
    return out


def save_findings(topic: str, findings: List[Dict[str, Any]], limit: int = 10) -> bool:
    """Save top findings to neural memory for future recall."""
    if not findings:
        return False

    top = findings[:limit]
    summary_lines = [f"PULSE Research: {topic}"]
    for i, f in enumerate(top, 1):
        title = f.get("title", "")[:100]
        source = f.get("source", "unknown")
        url = f.get("url", "")
        summary_lines.append(f"{i}. [{source}] {title}")
        if url:
            summary_lines.append(f"   {url}")
    content = "\n".join(summary_lines)
    label = f"pulse-{topic[:50].replace(' ', '-')}"

    def _do(mcp: MCPClient, c: str, l: str):
        return mcp.call("neural_remember", {"content": c, "label": l})

    result = _try_mcp(_do, content, label)
    if result is not None:
        _source_log(f"Saved {len(top)} findings to neural memory")
        return True
    return False


def enhance_context(topic: str, base_context: str) -> str:
    """Enhance a research context with neural memory insights."""
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
