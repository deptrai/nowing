---
story_key: 25-7-third-party-health-operations-dashboard
status: done
baseline_commit: 40a7a5031
epic: 25
story: 7
---

# Story 25.7: Third-Party Health & Operations Dashboard

**Status:** `done`

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

### Review Findings — Chunk 1: Backend Health Core (2026-09-04)

**Layer status:** All 4 split-run subagents completed: Blind Hunter (probes+registry), Blind Hunter (core+data), Acceptance Auditor (probes+registry), Acceptance Auditor (core+data).

#### Decision-needed
- [ ] [Review][Patch] **How should global model probes obtain API keys for `model_connection_service.verify_connection()`?** — `ModelHealthProbe` creates a temporary `Connection` with `provider`, `base_url`, and `extra={"model_ids": [...]}` but no `api_key`/`credentials`, so global model probes (azure-gpt-5, deepseek-chat, gemini, text-embedding-3-small, vllm) will likely return `not_configured` or `unavailable` even when the platform is configured. AC-2 requires probing each global + BYOK model. Either read provider API keys from `config`, look up a default `Connection` row, or change `verify_connection` to accept a key/credentials override. — `nowing_backend/app/services/health/probes/model_probe.py:116-121`
- [ ] [Review][Patch] **Should Caddy/Zero Cache probes be skipped when their config attributes do not exist?** — `InfrastructureHealthProbe` falls back to `http://localhost:2019/metrics` and `http://localhost:4848/keepalive` via `getattr(config, "CADDY_ADMIN_URL", ...)` and `getattr(config, "ZERO_CACHE_KEEPALIVE_URL", ...)`. These attributes are not defined on `app.config`, so the probe will always report `unavailable` in Dokploy/Traefik deployments. Decide whether to add config attributes, skip the component when unset, or remove these probes from the default set. — `nowing_backend/app/services/health/probes/infrastructure_probe.py:95-128`

