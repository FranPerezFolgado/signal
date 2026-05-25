# SIGNAL — MVP v2

> Versión actualizada del MVP tras el trabajo real con el pipeline.
> Incorpora las decisiones tomadas a partir de los logs reales del normalizer:
> separación de responsabilidades en el enricher, deprecación de audio features de Spotify,
> y estrategia de resiliencia con rate limiter + circuit breaker + backoff.
>
> La visión completa del sistema está en `SIGNAL_Architecture.md`.

---

## Qué cambia respecto a la v1 del MVP

| Cambio | Motivo |
|---|---|
| `normalizer` ya no llama a Spotify para enriquecer | El MAXPOLL de Kafka ocurría porque el normalizer bloqueaba el hilo esperando Spotify |
| Nuevo servicio `enricher` | Responsabilidad única: enriquecer tracks. Con rate limiter + circuit breaker + backoff |
| `audio_features` eliminado del scorer | Spotify deprecó `/v1/audio-features` en noviembre 2024. No hay alternativa equivalente |
| Scorer reformulado con 2 factores | `genre_novelty_ratio` + `popularity`. Más simple, más honesto, funciona con lo que Spotify sí da |
| Endpoints de Spotify redefinidos | Solo los disponibles para apps nuevas: `/artists/{id}`, `/tracks/{id}`, `/search` |
| `related-artists` eliminado del artist-tracker | También deprecado. El MVP usa `top-tracks` de artistas `FOLLOWING` |
| Kafka UI añadida al docker-compose | Útil para monitorizar lag del enricher en tiempo real |
| 2 ADRs nuevos (007 y 008) | Documentan las decisiones tomadas a partir de fallos reales |

---

## Qué resuelve el MVP v2

Una sola pregunta: **¿qué artistas han aparecido en mis escuchas recientes que no conocía, y cuánto se alejan de lo que ya escucho?**

Nada más. Sin expansión de grafo completa, sin curadores, sin dashboard, sin Go, sin SoundCloud.

---

## Qué NO está en el MVP v2

- `artist-tracker` con expansión de grafo real (Last.fm `artist.getSimilar` → v3)
- `stats-collector` y métricas
- `curator-aggregator` y curadores
- `novelty-detector` en Go (Python en MVP, Go en v3)
- Dashboard React
- `soundcloud-ingester`
- Schema Registry
- Observabilidad (OpenTelemetry + Grafana)
- CI/CD
- Kubernetes

---

## Stack del MVP v2

| Componente | Tecnología |
|---|---|
| Messaging | Kafka + Zookeeper + Kafka UI |
| Servicios | Python 3.12 |
| BD | PostgreSQL |
| API | FastAPI + Swagger UI |
| Infra | Docker Compose |

El MVP v2 tiene **7 servicios**: `lastfm-ingester`, `normalizer`, `enricher`, `history-tracker`, `novelty-detector`, `scorer`, `artist-tracker` y `api`.

---

## Endpoints de Spotify disponibles para el MVP v2

Spotify deprecó en noviembre 2024 los endpoints más útiles para análisis musical para apps nuevas. Los endpoints disponibles que usa el MVP son:

| Endpoint | Qué da | Dónde se usa |
|---|---|---|
| `GET /search?type=track,artist` | Resolver ID de Spotify desde nombre | normalizer |
| `GET /artists/{id}` | géneros, popularidad, followers | enricher |
| `GET /tracks/{id}` | popularidad del track, duración, ISRC | enricher |
| `GET /artists/{id}/top-tracks` | top tracks del artista | artist-tracker |
| `GET /me/following?type=artist` | artistas que sigues | script onboarding |

**Deprecados y no disponibles**: `/v1/audio-features`, `/v1/recommendations`, `/v1/artists/{id}/related-artists`.

---

## Pipeline del MVP v2

