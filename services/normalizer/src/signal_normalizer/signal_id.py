import hashlib
import string

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize_text(s: str) -> str:
    """Lowercase + strip ASCII punctuation + collapse whitespace.

    Non-ASCII letters (Cyrillic, Japanese, Arabic, accented-Latin) are preserved
    as-is per spec clarification. Only ASCII punctuation (string.punctuation) is
    removed. Unicode typographic characters such as em-dashes are intentionally
    kept — this matches the "preserve non-ASCII" decision from the spec.
    """
    return " ".join(s.lower().translate(_PUNCT_TABLE).split())


def compute_signal_id(artist: str, title: str) -> str:
    text = f"{normalize_text(artist)} {normalize_text(title)}"
    return hashlib.sha256(text.encode()).hexdigest()
