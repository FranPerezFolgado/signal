import hashlib
import string

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def compute_signal_id(artist: str, title: str) -> str:
    text = f"{_norm(artist)} {_norm(title)}"
    return hashlib.sha256(text.encode()).hexdigest()


def _norm(s: str) -> str:
    return " ".join(s.lower().translate(_PUNCT_TABLE).split())