```mermaid
flowchart TD
    subgraph PASIVO[ingesta pasiva · lo que escuchas]
        LFM[lastfm-ingester\nPython]
        RP[raw.plays]
        LFM --> RP
    end

    subgraph ACTIVO[descubrimiento activo · top-tracks de FOLLOWING]
        AT[artist-tracker\nPython]
        RT[raw.tracks]
        AT -->|GET top-tracks\nSpotify API| RT
    end

    RP --> NRM
    RT --> NRM

    NRM[normalizer\nPython · schema + resolver ID]
    TN[tracks.normalized]
    NRM --> TN

    ENR[enricher\nPython · rate limiter + CB + backoff]
    TE[tracks.enriched]
    TN --> ENR --> TE

    HT[history-tracker\nPython]
    LH[listening.history]
    TE --> HT
    HT --> LH
    HT -.->|persiste| PG

    ND[novelty-detector\nPython]
    TNV[tracks.novel]
    LH -.->|consulta| ND
    TE --> ND --> TNV

    SCR[scorer\nPython]
    TNV --> SCR
    SCR -.->|persiste| PG

    PG[(PostgreSQL)]
    API[api\nFastAPI]
    PG -->|lee| API
    PG -.->|artistas FOLLOWING| AT

    style LFM fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style AT  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style NRM fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style ENR fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style HT  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style ND  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style SCR fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style API fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style RP  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style RT  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TN  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TE  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style LH  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TNV fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style PG  fill:#185FA5,color:#E6F1FB,stroke:#0C447C
```

7 servicios. 6 topics. 1 base de datos. 1 API.

El cambio clave: `tracks.normalized` → `enricher` → `tracks.enriched`. El normalizer ya no bloquea el consumer de Kafka esperando a Spotify.

---

## Diagrama de resiliencia del enricher

```mermaid
flowchart TD
    TN[tracks.normalized\ntopic Kafka]
    TN --> RL

    subgraph ENRICHER[enricher]
        RL[rate limiter\ntoken bucket]
        CB[circuit breaker\nCLOSED / OPEN / HALF-OPEN]
        CALL[Spotify API\nGET /artists + GET /tracks]
        BO[backoff exponencial\n1s → 2s → 4s + jitter]

        RL -->|slot disponible| CB
        RL -->|sin slot| WAIT[espera slot\nsin bloquear Kafka]
        WAIT --> CB
        CB -->|CLOSED| CALL
        CB -->|OPEN| FAST[falla rápido]
        CALL -->|error| BO
        BO -->|N fallos acumulados| CB
    end

    CALL -->|éxito| TE[tracks.enriched\ngéneros + popularidad]
    FAST --> TF[tracks.enriched\npending_enrichment=true]

    style RL   fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style CB   fill:#BA7517,color:#FAEEDA,stroke:#854F0B
    style CALL fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style BO   fill:#A32D2D,color:#FCEBEB,stroke:#791F1F
    style FAST fill:#A32D2D,color:#FCEBEB,stroke:#791F1F
    style WAIT fill:#888780,color:#F1EFE8,stroke:#5F5E5A
    style TE   fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TF   fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TN   fill:#534AB7,color:#EEEDFE,stroke:#3C3489
```

---

## Fase 0 — Infraestructura base

**Duración estimada**: 1 sesión
**Objetivo**: Kafka, PostgreSQL y Kafka UI levantados y verificados.

### Tareas

- [x] Crear repo `signal` en GitHub con estructura de monorepo
- [x] Escribir `CLAUDE.md` en la raíz con el contexto del sistema
- [x] `infra/docker-compose.yml` con Kafka (KRaft) + Kafka UI + PostgreSQL + dbmate (ADR-009)
- [x] Verificar Kafka UI en `localhost:8080`
- [x] Crear schema inicial de PostgreSQL

### Kafka UI en docker-compose

```yaml
kafka-ui:
  image: provectuslabs/kafka-ui:latest
  ports:
    - "8080:8080"
  environment:
    KAFKA_CLUSTERS_0_NAME: signal
    KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
  depends_on:
    - kafka
```

### Schema PostgreSQL inicial

```sql
CREATE TABLE listening_history (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id          TEXT NOT NULL UNIQUE,
  artist             TEXT NOT NULL,
  artist_id          TEXT,
  title              TEXT NOT NULL,
  genres             TEXT[],
  played_at          TIMESTAMPTZ,
  sources            TEXT[],
  artist_popularity  INT,
  track_popularity   INT,
  pending_enrichment BOOLEAN DEFAULT false,
  created_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_listening_history_artist ON listening_history(artist);
CREATE INDEX idx_listening_history_genres ON listening_history USING GIN(genres);

CREATE TABLE artists (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name             TEXT NOT NULL,
  external_ids     JSONB,
  status           TEXT NOT NULL DEFAULT 'TRACKED',
  high_priority    BOOLEAN DEFAULT false,
  source           TEXT,
  genres           TEXT[],
  popularity       INT,
  play_count       INT DEFAULT 0,
  added_at         TIMESTAMPTZ DEFAULT now(),
  first_seen_at    TIMESTAMPTZ DEFAULT now(),
  last_explored_at TIMESTAMPTZ
);

CREATE TABLE artist_recommendations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artist_id       UUID REFERENCES artists(id),
  score           FLOAT NOT NULL,
  score_breakdown JSONB,
  evidence_tracks JSONB,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);
```

