#!/usr/bin/env bash
# wire.sh — register pulse's MCP server in every supported AI tool found
# on this machine. Mirrors the mazemaker wire.sh shape so muscle memory
# carries across.
#
# pulse exposes itself as a stdio MCP server (mcp_local.py) — there's no
# pod, no port, no service. Every tool gets a command/args entry, not a
# url.
#
# Idempotent. Always backs up the target config before editing.
#
# Usage:
#   bash wire.sh                  # interactive prompt per detected tool
#   bash wire.sh --all            # auto-yes for every tool detected
#   bash wire.sh --list           # detect only, no writes
#   bash wire.sh --tool=claude    # single tool (claude|hermes|cursor|cline|continue|goose|codex)
#   bash wire.sh --unwire         # remove pulse from every tool
#   bash wire.sh --python PATH    # override the python interpreter (default: $(command -v python3))
#   bash wire.sh --script PATH    # override mcp_local.py path (default: this dir's mcp_local.py)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_BIN="${PULSE_PY_BIN:-$(command -v python3)}"
MCP_SCRIPT="${PULSE_MCP_SCRIPT:-$SCRIPT_DIR/mcp_local.py}"
SERVER_NAME="pulse"

DO_ALL=0
DO_LIST=0
DO_UNWIRE=0
ONLY_TOOL=""

while [ $# -gt 0 ]; do
  case "$1" in
    --all)        DO_ALL=1; shift ;;
    --list)       DO_LIST=1; shift ;;
    --unwire)     DO_UNWIRE=1; shift ;;
    --tool)       ONLY_TOOL="${2:-}"; shift 2 ;;
    --tool=*)     ONLY_TOOL="${1#--tool=}"; shift ;;
    --python)     PY_BIN="${2:-}"; shift 2 ;;
    --python=*)   PY_BIN="${1#--python=}"; shift ;;
    --script)     MCP_SCRIPT="${2:-}"; shift 2 ;;
    --script=*)   MCP_SCRIPT="${1#--script=}"; shift ;;
    --help|-h)    sed -n '2,20p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *)            echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

if [ -t 1 ]; then
  GREEN=$(printf '\033[0;32m'); YELLOW=$(printf '\033[0;33m')
  CYAN=$(printf '\033[0;36m'); RED=$(printf '\033[0;31m')
  BOLD=$(printf '\033[1m'); RESET=$(printf '\033[0m')
else GREEN=""; YELLOW=""; CYAN=""; RED=""; BOLD=""; RESET=""; fi

info() { printf '%s[pulse-wire]%s %s\n' "$CYAN" "$RESET" "$*"; }
ok()   { printf '  %s✓%s %s\n'   "$GREEN" "$RESET" "$*"; }
warn() { printf '  %s⚠%s %s\n'   "$YELLOW" "$RESET" "$*"; }
err()  { printf '  %s✗%s %s\n'   "$RED" "$RESET" "$*"; }

require_jq() {
  command -v jq >/dev/null 2>&1 && return 0
  err "jq not installed — needed for safe JSON merging."
  err "  pacman -S jq | apt install jq | brew install jq"
  exit 3
}

require_python_yaml() {
  "$PY_BIN" -c "import yaml" 2>/dev/null && return 0
  err "python3 needs PyYAML — pip install pyyaml"
  exit 3
}

if [ ! -f "$MCP_SCRIPT" ]; then
  err "mcp script not found at $MCP_SCRIPT"
  err "  pass --script=/abs/path/to/mcp_local.py if it lives elsewhere"
  exit 4
fi
if [ ! -x "$PY_BIN" ] && ! command -v "$PY_BIN" >/dev/null 2>&1; then
  err "python interpreter $PY_BIN not found"
  exit 4
fi

# ─── JSON helpers ────────────────────────────────────────────────────────────

json_register() {
  local cfg="$1"
  require_jq
  mkdir -p "$(dirname "$cfg")"
  if [ ! -f "$cfg" ]; then echo '{}' > "$cfg"; fi
  cp "$cfg" "$cfg.bak.$(date +%s)"

  jq --arg name "$SERVER_NAME" \
     --arg cmd  "$PY_BIN" \
     --arg arg  "$MCP_SCRIPT" \
     '.mcpServers //= {}
      | .mcpServers[$name] = {
          "command": $cmd,
          "args":    [$arg],
          "env":     {}
        }' "$cfg" > "$cfg.tmp" && mv "$cfg.tmp" "$cfg"
}

