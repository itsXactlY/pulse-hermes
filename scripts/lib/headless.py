"""headless — playwright-backed last-resort fetcher.

DISABLED by default. Operator must opt in:

    pip install playwright && playwright install chromium
    export PULSE_PLAYWRIGHT=1

Only invoked as the final-but-one strategy in bypass.BYPASS_CHAINS
(before manual_queue), so it's never the first thing pulse tries.
The bypass module imports this module only when PULSE_PLAYWRIGHT=1,
so the chromium dependency is genuinely opt-in.

Single function: `fetch(url, timeout_s=20) -> str | None`.

Honours politeness (acquires the host token before launching the
browser; records 200 on success). Browser is reused across calls
for the lifetime of the worker process to avoid the ~2s cold-start.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from lib import politeness

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_browser = None
_playwright_ctx = None


def _get_browser():
    global _browser, _playwright_ctx
    if _browser is not None:
        return _browser
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright extras not installed. Run: "
            "pip install playwright && playwright install chromium"
        ) from exc
    with _lock:
        if _browser is None:
            _playwright_ctx = sync_playwright().start()
            _browser = _playwright_ctx.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            logger.info("headless: launched chromium")
    return _browser


def fetch(url: str, timeout_s: int = 20) -> Optional[str]:
    """Fetch URL in a real browser. Returns rendered HTML or None on failure."""
    politeness.acquire(url, timeout_s=30)
    try:
        browser = _get_browser()
    except RuntimeError as exc:
        logger.warning("headless: %s", exc)
        return None
    ctx = None
    page = None
    try:
        ctx = browser.new_context(
            user_agent=politeness.headers_for_host(url).get("User-Agent"),
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.goto(url, timeout=timeout_s * 1000, wait_until="networkidle")
        # Give SPA frameworks a moment to settle (300ms is enough for most)
        time.sleep(0.3)
        html = page.content()
        politeness.record_response(url, status_code=200)
        return html
    except Exception as exc:
        logger.warning("headless: fetch failed for %s: %s", url, exc)
        politeness.record_response(url, status_code=599)
        return None
    finally:
        try:
            if page: page.close()
        except Exception: pass
        try:
            if ctx: ctx.close()
        except Exception: pass


def shutdown() -> None:
    """Tear down the long-lived browser. Call at process exit."""
    global _browser, _playwright_ctx
    with _lock:
        if _browser is not None:
            try: _browser.close()
            except Exception: pass
            _browser = None
        if _playwright_ctx is not None:
            try: _playwright_ctx.stop()
            except Exception: pass
            _playwright_ctx = None
