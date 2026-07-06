# Workflow

How to build, configure, run, test and deploy the service.

## Prerequisites

- Python **3.10+**
- **PDM** (dependency manager) for local dev
- Docker / Docker Compose (optional, for containerised runs and tests)

## Dependency management

PDM is the source of truth (`pyproject.toml` + `pdm.lock`). `requirements.txt`
is **generated** from the lock for the Docker build.

```bash
pdm install                 # install into the local venv
pdm run update-all          # renew lock, update deps, re-export requirements.txt
pdm run export              # regenerate requirements.txt only
```

The runtime pins `fastapi-mcp` to the `am1ter` fork via a git URL; the Docker
builder installs `git` to resolve it.

## Running locally

```bash
cp .env.example .env        # then edit
pdm run dev                 # = pdm run src/main.py, loads .env
```

`main.py` builds the FastAPI app, mounts MCP, and launches uvicorn.

Serving path depends on `ASGI_ENV`:

- `ASGI_ENV=local` → app served at `/`, docs at `/docs`, schema at
  `/openapi.json`.
- otherwise → served under `PREFIX_PATH` (default `/v1`), docs at
  `<prefix>/docs`.

> ⚠️ `launch_asgi_server` only actually starts uvicorn when
> `ASGI_ENV != "development"`. With the shipped defaults (`prod`, or `local`
> from `.env.example`) it starts fine, but setting `ASGI_ENV=development` would
> silently **not** start the server. See
> [known-errors.md](known-errors.md#e6).

Default port is `3000` in code (`PORT`), but the Docker image and compose set
`8000`. The README's mention of "hot reload" is aspirational — uvicorn is run
without `reload=True`.

## Configuration (environment variables)

Read directly with `os.getenv`. Key variables actually consumed by the code:

| Variable | Default | Used for |
| -------- | ------- | -------- |
| `API_KEYS` | *(unset → auth off)* | comma-separated valid `X-API-Key` values |
| `RATE_LIMIT_DEFAULT` | `60/minute` | global slowapi limit |
| `RATE_LIMIT_BACKTEST` | `5/minute` | backtest endpoint limit |
| `DEFAULT_EXCHANGE` | `bitget` | default ccxt exchange |
| `PREFIX_PATH` | `/v1` | API root path (non-local) |
| `HEALTHY_PATH` / `LIVENESS_PATH` | `/healthy` / `/liveness` | health routes |
| `ASGI_ENV` | `prod` (`local` in `.env.example`) | root_path + serve gate |
| `PORT` / `HOST` | `3000` / `0.0.0.0` | uvicorn bind |
| `LOG_FORMAT` | `text` | set `json` for structured logs |
| `LOG_CONFIG_PATH` | `src/log_conf.yaml` | uvicorn log config (non-dev) |
| `APP_ID` | `mmk-mcp-indicadors` | service name in title/health |
| `APP_VERSION` | `1.0.0` | version in title/health |
| `PY_ENV` | `development` | environment label in health |
| `HEALTH_EXCHANGE_TIMEOUT` | `3` | `/healthy` exchange-probe timeout (s) |
| `CORS_ORIGINS` | `*` | comma-separated allowed origins |
| `RSI_OVERBOUGHT`, `RSI_OVERSOLD`, `ADX_TREND`, `BBWP_HIGH`, `BBWP_LOW` | 70/30/25/80/20 | rule thresholds (global) |
| `<SYMBOL>_<THRESHOLD>` | — | per-symbol threshold override |
| `<FAMILY>_WEIGHT` | — | per-family vote-weight override |

> ⚠️ `docs/ENVIRONMENT_VARIABLES.md` and `.env.example` are out of sync with the
> code (wrong defaults, `DD_*` vars that the code never reads, missing many of
> the above). See [known-errors.md](known-errors.md#e5).

## Testing

Offline `pytest` suite (no network, synthetic OHLCV). From the repo root with
`src/` on the path:

```bash
PYTHONPATH=src pytest -q tests/
```

Or in Docker (mirrors CI):

```bash
docker build -f Dockerfile.test -t mmk-test .
docker run --rm -v "$PWD":/app -w /app mmk-test pytest -q tests/
```

`tests/requirements-test.txt` is a runtime subset (no private packages).
`cloudbuild.yaml`'s comment references "46 tests". Notable suites: indicators,
rules, konkorde golden, market-data cache, movements ATR sizing, sizing parity,
backtest, security, MCP auth, health.

> This review environment **cannot run docker/pytest or install deps** — the
> commands above are documented for humans, not executed here.

## CI/CD (`cloudbuild.yaml`)

Three steps on Google Cloud Build:

1. **Test** — builds `Dockerfile.test` and runs `pytest -q tests/`. A failure
   fails the build and **blocks deploy**.
2. **Build** — kaniko builds the `runtime` target and pushes to Artifact
   Registry (with a 24h cache).
3. **Deploy** — `gcloud run deploy` to Cloud Run:
   `us-west1`, port 8000, `--allow-unauthenticated`, `max-instances=2`,
   `API_KEYS` from Secret Manager (`mmk-api-keys:latest`).

Because the service is publicly reachable, the `API_KEYS` secret is the only
access control for `/v1/*` and the MCP transport.

## Docker

- `Dockerfile` — multi-stage: `builder` (wheels) → `runtime` (non-root,
  healthcheck, `CMD python main.py`) → `debugger` (adds ptvsd on port 5678).
- `docker-compose.yaml` — runs the `runtime` target, `read_only` FS + tmpfs,
  `LOG_FORMAT=json`, healthcheck on `/v1/healthy`, publishes `${PORT:-8000}`.

## MCP usage (AI editors)

Install `mcp-proxy`, point your editor's `mcp.json` at
`http://<host>:<port>/<prefix>/mcp` (e.g. `.../v1/mcp`), and supply the API key.
The MCP transport enforces the same `X-API-Key` as the HTTP routes.

## Adding an endpoint (recap)

1. New `Service` class in `src/controllers/metrics/`.
2. New router in `src/routes/v1/<feature>_routing.py`, handler `@has_errors`.
3. Register in `src/routes/v1/__init__.py`.
4. Add an offline test with synthetic data (patch the market-data loader).
