# ADR-003: uv as Python workspace manager for the Signal monorepo

- **Status**: Accepted
- **Date**: 2026-05-21

## Context

Signal is a Python monorepo with 7 services under `services/*` and shared infrastructure code in `shared/python-common`. Each service needs to depend on `signal-common` without publishing it to PyPI — it's a local, frequently-changing library. The project also needs reproducible builds both locally and inside Docker, and fast dependency installs matter because each service gets its own Docker image. The team is a single developer iterating quickly on the MVP.

## Decision

`uv` is used as the sole package manager and workspace orchestrator for the entire monorepo. All services are declared as `[tool.uv.workspace]` members; `signal-common` is referenced as a workspace path dependency without any publish step.

## Alternatives considered

**pip + requirements.txt per service** — *Rejected*
No native workspace concept: sharing `signal-common` would require either publishing it to a private index or duplicating the `PYTHONPATH` setup in every Dockerfile and CI step. Lockfiles are manual.

**Poetry** — *Rejected*
Poetry workspaces exist but are less mature than uv's; `poetry install` for large dependency trees is significantly slower than `uv sync`. Poetry also lacks native support for installing a single workspace member (`--package` flag), which is critical for building minimal Docker images per service.

**pdm** — *Rejected*
Similar workspace support to uv but a much smaller ecosystem and less Docker-oriented tooling. No meaningful advantage over uv for this use case.

**uv** — *Accepted*

## Consequences

✅ `signal-common` is consumed as an editable workspace dependency from any service with no publish step — changes are immediately visible across the monorepo.
✅ `uv sync --package signal-lastfm-ingester --no-dev --frozen` installs only one service's closure in the Docker builder stage, keeping images small and builds fast (~1.5s for 22 packages).
✅ `uv.lock` at the workspace root gives a single reproducible lockfile covering all services and the shared library.
❌ `uv` is newer and less battle-tested than Poetry or pip in production environments; the `tool.uv.dev-dependencies` field used in `pyproject.toml` is already deprecated in favour of `dependency-groups`, meaning a migration will be needed before uv's next major breaking change.
❌ Docker images must copy the full workspace source tree (not just the installed `.venv`) because `signal-common` is an editable install — the source directory must be present in the runtime image.

## When to reconsider

If a second developer joins and their machine shows `uv.lock` conflicts on a regular basis due to cross-platform resolution differences (Linux vs macOS), or if uv's deprecation of `tool.uv.dev-dependencies` becomes a breaking change before migration, switch to `dependency-groups` at that point. If the editable-install constraint on Docker image size becomes a problem (images >1 GB), evaluate building `signal-common` as a proper wheel instead.