> `audio_features JSONB` eliminado. No hay datos de audio disponibles con la API actual de Spotify.

### ✅ Validación

- `docker compose up` arranca sin errores
- Kafka UI accesible en `localhost:8080`
- Tablas creadas en PostgreSQL
- Puedes producir y consumir un mensaje de prueba en Kafka

---

## Fase 1 — lastfm-ingester

**Duración estimada**: 1-2 sesiones
**Objetivo**: historial de Last.fm fluyendo a `raw.plays`.

### Tareas

- [x] Crear `services/lastfm-ingester/`
- [x] API key de Last.fm (gratuita)
- [x] Polling de `user.getRecentTracks` con paginación
- [x] Emitir a `raw.plays`
- [x] Checkpoint por timestamp: no re-emitir plays ya procesados
- [x] Flag `--full-history` para ingesta histórica con delay configurable entre páginas

### Schema `raw.plays`

```json
{
  "source": "lastfm",
  "artist": "Actress",
  "title": "Ascending",
  "played_at": "2026-01-15T21:30:00Z",
  "external_ids": { "lastfm_mbid": "..." },
  "raw": {}
}
```

### ✅ Validación

- Mensajes visibles en `raw.plays` en Kafka UI
- Checkpoint funciona: reanudar sin duplicados
- Ingesta histórica completa sin errores

---

## Fase 2 — normalizer

**Duración estimada**: 1-2 sesiones
**Objetivo**: schema unificado en `tracks.normalized`. El normalizer NO enriquece — solo normaliza y resuelve IDs.

### Responsabilidades del normalizer (y lo que NO hace)

Hace:
- Normalizar el schema a campos comunes
- Calcular `signal_id` = sha256 de `artist+title` normalizado
- Resolver el Spotify ID via `GET /search` — con timeout corto (2s), sin reintentos
- Detectar artistas nuevos e insertarlos como `TRACKED`

No hace:
- Obtener géneros (eso es el enricher)
- Obtener popularidad (eso es el enricher)
- Esperar a Spotify si tarda (si falla la búsqueda, emite con `spotify_id: null`)

### Schema `tracks.normalized`

```json
{
  "signal_id": "abc123...",
  "artist": "Actress",
  "artist_id": "spotify:artist:3G3Gdm4...",
  "track_id": "spotify:track:5CXokd...",
  "title": "Ascending",
  "sources": ["lastfm"],
  "played": true,
  "played_at": "2026-01-15T21:30:00Z",
  "processed_at": "2026-01-15T21:31:00Z"
}
```

### ✅ Validación

- Mensajes en `tracks.normalized` en Kafka UI
- El normalizer no acumula lag aunque Spotify search tarde
- Tabla `artists` se va poblando con artistas nuevos

---

## Fase 3 — enricher

**Duración estimada**: 2-3 sesiones
**Objetivo**: enriquecer tracks con géneros y popularidad. Servicio independiente con resiliencia completa.

### Por qué el enricher es un servicio separado

En la v1 del MVP el normalizer llamaba a Spotify durante el procesado del mensaje de Kafka. Esto provocó que el `max.poll.interval.ms` (300s) se excediera, Kafka expulsó al consumer, y se acumularon más de 61.000 mensajes de lag. El parche fácil habría sido aumentar el timeout. La decisión correcta es separar responsabilidades: el normalizer no bloquea nunca, el enricher gestiona la dependencia de Spotify con sus propios mecanismos.

### Endpoints que usa el enricher

```
GET /artists/{spotify_artist_id}
  → genres: ["electronic", "ambient"]
  → popularity: 42
  → followers.total: 12000

GET /tracks/{spotify_track_id}
  → popularity: 28
  → duration_ms: 245000
  → external_ids.isrc: "..."
```

### Mecanismos de resiliencia

**Rate limiter (token bucket)**: consume tokens a un ritmo configurable. Cuando no hay tokens, espera sin hacer poll a Kafka — el lag se acumula en el topic, que es exactamente para lo que sirve Kafka. Evita los 403 por exceder el límite de Spotify.

