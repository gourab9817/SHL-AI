import re
import unicodedata


TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)?")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "for",
    "from",
    "i",
    "in",
    "is",
    "it",
    "need",
    "of",
    "on",
    "or",
    "our",
    "should",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "use",
    "we",
    "what",
    "who",
    "with",
}


def normalize_text(value: str) -> str:
    """Normalize text for matching while preserving user-facing source strings elsewhere."""
    normalized = unicodedata.normalize("NFKC", value.casefold())
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("+", " plus ")
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = re.sub(r"[^a-z0-9.]+", " ", normalized)
    return " ".join(normalized.split())


def tokenize(value: str, *, keep_stopwords: bool = False) -> tuple[str, ...]:
    normalized = normalize_text(value)
    tokens = TOKEN_PATTERN.findall(normalized)
    if keep_stopwords:
        return tuple(tokens)
    return tuple(token for token in tokens if token not in STOPWORDS)
