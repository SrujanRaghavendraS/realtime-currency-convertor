# FX Rate Monitor — Real-Time Data Aggregation Service

FastAPI + Redis + React service that aggregates USD→INR/EUR/GBP/JPY rates from the public exchangerate.dev API, with centralized collection, a 15-observation sliding window, EWMA fallback and separate Free / Premium Preview views.

## Initial thought process
See [MY_APPROACH.md](MY_APPROACH.md) (written independently before implementation).

## Architecture
```
exchangerate.dev ──(1 req / 10 min open, 15 min closed)──> Collector (asyncio, Redis lock, budget guard)
                                           │ validate, record metrics
                                           ▼
                                         Redis: latest obs, 15-obs window per pair,
                                                tier snapshots, metrics, demo state
                                           ▲
React dashboard ──> nginx ──> FastAPI  /api/rates?plan=free|premium
                                       /api/history  /api/metrics  /api/demo/*  /health
```
API requests never call the provider. See [decisions.md](decisions.md) for trade-offs.

## Stack
Python 3.12, FastAPI, httpx, redis-py · Redis 7 · React 18 + Vite · nginx · Docker Compose.

## Provider (verified 2026-11-01)
| | Keyless | Free key |
|---|---|---|
| Quota | 100 req/hour per IP | 5,000 req/month |
| Rate | 10 req/min | 10 req/min |
| Delay | 15 min (weekends: Friday ECB fix) | 15 min |

Attribution "Rates by exchangerate.dev" is shown next to the rates, as the free plan requires.

## Run locally (Docker)
Requires Docker Desktop (Compose v2.24+). Run all commands from the project root.

### First start
```bash
cp .env.example .env              # optionally set PROVIDER_API_KEY
docker compose up -d --build      # builds and starts redis, backend, frontend
```
- Dashboard: http://localhost:8080 (change with `FRONTEND_PORT=xxxx` in `.env`)
- API: http://localhost:8000/api/rates?plan=free
- Health: http://localhost:8000/health

### Check status and logs
```bash
docker compose ps                     # container status
docker compose logs -f backend        # follow collector / API logs
docker compose logs -f frontend       # nginx logs
```

### Develop without stopping the stack
Rebuild only the service you changed; Redis keeps its data.
```bash
docker compose up -d --build --no-deps backend    # after backend code or .env changes
docker compose up -d --build --no-deps frontend   # after frontend changes
docker compose restart backend                    # restart without rebuilding
```

### Inspect Redis
```bash
docker compose exec redis redis-cli keys "fx:*"
```

### Stop
```bash
docker compose stop        # stop containers, keep them and Redis data
docker compose down        # remove containers, keep Redis data volume
docker compose down -v     # remove containers AND Redis data (sliding window, metrics)
```

## Run without Docker
```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/uvicorn app.main:app --port 8000      # needs Redis on localhost:6379
cd frontend && npm install && npm run dev           # http://localhost:5173
```

## Environment variables
See [.env.example](.env.example). Key ones: `PROVIDER_API_KEY` (optional, sent as `Authorization: Bearer`), `TRADING_INTERVAL_SECONDS` (600), `NON_TRADING_INTERVAL_SECONDS` (900), `BUDGET_SAFETY` (0.9), `FREE_UPDATE_EVERY_N` (5), `PREMIUM_UPDATE_EVERY_N` (1), `WINDOW_SIZE` (15), `EWMA_ALPHA` (0.4), `EWMA_MIN_OBSERVATIONS` (3), `MAX_DATA_AGE_SECONDS` (21600), `DEMO_MODE`, `REDIS_URL`, `CORS_ORIGINS`.

## API
| Endpoint | Purpose |
|---|---|
| `GET /api/rates?plan=free\|premium` | Aggregated rates with per-currency source, observation/retrieval time, status |
| `GET /api/history?pair=INR` | Sliding-window observations with running EWMA (Premium trend chart) |
| `GET /api/metrics` | Quota, reliability, sliding window, collector health and schedule |
| `GET /api/demo/status` | Both simulation states |
| `POST /api/demo/{free\|premium}/{start\|stop}` | Simulation controls (403 unless `DEMO_MODE=true`) |
| `GET /health` | Health check |

Statuses: `LIVE_FROM_PROVIDER` (fresh from provider, not live market), `CACHED`, `FALLBACK_ESTIMATED` (EWMA), `STALE` (last-known-good), `UNAVAILABLE`.

## Fallback
Provider fails → EWMA over the window (≥ 3 observations) → last-known-good (STALE) → UNAVAILABLE if retrieved > 6 h ago. Original timestamps are kept. On recovery the next success restores provider data.

## Failure simulation
Click **▶ Simulate Free API Failure** (HTTP 429 / outage / timeout) or **▶ Simulate Premium API Failure** in each card. Free shows the EWMA or last-known-good fallback; Premium steps through primary → secondary → public API → last-known-good every 8 s. Each stops independently via **Stop / Reset** or auto-expires after 120 s. No real API calls are made and real quota is untouched.

Tip: EWMA needs 3 collections. To see it quickly in a demo, set `TRADING_INTERVAL_SECONDS=60` and `NON_TRADING_INTERVAL_SECONDS=60` temporarily (keyless quota allows this for short periods).

## Dashboard extras
- **Premium trend chart**: collected rates and EWMA for the selected currency (last 15 observations).
- **How it works**: flowcharts for the Free strategy, the Premium fallback hierarchy and the rate-limit strategy, with the live active step highlighted.
- **EWMA explainer**: formula, worked example, α slider (teaching only) and the live INR EWMA.

## Tests
```bash
cd backend && .venv/Scripts/python -m pip install -r requirements-dev.txt && .venv/Scripts/python -m pytest -q
```
Covers EWMA math, provider parsing, window trimming, snapshot policy and simulation independence.

## Deployment
Not deployed yet. Deployment URLs: _TBD_.

## Limitations
See [decisions.md](decisions.md#known-limitations).
