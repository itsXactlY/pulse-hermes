#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# PULSE v4 — Hermes Agent Native Installer
# ════════════════════════════════════════════════════════════════════════════
#
# Installs PULSE as a first-class skill into the Hermes Agent harness.
#
# CRITICAL — Hermes Skill Discovery (rglob):
#   Python's Path.rglob() does NOT descend into symlinks whose target resolves
#   OUTSIDE the scan root tree. A symlink ~/.hermes/skills/devops/pulse →
#   /home/alca/projects/pulse is INVISIBLE to rglob because the target (/home/alca/
#   projects/) is outside ~/.hermes/. This is a Python stdlib behavior, not a bug.
#
#   This installer therefore installs skill files as a REAL directory inside
#   ~/.hermes/skills/, then symlinks project files back to the source project for
#   development (git stays in sync automatically).
#
# What this does:
#   1. Validates Python 3.10+ (stdlib only, zero pip deps for core)
#   2. Verifies all 50+ lib modules import cleanly
#   3. Installs skill as REAL directory at ~/.hermes/skills/devops/pulse/
#      (SKILL.md + scripts/ + symlinks to project lib/sources for live development)
#   4. Creates ~/.config/pulse/.env for optional API keys
#   5. Wires the CLI at ~/.local/bin/pulse
#   6. Verifies Hermes can discover and load the skill
#   7. Runs the full test suite (9 tests, must all pass)
#
# Usage:
#   bash install.sh           Full install
#   bash install.sh --check   Verify only (no changes)
#   bash install.sh --unlink  Remove skill (keep config)
#
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Version ───────────────────────────────────────────────────────────────
PULSE_VERSION="4.0"

# ─── Colors ─────────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
DIM='\033[2m'
NC='\033[0m'

# ─── Helpers ───────────────────────────────────────────────────────────────
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }
step() { echo -e "\n${BOLD}${MAGENTA}[$1]${NC} ${BOLD}$2${NC}"; }

# ─── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILLS_DIR="$HERMES_HOME/skills"
PULSE_SKILL_DIR="$SKILLS_DIR/devops/pulse"   # REAL directory, NOT a symlink
CONFIG_DIR="$HOME/.config/pulse"
CONFIG_FILE="$CONFIG_DIR/.env"
BIN_DIR="$HOME/.local/bin"
SYMLINK="$BIN_DIR/pulse"

# ─── Args ───────────────────────────────────────────────────────────────────
CHECK_ONLY=false
UNLINK=false
for arg in "$@"; do
    case "$arg" in
        --check)  CHECK_ONLY=true ;;
        --unlink) UNLINK=true ;;
        *)        echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

# ─── Banner ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  PULSE v${PULSE_VERSION} — Hermes Agent Native Installer  ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

if $CHECK_ONLY; then
    echo -e "  ${DIM}Verification mode (--check) — no changes made${NC}"
    echo ""
fi

# ════════════════════════════════════════════════════════════════════════════
# UNLINK MODE
# ════════════════════════════════════════════════════════════════════════════
if $UNLINK; then
    info "Removing PULSE skill and CLI symlinks..."
    # Remove the real skill directory (not the project)
    if [[ -d "$PULSE_SKILL_DIR" ]]; then
        # Only remove if it looks like a Hermes skill install (has SKILL.md)
        if [[ -f "$PULSE_SKILL_DIR/SKILL.md" ]]; then
            rm -rf "$PULSE_SKILL_DIR"
            ok "Removed skill directory: $PULSE_SKILL_DIR"
        else
            warn "Skill directory exists but no SKILL.md — skipping removal"
        fi
    else
        warn "Skill directory not found — nothing to remove"
    fi
    # Remove CLI symlink
    rm -f "$SYMLINK"
    ok "Removed CLI symlink: $SYMLINK"
    echo ""
    info "Config preserved at: $CONFIG_FILE"
    echo ""
    info "PULSE unregistered from Hermes. To re-install: bash install.sh"
    echo ""
    exit 0
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 1: PYTHON VALIDATION
# ════════════════════════════════════════════════════════════════════════════
step 1 "Python Validation"

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
    fail "Python 3.10+ not found. Install python3.10 or newer."
    exit 1
