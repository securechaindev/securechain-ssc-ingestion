FROM python:3.13-slim AS builder

WORKDIR /opt/dagster/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-group dev --no-cache

FROM python:3.13-slim

WORKDIR /opt/dagster/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/dagster/app/.venv /opt/dagster/app/.venv

ENV PATH=/opt/dagster/app/.venv/bin:$PATH

RUN mkdir -p /opt/dagster/dagster_home

COPY dagster_home/dagster.yaml /opt/dagster/dagster_home/dagster.yaml
COPY dagster_home/workspace.yaml /opt/dagster/dagster_home/workspace.yaml

COPY src/ ./src/

EXPOSE 3000

CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000"]