#### Patch
- [ ] [Review][Patch] **Model and Schema Discrepancy for `acknowledged_at` and Missing Foreign Key Constraints** — HealthAlertItem declares acknowledged_at: datetime | None = None, but the AdminHealthAlert database model does not define an acknowledged_at column (it only defines acknowledged_by and acknowledged_until). When serialized using from_attrib… — `nowing_backend/app/schemas/admin_health.py`
- [ ] [Review][Patch] **Race Condition in `HealthResultStore.save_result` Status Upsert** — `nowing_backend/app/services/health/result_store.py`
- [ ] [Review][Patch] **Flawed Rolling 15-Minute Rate Calculation and Hardcoded Next Probe Time** — `nowing_backend/app/services/health/result_store.py`
- [ ] [Review][Patch] **Incomplete Metric Condition Evaluation in `AdminHealthAlertEngine`** — `nowing_backend/app/services/health/alert_engine.py`
- [ ] [Review][Patch] **Unenforced Alert Cooldown and Overwritten Incident Timestamps** — `nowing_backend/app/services/health/alert_engine.py`
- [ ] [Review][Patch] **Incomplete Alert Auto-Resolution and Missing Reopening of Expired Snoozes** — `nowing_backend/app/services/health/alert_engine.py`
- [ ] [Review][Patch] **Uncalled Error Sanitization and Missing Probe Timeouts in `HealthProbeScheduler`** — raw error messages from probe.probe() are passed directly to storage. Additionally, probe.probe() … — `nowing_backend/app/services/health/scheduler.py`
- [ ] [Review][Patch] **Flawed Overall Status Aggregation in `ThirdPartyHealthService.get_overview`** — `nowing_backend/app/services/health/third_party_health_service.py`
- [ ] [Review][Patch] **Missing API Routes for Alert Resolution, Rule Management, and Category Probes** — The API provides no endpoint to manually resolve an active alert (POST /health/alerts/{alert_id}/resolve). There are also no CRUD endpoints for AdminHealthAlertRule, meaning alert rules cannot be created, updated, or disabled via… — `nowing_backend/app/routes/admin_telemetry_routes.py`
- [ ] [Review][Patch] **Missing Dedicated Queues and Distributed Locks for Celery Health Tasks** — The Celery beat schedule adds nine new tasks running as frequently as every 30 seconds, but does not route them to a dedicated queue via task_routes. Running them on the default queue risks starving critical application tasks. In ad… — `nowing_backend/app/celery_app.py`
- [ ] [Review][Patch] **Stubbed Notification Channel in `AdminHealthAlertEngine._dispatch_notification`** — `nowing_backend/app/services/health/alert_engine.py`
- [ ] [Review][Patch] **Unpaginated Endpoints for High-Frequency Historical Data** — The GET /health/history/{service_id} endpoint allows querying up to 168 hours of probe history without pagination parameters (limit and offset). For a service probed every 30 seconds, this can return more than 20,000 records in a… — `nowing_backend/app/routes/admin_telemetry_routes.py`
- [ ] [Review][Patch] **Trivialized Tests and Missing Test Coverage for `HealthResultStore`** — nowing_backend/tests/integration/routes/test_admin_health.py — `nowing_backend/app/services/health/result_store.py`
- [ ] [Review][Patch] **Static Hardcoded Probes Replacing Dynamic Discovery via CapabilityRegistry and Database Tables** — (lines 1231–1275, 1329–1404), probes are statically registered from hardcoded tuple arrays (CANONICAL_SCRAPER_PLATFORMS, CANONICAL_CONNECTORS, and five hardcoded ModelHealthProbe instances). CapabilityRegistry is not imported or queried in registry.py, and models/connectors ar… — `nowing_backend/app/services/health/registry.py`
- [ ] [Review][Patch] **ScraperHealthProbe Uses Dummy Ping Target (1.1.1.1) and Bypasses Capability Verification** — lines 1064–1072, all 25 scraper probes execute a generic httpx.head("https://1.1.1.1") instead of platform-specific reachability checks. Additionally, lines 1081–1083 check if not matching_caps: only inside except Exception as net_exc:. When 1.1.1.1 returns HTTP 20… — `nowing_backend/app/services/health/probes/scraper_probe.py`
- [ ] [Review][Patch] **ModelHealthProbe Omits Execution of test_model()** — lines 622, 700, and 727, the probe imports and calls verify_connection(), but completely omits test_model() and sample prompt evaluation. — `nowing_backend/app/services/health/probes/model_probe.py`
- [ ] [Review][Patch] **ChainLensHealthProbe Omits Sample Search Probe** — lines 189–203, the probe queries only /api/v1/health and does not execute a sample search query to verify search functionality. — `nowing_backend/app/services/health/probes/chainlens_probe.py`
- [ ] [Review][Patch] **Unsanitized Exception String Interpolation in ChainLensHealthProbe last_error** — line 206, last_error = f"{type(exc).__name__}: {exc}" captures raw HTTP exception text directly into last_error without applying secret sanitization or token redaction. — `nowing_backend/app/services/health/probes/chainlens_probe.py`
- [ ] [Review][Patch] **ModelHealthProbe Secret Sanitizer Fails to Redact Standard URL Userinfo Credentials** — lines 626 and 780, _SECRET_PATTERN = re.compile(r"(key|token|secret|password|bearer\s+|auth\s+)[=:\s]*([^\s,;&]+)", re.IGNORECASE) is used to sanitize base_url. This regular expression does not detect credentials embedded in URLs such as https://user:password@host or… — `nowing_backend/app/services/health/probes/model_probe.py`
- [ ] [Review][Patch] **Architecture Deviation: Direct Database Queries in ModelHealthProbe and Fabricated 15-Minute Metrics in Other Probes** — lines 756–774, ModelHealthProbe directly opens an async database session and queries AdminHealthHistory. Conversely, all other probes (chainlens_probe.py lines 208–209, connector_probe.py lines 316–317, infrastructure_probe.py lines 479–480, messaging_probe.py lines … — `nowing_backend/app/services/health/probes/model_probe.py`
- [ ] [Review][Patch] **Missing next_probe_at Field in HealthResult** — lines 20–51, HealthResult defines probed_at but omits next_probe_at, even though each probe declares an interval_seconds property. — `nowing_backend/app/services/health/probe_base.py`
- [ ] [Review][Patch] **ConnectorHealthProbe Only Checks Database Row Count Without Testing Upstream Reachability** — lines 289–309, the probe only executes a SELECT count() query on the local connections table for enabled entries. It performs no network reachability or authentication verification with the upstream connector providers. — `nowing_backend/app/services/health/probes/connector_probe.py`
- [ ] [Review][Patch] **Credential Redaction Helper `_sanitize_error` Is Defined but Never Invoked** — lines 29–33 define _sanitize_error(error_str: str | None). However, it is never called anywhere in scheduler.py, result_store.py, or alert_engine.py. In — `nowing_backend/app/services/health/scheduler.py`
- [ ] [Review][Patch] **Alert Cooldown Window Is Not Enforced and Deduplication Corrupts Incident Timestamp** — lines 78–92 perform deduplication by matching open or acknowledged alerts. When a matching alert exists: if existing_alert is not None: # Update triggered_at to now instead of creating duplicate existing_alert.triggered_at = now … — `nowing_backend/app/services/health/alert_engine.py`
- [ ] [Review][Patch] **Notification Dispatch Bypasses Generic Alert Engine and Completely Omits Telegram Dispatch** — lines 182–243, _dispatch_notification builds a standalone dispatch loop over User.is_superuser, calls NotificationService.create_notification directly, calls private _send_email_smtp via asyncio.to_thread, and leaves Telegram as a… — `nowing_backend/app/services/health/alert_engine.py`
- [ ] [Review][Patch] **Missing Python-Level Fallback/Default Alert Rules** — lines 54–56, evaluate_result queries AdminHealthAlertRule exclusively from the database: stmt = select(AdminHealthAlertRule).where(AdminHealthAlertRule.enabled.is_(True)) res = await session.execute(stmt) rules = res.scalars().all… — `nowing_backend/app/services/health/alert_engine.py`
- [ ] [Review][Patch] **Missing Rate Limiting on On-Demand Single Probe Endpoint** — lines 189–204, run_single_health_probe (POST /health/probe/{service_id:path}) has no rate limiter annotation (such as @limiter.limit) or throttling middleware, allowing unbounded concurrent trigger calls against third-party provi… — `nowing_backend/app/routes/admin_telemetry_routes.py`
- [ ] [Review][Patch] **Alert Acknowledgment Endpoint Resurrects Resolved Alerts Instead of Returning HTTP 404** — lines 259–279, acknowledge_alert fetches any alert by ID (select(AdminHealthAlert).where(AdminHealthAlert.id == alert_id)). It does not check if alert.status == "resolved". Acknowledging a resolved alert changes its status back to… — `nowing_backend/app/services/health/alert_engine.py`
- [ ] [Review][Patch] **Route Prefix Divergence from Specification** — all health endpoints are declared on router = APIRouter(prefix="/admin/telemetry"). When mounted in the application, the actual URLs are /api/v1/admin/telemetry/health/*. No route aliases or redirects exist for /api/v1/admin/hea… — `nowing_backend/app/routes/admin_telemetry_routes.py`
- [ ] [Review][Patch] **Overall Status Calculation Never Returns "unavailable"** — lines 62–66: overall_status = "healthy" if status_counts["unavailable"] > 0: overall_status = "degraded" # or unavailable if major elif status_counts["degraded"] > 0: overall_status = "degraded" overall_status is har… — `nowing_backend/app/services/health/third_party_health_service.py`
- [ ] [Review][Patch] **Field Name Inconsistency Between Health Status Item and Probe Result Metadata** — HealthStatusItem exposes metadata_payload: dict[str, Any] (line 28), whereas HealthProbeResultResponse exposes metadata: dict[str, Any] (line 91). This causes inconsistency between bulk status list responses and single probe results. — `nowing_backend/app/schemas/admin_health.py`
- [ ] [Review][Patch] **Hardcoded 300-Second `next_probe_at` Calculation Ignores Category Schedules** — lines 80 and 95, next_probe_at is hardcoded as now + timedelta(seconds=300) for all services. This conflicts with Celery beat intervals configured in nowing_backend/app/celery_app.py (30 sec… — `nowing_backend/app/services/health/result_store.py`
- [ ] [Review][Patch] **`test_infra_postgres_probe` Patches the Method Under Test (Tautology Test)** — lines 23–34: with patch.object(probe, "probe", new_callable=AsyncMock) as mock_probe: from app.services.health.probe_base import HealthResult mock_probe.return_value = HealthResult( service_id="infra/postgres",… — `nowing_backend/tests/unit/services/health/test_infrastructure_probe.py`
- [ ] [Review][Patch] **Alert Engine Unit Tests Do Not Cover Consecutive Probe Requirement or Cooldown** — lines 16–24, the test explicitly sets "consecutive_probes": 1 instead of verifying the 2 consecutive failure threshold. Furthermore, there are no tests for the 15-minute dedupe cooldown, auto-resolution upon recovery, … — `nowing_backend/tests/unit/services/health/test_alert_engine.py`
- [ ] [Review][Patch] **Missing Route Integration Tests for 404 Error Cases and PAT Rejection** — there are no integration tests verifying: - HTTP 404 when POST /health/probe/{service_id} targets an unregistered service. - HTTP 404 when POST /health/alerts/{alert_id}/acknowledge targets a non-existent or resolved al… — `nowing_backend/tests/integration/routes/test_admin_health.py`
- [ ] [Review][Patch] **Missing Unit Tests for Messaging, Payment, and Storage Probes** — While unit tests are provided for model, scraper, connector, infrastructure, proxy, and chainlens probes, no test files exist in nowing_backend/tests/unit/services/health/ for messaging, payment, or storage probes. — `nowing_backend/tests/unit/services/health/`
- [ ] [Review][Patch] **Scraper probe must test the actual scraper, not `https://1.1.1.1` with `verify=False`.** — ScraperHealthProbe HEADs https://1.1.1.1 with SSL verification disabled for every scraper. This tests nothing about the 25 registered platforms and introduces a security/egress concern. Replace with capability-specific lightweight health checks or remove the HTTP call. — `nowing_backend/app/services/health/probes/scraper_probe.py:83-85`
- [ ] [Review][Patch] **Scraper probe `matching_caps` check is unreachable when no proxy and network is up.** — If client.head(test_url) succeeds and proxy_configured is False, the if not matching_caps: branch is never reached, so an unregistered scraper is reported healthy. Move the capability check outside the exception block. — `nowing_backend/app/services/health/probes/scraper_probe.py:61-105`
- [ ] [Review][Patch] **Connector probe should verify actual credentials, not just count enabled rows.** — ConnectorHealthProbe reports healthy whenever active_accounts > 0 regardless of whether credentials are expired, revoked, or invalid. AC-2 expects real probe results. Either call a connector verification helper or at least test a lightweight API ping. — `nowing_backend/app/services/health/probes/connector_probe.py:60-80`
- [ ] [Review][Patch] **Messaging, payment, and storage probes should perform a real connectivity check, not just env-var presence.** — These probes return healthy immediately after reading config tokens/endpoint. Add a non-mutating ping/read-only check to satisfy the spec's "connectivity/config cơ bản" requirement. — nowing_backend/app/services/health/probes/messaging_probe.py:52-71, payment_probe.py:51-60, storage_probe.py:51-61 — `nowing_backend/app/services/health/probes/messaging_probe.py`
- [ ] [Review][Patch] **Alert cooldown/dedupe is not implemented using `cooldown_minutes`.** — AdminHealthAlertEngine.evaluate_result only checks whether an open/acknowledged alert row exists and updates triggered_at. It never compares triggered_at or acknowledged_until against rule.cooldown_minutes. An hours-old open alert will suppress new alerts indefinitely, violating AC-3's 15-minute dedupe window. — `nowing_backend/app/services/health/alert_engine.py:79-91`
- [ ] [Review][Patch] **Success/error rate calculation only treats `unavailable` as an error, ignoring `degraded`.** — HealthResultStore.save_result counts only status == "unavailable" as an error. The scraper alert rule depends on success_rate_15m < 50%, but a scraper that is consistently degraded will still show ~100% success and never trigger the rule. Include degraded in the error count or adjust the rule to also watch degraded. — `nowing_backend/app/services/health/result_store.py:47-51`
- [ ] [Review][Patch] **`next_probe_at` is always set to `now + 300s` regardless of probe `interval_seconds`.** — HealthResultStore hardcodes the 5-minute next-probe time for every probe, but infra is 30s, models 2m, connectors 15m, etc. Use probe.interval_seconds or pass the interval through the result. — `nowing_backend/app/services/health/result_store.py:81-94`
- [ ] [Review][Patch] **`HealthProbeScheduler._persist_and_alert` continues to use a rolled-back session for subsequent probes.** — After save_result/evaluate_result raises, the code calls session.rollback() but does not re-raise or create a new session, so later probes in the same batch may be processed in an aborted transaction. — `nowing_backend/app/services/health/scheduler.py:137-146`
- [ ] [Review][Patch] **`AdminHealthAlert` auto-resolve on a single `healthy` probe may cause flapping.** — When result.status == "healthy", all open/acknowledged alerts for the service are resolved immediately. Consider requiring at least one consecutive healthy probe before resolving, or align with the 2-consecutive-fail rule in AC-3. — `nowing_backend/app/services/health/alert_engine.py:38-51`
- [ ] [Review][Patch] **`admin_health_history` lacks TTL/purge policy and is written every 30 seconds for infra.** — Spec guardrails require a 30-day default TTL. Without a purge task or time-based partition, the table will grow quickly. Add a retention cleanup task or an index/partition on probe_at. — nowing_backend/app/models/admin_health.py:59-77, alembic/versions/238_add_admin_health_tables.py:64-90 — `nowing_backend/app/models/admin_health.py`
- [ ] [Review][Patch] **Schema field `acknowledged_at` does not exist in `AdminHealthAlert` model.** — HealthAlertItem.acknowledged_at has no matching SQLAlchemy column; it will always serialize as None and is misleading. Remove or rename to acknowledged_until. — `nowing_backend/app/schemas/admin_health.py:60`
- [ ] [Review][Patch] **Alert dispatch failure prevents alert from being persisted.** — AdminHealthAlertEngine.evaluate_result calls _dispatch_notification before session.commit(). If dispatch unexpectedly raises, the alert added to the session is never committed. Consider flushing the alert row before dispatch, or committing the alert before running best-effort notification. — `nowing_backend/app/services/health/alert_engine.py:109-113`
- [ ] [Review][Patch] **Alert rule condition only supports `<` for `success_rate_15m`.** — _check_rule_condition handles only metric == "success_rate_15m" and op == "<". Any rule with >, >=, <=, or error_rate_15m silently returns False. Extend condition evaluation to support generic metric operators. — `nowing_backend/app/services/health/alert_engine.py:165-171`
- [ ] [Review][Patch] **Connector probe opens one DB session per probe concurrently, risking pool exhaustion.** — ConnectorHealthProbe.probe() creates async_session_maker() for each of 14 connectors. Running run_category("connector") opens up to 14 concurrent DB sessions, which can exhaust the connection pool. Use a shared session or batch the count query. — `nowing_backend/app/services/health/probes/connector_probe.py:60-73`
- [ ] [Review][Patch] **Standalone/global model probe lacks `base_url` validation.** — ModelHealthProbe creates a temporary Connection without base_url when none is provided; verify_connection returns UNREACHABLE instead of not_configured. Check spec_for(provider).base_url_required and fallback to provider default before probing. — `nowing_backend/app/services/health/probes/model_probe.py:114-121`
- [ ] [Review][Patch] **Tests for scraper/connector probes validate the wrong behavior.** — test_scraper_probe_healthy asserts healthy after a real network call to https://1.1.1.1; test_connector_probe_healthy_when_active_accounts asserts healthy from a mocked count with no credential verification. These tests do not guard against regressions and should assert the real probe logic. — nowing_backend/tests/unit/servic… — `nowing_backend/tests/unit/services/health/test_scraper_probe.py`
- [ ] [Review][Patch] **`HealthResultStore.save_result` is mocked in all tests and has no direct coverage.** — No unit or integration test invokes save_result; the 15-minute rolling rate calculation, admin_health_status upsert, and Redis set/publish are therefore unverified. Add tests/unit/services/health/test_result_store.py with mocked and/or transactional session. — `nowing_backend/app/services/health/result_store.py:25-117`
- [ ] [Review][Patch] **Alert engine tests cover only one happy path.** — test_alert_engine.py only tests creation of a new alert on unavailable. Auto-resolve on healthy, deduplication when an alert already exists, and acknowledge_alert persistence are not tested. — `nowing_backend/tests/unit/services/health/test_alert_engine.py:14-52`
- [ ] [Review][Patch] **`probes/__init__.py` does not export `MessagingHealthProbe`, `PaymentHealthProbe`, `StorageHealthProbe`.** — The three probe classes are implemented but omitted from the module's imports and __all__ list. — `nowing_backend/app/services/health/probes/__init__.py:1-10`
- [ ] [Review][Patch] **Storage probe logic uses `or` instead of `and` and ignores secret key.** — if not (endpoint or access_key or bucket) allows any one env var to be present, and S3_SECRET_ACCESS_KEY / AWS_SECRET_ACCESS_KEY is never checked. — `nowing_backend/app/services/health/probes/storage_probe.py:52-60`
- [ ] [Review][Patch] **`httpx.AsyncClient` in scraper probe receives `requests`-style `proxies` dict for `proxy=`.** — proxy_dict.get("https") may return a dict while httpx.AsyncClient(proxy=…) expects a string/httpx.Proxy instance, causing a runtime type error in newer HTTPX versions. — `nowing_backend/app/services/health/probes/scraper_probe.py:84-85`
- [ ] [Review][Patch] **Proxy probe does not wrap `get_proxy_health()` in try/except and hardcodes `proxy/dataimpulse`.** — If AdminTelemetryService.get_proxy_health() raises, the exception escapes instead of returning unavailable. The service_id is hardcoded even though the provider may differ. — `nowing_backend/app/services/health/probes/proxy_probe.py:42-55`
- [ ] [Review][Patch] **ChainLens probe maps all non-200 responses (including 401/403/5xx) to `degraded`.** — Auth failures and upstream unavailability should be unavailable or not_configured rather than merely degraded. — `nowing_backend/app/services/health/probes/chainlens_probe.py:72-86`
- [ ] [Review][Patch] **Probes create new `httpx.AsyncClient` per check, no connection pooling.** — Scraper, ChainLens, and infrastructure probes instantiate a new client on every call. For 25 scrapers this causes repeated TLS handshakes and socket pressure. — nowing_backend/app/services/health/probes/scraper_probe.py:85, chainlens_probe.py:73, infrastructure_probe.py:97-116 — `nowing_backend/app/services/health/probes/scraper_probe.py`
- [ ] [Review][Patch] **`HealthProbeRegistry.ensure_initialized()` uses a boolean flag with no concurrency guard.** — _initialized is a class variable checked/assigned outside a lock; concurrent first calls can race and run discover_default_probes() multiple times. — `nowing_backend/app/services/health/registry.py:105-110`

#### Defer
- [x] [Review][Defer] **Hardcoded canonical lists of 25 scrapers / 14 connectors / 5 models in `HealthProbeRegistry` instead of dynamic discovery.** — While AC-2 calls for discovery from `CapabilityRegistry` and service registries, the current static lists function as a v1 seed. A follow-up should make the registry read from `CapabilityRegistry` and the active `Connection`/`Model` tables. — `nowing_backend/app/services/health/registry.py:22-195`