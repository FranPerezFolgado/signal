# ADR-011: BaseSpotifyClient in signal_common and SpotifyServiceError

- **Status**: Accepted
- **Date**: 2026-05-24

## Context

Two services — `normalizer` (via `SpotifyClient`) and `enricher` (via `EnricherSpotifyClient`) — independently implement Spotify API access. Both require identical HTTP machinery: OAuth2 token refresh, 401-retry-with-refresh, 429/Retry-After back-off, rate limiter acquisition, and timeout handling. After the resilience feature (ADR-010), both implementations were ~60-line `_get()` methods copied verbatim. Any change to the 429 logic (e.g. adding a lower bound on `sleep_s`) had to be applied in two places. Additionally, both clients returned `None` for all failure modes — transport errors, auth failures, and clean "not found" results — making it impossible for the circuit breaker in `normalizer/app.py` to distinguish a genuine Spotify outage from a track that simply does not exist in Spotify's catalogue, causing false circuit-open events on niche/unknown tracks.

## Decision

Shared HTTP machinery is extracted into `BaseSpotifyClient` in `signal_common/spotify.py`. `_get()` raises `SpotifyServiceError` on transport, auth, and rate-limit failures, and returns a `dict` only on HTTP 200. Service-specific clients (`SpotifyClient`, `EnricherSpotifyClient`) subclass it and add only their domain methods.

## Alternatives considered

**Keep duplicate `_get()` in each service** — *Rejected*
Within one sprint the two copies already diverged (enricher lacked the `token_refreshed` guard; normalizer lacked it in the 401-retry inner block). Duplication at this level is a maintenance hazard with a well-understood fix.

**Return a result type instead of raising** — *Rejected*
A `SearchResult(artist_id, track_id, error: bool)` or `Optional[dict]` return from `_get()` requires every call site to inspect the error field. Raising `SpotifyServiceError` lets the happy path stay linear and confines error handling to the one place that knows what to do with it (the circuit breaker at the app level).

**Move entire Spotify clients (domain methods included) to signal_common** — *Rejected*
`search_track` is a normalizer concern; `get_artist_data`/`get_track_data` are enricher concerns. Putting domain methods in `signal_common` would couple the shared library to the enrichment data model and Spotify's API surface, making it harder to evolve each service independently.

**BaseSpotifyClient with SpotifyServiceError in signal_common** — *Accepted*

## Consequences

✅ Any fix to auth, 429, or timeout handling is made once in `BaseSpotifyClient` and applies to both services immediately.
✅ `SpotifyServiceError` gives circuit breakers a typed signal to catch: `(None, None)` from `search_track` now unambiguously means "track not found", not "Spotify is down", eliminating false circuit-open events under normal load with obscure tracks.
✅ Adding a third Spotify-calling service requires only subclassing `BaseSpotifyClient` and implementing domain methods; all resilience is inherited.
❌ `signal_common` now depends on the `requests` library (previously only stdlib + confluent-kafka). Any service that imports `signal_common` transitively pulls in `requests`.
❌ Subclassing couples service clients to the base class's internal `_get()` contract. If the base class signature changes (e.g. async support), all subclasses must update simultaneously.

## When to reconsider

If a third client (e.g. `artist-tracker`) needs Spotify access with materially different retry semantics (e.g. async, streaming), evaluate whether inheritance or composition (injecting an `HttpClient` into each domain client) better fits the divergent needs.