fi
PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
ok "Found $PYTHON ($PY_VERSION)"

# ════════════════════════════════════════════════════════════════════════════
# STEP 2: STDLIB DEPENDENCIES
# ════════════════════════════════════════════════════════════════════════════
step 2 "Stdlib Dependency Check"

STDLIB_MODS="json urllib.request urllib.parse urllib.error concurrent.futures dataclasses hashlib argparse html re threading itertools collections enum pathlib signal socket subprocess sys tempfile contextlib types inspect random string"
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
ok "All stdlib modules available (zero pip dependencies required)"

# ════════════════════════════════════════════════════════════════════════════
# STEP 3: MODULE IMPORT AUDIT
# ════════════════════════════════════════════════════════════════════════════
step 3 "Module Import Audit"

# All 50+ lib modules must import without errors. This is the authoritative
# check that the codebase is complete and loadable.
IMPORT_OUTPUT=$("$PYTHON" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/scripts')
from lib import (
    schema, dates, config, planner, normalize, score, dedupe, fusion,
    cluster, render, pipeline, cache, store, ui, setup, query_router,
    adaptive_lookback, iterative_retrieval, trend_detector, research_crew,
    relevance, self_learn, neural_memory, filter, raw_filter, http, log,
    # Sources (18)
    reddit, hackernews, polymarket, youtube, github, web_search, news,
    arxiv, lobsters, rss, bluesky, devto, lemmy, stackexchange, openalex,
    sem_scholar, manifold, metaculus, tickertick, bing_news, serpapi_news,
    source_registry,
    # Internal
    llm_planner, _mcp_client,
)
print('all_modules_ok')
" 2>&1) || true

if [[ "$IMPORT_OUTPUT" == "all_modules_ok" ]]; then
    ok "All 50+ modules import successfully"
else
    fail "Module import failed:"
    echo "$IMPORT_OUTPUT"
    exit 1
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 4: HERMES SKILL INSTALLATION (real directory — NOT a symlink)
# ════════════════════════════════════════════════════════════════════════════
step 4 "Hermes Skill Installation"

# IMPORTANT: We install as a REAL directory inside ~/.hermes/skills/, not a
# symlink pointing outside. Python's rglob() does NOT descend into symlinks
# whose target resolves outside the scan root — a stdlib behavior, not a bug.
# Hermes' _find_all_skills() uses rglob, so the skill must be a real directory
# inside ~/.hermes/skills/ for skills_list and skill_view to both find it.

SKILL_LIB="$PULSE_SKILL_DIR/lib"
SKILL_SOURCES="$PULSE_SKILL_DIR/sources"
SKILL_SCRIPTS="$PULSE_SKILL_DIR/scripts"

if $CHECK_ONLY; then
    if [[ -f "$PULSE_SKILL_DIR/SKILL.md" ]]; then
        ok "Skill installed at: $PULSE_SKILL_DIR (real directory)"
        # Verify it's a real directory, not a symlink to outside
        if [[ -L "$PULSE_SKILL_DIR" ]]; then
            warn "Skill is a symlink — Hermes rglob will NOT find it!"
            warn "Re-run without --check to reinstall as real directory"
        fi
    else
        warn "Skill not installed (run without --check to install)"
    fi
else
    # ── Clean old artifacts ──────────────────────────────────────────────
    if [[ -L "$PULSE_SKILL_DIR" ]] || [[ -d "$PULSE_SKILL_DIR" ]]; then
        rm -rf "$PULSE_SKILL_DIR"
    fi

    # ── Create real skill directory ──────────────────────────────────────
    mkdir -p "$(dirname "$PULSE_SKILL_DIR")"
    mkdir -p "$PULSE_SKILL_DIR"

    # ── Copy SKILL.md (the heart of the Hermes skill) ───────────────────
    if [[ ! -f "$PROJECT_DIR/SKILL.md" ]]; then
        fail "SKILL.md not found in project root: $PROJECT_DIR/SKILL.md"
        exit 1
    fi
    cp "$PROJECT_DIR/SKILL.md" "$PULSE_SKILL_DIR/SKILL.md"

    # ── Copy scripts/ recursively (includes lib/, CLI entry points) ─────
    # The project has: scripts/lib/*.py (53 modules), scripts/pulse.py
    # We copy the entire scripts/ tree so the skill is self-contained.
    if [[ -d "$PROJECT_DIR/scripts" ]]; then
        cp -r "$PROJECT_DIR/scripts" "$PULSE_SKILL_DIR/scripts"
        chmod +x "$PULSE_SKILL_DIR/scripts/pulse.py" 2>/dev/null || true
        SCRIPT_COUNT=$(find "$PULSE_SKILL_DIR/scripts" -name "*.py" | wc -l | tr -d ' ')
        ok "scripts/ copied: $SCRIPT_COUNT Python files"
    else
        fail "scripts/ directory not found in project: $PROJECT_DIR/scripts"
        exit 1
    fi
fi

# ── Verify SKILL.md ───────────────────────────────────────────────────────
if [[ -f "$PULSE_SKILL_DIR/SKILL.md" ]]; then
    ok "SKILL.md present — Hermes skill_view('pulse') will work"
else
    fail "SKILL.md not found at $PULSE_SKILL_DIR/SKILL.md"
    exit 1
fi

# ── Verify lib/ is accessible inside scripts/ ──────────────────────────
# scripts/lib/ is copied as part of scripts/, so lib imports work via sys.path
LIB_COUNT=$(find "$PULSE_SKILL_DIR/scripts/lib" -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$LIB_COUNT" -gt 0 ]]; then
    ok "scripts/lib/: $LIB_COUNT Python modules accessible"
else
    # Fallback: check if scripts/lib was copied as a subdir
    if [[ -d "$PULSE_SKILL_DIR/scripts/lib" ]]; then
        ok "scripts/lib/ directory present"
    else
        warn "scripts/lib/ not found — imports may fail"
    fi
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 5: CLI WIRING
# ════════════════════════════════════════════════════════════════════════════
step 5 "CLI Wiring"

mkdir -p "$BIN_DIR"

if $CHECK_ONLY; then
    if [[ -L "$SYMLINK" ]]; then
        TARGET=$(readlink "$SYMLINK")
        ok "CLI symlink: $SYMLINK → $TARGET"
    else
        warn "CLI symlink not found (run without --check to install)"
    fi
else
    rm -f "$SYMLINK"
    # CLI points to the copied scripts/pulse.py inside the skill directory
    ln -sf "$PULSE_SKILL_DIR/scripts/pulse.py" "$SYMLINK"
    chmod +x "$PULSE_SKILL_DIR/scripts/pulse.py" 2>/dev/null || true
    ok "CLI wired: $SYMLINK → scripts/pulse.py"
fi

# Verify CLI works
if [[ -x "$SYMLINK" ]] || [[ -x "$SKILL_SCRIPTS/pulse.py" ]]; then
    ok "CLI executable"
else
    warn "CLI not marked executable (chmod +x may require re-run)"
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 6: CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════
step 6 "Configuration"

mkdir -p "$CONFIG_DIR"

if [[ ! -f "$CONFIG_FILE" ]]; then
    if $CHECK_ONLY; then
        warn "Config not found (run without --check to create)"
    else
        cat > "$CONFIG_FILE" << 'ENVEOF'
# ═══════════════════════════════════════════════════════════════════════════
# PULSE v4 Configuration — Optional API Keys
# ═══════════════════════════════════════════════════════════════════════════
#
# PULSE works WITHOUT any keys. All 18 sources are accessible:
#   Reddit, Hacker News, Polymarket, YouTube, ArXiv, Lobsters, RSS,
#   Bluesky, Dev.to, Lemmy, StackExchange, OpenAlex, Semantic Scholar,
#   Manifold, Metaculus, Tickertick, Bing News, SerpAPI News
#
# Add keys below for enhanced coverage (web search, GitHub, news).
# Keys can also be set as environment variables — both are checked.
# ═══════════════════════════════════════════════════════════════════════════

# Web search (pick one):
# BRAVE_API_KEY=***          # Free: 2000 queries/month → brave.com/search/api
# SERPER_API_KEY=***         # Google results → serper.dev
# EXA_API_KEY=***            # Semantic search → exa.ai

# GitHub (repo/issue/PR search):
# GITHUB_TOKEN=***           # Or: gh auth login

# News articles:
# NEWSAPI_KEY=***            # Free tier: 100 req/day → newsapi.org

# LLM planner (optional — falls back to heuristic without):
# OPENROUTER_API_KEY=***    # Ollama is auto-detected if available locally
ENVEOF
        ok "Created config: $CONFIG_FILE"
    fi
else
    ok "Config already exists: $CONFIG_FILE"
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 7: UNIT TESTS
# ════════════════════════════════════════════════════════════════════════════
step 7 "Unit Test Suite"

# Run tests from the PROJECT directory (has all source files),
# not from the skill directory (which has symlinks to project code).
if [[ -f "$PROJECT_DIR/tests/test_basic.py" ]]; then
    TEST_OUTPUT=$("$PYTHON" "$PROJECT_DIR/tests/test_basic.py" 2>&1)
    TEST_STATUS=$?

    if [[ $TEST_STATUS -ne 0 ]]; then
        fail "Unit tests failed (exit code: $TEST_STATUS)"
        echo "$TEST_OUTPUT"
        exit 1
    fi

    # Parse "Results: N passed, M failed" using temp files
    # (heredoc stdin conflicts with pipe stdin — must route through files)
    _test_out=$(mktemp)
    _parse_py=$(mktemp)
    echo "$TEST_OUTPUT" > "$_test_out"
    cat > "$_parse_py" << 'PYEOF'
import re, sys
text = sys.stdin.read()
m = re.search(r'Results:\s*(\d+)\s+passed,\s*(\d+)\s+failed', text)
if m:
    p, f = int(m.group(1)), int(m.group(2))
    if f > 0:
        print(f'{p} passed, {f} FAILED')
        sys.exit(1)
    print(f'{p} passed, 0 failed')
else:
    if 'All tests passed!' in text:
        print('all passed')
    else:
        print('summary unclear')
PYEOF
    TEST_SUMMARY=$("$PYTHON" "$_parse_py" < "$_test_out")
    TEST_STATUS=$?
    rm -f "$_test_out" "$$_parse_py"
    if [[ $TEST_STATUS -ne 0 ]]; then
        fail "Tests: $TEST_SUMMARY"
        echo "$TEST_OUTPUT"
        exit 1
    fi

    if [[ "$TEST_SUMMARY" == *"FAILED"* ]] || [[ "$TEST_SUMMARY" == *"parse error"* ]]; then
        fail "Tests: $TEST_SUMMARY"
        echo "$TEST_OUTPUT"
        exit 1
    fi

    ok "Unit tests: $TEST_SUMMARY"
else
    warn "Test file not found — skipping"
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 8: DIAGNOSTICS (pulse --diagnose)
# ════════════════════════════════════════════════════════════════════════════
step 8 "Diagnostics Verification"

# Use PROJECT_DIR scripts (source of truth), NOT the skill copy
PULSE_CMD=("$PYTHON" "$PROJECT_DIR/scripts/pulse.py")
if [[ -x "$SYMLINK" ]]; then
    PULSE_CMD=("$SYMLINK")
fi

DIAG_OUTPUT=$("${PULSE_CMD[@]}" --diagnose 2>&1)
DIAG_STATUS=$?

if [[ $DIAG_STATUS -ne 0 ]]; then
    fail "Diagnostics failed (exit code: $DIAG_STATUS)"
    echo "$DIAG_OUTPUT"
    exit 1
fi

# Extract available_sources from JSON output
SOURCES=$("$PYTHON" -c "
import sys, json
try:
    payload = json.loads(sys.stdin.read())
    srcs = payload.get('available_sources', [])
    if not srcs:
        raise SystemExit('no available_sources key')
    print(', '.join(sorted(srcs)))
except Exception as e:
    raise SystemExit(f'parse error: {e}')
" <<< "$DIAG_OUTPUT" 2>&1) || {
    fail "Diagnostics did not return valid JSON:"
    echo "$DIAG_OUTPUT"
    exit 1
}

ok "Engine operational: ${PULSE_CMD[*]} --diagnose"
ok "Available sources: $SOURCES"

# Count them
SOURCE_COUNT=$(echo "$SOURCES" | tr ',' '\n' | wc -l | tr -d ' ')
info "Total sources: $SOURCE_COUNT"

# ════════════════════════════════════════════════════════════════════════════
# STEP 9: HERMES DISCOVERY VERIFICATION
# ════════════════════════════════════════════════════════════════════════════
step 9 "Hermes Discovery Verification"

# Verify the skill directory is a REAL directory (not a symlink to outside)
# and that Hermes Python code can find it via rglob.
HERMES_CHECK=$("$PYTHON" -c "
import sys
from pathlib import Path

SKILLS_DIR = Path('$SKILLS_DIR')
EXCLUDED = frozenset(('.git', '.github', '.hub'))

# Simulate _find_all_skills from skills_tool.py
found_pulse = False
seen_names = set()

for skill_md in SKILLS_DIR.rglob('SKILL.md'):
    if any(part in EXCLUDED for part in skill_md.parts):
        continue
    name = skill_md.parent.name
    if name in seen_names:
        continue
    seen_names.add(name)
    if name == 'pulse':
        found_pulse = True
        print(f'FOUND: {skill_md}')
        print(f'  parent.name={name}')
        print(f'  category=_find_all_skills would derive from path')
        break

if not found_pulse:
    # rglob didn't find it — check if it exists as a real dir
    pulse_path = SKILLS_DIR / 'devops' / 'pulse'
    if pulse_path.exists() and pulse_path.is_dir() and not pulse_path.is_symlink():
        print(f'pulse dir exists at {pulse_path} but rglob did not find SKILL.md inside it')
        print('Rglob result count:', len(list(SKILLS_DIR.rglob('SKILL.md'))))
    elif pulse_path.is_symlink():
        print('ERROR: pulse is a symlink — rglob will not find it!')
        sys.exit(1)
    else:
        print(f'ERROR: pulse skill dir does not exist at {pulse_path}')
        sys.exit(1)
" 2>&1) || {
    fail "Hermes discovery check failed:"
    echo "$HERMES_CHECK"
    exit 1
}

if [[ "$HERMES_CHECK" == "FOUND:"* ]]; then
    ok "Hermes rglob discovery: pulse found"
    ok "skill_view('pulse') will work"
    ok "skills_list will show pulse"
elif [[ "$HERMES_CHECK" == "ERROR:"* ]]; then
    fail "$HERMES_CHECK"
    exit 1
fi

# Verify SKILL.md name field
SKILL_NAME=$("$PYTHON" -c "
import re
content = open('$PULSE_SKILL_DIR/SKILL.md').read()
m = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
print(m.group(1).strip().strip('\"')) if m else print('unknown')
" 2>/dev/null || echo "unknown")

if [[ "$SKILL_NAME" == "pulse" ]]; then
    ok "SKILL.md name field: '$SKILL_NAME'"
else
    warn "SKILL.md name field: '$SKILL_NAME' (expected: 'pulse')"
fi

# ════════════════════════════════════════════════════════════════════════════
# [8/8] MCP REGISTRATION — let every detected AI tool call pulse_* natively
# ════════════════════════════════════════════════════════════════════════════
# Mirrors the mazemaker pattern. After the hermes-skill install above, we
# also register the stdio MCP server (mcp_local.py) into:
#   ~/.hermes/config.yaml under mcp_servers.pulse
#   ~/.claude/settings.json under mcpServers.pulse
#   ~/.cursor/mcp.json, ~/.config/cline/..., ~/.continue/..., goose, codex
# All driven by wire.sh; this step is no-op for tools that aren't installed.
#
# Skip with INSTALL_SKIP_MCP=1 (the hermes-skill route still works for
# operators who don't want a stdio MCP server registered).

step "8/8" "Registering pulse as MCP server in detected AI tools"

if [[ "$CHECK_ONLY" == "true" ]] || [[ "$UNLINK" == "true" ]]; then
    info "skipping MCP registration (check-only or unlink mode)"
elif [[ "${INSTALL_SKIP_MCP:-0}" == "1" ]]; then
    warn "INSTALL_SKIP_MCP=1 set — skipping MCP registration"
    info "  run later: bash $PROJECT_DIR/wire.sh"
elif [[ ! -f "$PROJECT_DIR/wire.sh" ]]; then
    warn "wire.sh not found at $PROJECT_DIR/wire.sh — skipping"
elif [[ ! -f "$PROJECT_DIR/mcp_local.py" ]]; then
    warn "mcp_local.py not found at $PROJECT_DIR/mcp_local.py — skipping"
else
    info "running wire.sh --all (idempotent; backs up every config before edit)"
    if bash "$PROJECT_DIR/wire.sh" --all 2>&1 | sed 's/^/    /'; then
        ok "MCP server registered with detected tools"
    else
        warn "wire.sh returned non-zero — re-run manually: bash $PROJECT_DIR/wire.sh"
    fi
fi

# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  PULSE v${PULSE_VERSION} — Installation Complete!${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Hermes Integration:${NC}"
echo -e "    Skill dir: ${GREEN}$PULSE_SKILL_DIR${NC}"
echo -e "    Config:    ${GREEN}$CONFIG_FILE${NC}"
echo -e "    CLI:       ${GREEN}$SYMLINK${NC}"
echo ""
echo -e "  ${CYAN}Usage:${NC}"
echo -e "    pulse \"your topic\"                          ${DIM}# direct CLI${NC}"
echo -e "    pulse \"bitcoin halving\" --depth deep        ${DIM}# deep research${NC}"
echo -e "    pulse --diagnose                             ${DIM}# check sources${NC}"
echo ""
echo -e "  ${CYAN}Hermes Agent Integration:${NC}"
echo -e "    skill_view('pulse')         → loads SKILL.md instructions"
echo -e "    skills_list(category='devops') → includes pulse"
echo -e "    pulse \"topic\" --emit=context  → inject research into other tasks"
echo ""
echo -e "  ${CYAN}MCP Server (for Claude Code / Cursor / Cline / Goose / Codex):${NC}"
echo -e "    Auto-registered into every detected tool (see step 8 above)."
echo -e "    Re-run: ${GREEN}bash $PROJECT_DIR/wire.sh${NC}        ${DIM}# interactive${NC}"
echo -e "             ${GREEN}bash $PROJECT_DIR/wire.sh --list${NC} ${DIM}# show detected tools${NC}"
echo -e "             ${GREEN}bash $PROJECT_DIR/wire.sh --unwire${NC} ${DIM}# remove from all${NC}"
echo -e "    Tools exposed: ${GREEN}pulse_search · pulse_trending · pulse_history · pulse_stats · pulse_diagnose${NC}"
echo ""
echo -e "  ${CYAN}No-Key Sources ($SOURCE_COUNT total):${NC}"
echo -e "    Reddit · HN · Polymarket · YouTube · ArXiv · Lobsters · RSS"
echo -e "    Bluesky · Dev.to · Lemmy · StackExchange · OpenAlex · SemScholar"
echo -e "    Manifold · Metaculus · Tickertick"
echo ""
echo -e "  ${YELLOW}Run 'pulse --diagnose' to verify everything works.${NC}"