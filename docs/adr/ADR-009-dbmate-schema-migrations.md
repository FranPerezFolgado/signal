# ADR-009 — dbmate for schema migrations

- **Status**: Accepted
- **Date**: 2026-05-23

## Context

The MVP v1 used a single `init.sql` file mounted as a PostgreSQL `docker-entrypoint-initdb.d` script. This approach has a hard constraint: the init script runs only when the data volume is empty (i.e., on the very first container start). Any schema change to a running database — adding a column, renaming one, dropping another — requires either wiping the volume (losing data) or running hand-crafted SQL manually.

The MVP v2 introduced three schema changes driven by real architectural decisions (ADR-007, ADR-008):

- Drop `audio_features JSONB` (audio features permanently unavailable)
- Rename `popularity` → `artist_popularity` (naming clarity after adding `track_popularity`)
- Add `track_popularity INT`, `track_id TEXT`, `pending_enrichment BOOLEAN`

These changes need to be applied to existing databases without data loss, and idempotently so that a restart of the compose stack does not re-apply them.

## Decision

Adopt **dbmate** (`ghcr.io/amacneil/dbmate:2`) as the schema migration tool, run as a one-shot Docker Compose service that blocks dependent services until it exits 0.

Migrations live in `infra/postgres/migrations/` as numbered SQL files (`NNN-description.sql`) with `-- migrate:up` / `-- migrate:down` sections. dbmate tracks applied migrations in a `schema_migrations` table.

`init.sql` is kept as the canonical v2 schema for fresh database volumes. Migrations handle in-place upgrades from previous versions. This dual-schema strategy means both cold starts and warm upgrades arrive at the same final schema without branching logic.

## Alternatives considered

**Alembic (Python)**: Industry-standard for Python/SQLAlchemy projects. Rejected because Signal's services are Kafka consumers/producers with no ORM — adding a full SQLAlchemy dependency (and its model definitions) purely for migrations would be significant overhead with no benefit.

**Flyway**: JVM-based, requires a Java runtime in the container. Rejected: adds a large runtime for a task that is a small part of the project.

**Raw SQL scripts + manual execution**: Simple but not tracked — re-running a script that already ran can corrupt data. Requires human intervention on every deploy. Rejected.

**Liquibase**: XML/YAML migration format, JVM-based. Same objections as Flyway, with the added friction of a non-SQL DSL.

**dbmate**: Single static binary, SQL-native migration files, minimal image (`ghcr.io/amacneil/dbmate:2` is ~15 MB). Integrates as a compose `restart: on-failure` service with `--wait` to retry until PostgreSQL is ready. No additional language runtime or ORM dependency.

## Consequences

- Schema history is tracked in the database itself (`schema_migrations` table) — inspectable with a simple `SELECT`.
- Migrations are plain SQL with explicit up/down sections — readable by anyone without tool-specific knowledge.
- The compose `migrate` service uses `--wait up`, so all services with `depends_on: migrate: condition: service_completed_successfully` are guaranteed to start against the correct schema.
- Fresh installs and upgrades from v1 arrive at identical schemas. The `init.sql` invariant must be maintained: it must always reflect the final target schema, and each migration must be idempotent (using `IF EXISTS`, `IF NOT EXISTS`, and `DO $$` guards for operations that PostgreSQL does not support with those clauses natively).
- Down migrations are provided but not run automatically — recovery from a bad migration requires explicit intervention, which is intentional at this scale.
