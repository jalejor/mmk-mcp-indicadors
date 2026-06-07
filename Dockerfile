# syntax=docker/dockerfile:1.6
#
# Multi-stage build:
# - `builder` resolves Python wheels with PDM tooling.
# - `runtime` ships only the resolved wheels and the source tree, runs as a
#   non-root user and exposes a HEALTHCHECK that hits /v1/healthy.
# - `debugger` adds ptvsd for IDE attach but otherwise inherits everything.
#
FROM python:3.10-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends gcc git ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd --system --gid 1000 app \
  && useradd --system --uid 1000 --gid app --home /app app

WORKDIR /app

COPY --from=builder /install /usr/local
COPY ["src", "./"]

USER app:app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl --fail --silent --show-error http://localhost:${PORT:-8000}/v1/healthy || exit 1

CMD ["python", "main.py"]

# ---------------------------------------------------------------------------
FROM runtime AS debugger

USER root
RUN pip install --no-cache-dir ptvsd
USER app:app

CMD ["python", "-m", "ptvsd", "--host", "0.0.0.0", "--port", "5678", "--wait", "--multiprocess", "main.py"]
