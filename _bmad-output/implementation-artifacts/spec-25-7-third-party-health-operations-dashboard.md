---
title: 'Story 25.7: Third-Party Health & Operations Dashboard'
type: 'feature'
created: '09-03-2026'
status: 'done'
baseline_commit: 40a7a5031671f7f8f4b228a067c40d9f02efa2ae
review_loop_iteration: 0
context:
  - _bmad-output/implementation-artifacts/epic-25-context.md
  - _bmad-output/implementation-artifacts/design/admin-third-party-health-design.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Hiện tại superadmin không có một trung tâm duy nhất để quan sát health của toàn bộ third-party (LLM model, embedding, scraper, connector, proxy, messaging, payment, storage, infra, ChainLens). Khi một dịch vụ ngoài gặp sự cố, tổn hại thường chỉ được phát hiện qua user complaint hoặc phải tra cứu từng hệ thống riêng.

**Approach:** Mở rộng `/admin/telemetry` thành một Operations Dashboard tabbed, backed by `app/services/health/` — module probe pluggable chạy theo category-specific schedule, lưu snapshot Redis + DB, cảnh báo qua Generic Alert Engine, và cung cấp drill-down/on-demand probe cho từng service.

## Boundaries & Constraints

**Always:**
- Mọi admin endpoint bắt buộc `require_superuser`; PAT bị reject fail-closed.
- Probe chỉ đọc (read-only), không mutate state user hay resource bên ngoài.
- Không tự động disable bất kỳ model/scraper/connector nào; chỉ alert + `suggested_action`.
- Giới hạn concurrency: `asyncio.gather` với `asyncio.Semaphore(20)`.
- Redact API key, token, URL credential trong metadata và `last_error`.
- Reuse `CapabilityRegistry`, `model_connection_service`, `admin_telemetry_service`, `hybrid_llm_router`, Generic Alert Engine — không xây notification stack thứ hai.

**Ask First:**
- Nếu phát sinh nhu cầu auto-disable hoặc circuit-breaker tự động trong quá trình implement.
- Nếu cần thêm route prefix ngoài `/api/v1/admin/health/*` hoặc `/admin/telemetry`.

