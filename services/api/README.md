# api

[![CI](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-api.yml/badge.svg)](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-api.yml)

FastAPI service for managing artists and viewing discovery recommendations. Reads exclusively from PostgreSQL — no Kafka dependency.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/artists` | List all artists (paginated, filterable by status) |
| `GET` | `/artists/{id}` | Get a single artist by UUID |
| `PATCH` | `/artists/{id}/status` | Transition an artist's status (e.g. FOLLOWING → BLACKLISTED) |
| `GET` | `/recommendations` | List scored recommendations (paginated, ordered by score) |
| `GET` | `/v1/graph/data` | Artist-genre network graph data (see below) |
| `GET` | `/health` | Liveness check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/docs` | Swagger UI |

### `GET /v1/graph/data`

Returns a Graphology-compatible JSON snapshot of the artist-genre network. All parameters are optional.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | — | Filter artists by status: `FOLLOWING`, `TRACKED`, `PUBLISHED`, `BLACKLISTED` |
| `genre` | string | — | Filter to artists containing this genre tag (case-sensitive array match) |
| `min_score` | float 0–1 | — | Exclude artists with a novelty score below this threshold |
| `min_genre_artists` | int ≥ 1 | `2` | Minimum number of matched artists a genre must appear on to include a genre node |
| `limit` | int | `500` | Maximum number of artist nodes returned |

Response shape:
```json
{
  "nodes": [
    { "key": "artist:<uuid>", "attributes": { "nodeType": "artist", "label": "...", "status": "FOLLOWING", "score": 0.82, "scrobble_count": 47, "genres": ["indie pop"], "spotify_id": null } },
    { "key": "genre:indie pop", "attributes": { "nodeType": "genre", "label": "indie pop", "artist_count": 12 } }
  ],
  "edges": [
    { "key": "e:artist:<uuid>:genre:indie pop", "source": "artist:<uuid>", "target": "genre:indie pop", "attributes": { "edgeType": "tagged" } },
    { "key": "e:artist:<uuid>:artist:<origin-uuid>", "source": "artist:<uuid>", "target": "artist:<origin-uuid>", "attributes": { "edgeType": "similar" } }
  ]
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://signal:signal@localhost:5432/signal` | PostgreSQL DSN (required) |
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | Listen port |
| `POOL_MIN_SIZE` | `1` | Minimum DB connection pool size |
| `POOL_MAX_SIZE` | `10` | Maximum DB connection pool size |

## Running locally

```bash
make api-up
make api-logs
```

Or directly:

```bash
set -a && source .env && set +a
uv run signal-api
```

Open Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs).

## Tests

```bash
cd services/api
uv run pytest tests/unit/ -q
```

Integration tests require a live PostgreSQL instance (`make up`) and auto-skip otherwise:

```bash
uv run pytest tests/integration/ -q
```
