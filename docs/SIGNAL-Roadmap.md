# SIGNAL — Roadmap

> Written: 2026-05-25. Update as phases complete.
> The architecture reference is `SIGNAL-Architecture.md`. The MVP implementation detail is `SIGNAL — MVP v2.md`.

---

## Current state: MVP v2 complete

All 8 services are implemented and wired into Docker Compose:

| Service | Status | Notes |
|---|---|---|
| `lastfm-ingester` | ✅ Done | Polling + full-history flag, checkpoint by timestamp |
| `normalizer` | ✅ Done | Schema unification, Spotify ID resolution, new artist detection |
| `enricher` | ✅ Done | Rate limiter + circuit breaker + backoff, Last.fm fallback |
| `history-tracker` | ✅ Done | Upsert, play_count + scrobble_count tracking |
| `novelty-detector` | ✅ Done | Go 1.23 (migration complete; see ADR-017, ADR-018) |
| `scorer` | ✅ Done | 2-factor score (genre_novelty + popularity_norm) |
| `artist-tracker` | ✅ Done | Polling top-tracks of FOLLOWING artists |
| `api` | ✅ Done | FastAPI + Swagger UI, full artist lifecycle endpoints |

The pipeline runs end-to-end: Last.fm scrobbles → Kafka → normalizer → enricher → novelty-detector → scorer → PostgreSQL → API.

The artist onboarding script (`scripts/onboarding.py`) classifies existing artists on first run.

**Startup sequence**: `make up` → `python scripts/onboarding.py` (once) → `make api-up`

---

## Immediate cleanup (before starting v3)

Low-effort tasks that reduce technical debt from the MVP sprint:

- [ ] **Integration / e2e test suite** — end-to-end test that spins up the stack and validates the full pipeline: scrobble in → artist appears in recommendations
- [ ] **Scorer service review** — the scorer was not formally reviewed; run `/review` and apply findings
- [ ] **`ArtistStatus` migration** — non-API services still use raw strings; import from `signal_common.models.ArtistStatus` for consistency
- [ ] **CI per service** — GitHub Actions pipeline with tests + linting + Docker build for each service; add status badge to each service README
- [ ] **Service-level READMEs** — one README per service with: what it does, env vars, how to run locally, how to test

---

## v3 — Graph expansion + Go migration

**Goal**: real artist discovery beyond direct listening history. The MVP `artist-tracker` only fetches top-tracks of artists you already follow. v3 adds actual graph expansion.

### artist-tracker: Last.fm `artist.getSimilar`

Spotify deprecated `/v1/artists/{id}/related-artists` for new apps. The natural alternative is **Last.fm `artist.getSimilar`**, which is free and available.

The expanded loop:
1. For each `FOLLOWING` artist: fetch similar artists via Last.fm `artist.getSimilar`
2. New artists not yet in the DB → emit to `artist.discovered` with `source=LASTFM_SIMILAR`
3. `artist-tracker` picks them up, inserts as `TRACKED`, and starts monitoring their top-tracks

This closes the discovery loop: you follow an artist → Signal finds artists like them → those appear in your TRACKED queue for review.

**Scope**:
- Add `GET /artist.getSimilar` call in `artist-tracker` (alongside existing top-tracks polling)
- `artist.discovered` topic already exists and is already consumed
- New `source` value: `LASTFM_SIMILAR` (schema already supports it as free-text)
- Respect Last.fm rate limits; share the existing backoff primitive from `signal_common`

### ADRs to write for v3

- **ADR-014 — Last.fm `artist.getSimilar` as graph expansion source**: why not MusicBrainz or a paid alternative; why Last.fm; what the precision/recall trade-off looks like at 1-hop expansion

> **Note**: novelty-detector Go migration is ✅ complete. See ADR-017 and ADR-018.

---

## v4 — Dashboard

**Goal**: replace Swagger UI with a real personal curation interface. The API already exposes all the endpoints the dashboard needs.

**Stack**: React + Vite (decided in `SIGNAL-Architecture.md` — no SSR, no Next.js, personal use only).

**Four sections**:

1. **TRACKED queue** (daily use) — artists pending review, ordered by score; `high_priority` artists first; inline actions: follow / blacklist; evidence tracks visible; genre/source filters
2. **FOLLOWING** — artists you've validated, pending publication; recent tracks; publish / blacklist actions
3. **Stats** — novel ratio over time, genres discovered per month, new artists per week, score distribution, most active sources
4. **Exploration** — new genres detected in the period; recently discovered artists by graph expansion

**Structure**: `dashboard/` in the monorepo root. Vite proxy to `localhost:8000` for local dev.

**Prerequisite**: the `/stats/*` endpoints in the API are stubbed; they need real queries before the dashboard stats section works (see v5).

---

## v5 — Stats collector

**Goal**: materialise pipeline aggregations in PostgreSQL for the dashboard stats section.

### New service: `stats-collector`

- Read-only Kafka consumer: subscribes to `tracks.normalized`, `tracks.novel`, `recommendations`
- No business logic, no Kafka production
- Writes aggregated rows to a `stats` table (or multiple tables) in PostgreSQL

**What it tracks**:

| Metric | Source topic |
|---|---|
| Tracks processed per hour/day | `tracks.normalized` |
| Novel ratio (% new tracks) per period | `tracks.novel` |
| New genres discovered per month | `tracks.novel` |
| Score distribution | `recommendations` |
| Most active sources (Spotify vs Last.fm) | `tracks.normalized` |
| New artists per week | `recommendations` |

