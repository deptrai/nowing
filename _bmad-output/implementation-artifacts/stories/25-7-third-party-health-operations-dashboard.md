---
story_key: 25-7-third-party-health-operations-dashboard
status: ready-for-dev
baseline_commit: 40a7a5031
epic: 25
story: 7
---

# Story 25.7: Third-Party Health & Operations Dashboard

**Status:** `ready-for-dev`

**Governed by:** `FR-41b` (PRD §4.8), Story 25.4, Story 6.8, Story 8.11, Story 26.3, `AD-25.7`, `INV-25.8`, Epic 25 in [`_bmad-output/planning-artifacts/epics.md`](../planning-artifacts/epics.md) lines 3758–3779.

---

## Story

As a **Platform Superadmin**,
I want a unified health dashboard that monitors the health of every third-party integration (LLM/embedding/vision models, scrapers, proxies, connectors, messaging, payments, storage, infrastructure, ChainLens),
so that I can detect outages, degradation, and cost anomalies before users are affected and respond from a single operations center.

---

## Acceptance Criteria

### AC-1 — Tabbed Admin Operations Dashboard

**Given** `/admin/telemetry` is loaded by a verified Superadmin interactive session,
**When** the dashboard renders,
**Then** it displays:

- A top **Active Alerts banner** showing critical alerts with service name, failure reason, last successful probe, recommended action, and an **Acknowledge** button.
- Tabbed sections: **Infrastructure**, **LLM/AI**, **Scrapers**, **Connectors**, **Messaging**, **Payments**, **Storage**.
- Each tab shows a grid of **Health Status Cards** with:
  - Service name / icon.
  - Status badge (`healthy`/`degraded`/`unavailable`/`not_configured`/`disabled`).
  - Last probe latency.
  - 15m success/error rate.
  - Last error (truncated tooltip).
- Consistent styling with `nowing_web/app/admin/telemetry/page.tsx` (high-density tables, monospace numbers, recharts charts).

### AC-2 — Pluggable Health Probe System

**Given** the backend probe scheduler runs,
**When** it executes,
**Then** it:

- Discovers probe targets from `CapabilityRegistry` (scrapers, connectors, messaging, ChainLens) and existing service registries (models, proxies, infrastructure).
- Runs probes at category-specific intervals:
  - Infrastructure: 30s.
  - LLM/AI models: 2m.
  - Scrapers: 5m.
  - Connectors: 15m.
  - Messaging / Payments / Storage / ChainLens: 5m.
- Records per target: `latency_ms`, `status`, `error_rate_15m`, `success_rate_15m`, `last_error`, `last_probe_at`, `next_probe_at`, `metadata`.
- Persists the **latest snapshot** to Redis (TTL 5m) and **current/historical rows** to `admin_health_status` + `admin_health_history`.
- Emits a Redis pub/sub event (`nowing:health:updates`) for real-time UI refresh.
- Does **not** auto-disable any model/scraper; it only emits alerts (human-in-the-loop for v1).

### AC-3 — Default Alert Rules & Alerting

**Given** a critical service fails 2 consecutive probes,
**When** the alert engine evaluates rules,
**Then** it:

- Creates an `admin_health_alerts` row with `status=open`, `service_id`, `rule_id`, `triggered_at`, `message`.
- Deduplicates by `(service_id, rule_id)` within `cooldown_minutes` (default 15m).
- Dispatches to configured admin channels (`in_app`, `email`, `telegram`, `slack`).
- Shows the alert in the **Active Alerts banner** with an **Acknowledge** action that sets `acknowledged_until`.

**Default rules (seeded by migration):**

| Rule | Category | Condition | Severity |
|------|----------|-----------|----------|
| Core infra unavailable | `infra` | `status == unavailable` for 1 consecutive probe | critical |
| LLM/AI model dead | `model` | `status == unavailable` for 2 consecutive probes | high |
| Scraper degraded | `scraper` | `success_rate_15m < 50%` | medium |
| Proxy dead | `proxy` | `status == unavailable` | high |
| ChainLens research degraded | `research` | `status != healthy` for 2 consecutive probes | medium |

