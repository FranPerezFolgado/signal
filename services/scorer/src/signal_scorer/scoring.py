def validate_message(msg: dict) -> None:
    """Raise ValueError if the message is missing required fields or has invalid values."""
    if not isinstance(msg.get("signal_id"), str):
        raise ValueError("missing or invalid signal_id")
    if not isinstance(msg.get("artist"), str):
        raise ValueError("missing or invalid artist")
    novelty = msg.get("novelty_signals")
    if not isinstance(novelty, dict):
        raise ValueError("missing novelty_signals")
    ratio = novelty.get("genre_novelty_ratio")
    if not isinstance(ratio, (int, float)) or not (0.0 <= ratio <= 1.0):
        raise ValueError(f"genre_novelty_ratio out of range or missing: {ratio!r}")


def compute_score(
    genre_novelty_ratio: float,
    artist_popularity: int | None,
    high_priority: bool,
    w1: float,
    w2: float,
    hp_bonus: float,
) -> tuple[float, dict]:
    popularity_norm = (artist_popularity if artist_popularity is not None else 0) / 100.0
    genre_novelty = w1 * genre_novelty_ratio
    pop_component = w2 * (1.0 - popularity_norm)
    raw = genre_novelty + pop_component
    score = min(raw * hp_bonus, 1.0) if high_priority else min(raw, 1.0)
    breakdown = {
        "genre_novelty": round(genre_novelty, 4),
        "popularity_norm": round(pop_component, 4),
    }
    return score, breakdown
