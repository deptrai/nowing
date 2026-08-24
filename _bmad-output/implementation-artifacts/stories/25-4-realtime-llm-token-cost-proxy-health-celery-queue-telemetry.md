story_key: 25-4-realtime-llm-token-cost-proxy-health-celery-queue-telemetry
status: ready-for-dev
baseline_commit: be2efe015
epic: 25
story: 4
---

# Story 25.4: Realtime LLM Token Cost, Proxy Health & Celery Queue Telemetry

**Status:** `ready-for-dev`

**Governed by:** `INV-25.5` (Realtime Telemetry & Gross Margin Monitoring), `INV-25.6` (Dynamic Scraper Rule Invalidation via Redis Pub/Sub), `INV-25.8` (Fail-Closed Superadmin Guard), Epic 25 in [`_bmad-output/planning-artifacts/epics.md`](../planning-artifacts/epics.md) lines 3531–3603.

---

## Story

As a **Platform Superadmin**,  
I want a real-time telemetry dashboard for AI infrastructure costs, gross margins per model/workspace, proxy pool health, and Celery worker queue health with emergency purge controls,  
so that I can detect bleeding costs, dead proxies, and backed-up queues before they hurt users or margins.

---

## Acceptance Criteria

### AC-1 — Real-time LLM Cost & Gross Margin Dashboard

**Given** `/admin/telemetry` is loaded by a verified Superadmin interactive session,  
**When** the dashboard renders,  
**Then** it displays:

- Aggregate LLM cost cards and time-series charts by provider (`openai`, `anthropic`, `google`, `deepseek`, plus `unknown`), with time window selector (`1h`, `6h`, `24h`, `7d`, `30d`).
- Token consumption (input + output tokens) per workspace and per model.
- Live gross margin panel: `gross_margin = (revenue - cogs) / revenue` where:
  - `revenue` = sum of `credit_purchases.credit_micros_granted` or wallet debit bookings inside the window.
  - `cogs` = sum of `token_usage.cost_micros` for the same window.
- When margin < 0% or exceeds configured threshold, a red pill/alert is shown with the worst offending workspace and model.

### AC-2 — Proxy Pool Health Monitor

**Given** the Proxy Pool section on `/admin/telemetry`,  
**When** displayed,  
**Then** it lists active SOCKS5/HTTP proxies from the configured `PROXY_PROVIDER` with:

- `provider` (e.g. `dataimpulse`, `custom`).
- Current latency in ms, measured by a periodic probe through the active provider.
- Bandwidth / success rate (%) tracked from the probe results.
- Status badge `Healthy / Degraded / Dead` based on configurable latency/error-rate thresholds.
- A `Rotate Dead Proxies` button that refreshes the active provider session and clears the dead-proxy cache.

> **Ponytail:** Proxy health is a **best-effort probe**, not a vendor API. The active `ProxyProvider` is read from `app/utils/proxy/registry.py`. The probe must not break production scrapers. Use the canonical `get_proxy_url()` and a lightweight HEAD/GET to a well-known endpoint.

### AC-3 — Celery Worker & Queue Telemetry + DLQ Purge

**Given** the Celery Worker & Queue section on `/admin/telemetry`,  
**When** displayed,  
**Then** it shows:

- Real-time queue lengths for `celery`, `celery.connectors`, `nowing.lead_scrapers`, and `celery.gateway` (or whatever queues are defined in `app/celery_app.py`).
- Active worker count and per-queue throughput (tasks/min).
- Dead-letter / stalled task count by queue.
- Workload bars and a `Purge Dead Tasks` action that requires a safe 2-second long-press and a confirmation modal, then calls an admin API to purge the dead queue.

### AC-4 — Backend Admin API & Authz

**Given** any `/api/v1/admin/telemetry/*` endpoint,  
**When** called without a Superadmin session,  
**Then** it returns `HTTP 403 Forbidden` via `require_superuser` (INV-25.8).

### AC-5 — Real-time Updates

**Given** the telemetry dashboard is open,  
**When** new data arrives,  
**Then** the UI refreshes every 5 seconds via `useEffect` polling or the existing Zero-cache / React Query pattern, without requiring a full page reload.

---

## Tasks / Subtasks

