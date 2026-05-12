

> Este documento define qué construir primero. La visión completa está en `SIGNAL_Architecture.md`. El MVP no es una versión recortada del sistema completo. Es el sistema mínimo que ya te da valor real.

---

## Qué resuelve el MVP

Una sola pregunta: **¿qué artistas han aparecido en mis escuchas recientes que no conocía, y cuánto se alejan de lo que ya escucho?**

Nada más. Sin expansión de grafo, sin curadores, sin dashboard, sin Go, sin SoundCloud. Solo el pipeline mínimo que responde esa pregunta y te lo muestra en un endpoint consultable.

---

## Qué NO está en el MVP

Todo esto viene después, cuando el core funciona:

- `artist-tracker` con expansión de grafo completa (multi-salto, La versión del MVP solo hace un salto desde FOLLOWING)
- `stats-collector` y métricas
- `curator-aggregator` y curadores
- `novelty-detector` en Go (empieza en Python, migras después)
- Dashboard React
- `soundcloud-ingester`
- Schema Registry
- Observabilidad (OpenTelemetry + Grafana)
- CI/CD
- Kubernetes

---

## Stack del MVP

|Componente|Tecnología|
|---|---|
|Messaging|Kafka + Zookeeper|
|Servicios|Python 3.12|
|BD|PostgreSQL|
|API|FastAPI + Swagger UI|
|Infra|Docker Compose|

Todo en un `docker-compose.yml`. Sin cloud, sin K8s, sin Redis.

El MVP tiene **6 servicios**: `lastfm-ingester`, `normalizer`, `history-tracker`, `novelty-detector`, `scorer`, `artist-tracker` (versión simple), y `api`.

---

## Pipeline del MVP

```mermaid
flowchart LR
    LFM[lastfm-ingester\nPython]
    RP[raw.plays]
    NRM[normalizer\nPython]
    TN[tracks.normalized]
    HT[history-tracker\nPython]
    LH[listening.history]
    ND[novelty-detector\nPython]
    TNV[tracks.novel]
    SCR[scorer\nPython]
    PG[(PostgreSQL)]
    API[api\nFastAPI]

    LFM --> RP --> NRM --> TN
    TN --> HT --> LH
    LH -.->|consulta| ND
    TN --> ND --> TNV --> SCR
    SCR -.->|persiste| PG
    HT -.->|persiste| PG
    PG -->|lee| API

    style LFM fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style NRM fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style HT  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style ND  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style SCR fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style API fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style RP  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TN  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style LH  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TNV fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style PG  fill:#185FA5,color:#E6F1FB,stroke:#0C447C
```

5 servicios. 4 topics. 1 base de datos. 1 API.

---

## Fase 0 — Infraestructura base

**Duración estimada**: 1 sesión **Objetivo**: tener Kafka y PostgreSQL levantados y verificados localmente.

### Tareas

- [x] Crear repo `signal` en GitHub con estructura de monorepo
- [x] Escribir `CLAUDE.md` en la raíz con el contexto del sistema
- [ ] Escribir `infra/docker-compose.yml` con:
    - Kafka + Zookeeper
    - PostgreSQL
- [ ] Verificar que Kafka arranca y acepta mensajes con `kafka-console-producer`
- [ ] Crear schema inicial de PostgreSQL:
    - tabla `listening_history`
    - tabla `artists`
    - tabla `artist_recommendations`

### Schema PostgreSQL inicial