json_unregister() {
  local cfg="$1"
  require_jq
  [ -f "$cfg" ] || { warn "no config at $cfg"; return 0; }
  cp "$cfg" "$cfg.bak.$(date +%s)"
  jq --arg name "$SERVER_NAME" \
     'if .mcpServers then .mcpServers |= del(.[$name]) else . end' \
     "$cfg" > "$cfg.tmp" && mv "$cfg.tmp" "$cfg"
}

# ─── Per-tool integrations ───────────────────────────────────────────────────

wire_hermes() {
  local cfg="$HOME/.hermes/config.yaml"
  if [ ! -f "$cfg" ]; then warn "hermes config not found"; return 1; fi
  require_python_yaml
  cp "$cfg" "$cfg.bak.$(date +%s)"
  "$PY_BIN" - "$cfg" "$SERVER_NAME" "$PY_BIN" "$MCP_SCRIPT" <<'PY'
import sys, yaml
cfg_path, name, py_bin, script = sys.argv[1:5]
with open(cfg_path) as f: cfg = yaml.safe_load(f) or {}
cfg.setdefault("mcp_servers", {})
cfg["mcp_servers"][name] = {
    "description": "PULSE — multi-source social-engagement research (Reddit/HN/GH/YT/arXiv/…)",
    "enabled": True,
    "transport": "stdio",
    "command": py_bin,
    "args":    [script],
    "tools": {
        "pulse_search":   {"enabled": True},
        "pulse_trending": {"enabled": True},
        "pulse_history":  {"enabled": True},
        "pulse_stats":    {"enabled": True},
        "pulse_diagnose": {"enabled": True},
    },
}
with open(cfg_path, "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
PY
}

unwire_hermes() {
  local cfg="$HOME/.hermes/config.yaml"
  [ -f "$cfg" ] || { warn "no hermes config"; return 0; }
  require_python_yaml
  cp "$cfg" "$cfg.bak.$(date +%s)"
  "$PY_BIN" - "$cfg" "$SERVER_NAME" <<'PY'
import sys, yaml
cfg_path, name = sys.argv[1:3]
with open(cfg_path) as f: cfg = yaml.safe_load(f) or {}
cfg.get("mcp_servers", {}).pop(name, None)
with open(cfg_path, "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
PY
}

wire_claude()   { json_register "$HOME/.claude/settings.json"; }
unwire_claude() { json_unregister "$HOME/.claude/settings.json"; }

wire_cursor()   { json_register "$HOME/.cursor/mcp.json"; }
unwire_cursor() { json_unregister "$HOME/.cursor/mcp.json"; }

wire_cline()    { json_register "$HOME/.config/cline/cline_mcp_settings.json"; }
unwire_cline()  { json_unregister "$HOME/.config/cline/cline_mcp_settings.json"; }

wire_continue() { json_register "$HOME/.continue/config.json"; }
unwire_continue() { json_unregister "$HOME/.continue/config.json"; }

wire_goose() {
  local cfg="$HOME/.config/goose/config.yaml"
  mkdir -p "$(dirname "$cfg")"
  [ -f "$cfg" ] || echo "extensions: {}" > "$cfg"
  require_python_yaml
  cp "$cfg" "$cfg.bak.$(date +%s)"
  "$PY_BIN" - "$cfg" "$SERVER_NAME" "$PY_BIN" "$MCP_SCRIPT" <<'PY'
import sys, yaml
cfg_path, name, py_bin, script = sys.argv[1:5]
with open(cfg_path) as f: cfg = yaml.safe_load(f) or {}
cfg.setdefault("extensions", {})
cfg["extensions"][name] = {
    "name": name, "type": "stdio", "enabled": True,
    "cmd": py_bin, "args": [script],
}
with open(cfg_path, "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
PY
}
unwire_goose() {
  local cfg="$HOME/.config/goose/config.yaml"
  [ -f "$cfg" ] || { warn "no goose config"; return 0; }
  require_python_yaml
  cp "$cfg" "$cfg.bak.$(date +%s)"
  "$PY_BIN" - "$cfg" "$SERVER_NAME" <<'PY'
import sys, yaml
cfg_path, name = sys.argv[1:3]
with open(cfg_path) as f: cfg = yaml.safe_load(f) or {}
cfg.get("extensions", {}).pop(name, None)
with open(cfg_path, "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
PY
}

wire_codex() {
  local cfg="$HOME/.codex/config.toml"
  mkdir -p "$(dirname "$cfg")"
  [ -f "$cfg" ] || touch "$cfg"
  if grep -q "^\[mcp_servers\.$SERVER_NAME\]" "$cfg" 2>/dev/null; then
    warn "codex already has [mcp_servers.$SERVER_NAME] — leaving alone"
    return 0
  fi
  cp "$cfg" "$cfg.bak.$(date +%s)"
  cat >> "$cfg" <<EOF

[mcp_servers.$SERVER_NAME]
command = "$PY_BIN"
args    = ["$MCP_SCRIPT"]
EOF
}
unwire_codex() {
  local cfg="$HOME/.codex/config.toml"
  [ -f "$cfg" ] || { warn "no codex config"; return 0; }
  cp "$cfg" "$cfg.bak.$(date +%s)"
  "$PY_BIN" - "$cfg" "$SERVER_NAME" <<'PY'
import sys, re
path, name = sys.argv[1:3]
with open(path) as f: text = f.read()
pattern = re.compile(rf"\n?\[mcp_servers\.{re.escape(name)}\][^\[]*", re.DOTALL)
new = pattern.sub("", text)
with open(path, "w") as f: f.write(new.rstrip() + "\n")
PY
}

# ─── Discovery ───────────────────────────────────────────────────────────────

TOOLS=(hermes claude cursor cline continue goose codex)

detect() {
  local t="$1"
  case "$t" in
    hermes)   [ -f "$HOME/.hermes/config.yaml" ] ;;
    claude)   [ -d "$HOME/.claude" ] ;;
    cursor)   [ -d "$HOME/.cursor" ] || command -v cursor >/dev/null 2>&1 ;;
    cline)    [ -d "$HOME/.config/cline" ] ;;
    continue) [ -d "$HOME/.continue" ] ;;
    goose)    [ -d "$HOME/.config/goose" ] || command -v goose >/dev/null 2>&1 ;;
    codex)    [ -d "$HOME/.codex" ] || command -v codex >/dev/null 2>&1 ;;
    *)        return 1 ;;
  esac
}