**Circuit breaker**: tres estados. Se abre tras `CIRCUIT_BREAKER_FAILURE_THRESHOLD` errores consecutivos. En `OPEN` falla rápido y emite con `pending_enrichment=true`. Tras `CIRCUIT_BREAKER_TIMEOUT_S` segundos pasa a `HALF-OPEN` y prueba una llamada.

**Backoff exponencial con jitter**: `wait = BASE * 2^attempt + random(0, BASE)`. El jitter evita que múltiples reintentos lleguen a Spotify a la vez (thundering herd).

### Estrategia de fallback

```
1. Spotify GET /artists + GET /tracks  →  géneros + popularidad completos
2. Si Spotify no encuentra             →  Last.fm track.getInfo  →  tags como géneros
3. Si tampoco                          →  pending_enrichment=true, sin géneros
```

### Schema `tracks.enriched`

```json
{
  "signal_id": "abc123...",
  "artist": "Actress",
  "artist_id": "spotify:artist:3G3Gdm4...",
  "track_id": "spotify:track:5CXokd...",
  "title": "Ascending",
  "genres": ["electronic", "experimental"],
  "artist_popularity": 42,
  "track_popularity": 28,
  "sources": ["lastfm"],
  "played": true,
  "played_at": "2026-01-15T21:30:00Z",
  "enrichment_source": "spotify",
  "pending_enrichment": false,
  "processed_at": "2026-01-15T21:31:05Z"
}
```

### ✅ Validación

- Mensajes en `tracks.enriched` con géneros y popularidad
- En Kafka UI: el consumer group del enricher tiene lag bajo y estable
- Si Spotify devuelve 429, el enricher emite `pending_enrichment=true` y sigue procesando sin caerse
- El circuit breaker pasa a OPEN tras varios fallos y a HALF-OPEN tras el timeout

---

## Fase 4 — history-tracker

**Duración estimada**: 1 sesión
**Objetivo**: historial persistido en PostgreSQL. Consume de `tracks.enriched`.

### Tareas

- [x] Crear `services/history-tracker/`
- [x] Consumir `tracks.enriched`
- [x] Upsert en `listening_history` por `signal_id`
- [x] Actualizar `play_count` en tabla `artists`
- [x] Emitir a `listening.history`

### ✅ Validación

- Tabla `listening_history` con tracks, géneros y popularidad
- `play_count` actualizado en `artists`
- Upsert idempotente: mismo track dos veces no genera duplicado

---

## Fase 5 — onboarding de artistas

**Duración estimada**: 1 sesión
**Objetivo**: clasificar correctamente los artistas del historial previo antes de arrancar el pipeline.

### Orden de arranque obligatorio

```
1. docker compose up               (infra)
2. python scripts/onboarding.py    (solo la primera vez)
3. arrancar servicios del pipeline
```

### Lógica del script

```
GET /me/following?type=artist  →  status = FOLLOWING
play_count ≥ INITIAL_HIGH_PRIORITY_PLAYS  →  status = TRACKED, high_priority = true
resto  →  status = TRACKED
```

### Diagrama de onboarding

```mermaid
flowchart TD
    START([script onboarding\nuna sola vez])
    START --> SPO[GET /me/following\nSpotify]
    SPO --> FOL[FOLLOWING]
    START --> REST[resto de artistas]
    REST --> CHK{play_count ≥\nINITIAL_HIGH_PRIORITY_PLAYS?}
    CHK -->|sí| THP[TRACKED\nhigh_priority=true]
    CHK -->|no| TRK[TRACKED]
    FOL --> PG[(PostgreSQL)]
    THP --> PG
    TRK --> PG

    style START fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style SPO   fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style REST  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style FOL   fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style THP   fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TRK   fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style PG    fill:#185FA5,color:#E6F1FB,stroke:#0C447C
    style CHK   fill:#888780,color:#F1EFE8,stroke:#5F5E5A
```

### ✅ Validación

- Artistas que sigues en Spotify tienen `status=FOLLOWING`
- Artistas con muchos plays tienen `high_priority=true`
- `SELECT status, count(*) FROM artists GROUP BY status` muestra distribución correcta

---

## Fase 6 — novelty-detector

**Duración estimada**: 2 sesiones
**Objetivo**: detectar artistas y géneros nuevos. Consume de `tracks.enriched`.

### Métricas de escucha disponibles en `artists`