```sql
CREATE TABLE listening_history (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id       TEXT NOT NULL UNIQUE,
  artist          TEXT NOT NULL,
  artist_id       TEXT,
  title           TEXT NOT NULL,
  genres          TEXT[],
  played_at       TIMESTAMPTZ,
  sources         TEXT[],
  audio_features  JSONB,
  popularity      INT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_listening_history_artist ON listening_history(artist);
CREATE INDEX idx_listening_history_genres ON listening_history USING GIN(genres);

CREATE TABLE artists (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  external_ids    JSONB,
  status          TEXT NOT NULL DEFAULT 'TRACKED',
  high_priority   BOOLEAN DEFAULT false,
  source          TEXT,
  genres          TEXT[],
  play_count      INT DEFAULT 0,
  added_at        TIMESTAMPTZ DEFAULT now(),
  first_seen_at   TIMESTAMPTZ DEFAULT now(),
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

### ✅ Validación

- `docker compose up` arranca sin errores
- Puedes conectarte a PostgreSQL y ver las tablas creadas
- Puedes producir y consumir un mensaje de prueba en Kafka

---

## Fase 1 — lastfm-ingester

**Duración estimada**: 1-2 sesiones **Objetivo**: tu historial de Last.fm fluyendo al topic `raw.plays`.

### Tareas

- [ ] Crear `services/lastfm-ingester/`
- [ ] Obtener API key de Last.fm (gratuita)
- [ ] Implementar polling de `user.getRecentTracks` con paginación
- [ ] Emitir cada scrobble a `raw.plays`
- [ ] Checkpoint por timestamp: no re-emitir plays ya procesados
- [ ] Ingesta histórica: flag para cargar todo el historial desde el principio

### Schema `raw.plays`

```json
{
  "source": "lastfm",
  "artist": "Actress",
  "title": "Ascending",
  "played_at": "2026-01-15T21:30:00Z",
  "external_ids": {
    "lastfm_mbid": "..."
  },
  "raw": {}
}
```

### ✅ Validación

- Arrancas el ingester y ves mensajes llegando a `raw.plays` con `kafka-console-consumer`
- El checkpoint funciona: si paras y arrancas, no re-emite lo ya procesado
- La ingesta histórica carga todo tu historial sin duplicados

---

## Fase 2 — normalizer

**Duración estimada**: 1-2 sesiones **Objetivo**: tracks normalizados con géneros y audio features en `tracks.normalized`.

### Tareas

- [ ] Crear `services/normalizer/`
- [ ] Consumir `raw.plays`
- [ ] Para cada play, enriquecer con Spotify:
    - Buscar el track por `artist + title`
    - Obtener géneros del artista
    - Obtener audio features del track
- [ ] Calcular `signal_id` = sha256 de `artist+title` normalizado (lowercase, sin puntuación)
- [ ] Emitir a `tracks.normalized`
- [ ] Detectar artistas nuevos: si el artista no está en tabla `artists`, insertarlo con `status=TRACKED`

### Schema `tracks.normalized`

```json
{
  "signal_id": "abc123...",
  "artist": "Actress",
  "artist_id": "spotify:artist:...",
  "title": "Ascending",
  "genres": ["electronic", "experimental"],
  "sources": ["lastfm"],
  "played": true,
  "played_at": "2026-01-15T21:30:00Z",
  "audio_features": {
    "energy": 0.3,
    "valence": 0.2,
    "tempo": 95
  },
  "popularity": 28,
  "processed_at": "2026-01-15T21:31:00Z"
}
```

### ✅ Validación

- Ves mensajes en `tracks.normalized` con géneros y audio features
- La tabla `artists` se va poblando con artistas de tu historial
- El `signal_id` es consistente: el mismo track siempre produce el mismo ID

---

## Fase 3 — history-tracker

**Duración estimada**: 1 sesión **Objetivo**: tu historial de escuchas persistido en PostgreSQL.

### Tareas

- [ ] Crear `services/history-tracker/`
- [ ] Consumir `tracks.normalized`
- [ ] Insertar en `listening_history` (upsert por `signal_id`)
- [ ] Emitir a `listening.history` cuando se añade un track nuevo
- [ ] Actualizar `play_count` en tabla `artists` por cada play

### ✅ Validación

- La tabla `listening_history` tiene tus tracks con géneros y audio features
- La tabla `artists` tiene el `play_count` actualizado
- Si el mismo track llega dos veces, no se duplica en la BD

---

## Fase 4 — onboarding de artistas

**Duración estimada**: 1 sesión **Objetivo**: clasificar correctamente los artistas de tu historial previo usando la lógica D.

### Tareas

- [ ] Script de onboarding (se ejecuta una sola vez):
    1. Obtener artistas que sigues en Spotify → `status=FOLLOWING`
    2. Para el resto de artistas en la tabla `artists`:
        - `play_count >= INITIAL_HIGH_PRIORITY_PLAYS` → `status=TRACKED`, `high_priority=true`
        - `play_count < umbral` → `status=TRACKED`
- [ ] Variable de entorno `INITIAL_HIGH_PRIORITY_PLAYS=20`

### Diagrama de onboarding

```mermaid
flowchart TD
    START([script onboarding\nse ejecuta una vez])
    START --> SPO[obtener artistas\nseguidos en Spotify]
    SPO --> FOL[status = FOLLOWING]

    START --> REST[resto de artistas\nen tabla artists]
    REST --> CHK{play_count ≥\nINITIAL_HIGH_PRIORITY_PLAYS?}
    CHK -->|sí| THP[status = TRACKED\nhigh_priority = true]
    CHK -->|no| TRK[status = TRACKED]

    FOL --> PG[(PostgreSQL · artists)]
    THP --> PG
    TRK --> PG

    style START fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style SPO fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style REST fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style FOL fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style THP fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TRK fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style PG  fill:#185FA5,color:#E6F1FB,stroke:#0C447C
    style CHK fill:#888780,color:#ffffff,stroke:#5F5E5A
