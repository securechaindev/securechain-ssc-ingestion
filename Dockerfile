FROM python:3.12-slim AS builder

WORKDIR /opt/dagster/app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim

WORKDIR /opt/dagster/app

RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH

RUN mkdir -p /opt/dagster/dagster_home

COPY dagster_home/dagster.yaml /opt/dagster/dagster_home/dagster.yaml
COPY dagster_home/workspace.yaml /opt/dagster/dagster_home/workspace.yaml

COPY src/ ./src/

EXPOSE 3000

CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000"]