- [ ] **Task 1: Backend Telemetry Aggregator Service**
  - [ ] Create `app/services/admin_telemetry_service.py`. **Do NOT rewrite cost aggregation SQL** — reuse/extend `app/services/usage_service.py` (`_breakdown_by_provider`, `_breakdown_by_model`, `_breakdown_by_usage_type`, `get_time_series`, `_workspace_totals`) and `app/routes/admin_latency_routes.py` SQL patterns for superadmin aggregates.
  - [ ] Functions to implement:
    - `get_llm_cost_breakdown(session, window_hours, provider, workspace_id)` — aggregate from `TokenUsage` and `BillingEvent` across all workspaces (or filtered), with provider/model buckets.
    - `get_gross_margin(session, window_hours)` — `revenue - cogs` per time bucket. Revenue = completed `CreditPurchase.credit_micros_granted` within window; COGS = `TokenUsage.cost_micros` + `BillingEvent.cost_micros` within window. Guard division-by-zero when `revenue=0`.
    - `get_proxy_health()` — probe active proxy via `app/utils/proxy` and return latency/success-rate snapshots. Handle `PROXY_URL` not configured => `status: not_configured`.
    - `get_celery_queue_stats()` — inspect Redis broker via `app.celery_app:celery_app.control.inspect()`; return queue lengths, active worker count, stalled/DLQ counts. On broker unreachable return `status: unavailable` (HTTP 200) not 500.
    - `purge_dead_letter_queue(queue_name)` — safe purge with Redis lock + `AuditEvent` logging; idempotent; guard double-submit.
  - [ ] Ensure all aggregator queries use existing DB indexes and do not full-scan `token_usage` / `billing_events`.
  - [ ] Add guards for Q3/Q4 edge cases: clamp `window_hours`, no rows => `0` not `null`, `revenue=0` => `N/A`, unsupported provider => `unknown`, `cost_micros=0` flagged as `unreported`.

- [ ] **Task 2: Backend Admin Telemetry Routes**
  - [ ] Create `app/routes/admin_telemetry_routes.py` with `APIRouter(prefix="/admin/telemetry", tags=["admin"])`.
  - [ ] Endpoints:
    - `GET /api/v1/admin/telemetry/llm-cost?window_hours=24&provider=&workspace_id=`
    - `GET /api/v1/admin/telemetry/gross-margin?window_hours=24`
    - `GET /api/v1/admin/telemetry/proxy-health`
    - `GET /api/v1/admin/telemetry/celery-queues`
    - `POST /api/v1/admin/telemetry/celery-queues/{queue_name}/purge`
  - [ ] Reuse `require_superuser` pattern from `app/routes/admin_credits_routes.py`.
  - [ ] Wire router into `app/routes/__init__.py` next to `admin_credits_router`.

- [ ] **Task 3: DB Schema & Migrations (if needed)**
  - [ ] **Do NOT add a new table** for telemetry unless absolutely necessary. Use existing `token_usage` and `credit_purchases` plus in-memory Redis/Celery inspection.
  - [ ] If a cache table is needed for probe snapshots, create a small `proxy_health_snapshots` table (optionally) with TTL 7 days. Defer to a later story unless required for real-time performance.
  - [ ] Consider adding a partial index on `token_usage(created_at, usage_type, workspace_id)` if query analysis shows a need.

- [ ] **Task 4: Frontend `/admin/telemetry` Page**
  - [ ] Create `nowing_web/app/admin/telemetry/page.tsx` inside `AdminShell`.
  - [ ] Use high-density 36px row tables and monospace numbers, consistent with `nowing_web/app/admin/credits/page.tsx`.
  - [ ] Add `nowing_web/lib/apis/admin-telemetry-api.service.ts` mirroring `admin-credits-api.service.ts`.
  - [ ] Use `recharts` for line/bar charts (already in `package.json`); no new chart library.
  - [ ] Add navigation link in `nowing_web/app/admin/admin-shell.tsx`.

- [ ] **Task 5: Frontend Components**
  - [ ] `components/admin/telemetry/LlmCostPanel.tsx` — provider/model/workspace selectors and charts.
  - [ ] `components/admin/telemetry/ProxyHealthPanel.tsx` — proxy table, rotate button.
  - [ ] `components/admin/telemetry/CeleryQueuePanel.tsx` — queue cards, long-press purge button with confirmation.
  - [ ] `components/admin/telemetry/GrossMarginAlert.tsx` — negative/warning margin pill.

