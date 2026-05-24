#!/usr/bin/env python3
"""stdio MCP server — PULSE (multi-source social search).

Exposes PULSE's research pipeline as MCP tools any Claude-Code-style
client can call: `pulse_search`, `pulse_trending`, `pulse_history`,
`pulse_stats`, `pulse_diagnose`. No subprocess, no shelling out — the
pipeline lib is imported directly.

Wire format mirrors the rest of the operator's MCP stack:

  * **stdio** — JSON-RPC 2026-11-05, one message per line, exactly what
    Claude Code / Cursor / Cline / Goose / Codex speak when registered
    via `mcpServers` in their config.

  * **socket** (optional) — length-prefixed JSON over a Unix socket at
    `$PULSE_MCP_SOCK_PATH` (default `~/.config/pulse/mcp.sock`). Lets
    multiple agents share one warm pulse process (model cache, store
    handle). Off by default; opt-in via `PULSE_MCP_SOCKET=1`.

Run directly for stdio (what Claude-Code does):

    python3 mcp_local.py

Stdlib-only, zero pip deps for the wire layer. The pipeline itself may
pull `requests` etc — that's the project's existing baseline.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Any

# ── Make `lib` importable (the project's scripts/ dir lives next to us) ──
PROJECT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

# Lazy-imported below so a borked config or missing optional dep doesn't
# kill the MCP handshake — we surface the error in the first tool call
# instead of dying on startup.

PROTOCOL = "2024-11-05"
SERVER_INFO = {"name": "pulse", "version": "0.0.3"}

SERVER_INSTRUCTIONS = """\
PULSE — multi-source social-engagement search engine.

Connected to a research pipeline that fans out across Reddit, Hacker
News, GitHub, YouTube, arXiv, Bluesky, Lemmy, Lobsters, dev.to,
Polymarket, Bing News, web, and more — ranks results by REAL engagement
(upvotes / stars / volume), not text-similarity.

WHEN TO USE
  - Operator asks "what's happening with X right now", "trending on Y",
    "latest reactions to Z", "is X breaking news"
  - You need primary-source quotes / links across several sites rather
    than one model-summary
  - You need to verify a claim against MULTIPLE platforms' real
    engagement signal

HOW TO USE
  - `pulse_search(topic)` is the default tool. Pass a clear topic
    phrase, optional depth ('quick'|'default'|'deep'), optional
    `lookback_days` (default 30). Returns a compact rendered report
    (clusters + top candidates with engagement metrics + URLs).
  - `pulse_trending()` for "what's been hot across all my past
    research" (no fresh fetch).
  - `pulse_history(topic)` for past runs on a specific topic.
  - `pulse_stats()` for cache + store size diagnostics.
  - `pulse_diagnose()` for "which sources are even available right
    now" (env + API-key state).

OUTPUT
  All tools return JSON or compact-markdown text. Treat returned URLs
  as authoritative — they point at the live source (Reddit thread,
  GitHub repo, HN comment, etc.). When you cite, quote the source +
  the engagement signal ("HN: 312 points / 84 comments") so the
  operator can see WHY this surfaced.

