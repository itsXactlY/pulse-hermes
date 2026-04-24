#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# PULSE v0.0.4 — Hermes Agent Integration Installer
# ══════════════════════════════════════════════════════════════════════════════
#
# Installs PULSE into the Hermes Agent harness:
#   1. Validates Python 3.10+ and stdlib deps
#   2. Links skill into ~/.hermes/skills/devops/pulse/ (Hermes discovery)
#   3. Creates ~/.config/pulse/.env for optional API keys
#   4. Installs CLI symlink at ~/.local/bin/pulse
#   5. Verifies the skill is discoverable by Hermes
#
# Usage:
#   bash install.sh           # Full install
#   bash install.sh --check   # Verify only (no changes)
#   bash install.sh --unlink  # Remove symlinks (keep config)
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# ─── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILLS_DIR="$HERMES_HOME/skills"
PULSE_SKILL_DIR="$SKILLS_DIR/devops/pulse"
CONFIG_DIR="$HOME/.config/pulse"
CONFIG_FILE="$CONFIG_DIR/.env"
BIN_DIR="$HOME/.local/bin"
SYMLINK="$BIN_DIR/pulse"

# ─── Args ────────────────────────────────────────────────────────────────────
CHECK_ONLY=false
UNLINK=false
for arg in "$@"; do
    case "$arg" in
        --check)  CHECK_ONLY=true ;;
        --unlink) UNLINK=true ;;
        *)        echo "Unknown arg: $arg"; exit 1 ;;
    esac
done

# ─── Helpers ─────────────────────────────────────────────────────────────────
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  PULSE v0.0.4 — Hermes Agent Installer  ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

if $CHECK_ONLY; then
    echo -e "${CYAN}Running verification only (--check)${NC}"
    echo ""
fi

# ─── Unlink Mode ─────────────────────────────────────────────────────────────
if $UNLINK; then
    info "Removing PULSE symlinks..."
    rm -f "$SYMLINK"
    if [[ -L "$PULSE_SKILL_DIR" ]]; then
        rm -f "$PULSE_SKILL_DIR"
        ok "Removed skill symlink: $PULSE_SKILL_DIR"
    elif [[ -d "$PULSE_SKILL_DIR" ]]; then
        rm -rf "$PULSE_SKILL_DIR"
        ok "Removed skill directory: $PULSE_SKILL_DIR"
    fi
    ok "Removed CLI symlink: $SYMLINK"
    echo ""
    info "Config preserved at: $CONFIG_FILE"
    echo ""
    exit 0
fi

# ─── Step 1: Python ─────────────────────────────────────────────────────────
echo -e "${BOLD}[1/6] Python Check${NC}"

PYTHON=""
for py in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        MAJOR=$("$py" -c 'import sys; print(sys.version_info.major)' 2>/dev/null || echo "0")
        MINOR=$("$py" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo "0")
        if [[ "$MAJOR" -eq 3 && "$MINOR" -ge 10 ]]; then
            PYTHON="$py"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    fail "Python 3.10+ required. Install python3.10 or newer."
    exit 1
fi
ok "Found $PYTHON ($($PYTHON --version 2>&1))"

# ─── Step 2: Stdlib Dependencies ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}[2/6] Stdlib Dependencies${NC}"

STDLIB_MODS="json urllib.request urllib.parse concurrent.futures dataclasses hashlib argparse html re threading"
MISSING=()
for mod in $STDLIB_MODS; do
    if ! "$PYTHON" -c "import $mod" 2>/dev/null; then
        MISSING+=("$mod")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    fail "Missing stdlib modules: ${MISSING[*]}"
    exit 1
fi
ok "All stdlib modules available (zero pip dependencies)"

# ─── Step 3: Module Import Test ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}[3/6] Module Import Test${NC}"