- [ ] **Task 6: Tests**
  - [ ] `tests/unit/services/test_admin_telemetry_service.py` — mock Redis/Celery for queue stats, mock `TokenUsage`/`CreditPurchase` for cost math.
  - [ ] `tests/integration/routes/test_admin_telemetry.py` — verify `require_superuser` gating and endpoint shape.
  - [ ] `nowing_web` typecheck with `pnpm tsc --noEmit` and biome for changed files.

---

## Dev Notes

### Existing Code to Reuse (Do Not Reinvent)

- **Token usage and cost data model:**
  - `nowing_backend/app/db.py` `TokenUsage` class (lines 1200–1293) — `cost_micros`, `usage_type`, `model_breakdown`, `workspace_id`, `user_id`, `created_at`.
  - `nowing_backend/app/db.py` `BillingEvent` class (lines 4463–4507) — non-LLM business-event cost ledger (`cost_micros`, `event_type`, `workspace_id`). Must be included in total COGS.
  - `nowing_backend/app/db.py` `CreditPurchase` class (lines 2772–2812) — `credit_micros_granted`, `status`, `completed_at`.
  - `nowing_backend/app/services/token_tracking_service.py` — how `cost_micros` is extracted and persisted; `record_token_usage` signature.
- **Existing usage aggregation (must reuse/extend, not duplicate):**
  - `nowing_backend/app/services/usage_service.py` — already aggregates `TokenUsage` + `BillingEvent` per workspace with `_breakdown_by_provider`, `_breakdown_by_model`, `_breakdown_by_usage_type`, `get_time_series`, `_workspace_totals`. Reuse static helpers or instantiate with admin scope.
  - `nowing_backend/app/routes/usage_routes.py` — workspace-scoped `/usage/*` endpoints. Admin telemetry must NOT call these; reuse the service layer.
- **Telemetry/OpenTelemetry patterns:**
  - `nowing_backend/app/observability/metrics.py` — existing OTel instruments, e.g. `record_celery_queue_latency` (line 869).
  - `nowing_backend/app/celery_app.py` — queue names, `task_prerun` latency stamping, broker config.
- **Proxy subsystem:**
  - `nowing_backend/app/utils/proxy/registry.py` / `app/utils/proxy/__init__.py` — get active provider, canonical `get_proxy_url()`.
  - `nowing_backend/app/utils/proxy/providers/dataimpulse.py` — only provider with vendor-specific routing today.
- **Admin route & UI patterns:**
  - `nowing_backend/app/routes/admin_latency_routes.py` — example of Superadmin metrics endpoint aggregating `TokenUsage` with SQL.
  - `nowing_backend/app/routes/admin_credits_routes.py` — `require_superuser`, Pydantic response models, ledger pattern.
  - `nowing_backend/app/routes/__init__.py` — where to include the new router.
  - `nowing_web/app/admin/admin-shell.tsx` — add the nav link.
  - `nowing_web/app/admin/credits/page.tsx` — high-density table, stats cards, filters, CSV export pattern.
  - `nowing_web/lib/apis/admin-credits-api.service.ts` — API service pattern.

### Key Decisions

1. **Revenue definition for gross margin:** Use the USD micro-units actually paid by users (`CreditPurchase.credit_micros_granted` with `status = 'completed'`). If a wallet debit view is preferred in the future, add a toggle; the first version uses purchase data.
2. **Proxy health:** Probes must be **read-only and throttled** (e.g. max 1 probe every 10 s per process). Do not probe inside request/response hot paths by default; the dashboard polls the cached snapshot.
3. **Celery queue inspection:** Use the configured Redis broker directly (`from app.celery_app import celery_app; inspect = celery_app.control.inspect()`). Do not add new broker infrastructure.
4. **DLQ / stalled tasks:** For the first version, define a stalled task as any task in a Celery queue older than `CELERY_TASK_STALLED_SECONDS` (config default 300 s). Purge only those messages.

### Performance & Security Guardrails

- All admin endpoints MUST use `require_superuser` (INV-25.8).
- SQL aggregations on `token_usage` MUST be time-bounded (`created_at >= cutoff`) and hit existing indexes.
- Proxy probes MUST NOT leak credentials in logs or error traces.
- `Purge Dead Tasks` MUST write an `AuditEvent` with `actor_id`, `action='telemetry.purge_dlq'`, `diff_payload={"queue": ..., "count": ...}` for PDPD Decree 13 compliance (INV-25.2).
- Long-press UI action prevents accidental destructive purge.

