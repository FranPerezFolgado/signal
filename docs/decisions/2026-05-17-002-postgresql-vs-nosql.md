# ADR-002 — PostgreSQL como única base de datos en lugar de NoSQL

- **Status**: Accepted
- **Date**: 2026-05-17

## Context

Signal necesita persistir tres tipos de datos:

- **`listening_history`**: historial de plays (append-only, alta cardinalidad, queries por artista y por género).
- **`artists`**: entidades con ciclo de vida y estado (`TRACKED → FOLLOWING → PUBLISHED / BLACKLISTED`), joins frecuentes con `listening_history` para calcular `play_count`, queries de distribución por status.
- **`artist_recommendations`**: tabla derivada con score, breakdown por factor y tracks de evidencia. Relacionada con `artists`.

Los datos son estructuralmente relacionales: las recomendaciones referencian artistas, el historial se agrupa por artista, y el `scorer` necesita joins entre las tres tablas para calcular el perfil de audio del usuario.

## Decision

PostgreSQL 16 como única base de datos del MVP.

## Rationale

**MongoDB descartado por**:
- Los datos son relacionales. MongoDB no tiene joins nativos eficientes; modelar relaciones implica desnormalización o queries de aplicación que reemplazan el join.
- Perdemos consistencia transaccional (importante en upserts de `listening_history` y actualizaciones de estado de artistas).
- El argumento a favor de MongoDB suele ser la flexibilidad de schema, pero PostgreSQL con `JSONB` cubre los campos variables sin renunciar a la capacidad de query.

**DynamoDB (u otra BD cloud-gestionada) descartado por**:
- Sin joins ni agregaciones flexibles de forma nativa.
- Atado a un proveedor cloud. El MVP corre todo local en Docker.
- El volumen del MVP (miles de artistas, decenas de miles de plays) no justifica una BD distribuida.

**Neo4j descartado para el MVP por**:
- Relevante cuando el `artist-tracker` haga expansión multi-salto en v2 y las queries de path sean el cuello de botella.
- En el MVP el `artist-tracker` hace un único salto desde artistas `FOLLOWING`: un join simple en Postgres es suficiente.
- Añadir Neo4j ahora sería una segunda tecnología de persistencia sin beneficio concreto todavía.

**PostgreSQL aceptado por**:
- Joins, agregaciones y constraints nativos — exactamente lo que necesita el pipeline.
- `JSONB` para campos variables (`external_ids`, `audio_features`, `score_breakdown`) con soporte de indexación y query (`@>`, `->>`, índices GIN).
- Arrays nativos (`TEXT[]` para géneros) con índice GIN para queries de "¿alguno de los géneros del track está en el historial?"
- Una sola tecnología de persistencia: menos superficie operativa, una sola conexión por servicio, backups simples.

## Consequences

**Beneficios**:
- Joins relacionales nativos entre `listening_history`, `artists` y `artist_recommendations`.
- `JSONB` cubre la heterogeneidad de `audio_features` (no todos los tracks los tienen) y `score_breakdown` sin sacrificar la capacidad de query.
- Arrays con GIN permiten `SELECT * FROM listening_history WHERE genres @> ARRAY['footwork']` eficientemente.
- Schema fuertemente tipado con constraints: garantías de integridad que un document store no da por defecto.

**Costes**:
- Scaling vertical antes que horizontal. Aceptable: el volumen del MVP no lo requerirá durante meses o años.
- Migraciones de schema explícitas cuando evolucionen las tablas (deseable — fuerza que los cambios sean deliberados).

## When to reconsider

Cuando el `artist-tracker` expanda el grafo a múltiples saltos y las queries de path (relacionados de relacionados, con filtros de relevancia) se vuelvan costosas en Postgres → evaluar Neo4j como BD secundaria de grafo, manteniendo Postgres como source of truth para estado y recomendaciones.
