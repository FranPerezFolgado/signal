# Stage 1 — builder: install deps with uv
FROM python:3.12-slim AS builder

WORKDIR /workspace

RUN pip install --no-cache-dir uv

# Copy workspace definition first (maximises layer cache reuse)
COPY pyproject.toml uv.lock ./

# Copy source packages needed by this service
COPY shared/python-common/ shared/python-common/
COPY services/normalizer/ services/normalizer/

# Install only runtime deps; honour lockfile for reproducibility
RUN uv sync --package signal-normalizer --no-dev --frozen

# Stage 2 — runtime: minimal image with installed env + source
FROM python:3.12-slim

WORKDIR /workspace

# signal-common is an editable workspace dep — source must be present
COPY --from=builder /workspace /workspace

ENV PATH="/workspace/.venv/bin:$PATH"

CMD ["signal-normalizer"]