### Suggested File Tree

```
nowing_backend/
  app/services/admin_telemetry_service.py
  app/routes/admin_telemetry_routes.py
  app/schemas/admin_telemetry.py
  app/routes/__init__.py  (add include_router)

nowing_web/
  app/admin/telemetry/page.tsx
  lib/apis/admin-telemetry-api.service.ts
  components/admin/telemetry/
    LlmCostPanel.tsx
    ProxyHealthPanel.tsx
    CeleryQueuePanel.tsx
    GrossMarginAlert.tsx
  app/admin/admin-shell.tsx  (add nav link)
```

---

## Project Structure Notes

- Align with existing `admin_*_routes.py` naming in `app/routes/`.
- Align with `app/services/admin_*_service.py` naming (e.g. `admin_affiliate_payouts_service.py` currently under `app/services/partner_payout_service.py`; prefer `admin_telemetry_service.py` for this story).
- Reuse `nowing_web/app/admin/[feature]/page.tsx` structure. Do not create a new layout; `AdminShell` is already in `app/admin/admin-shell.tsx`.
- Use `recharts` for charts; do not install new libraries.

---

## References

- Epic 25 & Story 25.4: [`_bmad-output/planning-artifacts/epics.md`](../planning-artifacts/epics.md) lines 3531–3603.
- `INV-25.5` / `INV-25.6` / `INV-25.8` same file, lines 3539–3542.
- `TokenUsage` model: `nowing_backend/app/db.py` lines 1200–1293.
- `BillingEvent` model: `nowing_backend/app/db.py` lines 4463–4507.
- `CreditPurchase` model: `nowing_backend/app/db.py` lines 2772–2812.
- `User.credit_micros_balance`: `nowing_backend/app/db.py` lines 3110–3122.
- `Workspace`: `nowing_backend/app/db.py` lines 1897–1996.
- Token tracking service: `nowing_backend/app/services/token_tracking_service.py`.
- Existing usage aggregation (must reuse): `nowing_backend/app/services/usage_service.py`, `nowing_backend/app/routes/usage_routes.py`.
- OTel metrics: `nowing_backend/app/observability/metrics.py`.
- Celery app & queue names: `nowing_backend/app/celery_app.py`.
- Proxy provider abstraction: `nowing_backend/app/utils/proxy/`.
- Admin latency routes (closest precedent): `nowing_backend/app/routes/admin_latency_routes.py`.
- Admin credits routes & UI pattern: `nowing_backend/app/routes/admin_credits_routes.py`, `nowing_web/app/admin/credits/page.tsx`, `nowing_web/lib/apis/admin-credits-api.service.ts`.
- Admin shell: `nowing_web/app/admin/admin-shell.tsx`.
- Quality pipeline: `_bmad/custom/nowing-quality-pipeline.md`.

---

## Lệnh xác minh (Verification Commands)

```bash
# Backend lint & typecheck (targeted)
cd nowing_backend
uv run ruff check app/services/admin_telemetry_service.py app/routes/admin_telemetry_routes.py app/schemas/admin_telemetry.py
uv run pytest tests/unit/services/test_admin_telemetry_service.py tests/integration/routes/test_admin_telemetry.py -q

# Frontend typecheck & biome
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/admin/telemetry/page.tsx app/admin/admin-shell.tsx lib/apis/admin-telemetry-api.service.ts components/admin/telemetry/
```

---

## Challenge Log (grill-me)

### Q1 — Is this already implemented?

- **Partial duplicate found — recommendation: reuse/extend, not rewrite.**
  - `nowing_backend/app/services/usage_service.py` already aggregates `TokenUsage` + `BillingEvent` per workspace, with breakdown by `usage_type`, `model`, `provider`, and time-series (`get_time_series`, `get_summary`, `get_service_breakdown`).
  - `nowing_backend/app/routes/usage_routes.py` exposes `/api/v1/usage/summary`, `/time-series`, `/per-turn`, `/service-breakdown` for **workspace-scoped user access**.
  - `nowing_backend/app/routes/admin_latency_routes.py` already computes latency percentiles from `TokenUsage` for **superadmin**.
- **Conclusion:** Do NOT implement a second cost-aggregation SQL engine. Build an `AdminTelemetryService` that reuses `UsageService`'s SQL primitives (or extracts static helpers) and removes the `user_id`/`workspace_id` filter for superadmin aggregates. Admin page must call `/admin/telemetry/*`, not the user `/usage/*` endpoints.

