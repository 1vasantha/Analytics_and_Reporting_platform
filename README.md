# Analytics Platform

A real-time analytics and reporting platform: multi-tenant, multi-role event ingestion, custom dashboards with live-refreshing charts, threshold alerts with multi-channel notifications, and scheduled email reports.

## Quick start

The fastest path to a working demo is Docker Compose:

```bash
git clone <this-repo>
cd analytics-platform
docker compose up
```

Then visit:
- **App**: http://localhost:3000 — login as `demo@example.com` / `demopass123`
- **API docs**: http://localhost:8000/docs
- **Mailhog** (catches outgoing emails): http://localhost:8025
- **Flower** (Celery monitoring): http://localhost:5555

The first boot runs migrations and seeds a demo organization with 5,000 sample events, two dashboards, and two alerts.

## What's inside

```
analytics-platform/
├── backend/           FastAPI + SQLAlchemy 2.0 async + Celery + Redis
│   ├── app/
│   │   ├── api/       HTTP layer (endpoints, dependencies, middleware)
│   │   ├── core/      Config, security, logging, exceptions
│   │   ├── db/        SQLAlchemy base, session, Redis client
│   │   ├── models/    Domain ORM models
│   │   ├── schemas/   Pydantic request/response contracts
│   │   ├── services/  Business logic (auth, ingestion, metrics, alerts...)
│   │   ├── websockets/ Real-time push (org-scoped channels)
│   │   ├── workers/   Celery app + tasks (CSV, alert eval, reports)
│   │   └── templates/ Email templates (Jinja2)
│   ├── alembic/       DB migrations
│   ├── tests/         pytest suite (async, transactional fixtures)
│   └── scripts/seed.py  Demo data generator
│
├── frontend/          Next.js 14 (App Router) + React 18 + TypeScript
│   └── src/
│       ├── app/       Pages: login, register, dashboards, alerts, reports, settings
│       ├── components/ ChartRenderer, WidgetCard, WidgetEditor, AppShell
│       ├── hooks/     useWebSocket
│       ├── lib/       API client (axios with token refresh), utils
│       ├── stores/    Zustand stores: auth, notifications
│       └── types/     Shared types mirroring backend schemas
│
└── docker-compose.yml  Orchestrates postgres, redis, mailhog, backend, worker, beat, flower, frontend
```

## Architecture

**Backend (FastAPI)** is structured as clean layers:

- `api/` — HTTP concerns only: routes, request parsing, auth dependencies, rate limiting middleware
- `services/` — Business logic; pure async functions on a DB session
- `models/` — SQLAlchemy 2.0 typed ORM with multi-tenant FK isolation
- `schemas/` — Pydantic v2 with rigorous validation (e.g. metric query DSL)

**Real-time** uses two paths:
1. After event ingestion the service publishes `org:{id}:events` on Redis. WebSocket-serving processes subscribe via `pubsub` and fan out `events_ingested` messages to all connected clients in that org.
2. The Celery alert worker publishes `org:{id}:ws` messages when alerts fire — the WebSocket layer pushes them to the in-app notification center.

**Multi-tenancy** is enforced at every query: every domain table carries `organization_id`, and services accept it as a required parameter. The metric service uses parameterized SQL exclusively; field names are whitelisted via Pydantic regex validators to prevent injection through the query DSL.

**Caching** — metric query results are cached in Redis keyed on `sha256(org + query_json)` with granularity-aware TTL (15s for minute-level, 60s for hour, 300s for day). Cache is invalidated on every event ingest for that org.

**Rate limiting** uses Redis sorted-set sliding-window counters with three tiers: auth (5/min), ingestion (1000/min), global (60/min).

## Backend deep dive

### The metric query engine (`app/services/metric_service.py`)

A declarative `MetricQuery` (Pydantic model) is translated into a parameterized SQLAlchemy Core query. Key design choices:

- **No string interpolation** — every user value is bound as a parameter.
- **Field whitelist** — top-level columns are mapped via a static dict; properties paths (`properties.country`) translate to JSONB `->>` operators.
- **Time bucketing** uses `date_trunc()` so the index on `(org_id, occurred_at)` can be used.
- **Result shape** — `MetricQueryResult` includes a roll-up `total` (useful for KPI widgets) plus per-bucket `points` (with optional `group` for multi-series).

### Auth & sessions (`app/services/auth_service.py`)

- bcrypt with cost factor 12.
- Access tokens (30 min) carry `org` and `role` claims so RBAC checks don't need a DB hit.
- Refresh tokens (7 days) have their JTI stored in Redis. Refresh rotates the JTI so a stolen token works at most once.
- Constant-time-ish login: `verify_password` is always called even on missing users to mitigate username enumeration timing attacks.

### Workers (`app/workers/tasks.py`)

Three task groups:

