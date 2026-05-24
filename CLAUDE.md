# Signal

Musical artist discovery system. Event-driven pipeline that ingests Last.fm listening history, normalises with Spotify, detects new artists, and scores them by novelty.

## Stack
- **Language**: Python 3.12 (all MVP services; novelty-detector migrates to Go in v2)
- **Messaging**: Kafka (KRaft mode, no Zookeeper)
- **DB**: PostgreSQL
- **API**: FastAPI + Swagger UI
- **Infra**: Docker Compose (no cloud, no K8s in the MVP)

## Services (MVP v2)
| Service | Description |
|---|---|
| `lastfm-ingester` | Polls Last.fm → topic `raw.plays` |
| `normalizer` | ID resolution only (Spotify search) → `tracks.normalized` |
| `enricher` | Genres + popularity via Spotify/Last.fm fallback → `tracks.enriched` |
| `history-tracker` | Persists history + artist upsert in PostgreSQL → `listening.history` |
| `novelty-detector` | Detects new artists/genres → `tracks.novel` |
| `scorer` | 2-factor score (genre_novelty + popularity_norm) → PostgreSQL |
| `artist-tracker` | 1-hop expansion via Spotify related-artists → `raw.tracks` |
| `api` | FastAPI + Swagger UI to manage artists and view recommendations |

## Kafka Topics
raw.plays → tracks.normalized → tracks.enriched → listening.history / tracks.novel → scorer → PostgreSQL

## Artist States
TRACKED → FOLLOWING → PUBLISHED / BLACKLISTED
- Onboarding: Spotify follows → FOLLOWING; plays ≥ INITIAL_HIGH_PRIORITY_PLAYS → TRACKED high_priority
- Auto-promotion: plays ≥ AUTO_FOLLOW_PLAYS → FOLLOWING

## Repo Structure
signal/
├── infra/
│   ├── docker-compose.yml     # Kafka (KRaft) + PostgreSQL
│   └── postgres/init.sql      # Initial schema
├── services/                  # One directory per Python service
├── shared/python-common/      # Kafka client, logging, shared models
├── scripts/onboarding.py      # Initial classification (run once)
└── docs/                      # Indexed by QMD (collection: signal)
    ├── adr/                   # ADRs — ADR-XXX-title.md
    └── sessions/              # Session summaries

## ADRs pending
Python MVP / Go v2 · Artist as primary entity · Initial classification

## QMD Collection
Active collection: `signal`

## Session startup
1. /recall — loads previous context from QMD
2. If codebase is not indexed: index_repository via codebase-memory-mcp

## Conventions
- Commits in English, Conventional Commits format
- ADRs in docs/adr/ADR-XXX-title.md
- Sessions saved with /save-session topic
- Mandatory startup order: make up → scripts/onboarding.py → services

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan at
`specs/008-scorer/plan.md`
<!-- SPECKIT END -->