### Q2 — Is there a simpler alternative?

- **Yes — reuse `UsageService` and extend it for admin scope.**
  - Option A (preferred): Add admin-only methods to a new `AdminTelemetryService` that calls `UsageService._breakdown_by_provider/model/usage_type` with `workspace_id=None` and optionally a `provider`/`model` filter.
  - Option B (simpler but less flexible): Wrap `UsageService` with a superadmin user that has access to all workspaces and union results. Rejected — too much per-workspace round-tripping.
  - Proxy health can be a small helper in `app/services/admin_telemetry_service.py` using `app.utils.proxy.get_active_provider()`; no new microservice.
  - Celery queue inspection can reuse the configured `celery_app` + Redis broker directly; no extra queue.
- **Conclusion:** Proceed with Option A. Update the story's Task 1 to explicitly state reuse of `UsageService` helpers and `admin_latency_routes.py` SQL pattern.

### Q3 — Edge cases the spec misses (Pattern 3)

- **Boundary / empty buckets:**
  - [ ] `window_hours=0`, negative, or > 720 (30 days) must be rejected or clamped.
  - [ ] No `TokenUsage` rows in window → response must return `0` totals, not `null` or 500.
  - [ ] `revenue=0` (no completed `CreditPurchase`) → gross margin is undefined, UI must show `N/A` or `—`, never divide by zero.
  - [ ] Provider string not in `{openai, anthropic, google, deepseek}` → include in `unknown` bucket, not reject.
- **Null / malformed data:**
  - [ ] `TokenUsage.cost_micros` may be `0` if LiteLLM callback failed to extract cost; dashboard should still show tokens and flag `cost unreported`.
  - [ ] `TokenUsage.model_breakdown` JSONB can be `null`; aggregate must treat as `{}`.
  - [ ] `CreditPurchase.status` must be `completed` before counting as revenue; `pending`/`failed` excluded.
  - [ ] Proxy not configured (`PROXY_URL` empty / `CustomProxyProvider`) → probe returns `status: not_configured` rather than `Dead`.
- **Concurrency / destructive:**
  - [ ] Double-click / double-submit `Purge Dead Tasks` must be idempotent (Redis lock on `queue_name` + `AuditEvent`).
  - [ ] Admin opens multiple tabs polling — API must be read-only and cheap (no full table scans).

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **Postgres slow query on `token_usage` / `billing_events`:** add `max 30s` window, use existing indexes, consider materialized cache if > 30s.
- [ ] **Redis/Celery broker unreachable:** `celery_app.control.inspect()` throws; return empty queue list with `status: unavailable`, 200 not 500.
- [ ] **Proxy probe network timeout:** cap probe at `5s`, on timeout mark `status: dead` with `last_error: timeout`.
- [ ] **LiteLLM cost not captured (`cost_micros=0`):** UI must show `cost: 0` and `unreported` badge, not hide the call.
- [ ] **`UsageService` raises because `start_date > end_date`:** admin endpoint should normalize to 24h window if user sends bad query params.
- [ ] **OTel metrics disabled / `otel.is_enabled() == False`:** Celery queue latency chart falls back to probe timestamps or Celery `nowing.enqueued_at_ns` header.
- [ ] **Missing `require_superuser` bypass:** any endpoint not wrapped with `Depends(require_superuser)` is a P0 security bug.

### Triage

- **No Critical HALT.** Findings are non-critical: Q1/Q2 identify reuse opportunities (refactor before red-green, not rewrite), Q3/Q4 list edge/failure cases for test-first ATDD.
- **Action before implementation:** Update Task 1 in this story to (a) reuse `UsageService` helpers, (b) reuse `admin_latency_routes.py` SQL pattern, and (c) add the Q3/Q4 cases to the ATDD skeleton.

---

## Dev Agent Record

### Agent Model Used

Claude (Sonnet 4) via Devin CLI.

### Completion Notes

Story 25.4 generated with `bmad-create-story` workflow. Cross-checked against existing admin routes, `TokenUsage` schema, `CreditPurchase` schema, proxy abstraction, Celery/OTel metrics, and Nowing quality pipeline. All 3 epics ACs preserved and expanded with technical tasks and file locations.

### File List

- New: `_bmad-output/implementation-artifacts/stories/25-4-realtime-llm-token-cost-proxy-health-celery-queue-telemetry.md`