| Columna | Representa | Uso en novelty-detector |
|---|---|---|
| `play_count` | Amplitud de catálogo — nº de canciones distintas escuchadas del artista | Verificar si un artista supera `AUTO_FOLLOW_PLAYS` para promover a `FOLLOWING` |
| `scrobble_count` | Intensidad de escucha — total de plays procesados por el pipeline | Señal de intensidad: un artista nuevo con `scrobble_count` alto ya tiene tracción real |

### Tareas

- [ ] Crear `services/novelty-detector/` (Python; Go en v3)
- [ ] Consumir `tracks.enriched`
- [ ] Calcular `genre_novelty_ratio` y `artist_is_new`
- [ ] Si hay novedad → emitir a `tracks.novel`
- [ ] Si artista nuevo supera `AUTO_FOLLOW_PLAYS` (comparar con `scrobble_count`) → promover a `FOLLOWING`

### Schema `tracks.novel`

```json
{
  "signal_id": "...",
  "artist": "Actress",
  "artist_id": "spotify:artist:...",
  "genres": ["footwork", "experimental"],
  "artist_popularity": 42,
  "track_popularity": 28,
  "novelty_signals": {
    "track_is_new": true,
    "artist_is_new": true,
    "new_genres": ["footwork"],
    "known_genres": ["experimental"],
    "genre_novelty_ratio": 0.5
  }
}
```

### ✅ Validación

- Tracks de artistas conocidos con géneros conocidos NO aparecen en `tracks.novel`
- Tracks de artistas nuevos SÍ aparecen con `artist_is_new=true`

---

## Fase 7 — scorer

**Duración estimada**: 1-2 sesiones
**Objetivo**: puntuar artistas candidatos con la fórmula reformulada sin audio features.

### Fórmula de scoring v2

```
score = (
  w1 * genre_novelty_ratio      # géneros nuevos para ti (0-1)
  + w2 * (1 - popularity_norm)  # artistas menos mainstream son más interesantes (0-1)
)

si high_priority: score *= HP_BONUS
```

**Por qué no hay `audio_distance`**: Spotify deprecó `/v1/audio-features` en noviembre 2024. No hay endpoint equivalente para apps nuevas. Se elimina el factor y se redistribuye el peso hacia género. Decisión documentada en ADR-008.

### Inputs disponibles de la tabla `artists`

| Columna | Uso en scorer |
|---|---|
| `scrobble_count` | **Intensidad de escucha** — usar para ponderar o filtrar artistas con poca escucha real |
| `play_count` | Amplitud de catálogo — indica variedad de tracks escuchados, no frecuencia |
| `high_priority` | Multiplicador `HP_BONUS` si `true` |

> `scrobble_count` es la métrica recomendada para medir afinidad con un artista. `play_count` mide amplitud, no intensidad.

### Tareas

- [ ] Crear `services/scorer/`
- [ ] Consumir `tracks.novel`
- [ ] Calcular score con 2 factores
- [ ] Aplicar `HP_BONUS` si `high_priority=true`
- [ ] Upsert en `artist_recommendations`

### ✅ Validación

- Tabla `artist_recommendations` con scores entre 0 y 1
- Artistas `high_priority` tienen scores más altos
- Cambiar pesos en `.env` cambia el ranking sin tocar código

---

## Fase 8 — artist-tracker (versión simple)

**Duración estimada**: 1-2 sesiones
**Objetivo**: descubrimiento activo mediante top tracks de artistas `FOLLOWING`.

> `GET /artists/{id}/related-artists` fue deprecado por Spotify en noviembre 2024. El MVP usa `GET /artists/{id}/top-tracks`, que sí está disponible. La expansión real del grafo via `Last.fm artist.getSimilar` queda para v3.

### Tareas

- [ ] Crear `services/artist-tracker/`
- [ ] Polling cada `ARTIST_TRACKER_INTERVAL_HOURS` horas
- [ ] Para cada artista `FOLLOWING` con `last_explored_at` antiguo:
  - `GET /artists/{id}/top-tracks` → emitir a `raw.tracks`
- [ ] Actualizar `last_explored_at`

### Schema `raw.tracks`

```json
{
  "source": "spotify",
  "artist": "Actress",
  "artist_id": "spotify:artist:...",
  "track_id": "spotify:track:...",
  "title": "Ascending",
  "origin": {
    "type": "ARTIST_TOP_TRACKS",
    "origin_artist_id": "spotify:artist:..."
  },
  "raw": {}
}
```

