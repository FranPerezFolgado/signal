# ADR-008 — Remove audio features and reformulate scorer with two factors

- **Status**: Accepted
- **Date**: 2026-05-23

## Context

The MVP v1 scorer used three factors:

```
score = w1 * genre_novelty_ratio + w2 * (1 - popularity_norm) + w3 * audio_distance
```

`audio_distance` measured how far a track's audio profile (energy, valence, tempo, danceability, acousticness, instrumentalness) was from the user's baseline. These features came from Spotify's `GET /v1/audio-features/{id}` endpoint.

In November 2024, Spotify deprecated `/v1/audio-features` for new applications. 100% of calls to this endpoint from new app credentials return HTTP 403. There is no migration path and no equivalent endpoint available to apps created after the deprecation date.

The Signal project uses credentials created after this date. Audio features are permanently unavailable.

## Decision

Remove `audio_distance` from the scoring formula. Reformulate with two factors:

```
score = w1 * genre_novelty_ratio + w2 * (1 - popularity_norm)
si high_priority: score *= HP_BONUS
```

Increase `w1` to 0.6 and set `w2` to 0.4 to redistribute the weight previously held by `w3`. Genre novelty is the strongest signal for editorial discovery and absorbs the lost audio dimension.

Remove `audio_features JSONB` from `listening_history` and all references to `AudioFeatures` from the codebase. The enricher does not call `/v1/audio-features`.

## Alternatives considered

**Cyanite.ai**: Third-party audio analysis API with mood, genre, and audio features. Rejected: paid service with per-call pricing, introduces a new external dependency for a factor that is secondary to genre novelty, and requires licensing review.

**getsongbpm.com**: Free API providing BPM and key. Rejected: covers only two dimensions (tempo, tonality) out of the original six, insufficient to reconstruct a meaningful `audio_distance`.

**Scraping**: Parsing Spotify's web player or third-party music databases. Rejected: fragile, violates terms of service, not a viable long-term strategy.

**Store existing data, skip for new tracks**: Keep the column and factor but treat missing values as neutral (distance = 0). Rejected: produces misleading scores where tracks without audio features appear equally distant as tracks with average profiles, corrupting the ranking signal.

## Consequences

- The scorer is simpler and more honest: it scores on what the API actually provides.
- `audio_features JSONB` column is removed from `listening_history`. Existing rows lose this data, which is acceptable because the data is no longer obtainable from the source.
- `W3` environment variable is removed from the constitution and all service configurations.
- The two-factor formula produces rankings that are directionally correct for editorial discovery: niche, genre-diverse artists score highest.
- If a future Spotify API revision restores audio features, or if an alternative source is integrated, `audio_distance` can be re-introduced with an ADR amendment.