### AC-4 — Drill-Down Panel

**Given** the superadmin clicks a service card,
**When** the drill-down opens,
**Then** it displays:

- 24h latency and success-rate charts (recharts line chart).
- Recent error logs (last 50 entries from `admin_health_history` and recent `Run`/`TokenUsage` errors for that service).
- Service metadata: provider, endpoint, region, cost today (if applicable).
- A **Test Now** button to trigger an on-demand probe for that service.

### AC-5 — Backend Admin API & Authz

**Given** any `/api/v1/admin/health/*` endpoint,
**When** called without a Superadmin session,
**Then** it returns `HTTP 403 Forbidden` via `require_superuser` (INV-25.8).

### AC-6 — Tests

**Given** the health probe system,
**When** tests run,
**Then** there are:

- Unit tests for each probe type (model, scraper, proxy, infra, ChainLens).
- Unit tests for `HealthProbeScheduler`, `HealthResultStore`, `AdminHealthAlertEngine`.
- Integration tests for `/api/v1/admin/health/*` routes.
- E2E Playwright test for `/admin/telemetry` tab switching and alert acknowledgement.

---

## Tasks / Subtasks

- [ ] **Task 1: Backend Health Probe Module**
  - [ ] Create `app/services/health/__init__.py`.
  - [ ] Create `app/services/health/probe_base.py` with `HealthProbe(ABC)` and `HealthResult` dataclass.
  - [ ] Create `app/services/health/registry.py` with `HealthProbeRegistry` (category → probe list, dynamic discovery from `CapabilityRegistry` and model/proxy lists).
  - [ ] Create probes:
    - `app/services/health/probes/model_probe.py` — uses `model_connection_service.verify_connection()` / `test_model()` for each global model + BYOK `Connection`.
    - `app/services/health/probes/scraper_probe.py` — probes each capability in `CapabilityRegistry` with category `scraper` / `search`.
    - `app/services/health/probes/connector_probe.py` — probes each connector type with at least one active `Connection`.
    - `app/services/health/probes/infrastructure_probe.py` — PostgreSQL `SELECT 1`, Redis `PING`, Caddy `/health`, Celery worker inspection, Zero Cache keepalive.
    - `app/services/health/probes/chainlens_probe.py` — `GET /api/v1/health` and a lightweight sample search.
    - `app/services/health/probes/proxy_probe.py` — reuse `admin_telemetry_service.get_proxy_health()`.
  - [ ] Create `app/services/health/result_store.py` to persist to Redis and DB.
  - [ ] Create `app/services/health/alert_engine.py` (`AdminHealthAlertEngine`) to evaluate rules, dedupe, dispatch.
  - [ ] Create `app/services/health/scheduler.py` (`HealthProbeScheduler`) to run probes with `asyncio.gather` + semaphore (max 20 concurrent).
  - [ ] Create `app/services/health/third_party_health_service.py` as the public facade.

- [ ] **Task 2: DB Schema & Migrations**
  - [ ] Add `admin_health_status` table.
  - [ ] Add `admin_health_history` table (time-series, TTL 30 days recommended).
  - [ ] Add `admin_health_alert_rules` table.
  - [ ] Add `admin_health_alerts` table.
  - [ ] Seed 5 default alert rules via migration.

- [ ] **Task 3: Celery Scheduler**
  - [ ] Create `app/tasks/celery_tasks/health_probe_task.py` to call `HealthProbeScheduler.run_category(category)`.
  - [ ] Register tasks in `app/celery_app.py` with category-specific `beat` schedules.