**Never:**
- Không chạy probe cho non-admin user.
- Không lưu raw API key/credential trong `admin_health_status` hay `admin_health_history`.
- Không vượt quá scope: messaging/payments/storage probes trong v1 chỉ kiểm tra connectivity/config cơ bản, không chạy full transaction.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_PATH | Superadmin mở `/admin/telemetry` | Hiển thị tabbed dashboard với health cards, active alerts banner | N/A |
| PROBE_DEGRADED | Model trả về latency > threshold | Status `degraded`, latency_ms ghi nhận, alert chỉ tạo khi đạt rule condition | `last_error` redacted, vẫn lưu history |
| PROBE_UNAVAILABLE | Service unreachable 2 lần liên tiếp | Status `unavailable`, tạo `admin_health_alerts` duy nhất trong 15 phút, dispatch notification | Ghi `last_error` dạng safe message; không crash scheduler |
| UNAUTHORIZED | Non-superadmin gọi `/api/v1/admin/health/*` | HTTP 403 | Không ghi audit mới |
| ON_DEMAND | POST `/api/v1/admin/health/probe/{service_id}` | Trigger probe ngay lập tức, trả kết quả mới nhất | Rate limit; 404 nếu `service_id` không tồn tại |
| ACKNOWLEDGE | POST `/api/v1/admin/health/alerts/{alert_id}/acknowledge` | Cập nhật `acknowledged_until` cho alert; banner ẩn alert đó | 404 nếu alert không tồn tại hoặc đã resolve |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/services/health/__init__.py` -- export module public API (`ThirdPartyHealthService`, `HealthProbeScheduler`, ...).
- `nowing_backend/app/services/health/probe_base.py` -- `HealthProbe(ABC)`, `HealthResult` dataclass, status enum.
- `nowing_backend/app/services/health/registry.py` -- `HealthProbeRegistry`: category → probe list, discovery từ `CapabilityRegistry` và global model/proxy lists.
- `nowing_backend/app/services/health/scheduler.py` -- `HealthProbeScheduler.run_category(category)` với `asyncio.gather` + `Semaphore(20)`.
- `nowing_backend/app/services/health/result_store.py` -- `HealthResultStore`: Redis latest snapshot (TTL 5m), pub/sub `nowing:health:updates`, persist DB `admin_health_status` + `admin_health_history`.
- `nowing_backend/app/services/health/alert_engine.py` -- `AdminHealthAlertEngine`: evaluate default rules, dedupe `(service_id, rule_id)` cooldown, dispatch qua Generic Alert Engine (`app/alerts/engine/notify.py`).
- `nowing_backend/app/services/health/third_party_health_service.py` -- public facade: `run_all()`, `run_category(category)`, `probe(service_id)`.
- `nowing_backend/app/services/health/probes/model_probe.py` -- `ModelHealthProbe`: gọi `model_connection_service.verify_connection()` / `test_model()` cho global + BYOK `Connection`/`Model`.
- `nowing_backend/app/services/health/probes/scraper_probe.py` -- `ScraperHealthProbe`: lặp capability `CapabilityRegistry.all()` với metadata category `scraper`/`search`, chạy canonical lightweight probe.
- `nowing_backend/app/services/health/probes/connector_probe.py` -- `ConnectorHealthProbe`: kiểm tra connector types có active `Connection`.
- `nowing_backend/app/services/health/probes/infrastructure_probe.py` -- `InfrastructureHealthProbe`: Postgres `SELECT 1`, Redis `PING`, Caddy `/health`, Celery worker inspection, Zero Cache keepalive.
- `nowing_backend/app/services/health/probes/proxy_probe.py` -- `ProxyHealthProbe`: reuse `admin_telemetry_service.get_proxy_health()`.
- `nowing_backend/app/services/health/probes/chainlens_probe.py` -- `ChainLensHealthProbe`: `GET /api/v1/health` + sample search.
- `nowing_backend/app/services/model_connection_service.py` -- `verify_connection()` / `test_model()` (dòng ~172 / ~190) dùng cho model probes.
- `nowing_backend/app/services/admin_telemetry_service.py` -- `get_proxy_health()` (dòng 620) và `get_celery_queue_stats()` (dòng 699) cho proxy + worker metrics.
- `nowing_backend/app/services/hybrid_llm_router.py` -- `_vllm_health()` (dòng 349) cho local vLLM probe.
- `nowing_backend/app/capabilities/core/store.py` -- `CapabilityRegistry.all()`, `query_metadata()`; 110+ capability registrations.
- `nowing_backend/app/capabilities/core/types.py` -- `Capability` dataclass; metadata field dùng để gắn `health_category`.
- `nowing_backend/app/alerts/engine/tick.py` -- `alert_engine_tick` Celery tick task; pattern để tái sử dụng schedule/execute.
- `nowing_backend/app/alerts/engine/notify.py` -- in-app, Telegram, email dispatch; cần adapt cho admin health scope.
- `nowing_backend/app/alerts/persistence/models/alert_rule.py` -- `AlertRule` model workspace-scoped; health rules dùng `capability_id='admin_health'` hoặc workspace_id đặc biệt.
- `nowing_backend/app/celery_app.py` -- thêm `beat_schedule` cho `health_probe_*` tasks.
- `nowing_backend/app/routes/admin_telemetry_routes.py` -- mở rộng với `/api/v1/admin/health/*`; tái sử dụng `require_superuser`.
- `nowing_backend/app/schemas/admin_health.py` -- Pydantic schemas request/response.
- `nowing_web/app/admin/telemetry/page.tsx` -- mở rộng với tabs và alert banner.
- `nowing_web/components/admin/health/` -- `HealthOverviewGrid`, `HealthStatusCard`, `HealthCategoryTabs`, `AlertBanner`, `HealthDrillDown`.
- `nowing_web/lib/apis/admin-health-api.service.ts` -- HTTP client gọi admin health API.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/services/health/probe_base.py` -- tạo `HealthProbe` ABC và `HealthResult` dataclass với status 5 giá trị.
- [x] `nowing_backend/app/services/health/registry.py` -- tạo `HealthProbeRegistry`, đăng ký probe theo category, discovery từ `CapabilityRegistry` + global models.
- [x] `nowing_backend/app/services/health/probes/*.py` -- implement 6 probe classes (model, scraper, connector, infrastructure, proxy, chainlens).
- [x] `nowing_backend/app/services/health/result_store.py` -- tạo store ghi Redis (latest + pub/sub) và DB tables.
- [x] `nowing_backend/app/services/health/alert_engine.py` -- tạo `AdminHealthAlertEngine` với 5 default rules và dedupe cooldown 15m.
- [x] `nowing_backend/app/services/health/scheduler.py` -- tạo scheduler chạy `run_category` với `asyncio.gather` + `Semaphore(20)`.
- [x] `nowing_backend/app/services/health/third_party_health_service.py` -- public facade cho Celery task và routes.
- [x] `nowing_backend/app/tasks/celery_tasks/health_probe_task.py` -- Celery task gọi scheduler theo category.
- [x] `nowing_backend/app/celery_app.py` -- thêm beat schedules với interval category-specific.
- [x] `alembic/versions/xxx_add_admin_health_tables.py` -- migration tạo 4 bảng và seed 5 alert rules.
- [x] `nowing_backend/app/schemas/admin_health.py` -- request/response Pydantic schemas.
- [x] `nowing_backend/app/routes/admin_telemetry_routes.py` -- extend với 6 admin health endpoints.
- [x] `nowing_web/components/admin/health/*.tsx` -- tạo 5 reusable health UI components.
- [x] `nowing_web/app/admin/telemetry/page.tsx` -- mở rộng tabbed layout + alert banner.
- [x] `nowing_web/lib/apis/admin-health-api.service.ts` -- tạo API client.
- [x] `nowing_backend/tests/unit/services/health/test_*_probe.py` -- unit test mỗi probe.
- [x] `nowing_backend/tests/unit/services/health/test_scheduler.py` -- unit test scheduler.
- [x] `nowing_backend/tests/unit/services/health/test_alert_engine.py` -- unit test alert engine.
- [x] `nowing_backend/tests/integration/routes/test_admin_health.py` -- integration test admin routes.
- [x] `nowing_web/tests/admin/health-operations.spec.ts` -- E2E Playwright tab switching + acknowledge.

**Acceptance Criteria:**
- Given `/admin/telemetry` được load bởi superadmin, when dashboard render, then hiển thị active alerts banner, tab navigation, và health status cards với badge/latency/success rate/last error.
- Given scheduler chạy, when hoàn tất một category, then kết quả được persist Redis snapshot + DB + pub/sub `nowing:health:updates`.
- Given service fail 2 consecutive probes, when alert engine evaluate, then tạo duy nhất một `admin_health_alerts` row trong 15 phút và dispatch qua kênh đã cấu hình.
- Given non-superadmin gọi `/api/v1/admin/health/*`, when xác thực, then trả HTTP 403.
- Given superadmin click một health card, when drill-down mở, then hiển thị 24h chart, recent error logs, metadata, và nút Test Now.

## Spec Change Log

## Design Notes

- **Health rules là một scope đặc biệt trong Generic Alert Engine.** `AlertRule` hiện có `workspace_id` nullable không (FK workspaces). Để reuse, health rules có thể dùng `workspace_id = NULL` + `capability_id = "admin_health"` hoặc thêm cột `scope` mặc định `"workspace"` và để health rules là `"admin"`. Ưu tiên cách thêm cột `scope` để không làm rối FK.
- **Probe discovery:** `CapabilityRegistry.all()` trả về list capability; mỗi capability có thể khai `metadata={"health_category": "scraper", "health_probe": "lightweight"}`. Probe sẽ fallback theo tên namespace (`tiktok.scrape` → `tiktok`) nếu metadata thiếu.
- **Proxy probe reuse:** `admin_telemetry_service.get_proxy_health()` đã có cache + throttling 10s. `ProxyHealthProbe` gọi trực tiếp method này và map `dead` → `unavailable`.
- **Celery beat schedule:** infrastructure 30s, model 2m, scraper 5m, connector 15m, messaging/payment/storage/ChainLens 5m. Dùng các task name riêng (`health_probe_infra`, `health_probe_model`, ...) để dễ trace.
- **Alert dedupe:** `AdminHealthAlertEngine` query `admin_health_alerts` với `service_id`, `rule_id`, `status='open'` hoặc `acknowledged_until > now()`; nếu tồn tại và chưa hết cooldown thì skip.

## Verification

**Commands:**
- `cd nowing_backend && uv run ruff check app/services/health app/routes/admin_telemetry_routes.py app/schemas/admin_health.py` -- expected: no errors.
- `cd nowing_backend && uv run pytest tests/unit/services/health tests/integration/routes/test_admin_health.py -q` -- expected: all pass.
- `cd nowing_web && pnpm tsc --noEmit` -- expected: no type errors.
- `cd nowing_web && pnpm exec biome check --max-diagnostics 500 app/admin/telemetry/page.tsx components/admin/health lib/apis/admin-health-api.service.ts` -- expected: clean.

## Suggested Review Order

**Entry point & data shape**

- Defines 5-state HealthResult and ABC contract.
  [`probe_base.py:14`](../../nowing_backend/app/services/health/probe_base.py#L14)
- Registers 25 scrapers, 13 connectors, 5 models + infra/proxy/research/messaging/payment/storage.
  [`registry.py:120`](../../nowing_backend/app/services/health/registry.py#L120)

**Probe implementations**

- Tests LLM/embedding connections and maps auth/missing-key to not_configured.
  [`model_probe.py:70`](../../nowing_backend/app/services/health/probes/model_probe.py#L70)
- Lightweight reachability checks for canonical scraper platforms.
  [`scraper_probe.py:53`](../../nowing_backend/app/services/health/probes/scraper_probe.py#L53)
- Counts active enabled Connections with credentials.
  [`connector_probe.py:52`](../../nowing_backend/app/services/health/probes/connector_probe.py#L52)
- Read-only Postgres/Redis/Caddy/Celery/Zero Cache checks.
  [`infrastructure_probe.py:56`](../../nowing_backend/app/services/health/probes/infrastructure_probe.py#L56)
- Reuses admin_telemetry_service proxy health.
  [`proxy_probe.py:41`](../../nowing_backend/app/services/health/probes/proxy_probe.py#L41)
- Calls ChainLens /api/v1/health endpoint.
  [`chainlens_probe.py:48`](../../nowing_backend/app/services/health/probes/chainlens_probe.py#L48)
- Basic messaging-gateway connectivity.
  [`messaging_probe.py:44`](../../nowing_backend/app/services/health/probes/messaging_probe.py#L44)
- Basic payment-gateway connectivity.
  [`payment_probe.py:44`](../../nowing_backend/app/services/health/probes/payment_probe.py#L44)
- Basic storage-gateway connectivity.
  [`storage_probe.py:44`](../../nowing_backend/app/services/health/probes/storage_probe.py#L44)

**Scheduling & persistence**

- Bounded concurrency, per-probe persist/alert, fallback result on failure.
  [`scheduler.py:35`](../../nowing_backend/app/services/health/scheduler.py#L35)
- Upserts DB, appends history, computes 15m rates, Redis snapshot + pub/sub.
  [`result_store.py:26`](../../nowing_backend/app/services/health/result_store.py#L26)

**Alerting**

- Rule evaluation, auto-resolve, dedupe, in-app/email/telegram dispatch.
  [`alert_engine.py:25`](../../nowing_backend/app/services/health/alert_engine.py#L25)

**Public API**

- Facade for overview, statuses, history, on-demand probe, alerts, acknowledge.
  [`third_party_health_service.py:25`](../../nowing_backend/app/services/health/third_party_health_service.py#L25)
- Superuser-gated health endpoints under /api/v1/admin/telemetry/health/*.
  [`admin_telemetry_routes.py:117`](../../nowing_backend/app/routes/admin_telemetry_routes.py#L117)
- Pydantic request/response schemas.
  [`admin_health.py:12`](../../nowing_backend/app/schemas/admin_health.py#L12)

**Models & migration**

- SQLAlchemy models for status, history, rules, alerts.
  [`admin_health.py:24`](../../nowing_backend/app/models/admin_health.py#L24)
- Creates four tables and seeds five default alert rules.
  [`238_add_admin_health_tables.py:23`](../../nowing_backend/alembic/versions/238_add_admin_health_tables.py#L23)

**Background jobs**

- Category-specific Celery Beat schedules (30s-15m).
  [`celery_app.py:444`](../../nowing_backend/app/celery_app.py#L444)
- Celery tasks delegating to HealthProbeScheduler.run_category.
  [`health_probe_task.py:35`](../../nowing_backend/app/tasks/celery_tasks/health_probe_task.py#L35)

**Frontend**

- Tabbed admin page with live polling and drill-down integration.
  [`page.tsx:25`](../../nowing_web/app/admin/telemetry/page.tsx#L25)
- Active alerts banner with acknowledge action.
  [`AlertBanner.tsx:14`](../../nowing_web/components/admin/health/AlertBanner.tsx#L14)
- Aggregated status metrics.
  [`HealthOverviewGrid.tsx:11`](../../nowing_web/components/admin/health/HealthOverviewGrid.tsx#L11)
- Category filter tabs.
  [`HealthCategoryTabs.tsx:14`](../../nowing_web/components/admin/health/HealthCategoryTabs.tsx#L14)
- Per-service health card.
  [`HealthStatusCard.tsx:13`](../../nowing_web/components/admin/health/HealthStatusCard.tsx#L13)
- 24h chart, recent errors, on-demand Test Now.
  [`HealthDrillDown.tsx:30`](../../nowing_web/components/admin/health/HealthDrillDown.tsx#L30)
- HTTP client for admin health endpoints.
  [`admin-health-api.service.ts:104`](../../nowing_web/lib/apis/admin-health-api.service.ts#L104)

**Tests**

- Alert engine creates and dispatches on unavailable.
  [`test_alert_engine.py:15`](../../nowing_backend/tests/unit/services/health/test_alert_engine.py#L15)
- Scheduler runs category and persists all results.
  [`test_scheduler.py:45`](../../nowing_backend/tests/unit/services/health/test_scheduler.py#L45)
- Model probe status transitions.
  [`test_model_probe.py:13`](../../nowing_backend/tests/unit/services/health/test_model_probe.py#L13)
- Scraper probe happy path.
  [`test_scraper_probe.py:11`](../../nowing_backend/tests/unit/services/health/test_scraper_probe.py#L11)
- Connector probe not_configured/healthy cases.
  [`test_connector_probe.py:13`](../../nowing_backend/tests/unit/services/health/test_connector_probe.py#L13)
- Infrastructure Postgres/Redis probes.
  [`test_infrastructure_probe.py:13`](../../nowing_backend/tests/unit/services/health/test_infrastructure_probe.py#L13)
- Proxy probe happy path.
  [`test_proxy_probe.py:13`](../../nowing_backend/tests/unit/services/health/test_proxy_probe.py#L13)
- ChainLens probe happy path.
  [`test_chainlens_probe.py:13`](../../nowing_backend/tests/unit/services/health/test_chainlens_probe.py#L13)
- Admin route happy paths and superuser gating.
  [`test_admin_health.py:18`](../../nowing_backend/tests/integration/routes/test_admin_health.py#L18)
- Celery task registration and Beat schedule.
  [`test_health_probe_task.py:27`](../../nowing_backend/tests/unit/tasks/celery_tasks/test_health_probe_task.py#L27)
- Playwright E2E for dashboard, tabs, acknowledge, drill-down.
  [`health-operations.spec.ts:171`](../../nowing_web/tests/admin/health-operations.spec.ts#L171)
