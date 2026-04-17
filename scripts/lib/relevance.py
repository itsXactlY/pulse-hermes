"""Token overlap relevance scoring with bigram/trigram support."""

import re
from collections import Counter


_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
    "of", "and", "or", "but", "not", "with", "this", "that", "it", "be", "by",
    "from", "as", "do", "has", "had", "have", "will", "would", "could", "should",
    "be", "been", "being", "can", "may", "might", "must", "shall", "should",
    "about", "above", "after", "again", "all", "also", "am", "any", "because",
    "before", "between", "both", "each", "few", "more", "most", "other", "some",
    "such", "than", "too", "very", "just", "into", "over", "own", "same", "so",
    "still", "up", "down", "out", "off", "now", "then", "here", "there", "when",
    "where", "why", "how", "what", "which", "who", "whom", "while", "during",
})


def _tokenize(text: str) -> list[str]:
    """Tokenize and filter stop words."""
    words = re.findall(r'\w+', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def _bigrams(tokens: list[str]) -> list[str]:
    """Generate bigrams from token list."""
    return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]


def _trigrams(tokens: list[str]) -> list[str]:
    """Generate trigrams from token list."""
    return [f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}" for i in range(len(tokens) - 2)]


def token_overlap_relevance(query: str, text: str) -> float:
    """Calculate relevance based on unigram + bigram overlap between query and text.

    Uses weighted combination: 60% unigram, 30% bigram, 10% trigram.
    Better at matching phrases like "machine learning" vs separate words.
    """
    if not query or not text:
        return 0.0

    q_tokens = _tokenize(query)
    t_tokens = _tokenize(text)

    if not q_tokens:
        return 0.5

    # Unigram overlap (Jaccard)
    q_set = set(q_tokens)
    t_set = set(t_tokens)
    unigram_score = len(q_set & t_set) / len(q_set) if q_set else 0.0

    # Bigram overlap
    q_bigrams = set(_bigrams(q_tokens))
    t_bigrams = set(_bigrams(t_tokens))
    bigram_score = 0.0
    if q_bigrams:
        bigram_score = len(q_bigrams & t_bigrams) / len(q_bigrams)

    # Trigram overlap (only if enough tokens)
    trigram_score = 0.0
    if len(q_tokens) >= 3:
        q_trigrams = set(_trigrams(q_tokens))
        t_trigrams = set(_trigrams(t_tokens))
        if q_trigrams:
            trigram_score = len(q_trigrams & t_trigrams) / len(q_trigrams)

    # Weighted combination
    score = 0.6 * unigram_score + 0.3 * bigram_score + 0.1 * trigram_score
    return min(1.0, score)


def cosine_similarity(text1: str, text2: str) -> float:
    """Cosine similarity between two texts using term frequency vectors.

    Useful for semantic-ish comparison without embeddings.
    """
    tokens1 = _tokenize(text1)
    tokens2 = _tokenize(text2)

    if not tokens1 or not tokens2:
        return 0.0

    freq1 = Counter(tokens1)
    freq2 = Counter(tokens2)

    # Dot product
    common = set(freq1.keys()) & set(freq2.keys())
    dot = sum(freq1[w] * freq2[w] for w in common)

    # Magnitudes
    mag1 = sum(v ** 2 for v in freq1.values()) ** 0.5
    mag2 = sum(v ** 2 for v in freq2.values()) ** 0.5

    if mag1 == 0 or mag2 == 0:
        return 0.0

    return dot / (mag1 * mag2)


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