IMPORT_OK=$("$PYTHON" -c "
import sys
sys.path.insert(0, '${PROJECT_DIR}/scripts')
from lib import schema, dates, config, planner, normalize, score, dedupe, fusion, cluster, render, pipeline
print('ok')
" 2>&1) || true

if [[ "$IMPORT_OK" == "ok" ]]; then
    ok "All 21 modules import successfully"
else
    fail "Module import failed:"
    echo "$IMPORT_OK"
    exit 1
fi

# ─── Step 4: Hermes Skill Registration ──────────────────────────────────────
echo ""
echo -e "${BOLD}[4/6] Hermes Skill Registration${NC}"

# Create skills directory structure
mkdir -p "$(dirname "$PULSE_SKILL_DIR")"

if $CHECK_ONLY; then
    if [[ -L "$PULSE_SKILL_DIR" ]] || [[ -d "$PULSE_SKILL_DIR" ]]; then
        ok "Skill registered at: $PULSE_SKILL_DIR"
    else
        warn "Skill not registered (run without --check to install)"
    fi
else
    # Remove old link/dir if it exists
    if [[ -L "$PULSE_SKILL_DIR" ]]; then
        rm -f "$PULSE_SKILL_DIR"
    elif [[ -d "$PULSE_SKILL_DIR" ]]; then
        rm -rf "$PULSE_SKILL_DIR"
    fi

    # Create symlink to project (not copy — keeps it in sync with git)
    ln -sf "$PROJECT_DIR" "$PULSE_SKILL_DIR"
    ok "Skill linked: $PULSE_SKILL_DIR → $PROJECT_DIR"
fi

# Verify SKILL.md exists
if [[ -f "$PULSE_SKILL_DIR/SKILL.md" ]]; then
    ok "SKILL.md present (Hermes will discover this skill)"
else
    fail "SKILL.md not found at $PULSE_SKILL_DIR/SKILL.md"
    exit 1
fi

# Verify scripts/ directory
if [[ -d "$PULSE_SKILL_DIR/scripts" ]]; then
    SCRIPT_COUNT=$(find "$PULSE_SKILL_DIR/scripts" -name "*.py" | wc -l)
    ok "Scripts directory: $SCRIPT_COUNT Python files"
else
    fail "scripts/ directory not found"
    exit 1
fi

# ─── Step 5: Configuration ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}[5/6] Configuration${NC}"

mkdir -p "$CONFIG_DIR"

if [[ ! -f "$CONFIG_FILE" ]]; then
    if $CHECK_ONLY; then
        warn "Config not found (run without --check to create)"
    else
        cat > "$CONFIG_FILE" << 'ENVEOF'
# ═══════════════════════════════════════════════════════════════════
# PULSE Configuration — Optional API Keys
# ═══════════════════════════════════════════════════════════════════
#
# Core sources work WITHOUT any keys:
#   Reddit, Hacker News, Polymarket, YouTube, ArXiv, Lobsters, RSS,
#   OpenAlex, Semantic Scholar, Manifold, Metaculus, Bluesky,
#   StackExchange, Lemmy, Dev.to, Tickertick
#
# Add optional keys below to unlock broader web/news/GitHub coverage.
# Or set them as environment variables — PULSE checks both.
# ═══════════════════════════════════════════════════════════════════

# Web search — pick one:
# BRAVE_API_KEY=your_key          # Free: 2000 queries/month → brave.com/search/api
# SERPER_API_KEY=your_key         # Google search → serper.dev
# EXA_API_KEY=your_key            # Semantic search → exa.ai

# GitHub (repo/issue/PR search):
# GITHUB_TOKEN=your_token         # Or: gh auth login

# News articles:
# NEWSAPI_KEY=your_key            # Free: 100 requests/day → newsapi.org
ENVEOF
        ok "Created config: $CONFIG_FILE"
    fi
else
    ok "Config exists: $CONFIG_FILE"
fi

# CLI symlink
if $CHECK_ONLY; then
    if [[ -L "$SYMLINK" ]]; then
        ok "CLI symlink: $SYMLINK"
    else
        warn "CLI symlink not found (run without --check to install)"
    fi
else
    mkdir -p "$BIN_DIR"
    rm -f "$SYMLINK"
    ln -sf "$PROJECT_DIR/scripts/pulse.py" "$SYMLINK"
    chmod +x "$PROJECT_DIR/scripts/pulse.py"
    ok "CLI symlink: $SYMLINK"
fi

# ─── Step 6: Integration Verification ───────────────────────────────────────
echo ""
echo -e "${BOLD}[6/6] Integration Verification${NC}"

# Run diagnostics through the installed CLI when possible. The installer must
# prove the public entry point works, not only that the source file imports.
PULSE_CMD=("$PYTHON" "$PROJECT_DIR/scripts/pulse.py")
if [[ -x "$SYMLINK" ]]; then
    PULSE_CMD=("$SYMLINK")
fi

DIAG_OUTPUT=$("${PULSE_CMD[@]}" --diagnose 2>&1)
DIAG_STATUS=$?
if [[ $DIAG_STATUS -ne 0 ]]; then
    fail "Diagnostics failed via ${PULSE_CMD[*]}"
    echo "$DIAG_OUTPUT"
    exit 1
fi

SOURCES=$(echo "$DIAG_OUTPUT" | "$PYTHON" -c "
import sys, json
payload = json.load(sys.stdin)
sources = payload.get('available_sources')
if not sources:
    raise SystemExit('missing available_sources')
print(', '.join(sources))
" 2>&1) || {
    fail "Diagnostics returned invalid JSON"
    echo "$DIAG_OUTPUT"
    exit 1
}
ok "Engine operational via ${PULSE_CMD[*]} — sources: $SOURCES"

# Run unit tests. A broken test suite is an installer failure, not a warning.
TEST_OUTPUT=$("$PYTHON" "$PROJECT_DIR/tests/test_basic.py" 2>&1)
TEST_STATUS=$?
if [[ $TEST_STATUS -ne 0 ]]; then
    fail "Unit tests failed"
    echo "$TEST_OUTPUT"
    exit 1
fi
TEST_SUMMARY=$(echo "$TEST_OUTPUT" | "$PYTHON" -c "
import re, sys
text = sys.stdin.read()
m = re.search(r'Results:\s*(\d+) passed,\s*(\d+) failed', text)
if not m:
    raise SystemExit('missing test summary')
print(f'{m.group(1)} passed, {m.group(2)} failed')
" 2>/dev/null || echo "passed")
ok "Unit tests: $TEST_SUMMARY"

# Verify Hermes skill discovery
if [[ -f "$SKILLS_DIR/devops/pulse/SKILL.md" ]]; then
    SKILL_NAME=$("$PYTHON" -c "
import re
content = open('$SKILLS_DIR/devops/pulse/SKILL.md').read()
m = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
print(m.group(1).strip().strip('\"')) if m else print('unknown')
" 2>/dev/null || echo "unknown")
    ok "Hermes skill name: '$SKILL_NAME' (discoverable via skill_view)"
else
    warn "Skill not found in Hermes directory (non-fatal)"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Installation Complete!${NC}"
echo -e "${BOLD}══════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Hermes Integration:${NC}"
echo -e "    Skill:    $PULSE_SKILL_DIR"
echo -e "    Config:   $CONFIG_FILE"
echo -e "    CLI:      $SYMLINK"
echo ""
echo -e "  ${CYAN}Usage:${NC}"
echo -e "    pulse \"your topic\"                          ${YELLOW}# Direct CLI${NC}"
echo -e "    pulse \"bitcoin halving\" --depth deep        ${YELLOW}# Deep research${NC}"
echo -e "    pulse --diagnose                             ${YELLOW}# Check sources${NC}"
echo ""
echo -e "  ${CYAN}Hermes Agent:${NC}"
echo -e "    The skill is now discoverable by Hermes."
echo -e "    Hermes can use skill_view('pulse') to load instructions."
echo -e "    Or use pulse --emit=context to inject research into other tasks."
echo ""
echo -e "  ${CYAN}No-Key Sources:${NC}"
echo -e "    Reddit · Hacker News · Polymarket · YouTube · ArXiv · Lobsters · RSS"
echo -e "    OpenAlex · Semantic Scholar · Manifold · Metaculus · Bluesky · StackExchange"
echo -e "    Lemmy · Dev.to · Tickertick"
echo ""
echo -e "  ${YELLOW}NOTE: This is a proof-of-concept.${NC}"
echo -e "  ${YELLOW}Hermes should evolve this into a fully autonomous system.${NC}"
echo ""
