"""Configuration and API key management for pulse skill."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "pulse"
CONFIG_FILE = CONFIG_DIR / ".env"


def load_env_file(path: Path) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env = {}
    if not path or not path.exists():
        return env

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key and value:
                    env[key] = value
    return env


def get_config() -> dict[str, Any]:
    """Load configuration from env vars and config files."""
    # Load from config file
    file_env = load_env_file(CONFIG_FILE) if CONFIG_FILE else {}

    # Priority: environment variables > config file
    keys = [
        "BRAVE_API_KEY",
        "EXA_API_KEY",
        "SERPER_API_KEY",
        "GITHUB_TOKEN",
        "SCRAPECREATORS_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "NEWSAPI_KEY",
    ]

    config = {}
    for key in keys:
        config[key] = os.environ.get(key) or file_env.get(key)

    # Check for gh CLI
    gh_token = os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        try:
            import shutil
            if shutil.which("gh"):
                import subprocess
                result = subprocess.run(
                    ["gh", "auth", "token"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    config["GITHUB_TOKEN"] = result.stdout.strip()
        except Exception:
            pass

    return config


def available_sources(config: dict[str, Any]) -> list[str]:
    """Determine which sources are available based on config."""
    available = []

    # Reddit - always available (public JSON)
    available.append("reddit")

    # Hacker News - always available (Algolia, no auth)
    available.append("hackernews")

    # Polymarket - always available (Gamma API, no auth)
    available.append("polymarket")

    # GitHub - needs gh CLI or token
    if config.get("GITHUB_TOKEN"):
        available.append("github")

    # Web search - needs Brave, Exa, or Serper key
    if config.get("BRAVE_API_KEY") or config.get("EXA_API_KEY") or config.get("SERPER_API_KEY"):
        available.append("web")

    # News API
    if config.get("NEWSAPI_KEY"):
        available.append("news")

    return available
