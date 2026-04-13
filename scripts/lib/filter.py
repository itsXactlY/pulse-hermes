"""Content filtering for PULSE.

Blocks specific terms, topics, or content that should be excluded from results.
"""

import re
from typing import List, Set

from . import log
from .schema import SourceItem

# Blocked terms (case-insensitive)
BLOCKED_TERMS = {
    "milla jovovich",
    "mempalace",
    "mem palace",
}

# Blocked URL patterns
BLOCKED_URL_PATTERNS: List[re.Pattern] = [
    re.compile(r"mempalace", re.IGNORECASE),
    re.compile(r"milla.*jovovich", re.IGNORECASE),
]


def _source_log(msg: str):
    log.source_log("Filter", msg)


def _contains_blocked_term(text: str) -> bool:
    """Check if text contains any blocked terms."""
    if not text:
        return False
    
    text_lower = text.lower()
    for term in BLOCKED_TERMS:
        if term in text_lower:
            return True
    return False


def _has_blocked_url(url: str) -> bool:
    """Check if URL matches any blocked patterns."""
    if not url:
        return False
    
    for pattern in BLOCKED_URL_PATTERNS:
        if pattern.search(url):
            return True
    return False


def filter_items(items: List[SourceItem]) -> List[SourceItem]:
    """Filter out items containing blocked terms or URLs.
    
    Args:
        items: List of SourceItems to filter
        
    Returns:
        Filtered list with blocked items removed
    """
    if not items:
        return items
    
    filtered = []
    blocked_count = 0
    
    for item in items:
        # Check title (both SourceItem and Candidate have this)
        if _contains_blocked_term(item.title):
            _source_log(f"Blocked by title: {item.title[:50]}...")
            blocked_count += 1
            continue
        
        # Check body (SourceItem) or snippet (Candidate)
        text_to_check = ""
        if hasattr(item, 'body'):
            text_to_check = item.body or ""
        elif hasattr(item, 'snippet'):
            text_to_check = item.snippet or ""
        
        if text_to_check and _contains_blocked_term(text_to_check):
            _source_log(f"Blocked by text: {item.title[:50]}...")
            blocked_count += 1
            continue
        
        # Check URL (both have this)
        if _has_blocked_url(item.url):
            _source_log(f"Blocked by URL: {item.url}")
            blocked_count += 1
            continue
        
        # Check explanation if available (Candidate)
        if hasattr(item, 'explanation') and _contains_blocked_term(item.explanation or ""):
            _source_log(f"Blocked by explanation: {item.title[:50]}...")
            blocked_count += 1
            continue
        
        filtered.append(item)
    
    if blocked_count > 0:
        _source_log(f"Filtered out {blocked_count} blocked items")
    
    return filtered


def add_blocked_term(term: str):
    """Add a term to the blocklist."""
    BLOCKED_TERMS.add(term.lower())
    _source_log(f"Added blocked term: {term}")


def remove_blocked_term(term: str):
    """Remove a term from the blocklist."""
    BLOCKED_TERMS.discard(term.lower())
    _source_log(f"Removed blocked term: {term}")


def get_blocked_terms() -> Set[str]:
    """Get current blocklist."""
    return BLOCKED_TERMS.copy()
