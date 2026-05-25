FROM python:3.12-slim AS builder

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

COPY shared/python-common/ shared/python-common/
COPY services/api/ services/api/

RUN uv sync --package signal-api --no-dev --frozen

FROM python:3.12-slim

WORKDIR /workspace

COPY --from=builder /workspace /workspace

ENV PATH="/workspace/.venv/bin:$PATH"

CMD ["signal-api"]
