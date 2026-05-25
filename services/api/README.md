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
| `GET` | `/health` | Liveness check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/docs` | Swagger UI |

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
