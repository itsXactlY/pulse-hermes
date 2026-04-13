"""HTTP utilities for pulse skill (stdlib only)."""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode

from . import log as _log

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
MAX_429_RETRIES = 2
RETRY_DELAY = 2.0
USER_AGENT = "pulse-hermes/3.0 (Research Tool)"

DEBUG = os.environ.get("LAST30DAYS_DEBUG", "").lower() in ("1", "true", "yes")


class HTTPError(Exception):
    """HTTP request error with status code."""
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
    max_429_retries: int = MAX_429_RETRIES,
    raw: bool = False,
) -> Union[Dict[str, Any], str]:
    """Make an HTTP request with retry logic."""
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)
    headers.setdefault("Accept", "application/json")

    data = None
    if json_data is not None:
        data = json.dumps(json_data).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    if DEBUG:
        safe_url = re.sub(r"([?&])(key|api_key|token|secret)=[^&]*", r"\1\2=***", url)
        _log.debug(f"{method} {safe_url}")

    last_error = None
    rate_limit_count = 0

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                if DEBUG:
                    _log.debug(f"Response: {response.status} ({len(body)} bytes)")
                if raw:
                    return body
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body_str = None
            try:
                body_str = e.read().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                pass

            last_error = HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body_str)

            # Don't retry client errors (4xx) except 429
            if 400 <= e.code < 500 and e.code != 429:
                raise last_error

            if e.code == 429:
                rate_limit_count += 1
                if rate_limit_count >= max_429_retries:
                    raise last_error
                retry_after = e.headers.get("Retry-After") if hasattr(e, "headers") else None
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = RETRY_DELAY * (2 ** attempt) + 1
                else:
                    delay = RETRY_DELAY * (2 ** attempt) + 1
                if DEBUG:
                    _log.debug(f"Rate limited (429). Waiting {delay:.1f}s before retry")
                time.sleep(delay)
                continue

            if attempt < retries - 1:
                delay = RETRY_DELAY * (2 ** attempt)
                time.sleep(delay)
        except urllib.error.URLError as e:
            last_error = HTTPError(f"URL Error: {e.reason}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except json.JSONDecodeError as e:
            last_error = HTTPError(f"Invalid JSON response: {e}")
            raise last_error
        except (OSError, TimeoutError, ConnectionResetError) as e:
            last_error = HTTPError(f"Connection error: {type(e).__name__}: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

    if last_error:
        raise last_error
    raise HTTPError("Request failed with no error details")


def get(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a GET request."""
    return request("GET", url, headers=headers, **kwargs)


def post(url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a POST request with JSON body."""
    return request("POST", url, headers=headers, json_data=json_data, **kwargs)


def get_text(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Make a GET request and return raw text."""
    return request("GET", url, headers=headers, timeout=timeout, raw=True)


def get_reddit_json(path: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Fetch Reddit thread JSON."""
    url = f"https://www.reddit.com{path}.json"
    headers = {"User-Agent": USER_AGENT}
    return get(url, headers=headers, timeout=timeout)