# ─── Main loop ───────────────────────────────────────────────────────────────

info "pulse wire — python=$PY_BIN  script=$MCP_SCRIPT"
info "scanning installed AI tools…"
echo

declare -a DETECTED=()
for t in "${TOOLS[@]}"; do
  if detect "$t"; then DETECTED+=("$t"); ok "found: $t"; fi
done

if [ ${#DETECTED[@]} -eq 0 ]; then
  warn "no supported AI tools detected — nothing to wire"
  exit 0
fi

if [ "$DO_LIST" -eq 1 ]; then exit 0; fi

if [ -n "$ONLY_TOOL" ]; then
  if ! printf '%s\n' "${DETECTED[@]}" | grep -qx "$ONLY_TOOL"; then
    err "$ONLY_TOOL not detected (or not supported). detected: ${DETECTED[*]}"
    exit 5
  fi
  DETECTED=("$ONLY_TOOL")
fi

echo
for t in "${DETECTED[@]}"; do
  if [ "$DO_UNWIRE" -eq 1 ]; then
    info "unwiring pulse from $t…"
    case "$t" in
      hermes)   unwire_hermes ;;
      claude)   unwire_claude ;;
      cursor)   unwire_cursor ;;
      cline)    unwire_cline ;;
      continue) unwire_continue ;;
      goose)    unwire_goose ;;
      codex)    unwire_codex ;;
    esac
    ok "$t: unwired"
    continue
  fi

  if [ "$DO_ALL" -ne 1 ]; then
    printf '  register pulse with %s? [Y/n] ' "$t"
    read -r ans
    [ "$ans" = "n" ] || [ "$ans" = "N" ] && { warn "$t: skipped"; continue; }
  fi
  info "wiring pulse into $t…"
  case "$t" in
    hermes)   wire_hermes ;;
    claude)   wire_claude ;;
    cursor)   wire_cursor ;;
    cline)    wire_cline ;;
    continue) wire_continue ;;
    goose)    wire_goose ;;
    codex)    wire_codex ;;
  esac
  ok "$t: registered (mcpServers.$SERVER_NAME → $PY_BIN $MCP_SCRIPT)"
done

echo
ok "done. Restart your AI tool(s) to pick up the new MCP server."
info "test from any registered tool: 'pulse_diagnose' → list available sources"
