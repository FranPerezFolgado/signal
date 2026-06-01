# ADR-018: confluent-kafka-go over sarama / kafka-go

- **Status**: Accepted
- **Date**: 2026-05-31

## Context

The novelty-detector is the first Go service in the repo. It needs a Kafka client for consuming `tracks.enriched` and producing to `tracks.novel` and `novelty-detector.dlq`. Three mature Go Kafka clients exist: `confluent-kafka-go` (CGo wrapper over librdkafka), `sarama` (pure Go, IBM-maintained), and `kafka-go` (pure Go, Segment). The Python services already use `confluent-kafka`; the Kafka broker is KRaft-mode Confluent-compatible. Manual offset commits and at-least-once delivery confirmation are required.

## Decision

`confluent-kafka-go/v2` is used as the Kafka client for the novelty-detector and will be the default for future Go services.

## Alternatives considered

**sarama** — *Rejected*
sarama is pure Go and has no CGo dependency, but it requires explicit partition assignment and manual consumer group rebalance handling, which adds boilerplate. Its API surface is larger and more error-prone for a service that only needs subscribe/poll/commit semantics. Offset commit behaviour differs from `confluent-kafka` in subtle ways that would require re-validating the at-least-once guarantees already validated in Python.

**kafka-go** — *Rejected*
kafka-go has a cleaner API than sarama and is pure Go, but it lacks first-class support for consumer group rebalancing callbacks and has had compatibility issues with KRaft-mode brokers in some versions. More importantly, it is the least battle-tested of the three for high-throughput production use, and the Python reference implementation uses confluent semantics.

**confluent-kafka-go** — *Accepted*
Wraps the same librdkafka used by the Python `confluent-kafka` client. Offset commit semantics, consumer group protocol, and error codes are identical between the Python and Go services, which makes cross-service debugging and comparison straightforward. The delivery-confirmation pattern (`Produce` blocks on a delivery channel) maps cleanly to the at-least-once commit requirement without additional coordination logic.

## Consequences

✅ Offset commit semantics are identical to the Python services — no surprises when comparing consumer group behaviour across the pipeline  
✅ librdkafka is mature, widely deployed, and well-tested against all Kafka-compatible brokers including KRaft  
✅ Delivery confirmation via internal channel means `Produce()` returns only after the broker has acknowledged — no separate flush-per-message needed  
❌ CGo dependency: `librdkafka-dev` and `pkgconfig` must be installed in every build environment (local, CI, Docker) — pure-Go builds are not possible  
❌ Cross-compilation (`GOOS=linux GOARCH=amd64` from macOS) requires a C cross-compiler; the Dockerfile handles this but local cross-builds are non-trivial  
❌ Adds `librdkafka` as a runtime dependency in Docker images — Alpine images grow by ~3MB and require `apk add librdkafka`  

## When to reconsider

If a Go service needs to run in a CGo-free environment (e.g., scratch Docker image, WebAssembly target), switch that service to `kafka-go`. If the cross-compilation friction becomes a recurring problem for more than one Go service, evaluate a migration to `kafka-go` which supports standard `GOOS`/`GOARCH` cross-compilation without a C toolchain.