1. `process_csv_ingestion` — reads pandas chunks, validates each row via `EventCreate`, bulk-inserts in 500-row batches, streams progress back to the `IngestionJob` row.
2. `evaluate_all_alerts` — Beat-scheduled (every 60s); evaluates every enabled alert, respects per-alert cooldown, emits notifications across configured channels (in-app via WebSocket pub/sub, email via aiosmtplib, webhook via httpx).
3. `run_scheduled_reports` — Beat-scheduled (every 60s); finds reports with `next_run_at <= now`, executes each widget's query, renders `dashboard_report.html`, emails, advances `next_run_at`.

## Frontend deep dive

- **Routing** uses Next.js 14 App Router. Authenticated routes share an `AppShell` (sidebar nav, notification bell, user menu).
- **Data fetching** is TanStack Query; cache keys are namespaced by entity so `useMutation` can invalidate precisely. Widget data queries auto-refetch on a dashboard's `refresh_interval`.
- **Auth state** lives in a Zustand store with `localStorage` persistence. The axios client has an interceptor that handles `401` by transparently rotating the refresh token.
- **Real-time** — a single WebSocket connection is opened on auth. Inbound `events_ingested` messages invalidate the `widget-data` cache (driving re-renders); inbound `alert_triggered` messages push directly into the notification store.
- **Charts** — Recharts. The `ChartRenderer` pivots `MetricQueryResult.points` into a wide format suitable for multi-series line/bar/area charts; KPI uses a custom formatted-number display.

## Local development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # edit as needed

# Start Postgres + Redis + Mailhog (or use docker compose up postgres redis mailhog)
alembic upgrade head
python -m scripts.seed

uvicorn app.main:app --reload
# In other terminals:
celery -A app.workers.celery_app worker --loglevel=INFO
celery -A app.workers.celery_app beat --loglevel=INFO
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Tests

```bash
cd backend
# Create the test database
createdb analytics_test
pytest
```

Tests use transactional fixtures: each test runs inside a transaction that's rolled back, keeping tests fast and isolated without a teardown step.

## API surface

Full OpenAPI docs at `/docs` once running. Highlights:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/auth/register` | Create org + owner user |
| POST | `/api/v1/auth/login` | Get access + refresh tokens |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| POST | `/api/v1/ingest/events` | Single event (API key) |
| POST | `/api/v1/ingest/events/batch` | Up to 1000 events (API key) |
| POST | `/api/v1/ingest/csv` | Async CSV upload (JWT) |
| GET/POST/PATCH/DELETE | `/api/v1/dashboards/...` | Dashboard CRUD |
| POST | `/api/v1/dashboards/query` | Run an ad-hoc metric query |
| GET/POST/PATCH/DELETE | `/api/v1/alerts/...` | Alert CRUD |
| GET | `/api/v1/notifications` | In-app notifications |
| GET/POST/PATCH/DELETE | `/api/v1/reports/...` | Scheduled report CRUD |
| WS | `/ws?token=<jwt>` | Real-time push |

## Deployment

### Backend → Railway / Render

- Builds the `backend/Dockerfile`. Expose port 8000.
- Required env: `SECRET_KEY`, `POSTGRES_*`, `REDIS_*`, `BACKEND_CORS_ORIGINS`, `FRONTEND_URL`.
- Run three processes from the same image:
  - **web**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - **worker**: `celery -A app.workers.celery_app worker --loglevel=INFO`
  - **beat**: `celery -A app.workers.celery_app beat --loglevel=INFO`
- Run `alembic upgrade head` as a release step.

### Frontend → Vercel

- Set root directory to `frontend/`.
- Env vars: `NEXT_PUBLIC_API_URL=https://your-backend.example.com`, `NEXT_PUBLIC_WS_URL=wss://your-backend.example.com`.
- Build command: `npm run build`. Output: `.next`.

## Roles & permissions

| Role | Manage org | Edit dashboards/alerts | View |
|------|:----------:|:----------------------:|:----:|
| Owner | ✓ | ✓ | ✓ |
| Admin | ✓ | ✓ | ✓ |
| Analyst | | ✓ | ✓ |
| Viewer | | | ✓ |

Owner is the only role created via `/register`; other roles are created via invitation (skeleton in place, full UI deferred to a follow-up).

## Tech choices, briefly

- **FastAPI** — best-in-class async perf + OpenAPI generation + type safety end-to-end.
- **SQLAlchemy 2.0 async** — typed Mapped[], modern API; using PG-only features (JSONB, GIN, `date_trunc`) deliberately because portability isn't worth the perf loss for time-series workloads.
- **Pydantic v2** — fast validation, exhaustive enough for the metric DSL.
- **Celery + Redis** — proven for the mix of one-shot (CSV) and Beat-scheduled (alerts/reports) work.
- **Recharts** — easy declarative API, customizable enough for our aesthetic, light on bundle weight.
- **Zustand** — simpler than Redux; perfect for auth/notification stores. TanStack Query handles server state separately.

## License

MIT
