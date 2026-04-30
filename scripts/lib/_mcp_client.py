"""Tiny stdlib-only MCP client for Mazemaker.

Talks length-prefixed JSON over the Unix socket at
~/.neural_memory/mcp.sock (provided by mcp_local.py's dual-listener,
shipped in commit 245e83f of itsXactlY/neural-memory-mcp).

If the socket is missing, falls back to spawning mcp_local.py over
stdio — same wire-format mcp_local.py speaks for Claude Code.

No external deps. Drop-in replacement for the previous subprocess +
inline-script approach in this directory's neural_memory.py.

Usage:

    from ._mcp_client import MCPClient
    with MCPClient() as mcp:
        results = mcp.call("neural_recall", {"query": "stripe", "limit": 5})
        mcp.call("neural_remember",
                 {"content": "PULSE saved: stripe webhook signature checks",
                  "label": "pulse-stripe"})
"""
from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional


_DEFAULT_SOCK = Path.home() / ".neural_memory" / "mcp.sock"
_DEFAULT_SPAWN = ["python3", str(Path.home() / "projects" / "neural-memory-mcp" / "mcp_local.py")]
_REQUEST_TIMEOUT = 30.0


class MCPClient:
    """Length-prefixed JSON over Unix socket; stdio subprocess fallback."""

    def __init__(
        self,
        socket_path: str | Path = _DEFAULT_SOCK,
        spawn_fallback: bool = True,
        spawn_cmd: list[str] | None = None,
        request_timeout: float = _REQUEST_TIMEOUT,
    ) -> None:
        self.socket_path = Path(socket_path).expanduser()
        self.spawn_fallback = spawn_fallback
        self.spawn_cmd = spawn_cmd or _DEFAULT_SPAWN
        self.request_timeout = request_timeout
        self._sock: Optional[socket.socket] = None
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._connect()
        self._initialized = False

    # ─── lifecycle ────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        if self.socket_path.exists():
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(self.request_timeout)
                s.connect(str(self.socket_path))
                self._sock = s
                return
            except OSError:
                pass
        if not self.spawn_fallback:
            raise RuntimeError(f"MCP socket {self.socket_path} not reachable; spawn_fallback=False")
        # Spawn mcp_local.py over stdio (newline-delimited JSON, NOT length-prefixed)
        self._proc = subprocess.Popen(
            self.spawn_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,                # binary mode — line-buffering not supported
            text=False,
        )

    def close(self) -> None:
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
            if self._proc:
                try:
                    if self._proc.stdin:
                        self._proc.stdin.close()
                    self._proc.terminate()
                    self._proc.wait(timeout=2)
                except (subprocess.TimeoutExpired, OSError):
                    try:
                        self._proc.kill()
                    except OSError:
                        pass
                self._proc = None

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ─── JSON-RPC ─────────────────────────────────────────────────────────────

    def _send_socket(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        assert self._sock is not None
        self._sock.sendall(struct.pack(">I", len(body)) + body)
        head = self._recv_n(4)
        (length,) = struct.unpack(">I", head)
        return json.loads(self._recv_n(length).decode("utf-8"))

    def _recv_n(self, n: int) -> bytes:
        buf = b""
        assert self._sock is not None
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("MCP socket closed mid-message")
            buf += chunk
        return buf

    def _send_stdio(self, payload: dict) -> dict:
        assert self._proc and self._proc.stdin and self._proc.stdout
        line = (json.dumps(payload) + "\n").encode("utf-8")
        self._proc.stdin.write(line)
        self._proc.stdin.flush()
        # mcp_local.py prints non-JSON banners on first call (embed-server banners
        # on stdout). Skip lines that don't parse as JSON-RPC responses.
        deadline = time.monotonic() + self.request_timeout
        while time.monotonic() < deadline:
            raw = self._proc.stdout.readline()
            if not raw:
                raise ConnectionError("mcp_local.py stdout closed")
            try:
                resp = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(resp, dict) and "jsonrpc" in resp:
                return resp
        raise TimeoutError("MCP stdio request timed out")

    def _send(self, payload: dict) -> dict:
        with self._lock:
            return self._send_socket(payload) if self._sock else self._send_stdio(payload)

    # ─── public API ───────────────────────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._send({
            "jsonrpc": "2.0", "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05",
                       "capabilities": {},
                       "clientInfo": {"name": "pulse-mcp-client", "version": "1.0"}},
        })
        self._initialized = True

    def call(self, tool: str, arguments: dict) -> Any:
        """Invoke an MCP tool. Returns the structuredContent payload, or None.

        Tool name accepts both `neural_*` (legacy) and `mazemaker_*` (new) — the
        server's alias map handles both.
        """
        self._ensure_initialized()
        resp = self._send({
            "jsonrpc": "2.0", "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        })
        if "error" in resp:
            raise RuntimeError(f"MCP tool {tool} error: {resp['error']}")
        result = resp.get("result", {})
        # MCP returns content[].text — try structuredContent first, then parse text
        if "structuredContent" in result:
            return result["structuredContent"]
        for item in result.get("content", []):
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except (json.JSONDecodeError, KeyError):
                    return item.get("text", "")
        return None