### Diagrama del bucle de descubrimiento activo

```mermaid
flowchart LR
    PG[(PostgreSQL\nartistas FOLLOWING)]
    AT[artist-tracker]
    SPO[Spotify\nGET /artists/top-tracks]
    RT[raw.tracks]
    NRM[normalizer]
    ENR[enricher]
    ND[novelty-detector]

    PG -->|cada N horas| AT
    AT -->|GET top-tracks| SPO
    SPO --> AT
    AT --> RT --> NRM --> ENR --> ND

    style AT  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style NRM fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style ENR fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style ND  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style RT  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style PG  fill:#185FA5,color:#E6F1FB,stroke:#0C447C
    style SPO fill:#185FA5,color:#E6F1FB,stroke:#0C447C
```

### ✅ Validación

- Tracks de artistas `FOLLOWING` aparecen en `raw.tracks`
- `last_explored_at` se actualiza tras cada ciclo
- El novelty-detector los detecta como nuevos si no estaban en tu historial

---

## Fase 9 — api

**Duración estimada**: 1-2 sesiones
**Objetivo**: endpoints para gestionar el universo de artistas desde Swagger UI.

### Endpoints del MVP v2

```
GET  /artists?status=TRACKED                       # cola pendiente de valorar
GET  /artists?status=TRACKED&high_priority=true    # cola prioritaria
GET  /artists?status=FOLLOWING                     # en seguimiento activo
GET  /artists/{id}                                 # detalle + score + tracks de evidencia
GET  /artists/search?q=Actress                     # buscar en Spotify para alta manual
POST /artists                                      # alta manual → FOLLOWING directo
POST /artists/{id}/follow                          # TRACKED → FOLLOWING
POST /artists/{id}/blacklist                       # → BLACKLISTED
POST /artists/{id}/publish                         # → PUBLISHED

GET  /stats/basic                                  # tracks procesados, artistas por status
```

### ✅ Validación final del MVP v2

- Swagger UI en `localhost:8000/docs`
- Cola de artistas `TRACKED` ordenada por score
- Puedes marcar artistas como `FOLLOWING`, `BLACKLISTED`, `PUBLISHED`
- Puedes buscar y añadir un artista manualmente
- Pipeline completo: escuchas en Last.fm → aparece procesado en BD en minutos
- Kafka UI en `localhost:8080`: enricher con lag bajo y estable incluso si Spotify va lento

---

## Diagrama de estados de artistas

```mermaid
stateDiagram-v2
    [*] --> FOLLOWING   : seguido en Spotify (onboarding)
    [*] --> TRACKED_HP  : plays ≥ umbral (onboarding, high_priority)
    [*] --> TRACKED     : historial normal (onboarding)
    [*] --> FOLLOWING   : añadido manualmente

    TRACKED    --> FOLLOWING   : plays ≥ AUTO_FOLLOW_PLAYS (auto)
    TRACKED    --> FOLLOWING   : POST /follow
    TRACKED    --> BLACKLISTED : POST /blacklist
    TRACKED_HP --> FOLLOWING   : plays ≥ AUTO_FOLLOW_PLAYS (auto)
    TRACKED_HP --> FOLLOWING   : POST /follow
    TRACKED_HP --> BLACKLISTED : POST /blacklist

    FOLLOWING  --> PUBLISHED   : POST /publish
    FOLLOWING  --> BLACKLISTED : POST /blacklist
    PUBLISHED  --> FOLLOWING   : nuevo contenido detectado

    note right of TRACKED_HP : score con bonus HP_BONUS
    note right of FOLLOWING  : artist-tracker explora top-tracks
```

---

## Variables de entorno del MVP v2

```env
# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# PostgreSQL
DATABASE_URL=postgresql://signal:signal@localhost:5432/signal

# Last.fm
LASTFM_API_KEY=...
LASTFM_USERNAME=...

# Spotify OAuth
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REFRESH_TOKEN=...

# Onboarding
INITIAL_HIGH_PRIORITY_PLAYS=20

# Enricher — resiliencia
SPOTIFY_RATE_LIMIT_PER_30S=180
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT_S=60
BACKOFF_BASE_S=1
BACKOFF_MAX_S=30
LASTFM_FALLBACK_ENABLED=true

# Novelty detector
AUTO_FOLLOW_PLAYS=3

# Scorer
W1=0.6
W2=0.4
HP_BONUS=1.2

# Artist tracker
ARTIST_TRACKER_INTERVAL_HOURS=6
ARTIST_REEXPLORE_DAYS=7
```

