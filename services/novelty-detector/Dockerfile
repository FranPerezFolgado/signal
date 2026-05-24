# Stage 1 — builder: install deps with uv
FROM python:3.12-slim AS builder

WORKDIR /workspace

RUN pip install --no-cache-dir uv

# Copy workspace definition first (maximises layer cache reuse)
COPY pyproject.toml uv.lock ./

# Copy source packages needed by this service
COPY shared/python-common/ shared/python-common/
COPY services/novelty-detector/ services/novelty-detector/

# Install only runtime deps; honour lockfile for reproducibility
RUN uv sync --package signal-novelty-detector --no-dev --frozen

# Stage 2 — runtime: minimal image with installed env + source
FROM python:3.12-slim

WORKDIR /workspace

# signal-common is an editable workspace dep — source must be present
COPY --from=builder /workspace /workspace

ENV PATH="/workspace/.venv/bin:$PATH"

CMD ["signal-novelty-detector"]
