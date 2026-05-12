# Signal

Sistema de discovery de artistas musicales. Pipeline event-driven que ingesta historial de Last.fm, normaliza con Spotify, detecta artistas nuevos y los puntúa por novedad.

## Stack
- **Lenguaje**: Python 3.12 (todos los servicios del MVP; novelty-detector migra a Go en v2)
- **Messaging**: Kafka + Zookeeper
- **BD**: PostgreSQL
- **API**: FastAPI + Swagger UI
- **Infra**: Docker Compose (sin cloud, sin K8s en el MVP)

## Servicios (MVP)
| Servicio | Descripción |
|---|---|
| `lastfm-ingester` | Polling Last.fm → topic `raw.plays` |
| `normalizer` | Enriquece con Spotify (géneros, audio features) → `tracks.normalized` |
| `history-tracker` | Persiste historial en PostgreSQL → `listening.history` |
| `novelty-detector` | Detecta artistas/géneros nuevos → `tracks.novel` |
| `scorer` | Score multi-factor (genre novelty + underground + audio distance) → PostgreSQL |
| `artist-tracker` | Expansión 1-salto via Spotify related-artists → `raw.tracks` |
| `api` | FastAPI + Swagger UI para gestionar artistas y ver recomendaciones |

## Topics Kafka
raw.plays → tracks.normalized → listening.history / tracks.novel → scorer → PostgreSQL

## Estados de artista
TRACKED → FOLLOWING → PUBLISHED / BLACKLISTED
- Onboarding: Spotify follows → FOLLOWING; plays ≥ INITIAL_HIGH_PRIORITY_PLAYS → TRACKED high_priority
- Auto-promoción: plays ≥ AUTO_FOLLOW_PLAYS → FOLLOWING

## Estructura del repo
signal/
├── infra/docker-compose.yml   # Kafka + Zookeeper + PostgreSQL
├── services/                  # Un directorio por servicio Python
├── shared/python-common/      # Kafka client, logging, modelos compartidos
├── scripts/onboarding.py      # Clasificación inicial (ejecutar una vez)
└── docs/                      # Indexado por QMD (colección: signal)
    ├── adr/                   # ADRs — YYYY-MM-DD-título.md
    └── sessions/              # Resúmenes de sesión

## ADRs pendientes de escribir
001 Kafka vs colas simples · 002 PostgreSQL vs NoSQL · 003 Python MVP / Go v2
004 Fallback de enriquecimiento · 005 Artista como objeto principal · 006 Clasificación inicial

## Arranque de sesión
1. /recall — carga contexto previo desde QMD
2. Si el codebase no está indexado: index_repository vía codebase-memory-mcp

## Convenciones
- Commits en inglés, formato Conventional Commits
- ADRs en docs/decisions/YYYY-MM-DD-título.md
- Sesiones guardadas con /save-session tema
- Orden de arranque obligatorio: docker compose up → scripts/onboarding.py → servicios
