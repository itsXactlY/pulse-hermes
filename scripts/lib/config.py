"""Configuration and API key management for pulse skill."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

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
        "BING_API_KEY",
        "SERPAPI_KEY",
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


def available_sources(config: Dict[str, Any]) -> List[str]:
    """Determine which sources are available based on config."""
    import shutil
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
    elif shutil.which("gh"):
        try:
            import subprocess
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                available.append("github")
        except Exception:
            pass

    # YouTube - needs yt-dlp
    if shutil.which("yt-dlp"):
        available.append("youtube")
    else:
        try:
            import yt_dlp
            available.append("youtube")
        except ImportError:
            pass

    # ArXiv - always available (public API, no auth)
    available.append("arxiv")

    # Lobsters - always available (public JSON, no auth)
    available.append("lobsters")

    # RSS - always available if feeds configured or defaults exist
    available.append("rss")

    # OpenAlex - always available (public API, no auth)
    available.append("openalex")

    # Semantic Scholar - always available (public API, no auth)
    available.append("sem_scholar")

    # Manifold Markets - always available (public API, no auth)
    available.append("manifold")

    # Metaculus - always available (public API, no auth)
    available.append("metaculus")

    # Bluesky - always available (public AT Protocol, no auth)
    available.append("bluesky")

    # Stack Exchange - always available (public API, no auth for basic)
    available.append("stackexchange")

    # Lemmy - always available (federated, public API)
    available.append("lemmy")

    # Dev.to - always available (public API, no auth)
    available.append("devto")

    # TickerTick - always available (free crypto news aggregator)
    available.append("tickertick")

    # Bing News - needs BING_API_KEY or falls back to web_search
    if config.get("BING_API_KEY") or config.get("BRAVE_API_KEY") or config.get("SERPER_API_KEY") or config.get("EXA_API_KEY"):
        available.append("bing_news")

    # SerpAPI News - needs SERPAPI_KEY
    if config.get("SERPAPI_KEY"):
        available.append("serpapi_news")

    # Web search - needs Brave, Exa, or Serper key
    if config.get("BRAVE_API_KEY") or config.get("EXA_API_KEY") or config.get("SERPER_API_KEY"):
        available.append("web")

    # News API
    if config.get("NEWSAPI_KEY"):
        available.append("news")

    return available
