from dataclasses import dataclass, field

from signal_normalizer.spotify_client import AudioFeatures, SpotifyClient, SpotifyTrack


@dataclass
class EnrichmentResult:
    artist_id: str | None
    genres: list[str]
    audio_features: AudioFeatures | None
    popularity: int | None
    pending_enrichment: bool
    enrichment_source: str  # "spotify" | "lastfm" | "pending"


class Enricher:
    def __init__(self, spotify: SpotifyClient, lastfm: "LastfmFallbackClient") -> None:  # type: ignore[name-defined]
        self._spotify = spotify
        self._lastfm = lastfm

    def enrich(self, artist: str, title: str) -> EnrichmentResult:
        track = self._spotify.search_track(artist, title)
        if track is not None:
            features = self._spotify.get_audio_features(track.track_id)
            return EnrichmentResult(
                artist_id=f"spotify:artist:{track.artist_id}",
                genres=track.genres,
                audio_features=features,
                popularity=track.popularity,
                pending_enrichment=False,
                enrichment_source="spotify",
            )

        tags = self._lastfm.get_tags(artist, title)
        if tags:
            return EnrichmentResult(
                artist_id=None,
                genres=tags,
                audio_features=None,
                popularity=None,
                pending_enrichment=False,
                enrichment_source="lastfm",
            )

        return EnrichmentResult(
            artist_id=None,
            genres=[],
            audio_features=None,
            popularity=None,
            pending_enrichment=True,
            enrichment_source="pending",
        )