- [ ] **Task 4: Backend Admin Routes**
  - [ ] Extend `app/routes/admin_telemetry_routes.py` (preferred over new file per AD-25.7) with:
    - `GET /api/v1/admin/health/status?category=&service_id=`
    - `GET /api/v1/admin/health/history/{service_id}?hours=24`
    - `GET /api/v1/admin/health/alerts`
    - `POST /api/v1/admin/health/alerts/{alert_id}/acknowledge`
    - `POST /api/v1/admin/health/probe/{service_id}` (on-demand)
    - `GET /api/v1/admin/health/categories`
  - [ ] Reuse `require_superuser` from `app/routes/admin_credits_routes.py`.
  - [ ] Add Pydantic schemas in `app/schemas/admin_health.py`.

- [ ] **Task 5: Frontend `/admin/telemetry` Extensions**
  - [ ] Add tabbed navigation to `nowing_web/app/admin/telemetry/page.tsx`.
  - [ ] Create components:
    - `components/admin/health/HealthOverviewGrid.tsx`
    - `components/admin/health/HealthStatusCard.tsx`
    - `components/admin/health/HealthCategoryTabs.tsx`
    - `components/admin/health/AlertBanner.tsx`
    - `components/admin/health/HealthDrillDown.tsx`
  - [ ] Create `nowing_web/lib/apis/admin-health-api.service.ts`.
  - [ ] Add 5-second polling or Redis pub/sub listener for real-time updates.

- [ ] **Task 6: Generic Alert Engine Reuse**
  - [ ] Map `AdminHealthAlertEngine` to existing `app/alerts/` models where possible (reuse `tick.py` schedule, `notify.py` dispatch).
  - [ ] Add `capability_id` or `admin_health` scope to `AlertRule` so health rules are distinguishable from workspace alert rules.
  - [ ] Avoid duplicating notification channel logic; reuse `notify.py` for `in_app`, `telegram`, `email`.

- [ ] **Task 7: Tests**
  - [ ] `tests/unit/services/health/test_*_probe.py`
  - [ ] `tests/unit/services/health/test_scheduler.py`
  - [ ] `tests/unit/services/health/test_alert_engine.py`
  - [ ] `tests/integration/routes/test_admin_health.py`
  - [ ] `nowing_web/tests/admin/health-operations.spec.ts`

---

## Dev Notes

### Existing Code to Reuse (Do Not Reinvent)

- **Admin telemetry foundation:**
  - `nowing_backend/app/services/admin_telemetry_service.py` — proxy health, Celery queue inspection, cost aggregation patterns.
  - `nowing_backend/app/routes/admin_telemetry_routes.py` — route patterns and `require_superuser` guard.
- **Generic Alert Engine:**
  - `nowing_backend/app/alerts/engine/tick.py` — Celery tick scheduler.
  - `nowing_backend/app/alerts/engine/execute.py` — rule execution and diff.
  - `nowing_backend/app/alerts/engine/notify.py` — in-app, Telegram, email dispatch.
  - `nowing_backend/app/alerts/persistence/models/alert_rule.py` — `AlertRule` schema.
- **Capability registry:**
  - `nowing_backend/app/capabilities/core/store.py` — `CapabilityRegistry` with 51 registered capabilities.
- **Model connection verification:**
  - `nowing_backend/app/services/model_connection_service.py` — `verify_connection()` / `test_model()`.
- **Hybrid LLM Router:**
  - `nowing_backend/app/agents/chat/routers/hybrid_llm_router.py` — `_vllm_health()` for vLLM health.
- **Frontend patterns:**
  - `nowing_web/app/admin/telemetry/page.tsx` — existing page to extend with tabs.
  - `nowing_web/components/admin/telemetry/*` — chart/table patterns.

### Key Decisions