---

## Estructura de repositorio del MVP v2

```
signal/
├── CLAUDE.md
├── infra/
│   └── docker-compose.yml        # Kafka + Zookeeper + Kafka UI + PostgreSQL
├── services/
│   ├── lastfm-ingester/          # Python
│   ├── normalizer/               # Python · schema + resolver ID Spotify
│   ├── enricher/                 # Python · rate limiter + circuit breaker + backoff
│   ├── history-tracker/          # Python
│   ├── artist-tracker/           # Python · top-tracks de artistas FOLLOWING
│   ├── novelty-detector/         # Python (Go en v3)
│   ├── scorer/                   # Python
│   └── api/                      # Python / FastAPI
├── shared/
│   └── python-common/            # Kafka client wrapper, logging, modelos compartidos
├── scripts/
│   └── onboarding.py             # clasificación inicial, se ejecuta una vez
└── README.md
```

---

## ADRs del MVP v2

✅ = escrito · ⬜ = pendiente

### ✅ 001 — Kafka sobre colas simples o llamadas directas
Múltiples consumers del mismo stream sin acoplamiento, replay para recalibrar el scorer sin re-ingestar, ritmos de ingesta distintos entre lastfm-ingester y artist-tracker.

### ✅ 002 — PostgreSQL sobre NoSQL
Los datos son relacionales con joins y agregaciones. JSONB cubre campos variables. El volumen no justifica solución distribuida. Neo4j solo si el grafo multi-salto lo requiere en el futuro.

### ✅ 003 — Python para todos los servicios del MVP (Go en v3)
SDKs maduros en Python, velocidad de desarrollo en MVP. El novelty-detector es el candidato natural para Go: lógica acotada, set membership, sin ORM.

### ✅ 004 — Estrategia de enriquecimiento: Spotify → Last.fm → pending
Cadena de fallback en vez de descartar. Perder tracks underground sería perder exactamente la señal más valiosa para curación editorial. Actualizado en ADR-007: el enricher, no el normalizer, es el propietario de esta cadena.

### ✅ 005 — Dead Letter Queue pattern
Mensajes que no pueden procesarse se publican en un topic DLQ (`history-tracker.dlq`) para inspección y reintento manual, en lugar de ser descartados silenciosamente.

### ⬜ 006 — Clasificación inicial: Spotify follows + plays
Por qué no fecha de corte (arbitraria y frágil). Por qué no onboarding manual completo (fricción excesiva). El gesto de "seguir en Spotify" es la señal más limpia de interés editorial.

### ✅ 007 — Separación de normalizer y enricher ⭐
**Contexto real**: en la v1 el normalizer llamaba a Spotify durante el procesado del mensaje de Kafka. El `max.poll.interval.ms` (300s) se excedió por 423ms, Kafka expulsó al consumer, y se acumularon 61.436 mensajes de lag.

**Decisión**: separar en dos servicios. El normalizer solo normaliza y resuelve IDs (timeout corto, sin reintentos). El enricher gestiona la dependencia de Spotify con rate limiter, circuit breaker y backoff.

**Alternativa descartada**: aumentar `max.poll.interval.ms`. Habría ocultado el problema sin resolverlo — el normalizer seguiría siendo frágil ante cualquier lentitud de Spotify.

### ✅ 008 — Eliminación de audio features y reformulación del scorer ⭐
**Contexto real**: Spotify deprecó `/v1/audio-features` en noviembre 2024 para apps nuevas. El 100% de las llamadas devuelven 403. No hay endpoint equivalente disponible.

**Decisión**: eliminar `audio_distance` de la fórmula. Reformular con dos factores: `genre_novelty_ratio` (w1=0.6) y `popularity_norm` (w2=0.4). Aumentar el peso de género para compensar.

**Alternativas evaluadas**: Cyanite (de pago), getsongbpm.com (solo BPM/tonalidad), scraping (inestable). Ninguna justifica una dependencia de terceros para un factor secundario.

**Trade-off aceptado**: menor granularidad sobre el "sonido" del track. A cambio, sistema más simple, sin dependencias externas de pago, y los dos factores disponibles son suficientes para curación editorial.

