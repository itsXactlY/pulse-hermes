#!/usr/bin/env bash
# pulse installer - Hermes Edition
# Proof of concept. Hermes should handle the rest autonomously.
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BOLD}pulse v0.0.1 - Hermes Edition${NC}"
echo -e "${YELLOW}Proof of Concept installer${NC}"
echo ""

# Check Python version
PYTHON=""
for py in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        MAJOR=$("$py" -c 'import sys; print(sys.version_info.major)')
        MINOR=$("$py" -c 'import sys; print(sys.version_info.minor)')
        if [[ "$MAJOR" -eq 3 && "$MINOR" -ge 10 ]]; then
            PYTHON="$py"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo -e "${RED}ERROR: Python 3.10+ required. Install python3.10 or newer.${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found $PYTHON ($($PYTHON --version))"

# Verify stdlib imports
echo -n "Checking stdlib dependencies... "
"$PYTHON" -c "import json, urllib.request, concurrent.futures, dataclasses, hashlib, argparse, html" 2>/dev/null
echo -e "${GREEN}✓${NC}"

# Test import
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo -n "Testing module imports... "
"$PYTHON" -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}/scripts')
from lib import schema, dates, config, planner, normalize, score, dedupe, fusion, cluster, render, pipeline
print('all OK')
" 2>/dev/null || {
    echo -e "${RED}FAIL${NC}"
    echo "Module import failed. Check that all files are in scripts/lib/"
    exit 1
}
echo -e "${GREEN}✓${NC}"

# Create config directory
CONFIG_DIR="$HOME/.config/pulse"
mkdir -p "$CONFIG_DIR"

# Create .env template if not exists
ENV_FILE="$CONFIG_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    cat > "$ENV_FILE" << 'EOF'
# pulse configuration
# Optional API keys - uncomment and fill in as needed

# Web search (pick one):
# BRAVE_API_KEY=your_key          # Free: 2000 queries/month
# SERPER_API_KEY=your_key         # Google search via serper.dev
# EXA_API_KEY=your_key            # Semantic search via exa.ai

# GitHub:
# GITHUB_TOKEN=your_token         # Or use `gh auth login`

# News:
# NEWSAPI_KEY=your_key            # Free: 100 requests/day
EOF
    echo -e "${GREEN}✓${NC} Created config at $ENV_FILE"
else
    echo -e "${GREEN}✓${NC} Config already exists at $ENV_FILE"
fi

# Test run
echo ""
echo -n "Running diagnostics... "
"$PYTHON" "${SCRIPT_DIR}/scripts/pulse.py" --diagnose 2>/dev/null
echo ""

# Symlink for easy access
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
SYMLINK="$BIN_DIR/pulse"
if [[ ! -L "$SYMLINK" ]]; then
ln -sf "${SCRIPT_DIR}/scripts/pulse.py" "$SYMLINK"
    chmod +x "${SCRIPT_DIR}/scripts/pulse.py"
    echo -e "${GREEN}✓${NC} Created symlink at $SYMLINK"
    echo -e "  ${YELLOW}Add to PATH if needed: export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
else
    echo -e "${GREEN}✓${NC} Symlink already exists at $SYMLINK"
fi

echo ""
echo -e "${BOLD}Installation complete!${NC}"
echo ""
echo "Usage:"
echo "  pulse \"your topic\""
echo "  pulse \"bitcoin halving\" --depth deep"
echo "  pulse --diagnose"
echo ""
echo "Sources available without API keys: Reddit, Hacker News, Polymarket"
echo "Optional: Add BRAVE_API_KEY, GITHUB_TOKEN, or NEWSAPI_KEY to $ENV_FILE"
echo ""
echo -e "${YELLOW}NOTE: This is a proof-of-concept clone of mvanhorn/last30days-skill.${NC}"
echo -e "${YELLOW}Hermes should evolve this into a fully autonomous system.${NC}"
