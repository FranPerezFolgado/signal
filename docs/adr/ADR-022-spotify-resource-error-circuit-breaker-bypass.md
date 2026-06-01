# ADR-022: SpotifyResourceError Subclass for Circuit-Breaker Bypass

- **Status**: Accepted
- **Date**: 2026-06-01

## Context

ADR-011 introduced `BaseSpotifyClient` and `SpotifyServiceError` as a single exception type for all Spotify API failures. The `artist-tracker` wraps Spotify calls with a circuit breaker (`CircuitBreaker.record_failure()`) to stop issuing requests when Spotify is genuinely unavailable. When investigating why the circuit breaker was opening every cycle, it emerged that all 470 FOLLOWING artists return HTTP 403 on the `/top-tracks` endpoint — a combination of the deprecated `market=from_token` parameter and the Spotify app not being approved for extended quota mode. These 403s are permanent: they will not resolve by retrying, and they affect every artist equally. Under the original code, five cumulative 403s opened the circuit and skipped every remaining artist in the cycle, making the top-tracks cycle effectively a no-op beyond the first few artists.

## Decision

A `SpotifyResourceError(SpotifyServiceError)` subclass is added to `signal_common/spotify.py` for HTTP 403 and 404 responses. The `artist-tracker` catches `SpotifyResourceError` before `SpotifyServiceError`: it logs a warning, increments `skipped`, and does **not** call `circuit_breaker.record_failure()`.

## Alternatives considered

**Treat 403/404 as non-failures at the `_get()` level (return None or empty dict)** — *Rejected*
Returning a sentinel from `_get()` would break the existing contract (callers expect either a `dict` or an exception) and would require every call site to add a None-check. It also makes it impossible to distinguish "resource not found" from "Spotify is down" at the call site.

**Lower the circuit-breaker failure threshold** — *Rejected*
A higher threshold would merely delay the circuit opening, not fix it. With 470 artists all returning 403, any threshold short of 470 still breaks the cycle partway through.

**Filter out artists with no valid Spotify access before the cycle** — *Rejected*
The 403s are caused by a Spotify app-level permission issue (extended quota mode), not by individual artist data. Pre-filtering would require a separate API call per artist to detect the condition, doubling Spotify traffic, and the filter would have to be invalidated and re-run every time the Spotify app's approval status changes.

**SpotifyResourceError subclass, caught before SpotifyServiceError in artist-tracker** — *Accepted*

## Consequences

✅ Circuit-breaker semantics are preserved for genuine service outages (5xx, timeouts, auth failures) without being triggered by permanent per-resource errors that can never be resolved by retry.
✅ `SpotifyResourceError` is a subclass of `SpotifyServiceError`, so existing `except SpotifyServiceError` handlers in `normalizer` and `enricher` continue to catch it without modification.
✅ The `artist-tracker` top-tracks cycle now runs to completion, logging each 403 as a `skipped` rather than aborting at the fifth artist.
❌ The root cause (Spotify app not approved for extended quota mode) is unresolved. The top-tracks cycle processes all artists but produces zero tracks until the Spotify app's quota is approved — this requires action in the Spotify Developer Dashboard, not in code.
❌ The distinction between 403 ("forbidden — permanent") and 404 ("not found — permanent") is collapsed into one exception. If a future endpoint needs to handle 403 and 404 differently, `SpotifyResourceError` will need to be further subclassed or carry a status code field.

## When to reconsider

If the Spotify app is approved for extended quota mode and top-tracks calls start succeeding, verify that `circuit_breaker.record_failure()` is still not being called for genuine 403s from other endpoints (e.g. artist data calls on blacklisted artists). If the 403/404 distinction matters for a new use case, split `SpotifyResourceError` into `SpotifyForbiddenError` and `SpotifyNotFoundError`.
