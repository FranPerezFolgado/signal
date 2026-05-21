from signal_normalizer.app import _build_output, _is_valid
from signal_normalizer.spotify_client import AudioFeatures
from signal_normalizer.enricher import EnrichmentResult


def _make_result(
    source: str = "spotify",
    pending: bool = False,
    genres: list[str] | None = None,
    audio: AudioFeatures | None = None,
    popularity: int | None = 30,
    artist_id: str | None = "spotify:artist:abc",
) -> EnrichmentResult:
    return EnrichmentResult(
        artist_id=artist_id,
        genres=genres if genres is not None else ["electronic"],
        audio_features=audio,
        popularity=popularity,
        pending_enrichment=pending,
        enrichment_source=source,
    )


class TestIsValid:
    def test_valid_message(self) -> None:
        assert _is_valid({"artist": "Actress", "title": "Ascending"}) is True

    def test_missing_artist(self) -> None:
        assert _is_valid({"title": "Ascending"}) is False

    def test_missing_title(self) -> None:
        assert _is_valid({"artist": "Actress"}) is False

    def test_empty_artist(self) -> None:
        assert _is_valid({"artist": "", "title": "Ascending"}) is False

    def test_whitespace_only_artist(self) -> None:
        assert _is_valid({"artist": "   ", "title": "Ascending"}) is False

    def test_whitespace_only_title(self) -> None:
        assert _is_valid({"artist": "Actress", "title": "   "}) is False

    def test_non_string_artist(self) -> None:
        assert _is_valid({"artist": 123, "title": "Ascending"}) is False

    def test_none_artist(self) -> None:
        assert _is_valid({"artist": None, "title": "Ascending"}) is False

    def test_artist_too_long(self) -> None:
        assert _is_valid({"artist": "a" * 501, "title": "Title"}) is False

    def test_artist_at_max_length(self) -> None:
        assert _is_valid({"artist": "a" * 500, "title": "Title"}) is True

    def test_empty_dict(self) -> None:
        assert _is_valid({}) is False


class TestBuildOutput:
    _RAW = {
        "artist": "Actress",
        "title": "Ascending",
        "played_at": "2026-01-15T21:30:00Z",
        "source": "lastfm",
    }

    def test_signal_id_present(self) -> None:
        out = _build_output(self._RAW, "abc123", _make_result(), "2026-01-15T21:31:00Z")
        assert out["signal_id"] == "abc123"

    def test_audio_features_mapped(self) -> None:
        audio = AudioFeatures(
            energy=0.3, valence=0.2, tempo=95.0,
            danceability=0.4, acousticness=0.1, instrumentalness=0.8,
        )
        out = _build_output(self._RAW, "x", _make_result(audio=audio), "t")
        assert out["audio_features"] == {
            "energy": 0.3, "valence": 0.2, "tempo": 95.0,
            "danceability": 0.4, "acousticness": 0.1, "instrumentalness": 0.8,
        }

    def test_audio_features_none_when_missing(self) -> None:
        out = _build_output(self._RAW, "x", _make_result(audio=None), "t")
        assert out["audio_features"] is None

    def test_pending_enrichment_false_on_spotify(self) -> None:
        out = _build_output(self._RAW, "x", _make_result(source="spotify", pending=False), "t")
        assert out["pending_enrichment"] is False

    def test_pending_enrichment_false_on_lastfm(self) -> None:
        out = _build_output(self._RAW, "x", _make_result(source="lastfm", pending=False), "t")
        assert out["pending_enrichment"] is False

    def test_pending_enrichment_true(self) -> None:
        out = _build_output(
            self._RAW, "x",
            _make_result(source="pending", pending=True, genres=[], audio=None, popularity=None, artist_id=None),
            "t",
        )
        assert out["pending_enrichment"] is True
        assert out["genres"] == []
        assert out["audio_features"] is None
        assert out["artist_id"] is None

    def test_sources_from_raw(self) -> None:
        out = _build_output(self._RAW, "x", _make_result(), "t")
        assert out["sources"] == ["lastfm"]

    def test_sources_defaults_to_lastfm(self) -> None:
        raw = {"artist": "A", "title": "B"}
        out = _build_output(raw, "x", _make_result(), "t")
        assert out["sources"] == ["lastfm"]

    def test_no_played_field(self) -> None:
        out = _build_output(self._RAW, "x", _make_result(), "t")
        assert "played" not in out
