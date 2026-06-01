# ADR-017: Go for the novelty-detector service

- **Status**: Accepted
- **Date**: 2026-05-31

## Context

The novelty-detector is a Kafka consumer that does three things: queries PostgreSQL for set-membership (is this artist / genre new?), computes a small novelty struct, and emits to `tracks.novel`. It has no HTTP layer, no ORM, no complex business logic, and no shared Python models. The MVP v2 specification already designated it as the first Go service (the Python version was explicitly marked as temporary). After the Python implementation was complete and validated, the Go migration became the first step of v3.

## Decision

The novelty-detector is rewritten in Go, replacing the Python source entirely. The service uses `confluent-kafka-go/v2` for Kafka, `pgx/v5` for PostgreSQL, and `log/slog` for structured JSON logging. All dependencies are injected through interfaces. Signal handling and dependency wiring live in `cmd/novelty-detector/main.go`; all business logic lives under `internal/`.

## Alternatives considered

**Keep Python** — *Rejected*
The Python service worked, but the domain is a natural fit for Go: pure data transformation, no framework overhead, and the set-membership queries are straightforward SQL that needs no ORM. Keeping Python here would mean no Go foothold in the repo and no established pattern for future Go services.

**Rewrite in Go with sarama or kafka-go** — *Rejected* (see ADR-018)
Pure-Go Kafka clients avoid CGo and `librdkafka`, but `confluent-kafka-go` was the existing library choice validated in prior services and matches the Python `confluent-kafka` client behaviour closely (same offset-commit semantics, same consumer group protocol). Switching client families for the first Go service introduces unnecessary variance.

**Go with flat `package main`** — *Rejected*
An initial flat-package implementation was written and committed, then restructured. A single `package main` prevents external test packages from importing service code and mixes signal handling, config loading, and business logic. The `cmd/internal` layout was adopted after a code review flagged this; it is now the established pattern for Go services in this repo.

## Consequences

✅ Establishes the `cmd/internal` package layout as the Go service template for the repo — future Go services have a reference implementation to follow  
✅ All seven dependencies of `consumer.Run` are interfaces, making unit tests fast and hermetic without Docker  
✅ Context-based shutdown means OS signal handling is isolated to `main.go` — business logic is testable without registering live signal handlers  
✅ `pgx/v5` with `pgxpool` gives connection pooling and native PostgreSQL array support needed for the `genres @> ARRAY[g]` query  
❌ CGo dependency (`confluent-kafka-go`) requires `librdkafka-dev` in the build environment and in Docker — Alpine images need explicit `apk add librdkafka-dev pkgconfig`  
❌ Go is not used anywhere else in the repo today — the team carries a second language toolchain and a second set of linting/testing conventions  
❌ `go mod tidy` must be run manually after restructures; it is not wired into any Makefile target yet  

## When to reconsider

If a second Go service is added and its domain is significantly more complex (HTTP layer, ORM, multiple external APIs), revisit whether `confluent-kafka-go` + raw `pgx` remain the right defaults or whether a higher-level framework makes more sense. If the CGo build overhead becomes a CI bottleneck (build times exceeding 3 minutes regularly), evaluate `kafka-go` as a drop-in replacement.
