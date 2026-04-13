"""Token overlap relevance scoring."""


def token_overlap_relevance(query: str, text: str) -> float:
    """Calculate relevance based on token overlap between query and text."""
    if not query or not text:
        return 0.0

    query_tokens = set(query.lower().split())
    text_tokens = set(text.lower().split())

    if not query_tokens:
        return 0.0

    # Remove very common words
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
                  "of", "and", "or", "but", "not", "with", "this", "that", "it", "be", "by",
                  "from", "as", "do", "has", "had", "have", "will", "would", "could", "should"}
    query_tokens -= stop_words
    text_tokens -= stop_words

    if not query_tokens:
        return 0.5

    overlap = query_tokens & text_tokens
    return len(overlap) / len(query_tokens)


def extract_core_subject(topic: str) -> str:
    """Extract core subject from topic string."""
    import re
    topic = topic.strip()
    prefixes = [
        r"^last \d+ days?\s+",
        r"^what(?:'s| is| are) (?:people saying about|happening with|going on with)\s+",
        r"^how (?:is|are)\s+",
        r"^tell me about\s+",
        r"^research\s+",
        r"^search\s+",
    ]
    for pattern in prefixes:
        topic = re.sub(pattern, "", topic, flags=re.IGNORECASE)
    return topic.strip()