```

### ✅ Validación

- Artistas que sigues en Spotify tienen `status=FOLLOWING`
- Artistas con muchos plays pero no seguidos tienen `high_priority=true`
- Puedes consultar la distribución: `SELECT status, count(*) FROM artists GROUP BY status`

---

## Fase 5 — novelty-detector

**Duración estimada**: 2 sesiones **Objetivo**: detectar artistas y géneros nuevos respecto a tu historial.

### Tareas

- [ ] Crear `services/novelty-detector/` (Python en el MVP, Go viene después)
- [ ] Consumir `tracks.normalized`
- [ ] Para cada track:
    - ¿El artista está en `listening_history`? → `track_is_new = false/true`
    - ¿Alguno de sus géneros no aparece en ningún track de `listening_history`? → `new_genres`
    - Calcular `genre_novelty_ratio = len(new_genres) / len(all_genres)`
- [ ] Si hay novedad → emitir a `tracks.novel`
- [ ] Si el artista es nuevo y supera `AUTO_FOLLOW_PLAYS` → promover a `FOLLOWING` automáticamente

### Schema `tracks.novel`

```json
{
  "signal_id": "...",
  "artist": "Actress",
  "artist_id": "spotify:artist:...",
  "genres": ["footwork", "experimental"],
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

- Ves mensajes en `tracks.novel` solo para tracks realmente nuevos
- Un track de un artista que ya tienes en historial con géneros conocidos NO aparece
- Un track de un artista nuevo SÍ aparece con `artist_is_new=true`

---

## Fase 6 — scorer

**Duración estimada**: 1-2 sesiones **Objetivo**: artistas puntuados y persistidos en PostgreSQL, consultables desde la API.

### Tareas

- [ ] Crear `services/scorer/`
- [ ] Consumir `tracks.novel`
- [ ] Calcular perfil de audio features del usuario (media de `listening_history`)
- [ ] Calcular score por artista:

```
score = (
  w1 * genre_novelty_ratio          # géneros nuevos (0-1)
  + w2 * (1 - popularity_norm)      # factor underground (0-1)
  + w3 * audio_distance             # distancia coseno al perfil (0-1)
)
```

- [ ] Bonus si `high_priority=true`: `score *= 1.2` (configurable)
- [ ] Upsert en `artist_recommendations` (un artista puede recibir varios tracks novel)
- [ ] Variables configurables: `W1=0.4`, `W2=0.3`, `W3=0.3`, `HP_BONUS=1.2`

### ✅ Validación

- La tabla `artist_recommendations` tiene artistas con scores entre 0 y 1
- Los artistas `high_priority` aparecen con scores más altos
- Puedes cambiar los pesos y ver cómo cambia el ranking

---

## Fase 6b — artist-tracker (versión simple)

**Duración estimada**: 1-2 sesiones **Objetivo**: descubrimiento activo de un salto. Para cada artista en `FOLLOWING`, buscar sus relacionados en Spotify e inyectarlos en el pipeline.

Esta es la diferencia entre un sistema reactivo (solo procesa lo que escuchas) y uno que descubre activamente. Sin esta fase, el MVP no tiene valor real de descubrimiento.

### Tareas

- [ ] Crear `services/artist-tracker/`
- [ ] Polling periódico (cada N horas, configurable con `ARTIST_TRACKER_INTERVAL_HOURS=6`)
- [ ] Para cada artista con `status=FOLLOWING`:
    - Llamar a `GET /artists/{spotify_id}/related-artists` en Spotify
    - Filtrar los que ya están en tabla `artists` (evitar re-procesar)
    - Para cada artista relacionado nuevo:
        - Insertar en `artists` con `status=TRACKED`, `source=SPOTIFY_RELATED`
        - Obtener sus top tracks (`GET /artists/{id}/top-tracks`)
        - Emitir cada track a `raw.tracks`
- [ ] Respetar rate limits de Spotify (429 con backoff exponencial)
- [ ] Idempotente: no re-procesar artistas ya conocidos

### Schema `raw.tracks`

```json
{
  "source": "spotify",
  "artist": "Burial",
  "artist_id": "spotify:artist:...",
  "title": "Archangel",
  "genres": ["uk garage", "ambient"],
  "popularity": 55,
  "audio_features": {
    "energy": 0.4,
    "valence": 0.2,
    "tempo": 140
  },
  "origin": {
    "type": "SPOTIFY_RELATED",
    "origin_artist_id": "spotify:artist:...",
    "origin_artist_name": "Actress"
  },
  "raw": {}
}
```

### Diagrama del bucle de descubrimiento

```mermaid
flowchart LR
    PG[(PostgreSQL
artistas FOLLOWING)]
    AT[artist-tracker]
    SPO[Spotify API
related-artists
+ top-tracks]
    RT[raw.tracks]
    NRM[normalizer]
    TN[tracks.normalized]
    ND[novelty-detector]

    PG -->|cada N horas| AT
    AT -->|GET related-artists| SPO
    SPO -->|artistas nuevos + tracks| AT
    AT --> RT --> NRM --> TN --> ND

    style AT  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style NRM fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style ND  fill:#0F6E56,color:#E1F5EE,stroke:#085041
    style RT  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style TN  fill:#534AB7,color:#EEEDFE,stroke:#3C3489
    style PG  fill:#185FA5,color:#E6F1FB,stroke:#0C447C
    style SPO fill:#185FA5,color:#E6F1FB,stroke:#0C447C
```

### ✅ Validación

- Arrancas el artist-tracker y ves tracks nuevos llegando a `raw.tracks` de artistas que nunca has escuchado
- La tabla `artists` se puebla con artistas relacionados con `source=SPOTIFY_RELATED`
- El novelty-detector los detecta como nuevos y el scorer los puntúa
- En la API ves artistas que nunca has escuchado en tu cola `TRACKED`

---

## Fase 7 — api

**Duración estimada**: 1-2 sesiones **Objetivo**: endpoints para gestionar tu universo de artistas desde Swagger UI.

### Endpoints del MVP

```
GET  /artists?status=TRACKED           # cola de artistas pendientes de valorar
GET  /artists?status=TRACKED&high_priority=true  # cola prioritaria
GET  /artists?status=FOLLOWING         # artistas en seguimiento
GET  /artists/{id}                     # detalle + score + tracks de evidencia
POST /artists                          # añadir artista manualmente → FOLLOWING
POST /artists/{id}/follow              # TRACKED → FOLLOWING
POST /artists/{id}/blacklist           # → BLACKLISTED
POST /artists/{id}/publish             # → PUBLISHED

GET  /stats/basic                      # tracks procesados, artistas por status
```

### ✅ Validación final del MVP

- Abres Swagger UI en `localhost:8000/docs`
- Ves tu cola de artistas `TRACKED` ordenada por score
- Puedes marcar un artista como `FOLLOWING` o `BLACKLISTED`
- Puedes añadir un artista manualmente
- El pipeline completo funciona: escuchas algo en Last.fm → aparece procesado en la BD en minutos

---

## Diagrama de estados del MVP

```mermaid
stateDiagram-v2
    [*] --> FOLLOWING : seguido en Spotify\n(onboarding)
    [*] --> TRACKED_HP : plays ≥ umbral\n(onboarding, high_priority)
    [*] --> TRACKED : historial normal\n(onboarding)
    [*] --> FOLLOWING : añadido manualmente

    TRACKED --> FOLLOWING : plays ≥ AUTO_FOLLOW_PLAYS\n(automático)
    TRACKED --> FOLLOWING : POST /artists/{id}/follow
    TRACKED --> BLACKLISTED : POST /artists/{id}/blacklist

    TRACKED_HP --> FOLLOWING : plays ≥ AUTO_FOLLOW_PLAYS\n(automático)
    TRACKED_HP --> FOLLOWING : POST /artists/{id}/follow
    TRACKED_HP --> BLACKLISTED : POST /artists/{id}/blacklist

    FOLLOWING --> PUBLISHED : POST /artists/{id}/publish
    FOLLOWING --> BLACKLISTED : POST /artists/{id}/blacklist
    PUBLISHED --> FOLLOWING : nuevo contenido detectado

    note right of TRACKED_HP : score con bonus HP_BONUS
```

---

## Qué viene después del MVP

Una vez el MVP funciona y te da valor real, el `artist-tracker` del MVP solo hace un salto desde tus artistas `FOLLOWING`. El siguiente paso natural es ampliar a múltiples saltos: relacionados de relacionados, con filtrado por relevancia para no explotar el grafo.

El orden después del MVP:

1. `artist-tracker` ampliado: multi-salto con control de profundidad y filtrado
2. `novelty-detector` migrado a Go
3. Dashboard React (cuando Swagger se vuelva incómodo)
4. `stats-collector` + métricas
5. `curator-aggregator` (YouTube, RSS)
6. Observabilidad + CI/CD
7. Kubernetes

---

## Variables de entorno del MVP

```env
# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# PostgreSQL
DATABASE_URL=postgresql://signal:signal@localhost:5432/signal

# Last.fm
LASTFM_API_KEY=...
LASTFM_USERNAME=...

# Spotify (OAuth)
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REFRESH_TOKEN=...

# Artist tracker
ARTIST_TRACKER_INTERVAL_HOURS=6

# Clasificación de artistas
INITIAL_HIGH_PRIORITY_PLAYS=20
AUTO_FOLLOW_PLAYS=3

# Scorer
W1=0.4
W2=0.3
W3=0.3
HP_BONUS=1.2
```

---

## Estructura de repositorio del MVP

```
signal/
├── CLAUDE.md
├── infra/
│   └── docker-compose.yml        # Kafka + Zookeeper + PostgreSQL
├── services/
│   ├── lastfm-ingester/          # Python
│   ├── normalizer/               # Python
│   ├── history-tracker/          # Python
│   ├── artist-tracker/           # Python (versión simple, un salto)
│   ├── novelty-detector/         # Python (Go en v2)
│   ├── scorer/                   # Python
│   └── api/                      # Python / FastAPI
├── shared/
│   └── python-common/            # Kafka client wrapper, logging, modelos compartidos
├── scripts/
│   └── onboarding.py             # clasificación inicial de artistas, se ejecuta una vez
└── README.md
```

---

## Criterio de éxito del MVP

> El MVP está terminado cuando puedes hacer esto sin tocar código:
>
> 1. Abrir Swagger UI
> 2. Ver una lista de artistas que **nunca has escuchado** ordenados por cuánto se alejan de lo que escuchas
> 3. Marcar uno como FOLLOWING
> 4. Esperar el siguiente ciclo del artist-tracker y ver nuevos artistas relacionados aparecer en la cola
> 5. Escuchar algo nuevo en Last.fm y verlo aparecer procesado en la BD en menos de 5 minutos

---

## Notas para v2

### Señal negativa de BLACKLISTED

Actualmente `BLACKLISTED` solo excluye al artista de la cola de revisión. No influye en el scoring ni en qué trae el artist-tracker.

Una posible mejora para v2, una vez tengas datos reales de uso:

**Penalty por géneros blacklisteados en el scorer** Calcular la intersección entre los géneros del track candidato y los géneros agregados de todos tus artistas `BLACKLISTED`. Restar un penalty proporcional al score.

```
penalty = overlap(track.genres, blacklisted_genres) * W_PENALTY
score = score - penalty
```

**Filtrado en el artist-tracker** Si un artista relacionado comparte todos sus géneros con artistas `BLACKLISTED`, no insertarlo en la BD directamente.

Por qué esperar a v2: es mejor tener datos reales de uso antes de asumir cómo se comportan las blacklists. Puede que blacklistees artistas por razones que no tienen nada que ver con el género, y aplicar el penalty haría más daño que bien.

---

## Preguntas pendientes y decisiones abiertas

### 1 — Búsqueda de artista al añadir manualmente

`POST /artists` necesita el Spotify ID del artista. Sin un endpoint de búsqueda el usuario tiene que buscarlo a mano, lo cual es incómodo.

**Pendiente**: añadir `GET /artists/search?q=Actress` que llame a Spotify Search y devuelva candidatos para elegir. Necesario antes de que la API sea usable para altas manuales.

---

### 2 — Estrategia de enriquecimiento cuando Spotify no encuentra el track

Last.fm no proporciona Spotify IDs. El normalizer busca por `artist + title` en Spotify, pero esta búsqueda puede fallar (artistas underground, nombres con caracteres especiales, tracks en vivo, ediciones alternativas).

**Estrategia de fallback propuesta** (cadena en orden):

```
1. Buscar en Spotify → géneros + audio features completos
2. Si no → buscar en MusicBrainz → géneros básicos (API gratuita, muy completa para underground)
3. Si no → usar tags de Last.fm via track.getInfo → géneros crowdsourced
4. Si todo falla → guardar sin enriquecer con pending_enrichment=true
```

`pending_enrichment=true` permite reintentar más tarde sin perder el track. El scorer funciona sin audio features usando solo los otros dos factores (genre_novelty y popularity).

**Decisión**: Spotify + fallback a Last.fm tags (`track.getInfo`). MusicBrainz queda para v2 si hay casos no cubiertos.

Flujo del normalizer:

```
1. Buscar en Spotify por artist+title → géneros + audio features
2. Si no encuentra → Last.fm track.getInfo → tags como géneros, sin audio features
3. Si tampoco → guardar con pending_enrichment=true, score sin audio_distance
```

---

### 3 — Orden de arranque explícito

El orden de ejecución en el primer arranque importa. Si el pipeline corre antes del onboarding, los artistas entran todos como `TRACKED` sin la clasificación correcta.

**Orden obligatorio**:

1. `docker compose up` (infra)
2. `python scripts/onboarding.py` (clasificación inicial de artistas)
3. Arrancar servicios del pipeline

**Pendiente**: documentar esto en el README y considerar un health check o guard en el pipeline que verifique que el onboarding se ha ejecutado antes de procesar.

---

### 4 — Comportamiento del artist-tracker: completo vs incremental

Con `ARTIST_TRACKER_INTERVAL_HOURS=6`, ¿hace una pasada completa de todos los artistas `FOLLOWING` cada vez, o es incremental (solo los que no se han explorado recientemente)?

**Propuesta para el MVP**: pasada completa cada vez, usando `last_explored_at` para no re-explorar artistas explorados hace menos de X días. Evita llamadas innecesarias a Spotify.

**Pendiente**: definir `ARTIST_REEXPLORE_DAYS` como variable de entorno (default: 7).

---

### 5 — Rate limits de Spotify en el normalizer durante ingesta histórica

La ingesta histórica completa de Last.fm puede ser miles de tracks. El normalizer llama a Spotify por cada uno para enriquecer. Con el rate limit de Spotify (429) esto puede romperse silenciosamente.

**Pendiente**: implementar backoff exponencial en el cliente de Spotify y batching de llamadas donde la API lo permita. Considerar un modo de ingesta histórica más lento con delay configurable entre llamadas.

---

## ADRs a escribir para el MVP

Cada ADR documenta una decisión arquitectónica con su contexto, alternativas consideradas y justificación. Son material de portfolio y de entrevista: demuestran que tomas decisiones conscientes, no por inercia.

### 001 — Kafka sobre colas simples o llamadas directas

**Decisión**: usar Kafka como bus de comunicación entre servicios en vez de llamadas HTTP síncronas o una cola simple (RabbitMQ, SQS).

**Por qué vale la pena documentarlo**: es la decisión más cuestionable del MVP dado el tamaño del sistema. Un entrevistador la va a preguntar.

Puntos a cubrir: múltiples consumers del mismo stream sin acoplamiento, replay para recalibrar el scorer sin re-ingestar, ritmos de ingesta distintos entre Last.fm y artist-tracker, y por qué RabbitMQ no encaja (no está pensado para múltiples consumers del mismo mensaje).

---

### 002 — PostgreSQL sobre NoSQL

**Decisión**: PostgreSQL como única base de datos en vez de MongoDB, DynamoDB u otra NoSQL.

**Por qué vale la pena documentarlo**: es una decisión contra la corriente en sistemas con Kafka, donde muchos equipos asumen que necesitan NoSQL.

Puntos a cubrir: los datos son relacionales (artistas, historial, recomendaciones con joins y agregaciones), JSONB de PostgreSQL cubre los campos variables sin perder capacidad de query, el volumen no justifica una solución distribuida, y cuándo reconsiderar (grafo multi-salto profundo → Neo4j).

---

### 003 — Python para todos los servicios del MVP (Go en v2)

**Decisión**: todos los servicios en Python 3.12 en el MVP, con el novelty-detector migrado a Go en v2.

**Por qué vale la pena documentarlo**: demuestra que la elección de lenguaje es deliberada, no por defecto.

Puntos a cubrir: SDKs de Last.fm y Spotify más maduros en Python, velocidad de desarrollo en MVP, el novelty-detector es el candidato natural para Go (lógica acotada, set membership, sin ORM), y cómo una arquitectura de servicios permite migrar un servicio sin tocar el resto.

---

### 004 — Enriquecimiento con fallback (Spotify → Last.fm → pending)

**Decisión**: cadena de fallback para enriquecer tracks en vez de descartar los que Spotify no encuentra.

**Por qué vale la pena documentarlo**: es una decisión de resiliencia con trade-offs claros.

Puntos a cubrir: por qué no descartar (pierdes señal de artistas underground que son exactamente los más interesantes), por qué no bloquear el pipeline esperando enriquecimiento (latencia), el campo `pending_enrichment` como mecanismo de reintento, y qué factores del scorer aplican sin audio features.

---

### 005 — Artista como objeto principal, track como señal

**Decisión**: el objeto de curación es el artista, no el track. Los tracks son evidencia que justifica una recomendación de artista.

**Por qué vale la pena documentarlo**: es una decisión de dominio que afecta toda la arquitectura y no es obvia al principio.

Puntos a cubrir: el objetivo es publicar sobre artistas, no sobre canciones individuales, los tracks aportan géneros y audio features pero no son el fin, cómo esto simplifica el ciclo de vida (un estado de artista en vez de estados por track), y qué se perdería modelando tracks como objeto principal.

---

### 006 — Clasificación inicial de artistas con señal de Spotify follows + plays

**Decisión**: combinar dos señales para el onboarding (seguir en Spotify = `FOLLOWING`, plays ≥ umbral = `TRACKED high_priority`) en vez de fecha de corte u onboarding manual completo.

**Por qué vale la pena documentarlo**: es una decisión de producto con alternativas claras que descartaste.

Puntos a cubrir: por qué no fecha de corte (arbitraria, frágil), por qué no onboarding manual completo (fricción excesiva), por qué el "seguir en Spotify" es la señal más limpia (gesto explícito del usuario), y cómo el umbral de plays complementa para artistas que escuchas mucho pero no sigues formalmente.

---

## Bullets de CV del MVP

El MVP ya es suficiente para actualizar el CV con honestidad. Cuando esté funcionando tienes esto:

|Logro|Bullet|
|---|---|
|Pipeline Kafka con 5 topics|Designed and implemented an event-driven artist discovery pipeline using Kafka, connecting 6 decoupled Python services processing music data from Last.fm and Spotify|
|Descubrimiento activo|Built an artist-tracker service that expands a monitored artist universe via Spotify related-artist graph, enabling proactive discovery beyond personal listening history|
|Scoring configurable|Implemented a configurable multi-factor scoring engine combining genre novelty ratio, underground factor, and cosine audio feature distance to rank artist recommendations|
|Clasificación de artistas|Designed an artist lifecycle state machine with automatic promotion logic based on play-count thresholds and Spotify follow signal|
|Enriquecimiento con fallback|Built a resilient track enrichment pipeline with Spotify → Last.fm fallback chain and pending_enrichment flag for retry, preserving underground tracks not indexed by Spotify|
|Decisiones documentadas|Documented 6 architectural decisions as ADRs covering messaging, storage, language choice, and domain modeling|

### Cómo presentarlo en entrevista

El sistema tiene Kafka pero es un proyecto personal pequeño en volumen. Si un entrevistador pregunta por qué Kafka para algo tan pequeño, la respuesta es el ADR-001: múltiples consumers, replay para recalibrar el scorer, y que el proyecto está diseñado para crecer. Esa respuesta es mejor que "porque quería aprenderlo", aunque ambas sean verdad.

El novelty-detector en Python del MVP se convierte en Go en v2. Puedes mencionarlo como decisión deliberada: "empecé en Python para validar la lógica, el plan es migrarlo a Go una vez estabilizado el comportamiento". Eso demuestra criterio, no indecisión.