DO NOT call pulse_search when a `mazemaker_recall` would answer from
persistent memory — they're different layers. Memory is what the
operator told you before; pulse is what the WORLD is saying right now.
"""


# ─── Tool schemas ────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "pulse_search",
        "description": (
            "Multi-source social-engagement search on a topic. Fans out across "
            "Reddit, HN, GitHub, YouTube, arXiv, Bluesky, Lemmy, Lobsters, "
            "dev.to, Polymarket, Bing News, web. Returns ranked clusters with "
            "real engagement metrics (upvotes/points/stars/volume) and primary "
            "URLs. Default depth='default' fetches a balanced slice; 'quick' "
            "is faster + shallower; 'deep' goes broader + longer lookback."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Research topic / query (free text)",
                },
                "depth": {
                    "type": "string",
                    "enum": ["quick", "default", "deep"],
                    "description": "Research depth (default 'default')",
                    "default": "default",
                },
                "lookback_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 365,
                    "description": "How many days back to search (default 30)",
                    "default": 30,
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: restrict to specific source names (e.g. ['reddit','hackernews'])",
                },
                "emit": {
                    "type": "string",
                    "enum": ["compact", "json", "context"],
                    "description": "Output rendering (default 'compact' — short prose; 'json' = structured; 'context' = LLM-friendly)",
                    "default": "compact",
                },
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pulse_trending",
        "description": (
            "Findings that appeared across multiple past research runs. NOT a "
            "fresh fetch — reads the local store. Use to surface what's been "
            "consistently hot across the operator's topics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Max findings to return",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "pulse_history",
        "description": (
            "Past pulse_search runs for a specific topic — when ran, source "
            "coverage, top findings. Useful for 'how has X evolved' queries."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pulse_stats",
        "description": "Cache + store size diagnostics — entries, hits, DB size.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "pulse_diagnose",
        "description": (
            "Which sources are wired right now (env + API keys present). "
            "Returns per-source availability + which LLM planner is active. "
            "Run first when the operator says 'pulse isn't finding anything'."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ─── Lazy bootstrap of the pipeline ─────────────────────────────────────────

_config_cache: dict[str, Any] | None = None
_lock = threading.Lock()


def _config() -> dict[str, Any]:
    """Lazily load pulse config; cached for the process."""
    global _config_cache
    if _config_cache is None:
        from lib import config as _cfg
        _config_cache = _cfg.get_config()
    return _config_cache


def _run_search(args: dict) -> str:
    """Wrap pipeline.run + render. Returns text per requested `emit`."""
    from lib import pipeline as _pipeline
    from lib import render as _render

    topic = str(args.get("topic", "")).strip()
    if not topic:
        return json.dumps({"error": "topic is required"})

    depth = str(args.get("depth", "default"))
    if depth not in ("quick", "default", "deep"):
        depth = "default"
    lookback = max(1, min(365, int(args.get("lookback_days", 30))))
    sources = args.get("sources") or None
    if sources is not None and not isinstance(sources, list):
        sources = [s.strip() for s in str(sources).split(",") if s.strip()]
    emit = str(args.get("emit", "compact"))
    if emit not in ("compact", "json", "context"):
        emit = "compact"

    report = _pipeline.run(
        topic=topic,
        config=_config(),
        depth=depth,
        requested_sources=sources,
        lookback_days=lookback,
        use_llm=True,
        use_cache=True,
        use_store=True,
        progress=False,           # never animate inside an MCP call
    )

    if emit == "json":
        return _render.render_json(report)
    if emit == "context":
        # render_context exists for LLM-friendly summarisation; fall back to
        # compact if the helper isn't present (older pulse versions).
        fn = getattr(_render, "render_context", None)
        return fn(report) if fn else _render.render_compact(report)
    return _render.render_compact(report)


def _run_trending(args: dict) -> str:
    from lib import store as _store
    limit = max(1, min(100, int(args.get("limit", 20))))
    findings = _store.get_trending_findings(limit=limit)
    return json.dumps({"count": len(findings), "findings": findings},
                      ensure_ascii=False, default=str)


def _run_history(args: dict) -> str:
    from lib import store as _store
    topic = str(args.get("topic", "")).strip()
    if not topic:
        return json.dumps({"error": "topic is required"})
    limit = max(1, min(50, int(args.get("limit", 10))))
    fn = getattr(_store, "get_topic_history", None) or \
         getattr(_store, "get_history", None)
    if fn is None:
        return json.dumps({"error": "history API unavailable in this pulse build"})
    history = fn(topic, limit=limit) if fn.__code__.co_argcount >= 2 else fn(topic)
    return json.dumps({"topic": topic, "history": history},
                      ensure_ascii=False, default=str)


def _run_stats(args: dict) -> str:
    from lib import cache as _cache
    from lib import store as _store
    out = {
        "cache": _cache.stats(),
        "store": getattr(_store, "stats", lambda: {})(),
    }
    return json.dumps(out, ensure_ascii=False, default=str)


def _run_diagnose(args: dict) -> str:
    from lib.setup import detect_environment, get_available_sources, has_llm
    env = detect_environment()
    env["available_sources"] = get_available_sources(env)
    env["has_llm"] = has_llm(env)
    # cache stats — cheap addition
    try:
        from lib import cache as _cache
        env["cache_stats"] = _cache.stats()
    except Exception:
        pass
    return json.dumps(env, ensure_ascii=False, default=str)


def _call_tool(name: str, args: dict) -> dict:
    try:
        with _lock:
            if name == "pulse_search":
                text = _run_search(args)
            elif name == "pulse_trending":
                text = _run_trending(args)
            elif name == "pulse_history":
                text = _run_history(args)
            elif name == "pulse_stats":
                text = _run_stats(args)
            elif name == "pulse_diagnose":
                text = _run_diagnose(args)
            else:
                return {"content": [{"type": "text",
                                     "text": f"Error: unknown tool '{name}'"}],
                        "isError": True}
        return {"content": [{"type": "text", "text": text}]}
    except Exception as exc:
        import traceback
        return {"content": [{"type": "text",
                             "text": f"Error: {exc}\n{traceback.format_exc()[:1500]}"}],
                "isError": True}


# ─── JSON-RPC dispatcher (shared between stdio + socket) ─────────────────────

def _handle(body: dict) -> dict | None:
    method = body.get("method", "")
    params = body.get("params") or {}
    req_id = body.get("id")

    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
                "instructions": SERVER_INSTRUCTIONS,
            }
        elif method in ("initialized", "notifications/cancelled"):
            return None
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = _call_tool(params.get("name", ""),
                                params.get("arguments") or {})
        else:
            if req_id is None:
                return None
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601,
                              "message": f"Method not found: {method}"}}
    except Exception as exc:
        if req_id is None:
            return None
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32603, "message": str(exc)}}

    if req_id is None:
        return None
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


# ─── stdio transport (the one Claude Code / Cursor wire to) ──────────────────

def _stdio_loop() -> None:
    """Read newline-delimited JSON-RPC from stdin, write to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            body = json.loads(line)
        except Exception as exc:
            sys.stderr.write(f"[pulse-mcp] bad JSON: {exc}\n")
            sys.stderr.flush()
            continue
        out = _handle(body)
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