### ✅ 009 — dbmate como herramienta de migraciones de schema
**Contexto**: `init.sql` solo se ejecuta en volúmenes vacíos. El MVP v2 requirió tres cambios de schema en una base de datos existente (drop `audio_features`, rename `popularity` → `artist_popularity`, add `track_popularity` y `pending_enrichment`).

**Decisión**: dbmate ejecutado como servicio one-shot en docker-compose con `--wait up`. Migraciones en `infra/postgres/migrations/`. `init.sql` mantiene el schema final para instalaciones limpias; las migraciones cubren upgrades in-place.

**Alternativas descartadas**: Alembic (requiere ORM/modelos para un proyecto sin ORM), Flyway/Liquibase (JVM, overhead innecesario), scripts SQL manuales (no trackeados, no idempotentes).

---

## Bullets de CV del MVP v2

| Logro | Bullet |
|---|---|
| Pipeline Kafka con 6 topics | Designed and implemented an event-driven artist discovery pipeline using Kafka, connecting 7 decoupled Python services processing music data from Last.fm and Spotify |
| Diagnóstico y fix del MAXPOLL | Identified and resolved a Kafka consumer MAXPOLL failure (61k message lag) caused by synchronous Spotify calls inside the normalizer; decoupled enrichment into a dedicated service |
| Resiliencia del enricher | Built a resilient Spotify enrichment service combining token-bucket rate limiting, circuit breaker (CLOSED/OPEN/HALF-OPEN), and exponential backoff with jitter |
| Scorer adaptado a API real | Reformulated scoring engine after Spotify deprecated audio features; designed a 2-factor model (genre novelty + underground factor) using only available API endpoints, documented as ADR |
| Enriquecimiento con fallback | Built enrichment fallback chain (Spotify → Last.fm tags → pending flag) preserving underground tracks not indexed by Spotify |
| Clasificación de artistas | Designed artist lifecycle state machine with automatic promotion via play-count thresholds and Spotify follow signal |
| Decisiones documentadas | Documented 9 ADRs including two driven by real production failures (MAXPOLL bug, Spotify API deprecation), demonstrating iterative architectural decision-making |

### Cómo presentarlo en entrevista

Los ADR-007 y ADR-008 son el material más valioso. Demuestran que encontraste un problema real (MAXPOLL con 61k de lag), lo diagnosticaste correctamente, entendiste la causa raíz (mezcla de responsabilidades), y tomaste la decisión arquitectónica correcta en vez del parche fácil.

El ADR-008 demuestra que adaptas el diseño a la realidad de las APIs externas — algo que distingue a un senior de alguien que solo implementa el happy path.

---

## Criterio de éxito del MVP v2

> El MVP v2 está terminado cuando puedes hacer esto sin tocar código:
>
> 1. Abrir Swagger UI en `localhost:8000/docs`
> 2. Ver artistas que nunca has escuchado, ordenados por score
> 3. Marcar uno como `FOLLOWING`
> 4. Ver sus top tracks procesados en el siguiente ciclo del artist-tracker
> 5. Escuchar algo en Last.fm y verlo aparecer en la BD en menos de 5 minutos
> 6. Abrir Kafka UI en `localhost:8080` y verificar que el enricher tiene lag bajo y estable

---

## Qué viene después del MVP v2

El `artist-tracker` del MVP solo hace un salto: top tracks de artistas que ya sigues. La expansión real del grafo — artistas relacionados con los que sigues — requiere una fuente alternativa al endpoint deprecado de Spotify. **Last.fm `artist.getSimilar`** sí está disponible y es la opción natural para v3.

Orden después del MVP v2:

1. `artist-tracker` ampliado con `Last.fm artist.getSimilar` → expansión real del grafo
2. `novelty-detector` migrado a Go
3. Dashboard React
4. `stats-collector` + métricas
5. `curator-aggregator` (YouTube, RSS)
6. Observabilidad + CI/CD
7. Kubernetes

---

## Notas para v3

### Señal negativa de BLACKLISTED
`BLACKLISTED` solo excluye de la cola. Posible mejora: penalty por géneros de artistas blacklisteados en el scorer. Esperar a datos reales de uso antes de implementar.

### MusicBrainz como tercer nivel de fallback
Si el fallback Last.fm no cubre suficientes casos (artistas muy underground), MusicBrainz es la siguiente opción: API gratuita, muy completa, ya usa MBIDs que Last.fm expone.

## ADD CI in every sevice with github actions, with tests and linters, and add a badge to the readme of each service
