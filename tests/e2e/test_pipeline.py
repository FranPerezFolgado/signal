"""
Full pipeline smoke test: tracks.enriched → recommendation in PostgreSQL.

Covers: history-tracker, novelty-detector, scorer.
"""

import pytest

from helpers import stack_available, wait_for_recommendation

pytestmark = pytest.mark.skipif(
    not stack_available(),
    reason="Live stack not available — run 'make up && make services-up' first",
)


def test_enriched_track_produces_recommendation(e2e_artist):
    artist_name = e2e_artist["artist_name"]
    signal_id = e2e_artist["signal_id"]

    rec = wait_for_recommendation(artist_name, timeout=60)

    assert rec is not None, (
        f"No recommendation for artist '{artist_name}' after 60 s. "
        "Check that history-tracker, novelty-detector, and scorer are all running."
    )
    assert 0.0 <= rec["score"] <= 1.0, f"Expected score in [0, 1], got {rec['score']}"
    assert signal_id in (rec["evidence_tracks"] or []), (
        f"signal_id '{signal_id}' missing from evidence_tracks: {rec['evidence_tracks']}"
    )