# ─── Optional Unix-socket transport (shared warm process) ────────────────────

def _socket_path() -> Path:
    custom = os.environ.get("PULSE_MCP_SOCK_PATH", "").strip()
    if custom:
        return Path(custom)
    return Path.home() / ".config" / "pulse" / "mcp.sock"


def _socket_loop_blocking(sock_path: Path) -> None:
    """Length-prefixed (4-byte big-endian) JSON-RPC. Same framing as embed-server."""
    import socket as _socket
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    if sock_path.exists():
        sock_path.unlink()
    srv = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(8)
    os.chmod(sock_path, 0o600)
    sys.stderr.write(f"[pulse-mcp] socket listening on {sock_path}\n")
    sys.stderr.flush()

    def _serve(conn):
        try:
            while True:
                hdr = conn.recv(4)
                if not hdr or len(hdr) < 4:
                    break
                n = struct.unpack(">I", hdr)[0]
                if n == 0 or n > 64 * 1024 * 1024:  # 64MB cap
                    break
                buf = b""
                while len(buf) < n:
                    chunk = conn.recv(n - len(buf))
                    if not chunk:
                        break
                    buf += chunk
                if len(buf) < n:
                    break
                try:
                    body = json.loads(buf.decode("utf-8"))
                except Exception:
                    continue
                out = _handle(body)
                if out is None:
                    continue
                payload = json.dumps(out, ensure_ascii=False).encode("utf-8")
                conn.sendall(struct.pack(">I", len(payload)) + payload)
        finally:
            try: conn.close()
            except Exception: pass

    while True:
        conn, _ = srv.accept()
        threading.Thread(target=_serve, args=(conn,), daemon=True).start()


# ─── entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    # Silence SIGPIPE — happens when Claude Code drops the pipe at shutdown
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):
        pass

    if os.environ.get("PULSE_MCP_SOCKET", "0") == "1":
        # Run socket listener in a background thread; stdio is still primary.
        threading.Thread(
            target=_socket_loop_blocking,
            args=(_socket_path(),),
            daemon=True,
        ).start()

    _stdio_loop()


if __name__ == "__main__":
    main()
