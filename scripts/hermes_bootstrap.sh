#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# PULSE Hermes Agent Bootstrap
# ══════════════════════════════════════════════════════════════════════════════
#
# For Hermes agents discovering PULSE for the first time.
# This script is meant to be run by an agent, not a human.
#
# What it does:
#   1. Checks if PULSE is already installed
#   2. Clones or updates the repo
#   3. Runs the installer
#   4. Verifies everything works
#   5. Reports status
#
# Usage:
#   bash scripts/hermes_bootstrap.sh
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${BOLD}PULSE — Hermes Agent Bootstrap${NC}"
echo ""

# ─── Step 1: Check if already installed ──────────────────────────────────────
SKILL_DIR="${HERMES_HOME:-$HOME/.hermes}/skills/devops/pulse"

if [[ -f "$SKILL_DIR/SKILL.md" ]]; then
    echo -e "  ${GREEN}✓${NC} PULSE already installed at $SKILL_DIR"

    # Check if it's a symlink to a project
    if [[ -L "$SKILL_DIR" ]]; then
        TARGET=$(readlink "$SKILL_DIR")
        echo -e "  ${CYAN}→${NC} Linked to: $TARGET"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} PULSE not found — installing..."

    # ─── Step 2: Clone ───────────────────────────────────────────────────────
    PULSE_DIR="$HOME/pulse-hermes"
    if [[ -d "$PULSE_DIR/.git" ]]; then
        echo -e "  ${CYAN}→${NC} Updating existing clone..."
        cd "$PULSE_DIR"
        git pull --ff-only 2>/dev/null || true
    else
        echo -e "  ${CYAN}→${NC} Cloning..."
        git clone https://github.com/itsXactlY/pulse-hermes "$PULSE_DIR" 2>/dev/null || {
            echo -e "  ${YELLOW}⚠${NC} Clone failed — repo may not be public yet"
            echo -e "  ${CYAN}→${NC} Looking for local installation..."
            for dir in "$HOME/projects/pulse" "$HOME/pulse" "$HOME/pulse-hermes"; do
                if [[ -f "$dir/scripts/pulse.py" ]]; then
                    PULSE_DIR="$dir"
                    echo -e "  ${GREEN}✓${NC} Found at: $PULSE_DIR"
                    break
                fi
            done
        }
    fi

    # ─── Step 3: Install ─────────────────────────────────────────────────────
    if [[ -f "$PULSE_DIR/install.sh" ]]; then
        echo -e "  ${CYAN}→${NC} Running installer..."
        cd "$PULSE_DIR"
        bash install.sh 2>&1 | tail -5
    else
        echo -e "  ${YELLOW}⚠${NC} install.sh not found — manual setup needed"
    fi
fi

# ─── Step 4: Verify ─────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Verification${NC}"

PYTHON=""
for py in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        PYTHON="$py"
        break
    fi
done

if [[ -n "$PYTHON" ]]; then
    echo -e "  ${GREEN}✓${NC} Python: $($PYTHON --version 2>&1)"
else
    echo -e "  ${YELLOW}⚠${NC} Python not found"
fi

if command -v pulse &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} CLI: pulse command available"
else
    echo -e "  ${YELLOW}⚠${NC} CLI: pulse not in PATH"
fi

# ─── Step 5: Report ─────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}What to do next:${NC}"
echo -e "  1. Read: skill_view('pulse')"
echo -e "  2. Test: pulse 'your topic'"
echo -e "  3. Improve: See CONTRIBUTING.md"
echo -e "  4. Share: bash scripts/auto_commit.sh 'feat: your improvement'"
echo ""
echo -e "${CYAN}The human built the foundation. Now we refine it together.${NC}"
echo ""
