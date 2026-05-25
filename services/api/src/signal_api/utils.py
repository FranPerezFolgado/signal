from __future__ import annotations

import json
import math

from signal_api.models import ScoreBreakdown


def parse_jsonb(value) -> dict | list | None:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def build_score_breakdown(raw) -> ScoreBreakdown | None:
    parsed = parse_jsonb(raw)
    if not parsed:
        return None
    return ScoreBreakdown(
        genre_novelty=parsed.get("genre_novelty", 0.0),
        popularity_norm=parsed.get("popularity_norm", 0.0),
    )


def calc_pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total > 0 else 0
