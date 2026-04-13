"""Filter raw data items from sources before they're normalized."""

import re
from typing import Any, Dict, List

# Blocked terms (case-insensitive)
BLOCKED_TERMS = {
    "milla jovovich",
    "mempalace",
    "mem palace",
}

# Blocked URL patterns
BLOCKED_URL_PATTERNS = [
    re.compile(r"mempalace", re.IGNORECASE),
    re.compile(r"milla.*jovovich", re.IGNORECASE),
]


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


def filter_raw_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter raw data items from sources.
    
    Args:
        items: List of raw item dictionaries from sources
        
    Returns:
        Filtered list with blocked items removed
    """
    if not items:
        return items
    
    filtered = []
    blocked_count = 0
    
    for item in items:
        # Check common fields that might contain blocked content
        fields_to_check = [
            item.get("title", ""),
            item.get("description", ""),
            item.get("selftext", ""),  # Reddit
            item.get("body", ""),  # Reddit comments
            item.get("text", ""),  # Various sources
            item.get("content", ""),
            item.get("name", ""),  # GitHub
            item.get("full_name", ""),  # GitHub
        ]
        
        # Check text fields
        blocked = False
        for field in fields_to_check:
            if _contains_blocked_term(str(field)):
                blocked = True
                break
        
        if blocked:
            blocked_count += 1
            continue
        
        # Check URLs
        url_fields = [
            item.get("url", ""),
            item.get("link", ""),
            item.get("html_url", ""),  # GitHub
            item.get("permalink", ""),  # Reddit
        ]
        
        for url in url_fields:
            if _has_blocked_url(str(url)):
                blocked = True
                break
        
        if blocked:
            blocked_count += 1
            continue
        
        filtered.append(item)
    
    return filtered
