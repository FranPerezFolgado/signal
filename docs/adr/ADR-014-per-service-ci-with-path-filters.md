# ADR-014: Per-Service CI Workflows with Path Filters

- **Status**: Accepted
- **Date**: 2026-05-26

## Context

Signal is a uv workspace containing eight Python services plus a shared library. CI needs to run lint (ruff), type checking (mypy), and unit tests for each service. The options are a single monolithic workflow that always runs everything, or per-service workflows that only trigger when relevant files change.

Additionally, the e2e smoke test — which spins up Docker Compose, starts all pipeline services, injects a synthetic event, and asserts a recommendation appears in PostgreSQL — is fundamentally different from unit/integration tests: it requires Docker-in-Docker, real Kafka, real PostgreSQL, and takes up to 90 seconds. It should not block the fast feedback loop on every file change.

## Decision

One GitHub Actions workflow per service (`ci-{service}.yml`), each running on `pull_request` and `push` to `main` only when files under `services/{service}/`, `shared/python-common/`, or `pyproject.toml` change. Each workflow runs three steps sequentially: `ruff check`, `mypy`, then `pytest` against the service's unit (and integration, if available) tests.

A separate `ci-e2e.yml` workflow runs the full pipeline smoke test. It triggers on the same events but without path filters — any change to the repo may affect the integrated pipeline, so it always runs.

All action SHAs are pinned (`actions/checkout@<sha>`, `astral-sh/setup-uv@<sha>`) to prevent supply-chain drift.

## Alternatives considered

**Single monolithic workflow** — *Rejected*
One workflow that lints and tests all eight services on every push. Simple to maintain but wastes CI minutes: a change to `lastfm-ingester` triggers mypy and pytest for `scorer`, `api`, etc., which have no relation to the change. On a team, this slows PR feedback.

**Matrix strategy (one job, service as matrix dimension)** — *Rejected*
A single workflow with `strategy.matrix` over all services. Cleaner YAML but inflexible: path filters per matrix value are not natively supported in GitHub Actions, making selective triggering awkward. Also couples all service checks into one workflow status, preventing per-service badge granularity.

**Separate repos per service** — *Rejected*
True isolation, but moves the shared library into a published package, adds cross-repo dependency management, and makes local development far more complex. Out of scope for the current MVP.

## Consequences

✅ Fast feedback: a change to one service triggers only that service's CI (~30s), not the full suite.
✅ Per-service status badges in each service README reflect the actual state of that service.
✅ E2e is isolated: it can be slow and infra-heavy without affecting the fast service-level checks.
✅ Pinned SHAs prevent undiscovered action version bumps from breaking builds silently.
❌ Nine workflow files to maintain; changes to the common pattern (e.g., adding a new lint rule) must be applied in eight places.
❌ Path filter logic must be kept in sync with the actual service directory names; renaming a service requires updating its workflow.

## When to reconsider

If workflow duplication becomes painful (more than one change per quarter touches all nine files), extract the shared steps into a reusable composite action or use a workflow templating tool. If the number of services grows beyond ~15, evaluate Nx or Turborepo for smarter change detection.
