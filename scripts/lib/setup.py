"""First-run setup wizard for PULSE.

Detects available sources, guides API key setup, and creates config.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from . import config as _config
from . import log

BOLD = "\033[1m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
RED = "\033[0;31m"
NC = "\033[0m"


def _source_log(msg: str):
    log.source_log("Setup", msg)


def detect_environment() -> Dict[str, Any]:
    """Detect available tools and configurations."""
    env: Dict[str, Any] = {
        "python_version": None,
        "python_path": None,
        "ytdlp": False,
        "gh_cli": False,
        "gh_authenticated": False,
        "ollama": False,
        "ollama_models": [],
        "api_keys": {},
    }

    # Python
    env["python_path"] = sys.executable
    env["python_version"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # yt-dlp
    env["ytdlp"] = shutil.which("yt-dlp") is not None
    if not env["ytdlp"]:
        try:
            import yt_dlp
            env["ytdlp"] = True
        except ImportError:
            pass

    # gh CLI
    env["gh_cli"] = shutil.which("gh") is not None
    if env["gh_cli"]:
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, timeout=5
            )
            env["gh_authenticated"] = result.returncode == 0
        except Exception:
            pass

    # Ollama
    env["ollama"] = shutil.which("ollama") is not None
    if env["ollama"]:
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")[1:]
                env["ollama_models"] = [
                    parts[0] for line in lines
                    if (parts := line.split())
                ]
        except Exception:
            pass

    # API keys (check env and config file)
    cfg = _config.get_config()
    key_checks = {
        "BRAVE_API_KEY": "Brave Search (web)",
        "SERPER_API_KEY": "Serper/Google (web)",
        "EXA_API_KEY": "Exa (web)",
        "GITHUB_TOKEN": "GitHub",
        "NEWSAPI_KEY": "NewsAPI",
        "OPENROUTER_API_KEY": "OpenRouter (LLM planner)",
        "OPENAI_API_KEY": "OpenAI (LLM planner)",
    }

    for key, label in key_checks.items():
        val = cfg.get(key) or os.environ.get(key)
        if val:
            env["api_keys"][key] = label

    return env


def get_available_sources(env: Dict[str, Any]) -> List[str]:
    """Determine available sources from environment."""
    sources = ["reddit", "hackernews", "polymarket"]  # Always available

    if env["ytdlp"]:
        sources.append("youtube")

    if env["gh_cli"] and env["gh_authenticated"]:
        sources.append("github")

    if env["api_keys"].get("BRAVE_API_KEY") or \
       env["api_keys"].get("SERPER_API_KEY") or \
       env["api_keys"].get("EXA_API_KEY"):
        sources.append("web")

    if env["api_keys"].get("NEWSAPI_KEY"):
        sources.append("news")

    return sources


def has_llm(env: Dict[str, Any]) -> bool:
    """Check if any LLM is available for planning."""
    return bool(
        env["api_keys"].get("OPENROUTER_API_KEY") or
        env["api_keys"].get("OPENAI_API_KEY") or
        env["ollama"]
    )


def print_status(env: Dict[str, Any]) -> None:
    """Print environment status."""
    sources = get_available_sources(env)

    print(f"\n{BOLD}PULSE Environment Status{NC}\n")

    # Core
    print(f"  {GREEN}✓{NC} Python {env['python_version']}")

    # Sources
    print(f"\n  {BOLD}Sources:{NC}")
    for source in sources:
        if source in ("reddit", "hackernews", "polymarket"):
            print(f"    {GREEN}✓{NC} {source:15s} (free, no auth)")
        elif source == "youtube":
            print(f"    {GREEN}✓{NC} {source:15s} (via yt-dlp)")
        elif source == "github":
            print(f"    {GREEN}✓{NC} {source:15s} (via gh CLI)")
        elif source == "web":
            print(f"    {GREEN}✓{NC} {source:15s} (via API key)")
        elif source == "news":
            print(f"    {GREEN}✓{NC} {source:15s} (via API key)")

    # Missing optional
    missing = []
    if not env["ytdlp"]:
        missing.append(("youtube", "pip install yt-dlp"))
    if not (env["gh_cli"] and env["gh_authenticated"]):
        missing.append(("github", "gh auth login"))
    if not any(k in env["api_keys"] for k in ("BRAVE_API_KEY", "SERPER_API_KEY", "EXA_API_KEY")):
        missing.append(("web", "Add BRAVE_API_KEY to ~/.config/pulse/.env"))
    if "NEWSAPI_KEY" not in env["api_keys"]:
        missing.append(("news", "Add NEWSAPI_KEY to ~/.config/pulse/.env"))

    if missing:
        print(f"\n  {BOLD}Optional (not configured):{NC}")
        for source, hint in missing:
            print(f"    {DIM}○ {source:15s} — {hint}{NC}")

    # LLM
    print(f"\n  {BOLD}LLM Planner:{NC}")
    if has_llm(env):
        if env["api_keys"].get("OPENROUTER_API_KEY"):
            print(f"    {GREEN}✓{NC} OpenRouter (recommended)")
        elif env["api_keys"].get("OPENAI_API_KEY"):
            print(f"    {GREEN}✓{NC} OpenAI")
        if env["ollama"]:
            models = ", ".join(env["ollama_models"][:3])
            print(f"    {GREEN}✓{NC} Ollama ({models})")
    else:
        print(f"    {YELLOW}⚠{NC} No LLM — using heuristic planner")
        print(f"      {DIM}Install Ollama (ollama.ai) for smart query planning{NC}")

    print()


def run_setup() -> Dict[str, Any]:
    """Run the interactive setup wizard.

    Returns environment dict.
    """
    env = detect_environment()
    print_status(env)

    config_file = _config.CONFIG_FILE
    existing = _config.load_env_file(config_file) if config_file.exists() else {}

    # Interactive key setup
    prompts = [
        ("BRAVE_API_KEY", "Brave Search API key (free: 2000/mo)", "brave.com/search/api"),
        ("GITHUB_TOKEN", "GitHub token (or: gh auth login)", "github.com/settings/tokens"),
        ("NEWSAPI_KEY", "NewsAPI key (free: 100/day)", "newsapi.org"),
        ("OPENROUTER_API_KEY", "OpenRouter key (for LLM planner)", "openrouter.ai"),
    ]

    new_keys = {}
    for key, desc, url in prompts:
        if key in existing or key in env["api_keys"]:
            continue

        print(f"\n  {CYAN}→{NC} {desc}")
        print(f"    {DIM}Get one at: https://{url}{NC}")
        val = input(f"    Enter key (or press Enter to skip): ").strip()
        if val:
            new_keys[key] = val

    # Write config
    if new_keys:
        _config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(config_file, "a") as f:
            for key, val in new_keys.items():
                f.write(f"{key}={val}\n")
        print(f"\n  {GREEN}✓{NC} Saved {len(new_keys)} key(s) to {config_file}")

        # Update env
        for key, val in new_keys.items():
            os.environ[key] = val
            env["api_keys"][key] = True

    # Re-detect after changes
    env = detect_environment()
    env["available_sources"] = get_available_sources(env)
    env["has_llm"] = has_llm(env)

    print(f"\n  {GREEN}✓{NC} Setup complete. {len(env['available_sources'])} sources available.")
    if env["has_llm"]:
        print(f"  {GREEN}✓{NC} LLM planner active.")
    else:
        print(f"  {YELLOW}⚠{NC} No LLM — heuristic planner active.")
    print()

    return env
