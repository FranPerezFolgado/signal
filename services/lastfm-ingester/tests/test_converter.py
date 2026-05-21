import json
from pathlib import Path

from signal_lastfm_ingester.converter import to_raw_play

_FIXTURES = Path(__file__).parent / "fixtures" / "lastfm_response.json"


def _tracks() -> list[dict]:
    return json.loads(_FIXTURES.read_text())["recenttracks"]["track"]


def test_nowplaying_returns_none():
    nowplaying = _tracks()[0]
    assert to_raw_play(nowplaying) is None


def test_normal_track_converts_correctly():
    track = _tracks()[1]
    result = to_raw_play(track)

    assert result is not None
    assert result["source"] == "lastfm"
    assert result["artist"] == "Actress"
    assert result["title"] == "Ascending"
    assert result["played_at"] == "2025-01-17T02:20:00+00:00"
    assert result["external_ids"]["lastfm_mbid"] == "some-mbid-123"
    assert result["raw"] is track


def test_empty_mbid_becomes_none():
    track = _tracks()[2]
    result = to_raw_play(track)

    assert result is not None
    assert result["external_ids"]["lastfm_mbid"] is None