**Implementation approach**: simple `INSERT ... ON CONFLICT DO UPDATE` per time-bucket. Full SQL aggregation on read; only pre-materialise what's slow. PostgreSQL is sufficient — no TimescaleDB.

### API `/stats/*` endpoints

The API already has the route stubs. Wire them up once `stats-collector` is writing data:

```
GET /stats               # tracks processed, novel ratio, artists by status
GET /stats/history       # time series
GET /stats/genres        # genres discovered per month
GET /stats/sources       # source activity breakdown
GET /stats/artists       # new artists per period, top by score
```

---

## v6 — Curators

**Goal**: add editorial signal sources. A curator is not an artist — it is a source that generates `artist.discovered` events.

### New service: `curator-aggregator`

Curator types:
- **YouTube channel** (Boiler Room, Cercle, NTS Live, label channels): parse tracklist/description → artists → `artist.discovered`
- **RSS feed** (Resident Advisor, FACT, Pitchfork, Bandcamp Daily): parse mentioned artists → `artist.discovered`
- **Spotify playlist** (editorial playlists, label playlists): artists from recently added tracks → `artist.discovered`

All emit with `source=CURATOR:{curator_id}`. The `artist-tracker` picks them up as `TRACKED` → normal pipeline.

### Curator precision metric

```
precision = artists_in_FOLLOWING_or_PUBLISHED / total_artists_generated
```

This tells you which curators align with your taste. High-precision curators get a bonus in the scorer (configurable weight).

### New API endpoints

```
GET  /curators                       # all curators
GET  /curators?status=ACTIVE
POST /curators                       # add curator (YouTube, RSS, Spotify playlist)
POST /curators/{id}/pause
POST /curators/{id}/archive
GET  /curators/{id}/artists          # artists discovered through this curator
GET  /stats/curators                 # precision per curator
```

### New Kafka topic

`editorial.signals` — emitted by `curator-aggregator`; consumed by scorer as an optional additional factor.

---

## v7 — Observability (partial ✅) and CI/CD

**Goal**: production-ready instrumentation and automated pipelines.

### Observability

**Done (feature 019)**:
- Prometheus metrics in all services via `signal_common.metrics`: `signal_events_consumed_total`, `signal_events_produced_total`, `signal_processing_errors_total`
- kafka-exporter for consumer group lag (`kafka_consumergroup_lag_sum`)
- Grafana "Signal Pipeline" dashboard: throughput, consumer lag, error rates
- Optional `tools` Docker Compose profile (`make obs-up`); see ADR-023

**Remaining**:
- **OpenTelemetry traces**: spans per Kafka message and per external API call (Spotify, Last.fm) — Prometheus counters cover aggregate rates but not per-request latency
- **Circuit breaker state metric**: expose enricher CB state as a Prometheus gauge
- **Alerting**: Alertmanager rules for lag > threshold, novel ratio == 0, polling loop stalled

### CI/CD

**Done**:
- GitHub Actions per service: lint (ruff) + type check (mypy) + test (pytest) + Docker build
- End-to-end pipeline smoke test in CI

**Remaining**:
- **Schema Registry**: formalise Kafka topic schemas with Avro/JSON Schema Registry; break the build if a producer changes schema without a migration

---

## v8 — Kubernetes

**Goal**: move from Docker Compose to a self-hosted Kubernetes cluster on the ZimaBoard, then optionally to cloud.

### k3s on ZimaBoard

- k3s (lightweight Kubernetes, single-node)
- One Helm chart per service
- Stateful workloads (PostgreSQL, Kafka) managed via Helm with persistent volumes
- Secrets via Kubernetes Secrets (or Vault if needed)

### Cloud (optional, future)

- EKS + Terraform
- One environment per stage (local k3s → staging EKS → prod EKS)
- Only warranted if the personal use case expands to multi-user or higher availability requirements

---

## v9 — Editorial aggregation (future)

**Goal**: fully automated editorial signal without manual curator setup.

- Web scraping of music editorial sites (Resident Advisor reviews, Pitchfork, FACT)
- NLP extraction of artist mentions from article text
- Signal weight based on publication authority score
- `editorial.signals` topic feeds directly into scorer

This is speculative and depends on v6 curators proving the value of editorial signal in practice.

---

## Priority order

```
Immediate cleanup  →  v3 (graph + Go)  →  v4 (dashboard)  →  v5 (stats)
→  v6 (curators)  →  v7 (observability + CI/CD)  →  v8 (k8s)
```

v4 and v5 are inter-dependent (dashboard needs stats endpoints); build them in the same sprint.
v6 is independent — can be built in parallel with v4/v5.
v7 should start alongside v4 rather than after — retrofitting observability is harder than adding it as you go.

---

## What this unlocks at each phase

| Phase | What you gain |
|---|---|
| Cleanup | Confidence the MVP is solid; CI catches regressions |
| v3 | Artists Signal discovers that you never listened to — the core discovery value prop |
| v4 | Daily use without Swagger UI; real curation workflow |
| v5 | Visibility into whether the pipeline is actually working |
| v6 | Passive discovery from trusted editorial sources |
| v7 | Production-grade reliability; automated safety net |
| v8 | Always-on pipeline without a laptop running |
