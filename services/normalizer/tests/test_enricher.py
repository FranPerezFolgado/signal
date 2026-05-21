from unittest.mock import MagicMock

import pytest

from signal_normalizer.enricher import Enricher, EnrichmentResult
from signal_normalizer.spotify_client import AudioFeatures, SpotifyTrack


def _make_track(
    track_id: str = "t1",
    artist_id: str = "a1",
    artist_name: str = "Actress",
    genres: list[str] | None = None,
    popularity: int = 30,
) -> SpotifyTrack:
    return SpotifyTrack(
        track_id=track_id,
        artist_id=artist_id,
        artist_name=artist_name,
        genres=genres or ["electronic"],
        popularity=popularity,
    )


def _make_features() -> AudioFeatures:
    return AudioFeatures(
        energy=0.3, valence=0.2, tempo=95.0,
        danceability=0.4, acousticness=0.1, instrumentalness=0.8,
    )


class TestEnricher:
    def setup_method(self) -> None:
        self.spotify = MagicMock()
        self.lastfm = MagicMock()
        self.enricher = Enricher(self.spotify, self.lastfm)

    def test_spotify_happy_path(self) -> None:
        track = _make_track()
        features = _make_features()
        self.spotify.search_track.return_value = track
        self.spotify.get_audio_features.return_value = features

        result = self.enricher.enrich("Actress", "Ascending")

        assert result.enrichment_source == "spotify"
        assert result.pending_enrichment is False
        assert result.artist_id == "spotify:artist:a1"
        assert result.genres == ["electronic"]
        assert result.audio_features == features
        assert result.popularity == 30

    def test_spotify_found_no_audio_features(self) -> None:
        self.spotify.search_track.return_value = _make_track()
        self.spotify.get_audio_features.return_value = None

        result = self.enricher.enrich("Actress", "Ascending")

        assert result.enrichment_source == "spotify"
        assert result.pending_enrichment is False
        assert result.audio_features is None

    def test_spotify_not_found_lastfm_fallback(self) -> None:
        self.spotify.search_track.return_value = None
        self.lastfm.get_tags.return_value = ["experimental", "ambient"]

        result = self.enricher.enrich("Unknown Artist", "Rare Track")

        assert result.enrichment_source == "lastfm"
        assert result.pending_enrichment is False
        assert result.genres == ["experimental", "ambient"]
        assert result.audio_features is None
        assert result.artist_id is None

    def test_both_fail_pending(self) -> None:
        self.spotify.search_track.return_value = None
        self.lastfm.get_tags.return_value = []

        result = self.enricher.enrich("Very Obscure", "Live Bootleg")

        assert result.enrichment_source == "pending"
        assert result.pending_enrichment is True
        assert result.genres == []
        assert result.audio_features is None
        assert result.artist_id is None

    def test_spotify_retries_exhausted_falls_back_to_lastfm(self) -> None:
        self.spotify.search_track.return_value = None
        self.lastfm.get_tags.return_value = ["drone"]

        result = self.enricher.enrich("Artist", "Track")

        assert result.enrichment_source == "lastfm"
        assert result.pending_enrichment is False
        assert result.genres == ["drone"]

    def test_pending_enrichment_always_explicit(self) -> None:
        self.spotify.search_track.return_value = _make_track()
        self.spotify.get_audio_features.return_value = _make_features()
        result = self.enricher.enrich("A", "B")
        assert result.pending_enrichment is False

        self.spotify.search_track.return_value = None
        self.lastfm.get_tags.return_value = ["jazz"]
        result = self.enricher.enrich("A", "B")
        assert result.pending_enrichment is False

        self.lastfm.get_tags.return_value = []
        result = self.enricher.enrich("A", "B")
        assert result.pending_enrichment is True
