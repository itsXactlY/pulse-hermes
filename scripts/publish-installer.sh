#!/usr/bin/env bash
# publish-installer.sh — build and stage the customer-facing installer
# bundle under remainder-pod/install/ on the VPS, so customers can
# `curl -fsSL https://remainder.online/install.sh | bash`.
#
# Run on the VPS as the `mazemaker` user (it owns ~/remainder-pod):
#
#   bash publish-installer.sh                       # default: pull from github, publish
#   bash publish-installer.sh --source LOCAL_PATH   # publish from an already-checked-out repo
#   bash publish-installer.sh --dry-run             # show what would be published

set -euo pipefail

PUBLISH_ROOT="${PULSE_PUBLISH_ROOT:-$HOME/remainder-pod/install}"
SOURCE_DIR="${PULSE_SOURCE_DIR:-}"
REPO_URL="${PULSE_REPO_URL:-https://github.com/itsXactlY/pulse-hermes.git}"
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --source)   SOURCE_DIR="${2:-}"; shift 2 ;;
    --source=*) SOURCE_DIR="${1#--source=}"; shift ;;
    --root)     PUBLISH_ROOT="${2:-}"; shift 2 ;;
    --root=*)   PUBLISH_ROOT="${1#--root=}"; shift ;;
    --dry-run)  DRY_RUN=1; shift ;;
    --help|-h)  sed -n '2,12p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *)          echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

if [ -t 1 ]; then
  GREEN=$(printf '\033[0;32m'); YELLOW=$(printf '\033[0;33m')
  CYAN=$(printf '\033[0;36m'); RED=$(printf '\033[0;31m')
  RESET=$(printf '\033[0m')
else GREEN=""; YELLOW=""; CYAN=""; RED=""; RESET=""; fi

info() { printf '%s[publish-installer]%s %s\n' "$CYAN" "$RESET" "$*"; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '  %s⚠%s %s\n' "$YELLOW" "$RESET" "$*"; }
err()  { printf '  %s✗%s %s\n' "$RED" "$RESET" "$*"; }

info "publish root: $PUBLISH_ROOT"

# ── 1. acquire source ────────────────────────────────────────────────────────
if [ -n "$SOURCE_DIR" ]; then
  if [ ! -d "$SOURCE_DIR/scripts" ]; then
    err "$SOURCE_DIR does not look like a pulse-hermes checkout (no scripts/ dir)"
    exit 3
  fi
  info "using local source: $SOURCE_DIR"
else
  SOURCE_DIR="$(mktemp -d -t pulse-publish-XXXXXX)"
  trap 'rm -rf "$SOURCE_DIR"' EXIT
  info "cloning $REPO_URL into $SOURCE_DIR"
  if [ "$DRY_RUN" -eq 0 ]; then
    git clone --depth=1 "$REPO_URL" "$SOURCE_DIR/pulse-hermes" >/dev/null 2>&1
    SOURCE_DIR="$SOURCE_DIR/pulse-hermes"
  else
    info "  (dry-run: skipping clone)"
    exit 0
  fi
fi

REVISION=$(cd "$SOURCE_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
info "source revision: $REVISION"

# ── 2. build the customer source.tar.gz ─────────────────────────────────────
mkdir -p "$PUBLISH_ROOT"
TMP_PKG="$(mktemp -d)"
trap 'rm -rf "$TMP_PKG"' EXIT
WRAP="$TMP_PKG/pulse-hermes"
mkdir -p "$WRAP"

info "packaging source (excluding .git/__pycache__/tests)"
rsync -a \
  --exclude=".git" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  --exclude=".pytest_cache" \
  --exclude=".venv" \
  --exclude="venv" \
  --exclude=".DS_Store" \
  --exclude="node_modules" \
  "$SOURCE_DIR/" "$WRAP/"

echo "$REVISION" > "$WRAP/.published-revision"
date -u '+%Y-%m-%dT%H:%M:%SZ' > "$WRAP/.published-at"

TARBALL="$PUBLISH_ROOT/source.tar.gz"
TARBALL_TMP="$TARBALL.tmp.$$"
( cd "$TMP_PKG" && tar -czf "$TARBALL_TMP" pulse-hermes/ )
mv "$TARBALL_TMP" "$TARBALL"
ok "wrote $TARBALL ($(du -h "$TARBALL" | cut -f1), rev $REVISION)"

# ── 3. copy install.sh + wire.sh + mcp_local.py to the install root ────────
for f in install.sh wire.sh mcp_local.py; do
  if [ -f "$SOURCE_DIR/$f" ]; then
    install -m 0644 "$SOURCE_DIR/$f" "$PUBLISH_ROOT/$f"
    ok "published $PUBLISH_ROOT/$f"
  else
    warn "missing $SOURCE_DIR/$f — skipped"
  fi
done

# ── 4. simple human-facing index ────────────────────────────────────────────
cat > "$PUBLISH_ROOT/index.html" <<'HTML'
<!doctype html>
<meta charset="utf-8">
<title>pulse — install</title>
<style>
  body { font-family: monospace; background: #0a0a0d; color: #ededf2; padding: 4rem; max-width: 720px; margin: auto; }
  code { background: #18181f; padding: 4px 8px; border-radius: 3px; color: #a78bfa; }
  pre  { background: #18181f; padding: 1rem; border-radius: 6px; overflow-x: auto; }
  h1   { color: #a78bfa; }
  a    { color: #a78bfa; }
</style>
<h1>pulse · install</h1>
<p>One-line install (curl-pipe-bash):</p>
<pre>curl -fsSL https://remainder.online/install.sh | bash</pre>
<p>Manual download:</p>
<ul>
  <li><a href="install.sh">install.sh</a> — bootstrapping installer</li>
  <li><a href="wire.sh">wire.sh</a> — re-register MCP with installed AI tools</li>
  <li><a href="source.tar.gz">source.tar.gz</a> — full source (.git excluded)</li>
  <li><a href="mcp_local.py">mcp_local.py</a> — the MCP server itself</li>
</ul>
<p>Source: <a href="https://github.com/itsXactlY/pulse-hermes">github.com/itsXactlY/pulse-hermes</a></p>
HTML
ok "wrote $PUBLISH_ROOT/index.html"

# ── 5. summary + nginx hint ─────────────────────────────────────────────────
echo
info "published artefacts:"
( cd "$PUBLISH_ROOT" && ls -lh ) | sed 's/^/    /'
echo
ok "done — customers can now: curl -fsSL https://remainder.online/install.sh | bash"
echo
info "matching nginx location blocks (paste once, then nginx -t && systemctl reload nginx):"
cat <<NGINX

    # pulse public installer
    location = /install.sh {
        alias $PUBLISH_ROOT/install.sh;
        default_type text/x-shellscript;
        add_header Cache-Control "no-cache, max-age=0";
    }
    location = /wire.sh {
        alias $PUBLISH_ROOT/wire.sh;
        default_type text/x-shellscript;
        add_header Cache-Control "no-cache, max-age=0";
    }
    location = /mcp_local.py {
        alias $PUBLISH_ROOT/mcp_local.py;
        default_type text/x-python;
        add_header Cache-Control "no-cache, max-age=0";
    }
    location = /source.tar.gz {
        alias $PUBLISH_ROOT/source.tar.gz;
        default_type application/gzip;
        add_header Cache-Control "public, max-age=300";
    }
    location = /install/ {
        alias $PUBLISH_ROOT/;
        index index.html;
    }

NGINX