1. **Data store — Redis + DB:** Redis holds the latest snapshot and publishes real-time updates; PostgreSQL holds `admin_health_status` (current) + `admin_health_history` (analytics, audit, alert dedupe).
2. **No auto-disable v1:** Health probes only alert; they do not disable models/scrapers to avoid user-facing side effects. Add a `suggested_action` text instead.
3. **Probe concurrency limit:** `asyncio.gather` with `asyncio.Semaphore(20)` to avoid overwhelming external services.
4. **Probe read-only:** All default probes must be non-mutating. Scraper probes should use lightweight `metadata` / `health` calls where available, not real user queries.
5. **Alert engine reuse:** Use existing `app/alerts/` engine; treat health rules as a special `scope='admin'` or `capability_id='admin_health'` rule set.

### Performance & Security Guardrails

- All admin endpoints MUST use `require_superuser`.
- Probe target enumeration must not leak `api_key` or credentials; redact URLs and errors.
- `admin_health_history` should have a TTL/purge policy (30 days default) to avoid unbounded growth.
- Celery beat schedules must be category-specific; do not run all probes every 30s.
- On-demand `POST /probe/{service_id}` must be rate-limited to prevent admin from hammering third-party APIs.

### Suggested File Tree

```
nowing_backend/
  app/services/health/
    __init__.py
    probe_base.py
    registry.py
    scheduler.py
    result_store.py
    alert_engine.py
    third_party_health_service.py
    probes/
      __init__.py
      model_probe.py
      scraper_probe.py
      connector_probe.py
      infrastructure_probe.py
      chainlens_probe.py
      proxy_probe.py
  app/tasks/celery_tasks/health_probe_task.py
  app/schemas/admin_health.py
  app/routes/admin_telemetry_routes.py  (extended)
  alembic/versions/XXX_add_admin_health_tables.py
  tests/unit/services/health/
  tests/integration/routes/test_admin_health.py

nowing_web/
  app/admin/telemetry/page.tsx  (extended with tabs)
  components/admin/health/
  lib/apis/admin-health-api.service.ts
  tests/admin/health-operations.spec.ts
```

---

## Architecture Compliance

- **AD-25.7** — `Admin Operations Health` governed by `ARCHITECTURE-SPINE.md`. Health monitoring is a platform-admin concern; probes are read-only, reuse existing registries, and do not auto-disable third-parties in v1.
- **AD-33** — Reuse Generic Alert Engine; do not build a second notification stack.
- **AD-1** — Health probes live inside the FastAPI monolith; no new microservice.
- **AD-2** — All new tables use Async SQLAlchemy + Alembic migrations.
- **AD-8** — Cost metrics use actual `TokenUsage.cost_micros`; do not invent flat pricing.

---

## References

- Epic 25 & Story 25.7: [`_bmad-output/planning-artifacts/epics.md`](../planning-artifacts/epics.md) lines 3758–3779.
- FR-41b: [`_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`](../planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md) line 956.
- Sprint Change Proposal: [`_bmad-output/implementation-artifacts/sprint-change-proposal-2026-09-03.md`](../implementation-artifacts/sprint-change-proposal-2026-09-03.md).
- Detailed design: [`_bmad-output/implementation-artifacts/design/admin-third-party-health-design.md`](../implementation-artifacts/design/admin-third-party-health-design.md) (to be copied from job temp if not present).
- `CapabilityRegistry`: `nowing_backend/app/capabilities/core/store.py`.
- `Generic Alert Engine`: `nowing_backend/app/alerts/`.
- `AdminTelemetryService`: `nowing_backend/app/services/admin_telemetry_service.py`.

---

## Verification Commands

```bash
# Backend lint & tests
cd nowing_backend
uv run ruff check app/services/health app/routes/admin_telemetry_routes.py app/schemas/admin_health.py
uv run pytest tests/unit/services/health tests/integration/routes/test_admin_health.py -q

# Frontend typecheck & biome
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/admin/telemetry/page.tsx components/admin/health lib/apis/admin-health-api.service.ts
```

---

## Change Log

- 2026-09-03: Created Story 25.7 file, PRD FR-41b, Epic entry, and sprint-status entry after Correct Course SCP approval.
