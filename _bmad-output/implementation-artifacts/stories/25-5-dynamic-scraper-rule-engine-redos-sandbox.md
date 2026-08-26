---
story_key: 25-5-dynamic-scraper-rule-engine-redos-sandbox
status: pending-human-review
baseline_commit: 0371c1147
epic: 25
story: 5
---

# Story 25.5: Dynamic Scraper Rule Engine & ReDoS Sandbox

**Status:** `pending-human-review`

**Governed by:** `INV-25.6` (Dynamic Scraper Rule Invalidation via Redis Pub/Sub), `INV-25.7` (ReDoS Sandbox Hard Limit & Schema AST Validation), `INV-25.8` (Fail-Closed Superadmin Guard & PAT Rejection), Epic 25 trong [`_bmad-output/planning-artifacts/epics.md`](../planning-artifacts/epics.md) dòng 3531–3640.

---

## Story

As a **Platform Superadmin**,  
I want to update CSS selectors, request delays, retry policies, and circuit-breaker settings for scrapers (Batdongsan, Chợ Tốt, TopCV, Muaban, v.v.) directly on the admin dashboard,  
so that I can react to site changes and anti-bot blocks without redeploying backend code.

---

## Acceptance Criteria

### AC-1 — Admin Rule CRUD API

**Given** `/api/v1/admin/scraper-rules` được gọi bởi một Superadmin session,  
**When** admin thực hiện CRUD trên rule,  
**Then** API hỗ trợ:

- `GET /api/v1/admin/scraper-rules` — liệt kê tất cả platform rules (phân trang `limit/offset`), kèm `version`, `is_active`, `updated_at`, `updated_by`.
- `GET /api/v1/admin/scraper-rules/{platform}` — lấy rule active hiện tại của một platform.
- `POST /api/v1/admin/scraper-rules/{platform}` — tạo version mới của rule.
- `PATCH /api/v1/admin/scraper-rules/{platform}/{version}` — kích hoạt/lên version hoặc chỉnh `is_active` (khóa chính thực tế là `(platform, version)`; `version` là số nguyên dương).
- `DELETE /api/v1/admin/scraper-rules/{platform}/{version}` — xóa một version **không active**; không được xóa version đang active.
- `POST /api/v1/admin/scraper-rules/{platform}/circuit-breaker/trip` — emergency trip.
- `POST /api/v1/admin/scraper-rules/{platform}/circuit-breaker/reset` — emergency reset.
- `POST /api/v1/admin/scraper-rules/{platform}/refresh` — force publish `scraper_config_updated`.

Payload rule phải chứa JSONB `rule_schema` với các trường:

```json
{
  "selectors": {
    "listing_card": "div.js__card-listing",
    "title": "span.js__card-title",
    "price": "span.re__card-config-price",
    "area": "...",
    "next_page_link": "a.next"
  },
  "regexes": {
    "phone_in_title": "(?:(?<=[^\d])|^)(?:\+84|84|0)[0-9\s\.\-]{8,15}(?:(?=[^\d])|$)"
  },
  "delays": {
    "request_ms": 1500,
    "retry_base_ms": 1000
  },
  "retries": {
    "max_attempts": 3,
    "statuses": [429, 500, 502, 503]
  },
  "circuit_breaker": {
    "error_threshold_pct": 20,
    "min_calls": 10,
    "trip_duration_seconds": 300,
    "tripped": false
  }
}
```

> **Ponytail:** Trong v1 chỉ cần lưu và validate schema; việc **áp dụng** selectors động vào parser cụ thể (thay `parsers.py` hardcoded) là optional và được ghi trong AC-6. Đừng phá vỡ parser đang chạy.

### AC-2 — Validation trước khi lưu

**Given** một rule payload được gửi lên,  
**When** backend validate,  
**Then**:

- Mọi CSS selector string trong `selectors.*` được parse qua `cssselect.parse` (`SelectorSyntaxError` → 422 với detail `Invalid CSS selector: ...`). Có thể dùng `cssselect.HTMLTranslator()` để kiểm tra translate sang XPath nếu cần.
- Mọi regex string trong `regexes.*` được compile bằng `google-re2` (`re2.compile(pattern)`) và benchmark ReDoS < 50ms. Nếu `google-re2` không cài thì dùng `re.compile` trong thread với hard timeout 50ms (dùng `concurrent.futures.ProcessPoolExecutor` hoặc `signal` nếu chạy trên main thread/process) nhưng **vẫn phải benchmark**. Lưu ý `google-re2` không hỗ trợ lookahead/lookbehind.
- `delays.request_ms`, `delays.retry_base_ms`, `retries.max_attempts`, `circuit_breaker.*` phải là số nguyên dương hoặc 0, nằm trong range hợp lý (`request_ms` 0–60000, `retry_base_ms` 0–60000, `max_attempts` 0–10, `error_threshold_pct` 0–100, `trip_duration_seconds` 0–3600).
- Nếu validation fail, trả về `HTTP 422 Unprocessable Entity` với body `{"detail": [{"loc": [...], "msg": ..., "type": ...}]}` (FastAPI default) hoặc `{"code": "INVALID_CSS"|"REDOS_TIMEOUT", "detail": ...}`. Giữ một format duy nhất.

> **Ponytail:** `google-re2` chưa có trong `pyproject.toml` / `uv.lock`. Thêm `google-re2>=1.1.20251105` vào dependencies. Nếu build C++ extension gặp khó trên local/dev, dùng `re` với sandbox 50ms như fallback có warning log.

### AC-3 — ReDoS Sandbox Benchmark

**Given** một regex string được gửi,  
**When** backend chạy ReDoS benchmark,  
**Then**:

- Dùng `google-re2` nếu có; với mỗi regex, compile và benchmark trên các input độ dài tăng dần (1 KB, 10 KB, 100 KB) được sinh từ charset của regex. Nếu `google-re2` không có, dùng `re.search` trong process/thread với hard timeout 50ms.
- Nếu một trong các lần chạy vượt 50 ms → `HTTP 422` với `code: REDOS_TIMEOUT`.
- Sandbox **không** chạy trong event loop chính; dùng `asyncio.to_thread()` cho thread-safe, hoặc `concurrent.futures.ProcessPoolExecutor` nếu cần thực sự kill thread bị treo.
- Bộ test cố định bao gồm pattern nguy hiểm `(a+)+$` với input `'a' * 30 + '!'`, pattern `(a|aa)+$`, `(a+)+b`, và các input ngắn dễ gây catastrophic backtracking. Các pattern này phải bị từ chối.

### AC-4 — Versioned JSONB Storage + Audit

**Given** một rule hợp lệ,  
**When** lưu thành công,  
**Then**:

- Tạo model `ScraperRule` trong `app/db.py` (ngay sau `ScraperPlatformAccount`) hoặc trong file riêng được import từ `app/db.py` để `Base.metadata` nhìn thấy. Tạo alembic migration `alembic/versions/NNN_add_scraper_rules_table.py`.
- Bảng `scraper_rules` có các cột:
  - `id` (PK BigInteger/Integer), `platform` (String(64), indexed, NOT NULL), `version` (Integer, NOT NULL), `rule_schema` (JSONB, NOT NULL), `is_active` (Boolean, default false), `created_by_user_id` (UUID, FK `user.id`, nullable), `updated_by_user_id` (UUID, FK `user.id`, nullable), `created_at`, `updated_at`.
  - Unique constraint `(platform, version)`.
  - Partial unique index `uq_scraper_rules_active_per_platform` trên `platform` WHERE `is_active = true` để chỉ có một active rule mỗi platform.
- `ScraperRule` là bảng toàn cục (không có `workspace_id`/`client_id`), do đó KHÔNG áp dụng RLS workspace. Admin routes dùng `require_superuser`.
- Mỗi create/update/activate/toggle/delete đều ghi `AuditEvent` với `action='scraper_rule.create'` / `'scraper_rule.update'` / `'scraper_rule.activate'` / `'scraper_rule.trip'` / `'scraper_rule.reset'`, `actor_id=<admin_uuid>`, `diff_payload={platform, version, rule_schema}` (INV-25.2).

### AC-5 — Redis Pub/Sub Live Invalidation + Auto-Rollback

**Given** một rule active được update hoặc activate version mới,  
**When** transaction commit,  
**Then**:

- Backend publish một message lên Redis Pub/Sub channel `scraper_config_updated` với payload JSON `{"platform": "batdongsan", "version": 7, "is_active": true, "updated_at": "..."}`.
- Mỗi Celery worker process (hoặc API process) có TTL cache < 5s cho active rule; khi nhận được message, invalidate in-memory cache và reload rule từ DB.
- **INV-25.6 (auto-fallback):** Worker theo dõi error rate của version hiện tại (số lỗi / tổng calls trong 5 phút gần nhất). Nếu error rate vượt 20% trong ít nhất `circuit_breaker.min_calls` calls, tự động deactivate version hiện tại và activate lại version trước đó (nếu có). V1 có thể ghi log + gửi alert thay vì auto-rollback phức tạp, nhưng metric phải được tính và hiển thị trên UI.
- Cung cấp endpoint `POST /api/v1/admin/scraper-rules/{platform}/refresh` để force publish `scraper_config_updated` và kiểm tra worker cache.

> **Ponytail:** Có thể dùng Redis Pub/Sub trong `app/redis_client.py:get_redis_client()` hoặc `celery_app` broadcast. V1 ưu tiên **Pub/Sub + in-process cache**; Celery worker subscribe trong `@worker_process_init` hoặc tại nơi cần config. Đừng restart worker.

### AC-6 — Wire rule vào scraper worker (v1: batdongsan delays/retries, selectors behind feature flag)

**Given** một platform scraper task chạy (ví dụ `batdongsan.scrape`),  
**When** nó cần delays/retries/selectors,  
**Then**:

- Feature flag `USE_DYNAMIC_SCRAPER_RULES` (default `false` trong `app/config/__init__.py`) quyết định có đọc `ScraperRule` active từ DB hay không.
- Ưu tiên `rule_schema` từ active `ScraperRule` nếu `is_active=true` và `USE_DYNAMIC_SCRAPER_RULES=true`.
- Nếu không có rule active hoặc feature flag tắt, fallback về hardcoded config hiện tại (`BATDONGSAN_PAGE_DELAY_S`, `BATDONGSAN_RETRY_BACKOFF_BASE_S`, `_MAX_RETRIES`, `PlatformRateLimiter`, `PlatformCircuitBreaker`).
- V1 tích hợp `delays.request_ms`/`retries.max_attempts` trước vì đây là đường chính trong `batdongsan/scraper.py:83-86, 130-219`. `selectors` CSS chỉ áp dụng cho web fallback path (`batdongsan/scraper.py:162-191`, `parsers.py:234-260`) nên được gói sau feature flag hoặc v1.1.
- Convert `request_ms`/`retry_base_ms` từ ms sang seconds (chia 1000) khi truyền vào `asyncio.sleep` / `time.sleep`.

### AC-7 — Emergency Circuit Breaker

**Given** admin bật `Emergency Circuit Breaker: Trip` trên một platform,  
**When** backend nhận toggle qua `POST /api/v1/admin/scraper-rules/{platform}/circuit-breaker/trip`,  
**Then**:

- Set `rule_schema.circuit_breaker.tripped = true` trong `ScraperRule` active (DB) để lưu ý định trạng thái.
- Ghi trực tiếp Redis key `circuit_breaker:scraper:{platform} = "OPEN"` với TTL `circuit_breaker.trip_duration_seconds` (hoặc `PlatformCircuitBreaker.CIRCUIT_COOLDOWN_SECONDS` mặc định 600s). `PlatformCircuitBreaker` hiện tại là count-based (3 lỗi liên tiếp) nên cần thêm hàm `trip(platform)` / `reset(platform)` hoặc ghi key thủ công.
- Ngay lập tức publish `scraper_config_updated` với `circuit_breaker.tripped=true`.
- Celery worker gặp `tripped=true` hoặc `PlatformCircuitBreaker.is_available(platform)==False` thì skip enqueue/execution các task scraper của platform đó và trả `degraded` với `reason: circuit_breaker_tripped`.
- Admin có thể `Reset` circuit breaker từ UI qua `POST /api/v1/admin/scraper-rules/{platform}/circuit-breaker/reset`; reset xóa cả `state_key` (`circuit_breaker:scraper:{platform}`) và `failure_counter_key` (`circuit_breaker:failures:{platform}`), set `tripped=false` trong DB, publish event.

### AC-8 — Superadmin Guard

**Given** bất kỳ endpoint `/api/v1/admin/scraper-rules/*`,  
**When** gọi bởi PAT, non-superuser, hoặc impersonated session,  
**Then** trả `HTTP 403 Forbidden` qua `require_superuser` (INV-25.8).

### AC-9 — Admin UI `/admin/scrapers/rules`

**Given** `/admin/scrapers/rules` được load bởi superadmin,  
**When** hiển thị,  
**Then**:

- Hiển thị danh sách platform, version active, trạng thái circuit breaker, last updated.
- Cho phép edit `rule_schema` qua JSON editor (textarea validate JSON) hoặc form theo từng trường (`selectors`, `delays`, `retries`, `circuit_breaker`).
- Nút `Save` chạy backend validation; nếu CSS/regex lỗi thì hiển thị lỗi inline.
- Nút `Trip Circuit Breaker` và `Reset Circuit Breaker` có xác nhận modal.
- Page reload / refresh mỗi 5 giây qua polling hoặc Zero-cache.

---

## Tasks / Subtasks

- [ ] **Task 1: DB Schema & Migration**
  - [ ] Tạo model `ScraperRule` trong `nowing_backend/app/db.py` (đề xuất ngay sau `ScraperPlatformAccount`) hoặc `nowing_backend/app/models/scraper_rule.py` và import trong `app/db.py` để `Base.metadata` đăng ký.
  - [ ] Tạo alembic migration `alembic/versions/NNN_add_scraper_rules_table.py` bằng `uv run alembic revision --autogenerate -m "add scraper rules table"`. Sau khi tạo, chạy `uv run alembic history` để kiểm tra single head; nếu có nhiều head thì tạo merge.
  - [ ] Cột: `id`, `platform` (String(64), index), `version` (Integer), `rule_schema` (JSONB, NOT NULL), `is_active` (Boolean, default false), `created_by_user_id` (UUID FK `user.id`), `updated_by_user_id` (UUID FK `user.id`), `created_at`, `updated_at`.
  - [ ] Unique constraint `(platform, version)`; partial unique index `uq_scraper_rules_active_per_platform` trên `platform` WHERE `is_active = true`.
  - [ ] Đảm bảo `rule_schema` là JSONB NOT NULL. Không cần bảng `scraper_circuit_breakers` riêng — dùng Redis key của `PlatformCircuitBreaker`.

- [ ] **Task 2: ReDoS & CSS Selector Validation Service**
  - [ ] Tạo `app/services/scraper_rule_validator.py`:
    - `validate_css_selectors(selectors: dict[str, str])` dùng `cssselect.parse`. Nếu cần kiểm tra translate, dùng `cssselect.HTMLTranslator()` với `lxml.etree`.
    - `validate_regexes(patterns: dict[str, str])` dùng `google-re2.compile` nếu có; fallback `re.compile` trong process/thread với hard timeout 50ms.
    - `benchmark_redos(pattern, test_inputs)` trả về max ms hoặc raise `ReDoSTimeoutError`. Test inputs bao gồm pattern `(a+)+$` với `'a'*30+'!'`, `(a|aa)+$`, `(a+)+b`, v.v.
  - [ ] Thêm `google-re2>=1.1.20251105` vào `pyproject.toml` và chạy `uv lock`. Kiểm tra `cssselect` và `lxml` được khai báo trực tiếp trong `pyproject.toml` (hiện tại `cssselect` là transitive qua `scrapling`; `lxml` được dùng trực tiếp nhưng cần pin để tránh mất đi nếu `scrapling` thay đổi).

- [ ] **Task 3: Scraper Rule CRUD Service**
  - [ ] Tạo `app/services/scraper_rules_service.py`:
    - `get_rules(session, limit, offset, platform=None)`.
    - `get_active_rule(session, platform)` — dùng partial index, cache 5s.
    - `create_rule(session, platform, rule_schema, auth)` — sinh `version = (max version hiện có) + 1` trong transaction với `SELECT ... FOR UPDATE`; set active nếu là version đầu tiên; publish Redis event.
    - `activate_rule(session, platform, version, auth)` — deactivate cũ, activate mới trong transaction; publish Redis event.
    - `delete_rule(session, platform, version)` — chỉ cho xóa version **không active**. Nếu muốn xóa active, phải activate version khác trước.
    - `trip_circuit_breaker(session, platform, auth)` / `reset_circuit_breaker(session, platform, auth)` — ghi Redis key `circuit_breaker:scraper:{platform}` OPEN/CLOSED, cập nhật `rule_schema.circuit_breaker.tripped`, publish event. Không dùng `record_failure`/`record_success` vì chúng là count-based; cần trực tiếp set/reset state.
    - Ghi `AuditEvent` mỗi lần mutate với `actor_id = auth.user.id`, `diff_payload`.
    - Cập nhật `updated_by_user_id` khi activate/toggle/delete.

- [ ] **Task 4: Redis Pub/Sub Listener + In-Memory Cache**
  - [ ] Tạo `app/services/scraper_rule_pubsub.py`:
    - `publish_rule_update(redis, platform, version, is_active, circuit_breaker_tripped)`.
    - `start_rule_subscriber(redis, callback)` — coroutine dùng `asyncio.create_task`.
    - `invalidate_rule_cache(platform)`.
  - [ ] Tạo `app/services/scraper_rule_cache.py` hoặc `lru_cache` + TTL trong `scraper_rules_service.py`.
  - [ ] API lifespan: tích hợp subscriber vào `app/app.py:lifespan` (`@asynccontextmanager`) bằng `asyncio.create_task`. Không dùng `app/main.py` vì file đó chỉ chạy `uvicorn`.
  - [ ] Celery worker: `@worker_process_init` là sync; **KHÔNG** `await` subscriber trực tiếp. Cách làm:
    - Spawn daemon thread với event loop riêng chạy `start_rule_subscriber`; hoặc
    - Dùng TTL cache 5s và reload từ DB trước mỗi task. V1 ưu tiên TTL fallback đơn giản.

- [ ] **Task 5: Backend Admin Routes**
  - [ ] Tạo `app/routes/admin_scraper_rules_routes.py` với `APIRouter(prefix="/admin/scraper-rules", tags=["admin"])` (giống `admin_telemetry_routes.py`, `admin_scraper_platform_accounts_routes.py`). Main `crud_router` trong `app/routes/__init__.py` đã được mount tại `/api/v1`, `/api` và `/` trong `app/app.py`, nên full path sẽ là `/api/v1/admin/scraper-rules`. KHÔNG hardcode `/api/v1` trong `APIRouter(prefix=...)`.
  - [ ] Thêm endpoints:
    - `GET /` — list rules.
    - `GET /{platform}` — get active rule.
    - `POST /{platform}` — create new version.
    - `PATCH /{platform}/{version}` — activate/deactivate a version.
    - `DELETE /{platform}/{version}` — delete a non-active version.
    - `POST /{platform}/circuit-breaker/trip` — emergency trip.
    - `POST /{platform}/circuit-breaker/reset` — emergency reset.
    - `POST /{platform}/refresh` — force publish `scraper_config_updated`.
  - [ ] Tất cả endpoints dùng `_auth: AuthContext = Depends(require_superuser)`.
  - [ ] Tạo Pydantic schemas trong `app/schemas/admin_scraper_rules.py` (`RuleSchema`, `ScraperRuleCreate`, `ScraperRuleUpdate`, `ScraperRuleRead`, `ScraperRuleListResponse`).
  - [ ] Wire router vào `app/routes/__init__.py` ngay cạnh `admin_scraper_platform_accounts_router`.

- [ ] **Task 6: Frontend Admin Page**
  - [ ] Tạo `nowing_web/app/admin/scrapers/rules/page.tsx` theo pattern `scraper-accounts/page.tsx` dùng `useState`/`useEffect` và `scraperPlatformAccountsApiService`.
  - [ ] Thêm nav link `/admin/scrapers/rules` trong `nowing_web/app/admin/admin-shell.tsx`.
  - [ ] Tạo `nowing_web/lib/apis/admin-scraper-rules-api.service.ts` dùng `baseApiService` (như `lib/apis/admin-telemetry-api.service.ts`) + Zod schemas.
  - [ ] Tạo các components: rule list, rule editor (textarea JSON với validate hoặc form), circuit breaker toggle, validation error display.
  - [ ] Gate superuser theo pattern `scraper-accounts/page.tsx`.

- [ ] **Task 7: Wiring to Scraper Worker (v1: delays/retries, selectors behind flag)**
  - [ ] Thêm `USE_DYNAMIC_SCRAPER_RULES: bool = os.getenv(..., "false").lower() == "true"` vào `app/config/__init__.py`.
  - [ ] Trong `app/tasks/lead_scrapers.py` hoặc `app/capabilities/batdongsan/scrape/executor.py`, gọi `ScraperRulesService.get_active_rule(platform)` trước khi scrape.
  - [ ] Nếu rule active tồn tại và flag bật: dùng `rule_schema.delays.request_ms`/`retries.max_attempts` thay cho `config.BATDONGSAN_PAGE_DELAY_S`/`_MAX_RETRIES`. Chia ms cho 1000.
  - [ ] Tích hợp `selectors` CSS vào `batdongsan/parsers.py:parse_web_listings` chỉ khi flag bật và đang ở web fallback path.
  - [ ] Fallback về hardcoded config khi rule thiếu hoặc flag tắt.
  - [ ] Kiểm tra `PlatformCircuitBreaker.is_available(platform)` và `rule_schema.circuit_breaker.tripped` trước khi chạy.

- [ ] **Task 8: Tests**
  - [ ] `tests/unit/services/test_scraper_rule_validator.py` — CSS valid/invalid, ReDoS timeout, ReDoS safe.
  - [ ] `tests/integration/routes/test_admin_scraper_rules.py` — CRUD, 403 PAT/non-superuser, validation 422, audit event.
  - [ ] `nowing_web/tests/admin/scraper-rules.spec.ts` — mocked API, UI render, circuit breaker toggle.

---

## Dev Notes

### Existing Code to Reuse (Do Not Reinvent)

- **Admin authz pattern:**
  - `nowing_backend/app/users.py:412-426` — `require_superuser`.
  - `nowing_backend/app/routes/admin_telemetry_routes.py:1-99` — admin router pattern.
  - `nowing_backend/app/routes/admin_scraper_platform_accounts_routes.py` — CRUD + alias router cho admin.
- **Redis client:**
  - `nowing_backend/app/redis_client.py` — `get_redis_client()` async singleton.
  - `nowing_backend/app/celery_app.py:216-220` — queue names (`LEAD_SCRAPERS_QUEUE`, `CONNECTORS_QUEUE`).
  - `nowing_backend/app/services/admin_telemetry_service.py:706-836` — ví dụ dùng `aioredis.from_url` với `socket_connect_timeout=2`.
- **Pub/Sub pattern:**
  - `nowing_backend/app/routes/dsh_routes.py:429-470` — subscribe/unsubscribe Redis pubsub với `get_message` loop.
- **API lifespan / startup:**
  - `nowing_backend/app/app.py:676-737` — `@asynccontextmanager async def lifespan` — đây là nơi subscribe Redis Pub/Sub non-blocking bằng `asyncio.create_task`.
- **AuditEvent:**
  - `nowing_backend/app/db.py:6273-6294` — model `AuditEvent` (`action`, `actor_id`, `diff_payload` JSONB).
  - `nowing_backend/app/routes/admin_telemetry_routes.py` — cách ghi audit cho DLQ purge.
- **Platform parser selectors (hardcoded today):**
  - `nowing_backend/app/proprietary/platforms/batdongsan/parsers.py:234-260` — `soup.select("div.js__card-listing")`, `select_one("a.js__product-link-for-product-id")`, `select_one("span.js__card-title")`, `select_one("span.re__card-config-price")`.
  - `nowing_backend/app/proprietary/platforms/chotot/fetch.py:62-` — `_CATEGORY_CONFIG` dict config, nhưng không dùng CSS selectors.
  - `nowing_backend/app/proprietary/platforms/topcv/scraper.py` — tồn tại TopCV scraper riêng, dùng `lxml_html` + XPath + regex.
- **Existing scraper worker / circuit breaker / rate limiter:**
  - `nowing_backend/app/tasks/lead_scrapers.py` — Celery task `run_platform_scrape_task`, queue `nowing.lead_scrapers`.
  - `nowing_backend/app/lead_intelligence/services/circuit_breaker.py` — `PlatformCircuitBreaker` với threshold 3 lỗi, cooldown 600s. **Reuse và mở rộng** cho emergency trip thay vì viết mới.
  - `nowing_backend/app/lead_intelligence/services/rate_limiter.py` — `PlatformRateLimiter` Lua token-bucket với `PLATFORM_RATE_LIMITS` hardcoded. Rule engine có thể cấu hình rate/delays động, fallback về hardcoded.
- **Versioned JSONB pattern:**
  - `nowing_backend/app/automations/persistence/models/playbook.py` — `Playbook` với `definition JSONB`, `version INTEGER`, `inputs_schema JSONB`. Đây là mẫu chuẩn cho bảng `scraper_rules`.
- **Admin UI patterns:**
  - `nowing_web/app/admin/scraper-accounts/page.tsx` — tabs, tables, modals, toggles.
  - `nowing_web/lib/apis/admin-telemetry-api.service.ts` — API service pattern với `baseApiService` + Zod.
  - `nowing_web/lib/apis/scraper-platform-accounts-api.service.ts` — API service pattern với Zod.
  - `nowing_web/app/admin/admin-shell.tsx:38-54` — thêm nav link.
- **Admin UI fetch pattern:**
  - `nowing_web/app/admin/telemetry/page.tsx` — dùng `useState`/`useEffect` và gọi service, polling 5s.
- **JSONB config versioning pattern:**
  - `nowing_backend/app/db.py:1002-1029` — `ScraperPlatformAccount.usage_state` JSONB.
  - `nowing_backend/app/automations/persistence/models/playbook.py` — `Playbook` với `definition JSONB` + `version INTEGER` là mẫu versioning chuẩn nhất.

### Key Decisions

1. **Versioned rule storage:** Mỗi platform có nhiều version nhưng chỉ một active. Tạo version mới khi admin save; activate/deactivate không xóa history. Đảm bảo audit và rollback.
2. **ReDoS engine:** Ưu tiên `google-re2` vì linear-time guarantee. Nếu build phức tạp, dùng Python `re` trong process/thread với hard 50 ms timeout; `google-re2` vẫn được recommend cho production. `google-re2` không hỗ trợ lookahead/lookbehind.
3. **CSS selector validation:** Dùng `cssselect.parse` để kiểm tra syntax. `cssselect.HTMLTranslator()` dùng để test translate sang XPath nếu cần. Không cần match real DOM.
4. **Cache invalidation:** Dùng Redis Pub/Sub `scraper_config_updated` thay vì database polling. API lifespan subscribe non-blocking. Worker dùng TTL cache 5s vì `@worker_process_init` là sync và không thể await trực tiếp.
5. **Circuit breaker:** Reuse `PlatformCircuitBreaker` (`app/lead_intelligence/services/circuit_breaker.py`) cho lỗi tự động count-based; mở rộng thêm `trip()`/`reset()` để admin emergency trip qua Redis key `circuit_breaker:scraper:{platform}=OPEN`. Khi tripped, worker trả `degraded` thay vì crash.
6. **Feature flag:** `USE_DYNAMIC_SCRAPER_RULES` (default `false`) trong `app/config/__init__.py` để giảm rủi ro hồi quy khi wire vào parser. V1 wire `delays`/`retries` trước; `selectors` CSS sau feature flag.
7. **DB model:** `ScraperRule` là global admin table, không có `workspace_id`/`client_id`, không RLS. Partial unique index `WHERE is_active = true` trên `platform`.

### Performance & Security Guardrails

- Tất cả admin endpoints **MUST** dùng `require_superuser` (INV-25.8). Không dùng workspace role.
- PAT **bị từ chối tuyệt đối** do `require_session_context` (INV-25.8).
- Validation ReDoS **KHÔNG** chạy trực tiếp trên event loop; dùng `asyncio.to_thread()` hoặc thread pool.
- `rule_schema` được validate bằng Pydantic `ConfigDict(extra="forbid")` trước khi merge; không cho phép extra fields gây confusion.
- `AuditEvent` ghi đầy đủ `actor_id`, `action`, `diff_payload` cho mọi create/update/activate/delete/trip (INV-25.2).
- `is_active` partial unique index để tránh race condition khi activate version; dùng transaction + `SELECT ... FOR UPDATE` nếu cần.
- Không expose `rule_schema` nguyên bản qua log/error (có thể chứa regex sensitive).

### Suggested File Tree

```
nowing_backend/
  alembic/versions/NNN_add_scraper_rules_table.py
  app/db.py  (add ScraperRule model)
  app/config/__init__.py  (add USE_DYNAMIC_SCRAPER_RULES)
  app/services/scraper_rule_validator.py
  app/services/scraper_rules_service.py
  app/services/scraper_rule_pubsub.py
  app/services/scraper_rule_cache.py  (optional, TTL + invalidation)
  app/routes/admin_scraper_rules_routes.py
  app/schemas/admin_scraper_rules.py
  app/routes/__init__.py  (import + include_router)
  app/lead_intelligence/services/circuit_breaker.py  (add trip/reset methods)

nowing_web/
  app/admin/scrapers/rules/page.tsx
  lib/apis/admin-scraper-rules-api.service.ts
  components/admin/scraper-rules/
    RuleList.tsx
    RuleEditor.tsx
    CircuitBreakerToggle.tsx
    ValidationErrors.tsx
  app/admin/admin-shell.tsx  (add nav link)
```

---

## Project Structure Notes

- Align với `admin_*_routes.py` naming và `Admin` service naming (`admin_scraper_rules_routes.py`, `scraper_rules_service.py`).
- Align với `nowing_web/app/admin/[feature]/page.tsx` structure. Không tạo layout mới; dùng `AdminShell`.
- `rule_schema` JSONB nên tương thích với cả `selectors` CSS, `regexes`, `delays`, `retries`, `circuit_breaker`. Để lại room cho extension (`headers`, `user_agent`, `cookies`).
- Dùng `shadcn/ui` components có sẵn: `table`, `card`, `dialog`, `button`, `badge`, `switch`, `select`, `input`, `textarea`, `tabs`, `sonner` toast.
- `ScraperRule` model nên đặt trong `app/db.py` (giống `ScraperPlatformAccount`) để `Base.metadata` tự động đăng ký; hoặc import `app/models/scraper_rule.py` trong `app/db.py`.
- Router prefix chỉ là `/admin/scraper-rules`; `/api/v1` được thêm bởi `app.app:app.include_router(crud_router, prefix="/api/v1")`.
- `USE_DYNAMIC_SCRAPER_RULES` thêm vào `app/config/__init__.py` dưới dạng `bool` từ env, default `false`.
- Worker subscribe Pub/Sub: API dùng `app.app:lifespan`; Celery worker dùng TTL cache hoặc background thread.

---

## References

- Epic 25 & Story 25.5: [`_bmad-output/planning-artifacts/epics.md`](../planning-artifacts/epics.md) dòng 3531–3640.
- `INV-25.6`, `INV-25.7`, `INV-25.8` cùng file, dòng 3543–3545.
- `AuditEvent` model: `nowing_backend/app/db.py:6273-6294`.
- `ScraperPlatformAccount` model: `nowing_backend/app/db.py:1002-1029`.
- Batdongsan parser selectors: `nowing_backend/app/proprietary/platforms/batdongsan/parsers.py:234-260`.
- Redis client: `nowing_backend/app/redis_client.py`.
- Celery app & queues: `nowing_backend/app/celery_app.py:216-220`.
- Admin auth pattern: `nowing_backend/app/users.py:412-426`.
- Admin route patterns: `nowing_backend/app/routes/admin_telemetry_routes.py`, `admin_scraper_platform_accounts_routes.py`.
- FastAPI router mount / `app.app:lifespan`: `nowing_backend/app/app.py:1200-1202`, `app/app.py:676-737`.
- Admin UI patterns: `nowing_web/app/admin/scraper-accounts/page.tsx`, `admin-shell.tsx`, `lib/apis/scraper-platform-accounts-api.service.ts`, `lib/apis/admin-telemetry-api.service.ts`.
- Versioned JSONB pattern: `nowing_backend/app/automations/persistence/models/playbook.py`.
- Existing scraper worker + circuit breaker + rate limiter: `nowing_backend/app/tasks/lead_scrapers.py`, `nowing_backend/app/lead_intelligence/services/circuit_breaker.py`, `nowing_backend/app/lead_intelligence/services/rate_limiter.py`.
- Scraper parser / executor wiring: `nowing_backend/app/proprietary/platforms/batdongsan/scraper.py`, `parsers.py:234-260`, `app/capabilities/batdongsan/scrape/executor.py`.
- `google-re2` PyPI docs: <https://pypi.org/project/google-re2/> (latest `1.1.20251105`).
- `cssselect` docs: <https://cssselect.readthedocs.io/>.

---

## Lệnh xác minh (Verification Commands)

```bash
# Alembic single-head check (run first)
cd nowing_backend
uv run alembic history
uv run alembic upgrade head

# Backend import smoke
cd nowing_backend
uv run python -c "from app.app import app; print('app import OK')"

# Backend lint & typecheck (targeted)
uv run ruff check app/db.py app/config/__init__.py app/services/scraper_rule_validator.py app/services/scraper_rules_service.py app/services/scraper_rule_pubsub.py app/services/scraper_rule_cache.py app/routes/admin_scraper_rules_routes.py app/schemas/admin_scraper_rules.py app/lead_intelligence/services/circuit_breaker.py tests/unit/services/test_scraper_rule_validator.py tests/integration/routes/test_admin_scraper_rules.py
uv run ruff format app/db.py app/config/__init__.py app/services/scraper_rule_validator.py app/services/scraper_rules_service.py app/services/scraper_rule_pubsub.py app/services/scraper_rule_cache.py app/routes/admin_scraper_rules_routes.py app/schemas/admin_scraper_rules.py app/lead_intelligence/services/circuit_breaker.py tests/unit/services/test_scraper_rule_validator.py tests/integration/routes/test_admin_scraper_rules.py
uv run pytest tests/unit/services/test_scraper_rule_validator.py tests/integration/routes/test_admin_scraper_rules.py -q

# Frontend typecheck & biome
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/admin/scrapers/rules/page.tsx lib/apis/admin-scraper-rules-api.service.ts components/admin/scraper-rules/RuleList.tsx components/admin/scraper-rules/RuleEditor.tsx components/admin/scraper-rules/CircuitBreakerToggle.tsx components/admin/scraper-rules/ValidationErrors.tsx tests/admin/scraper-rules.spec.ts

# Playwright E2E
pnpm test:e2e tests/admin/scraper-rules.spec.ts
```

---

## Challenge Log (grill-me)

### Q1 — Is this already implemented?

Partial. Admin shell and superadmin guards exist (`require_superuser`, `admin-shell.tsx`). `cssselect` is in dependencies. Redis Pub/Sub is used in DSH routes. There is **no** `ScraperRule` table, no admin CRUD, no ReDoS sandbox, and no live rule invalidation yet.

### Q2 — Why not store rules in a YAML file like `global_llm_config.yaml`?

Rule engine cần versioning, audit, và hot-reload mà không restart. YAML file yêu cầu deploy/restart và không có audit. JSONB + Redis Pub/Sub là đúng tầng.

### Q3 — Why `google-re2` instead of Python `re` with timeout?

`re` vẫn có thể gây catastrophic backtracking trước khi timeout kịp fire. `google-re2` guarantee linear time và memory safe. Timeout 50 ms trên `re` là fallback chứ không phải first-class defense.

### Q4 — What if a worker misses the Pub/Sub message?

Mỗi worker cache có TTL ngắn (5s) để lấy rule mới từ DB. Pub/Sub là tối ưu; TTL là an toàn.

### Q5 — How does this avoid breaking existing scrapers?

V1 lưu rule trong DB nhưng chỉ áp dụng khi `USE_DYNAMIC_SCRAPER_RULES=true`. Default false hoặc fallback về hardcoded. Chỉ một platform được wire end-to-end trong v1.

### Q6 — What is the schema for `rule_schema`?

Top-level keys: `selectors` (dict[str, str] CSS), `regexes` (dict[str, str]), `delays` (`request_ms`, `retry_base_ms`), `retries` (`max_attempts`, `statuses`), `circuit_breaker` (`error_threshold_pct`, `min_calls`, `trip_duration_seconds`, `tripped`). Pydantic `RuleSchema` với `ConfigDict(extra="forbid")` validate.

### Q7 — Where does the admin UI live?

`nowing_web/app/admin/scrapers/rules/page.tsx`, nav link trong `nowing_web/app/admin/admin-shell.tsx`. Theo pattern `/admin/scraper-accounts`.

### Q8 — How to test ReDoS sandbox?

Unit test với pattern `(a+)+$` trên input `"a" * 30 + "!"`; Python `re` sẽ timeout >50ms, `google-re2` sẽ trả `False` nhanh. Cả hai đều phải raise 422.

### Q9 — What about TopCV / ItViec?

Story AC ghi "Batdongsan, Chotot, TopCV, Muaban". Các platform tương ứng tồn tại: `batdongsan/`, `chotot/`, `topcv/`, `muaban_bds/`, `masothue/`, `itviec/`. V1 tập trung wire `batdongsan` (parser dùng CSS selectors rõ ràng) và tạo CRUD cho tất cả platform slug; wire parser cho các platform khác có thể deferred hoặc dùng feature flag.

### Q10 — What dependencies need to be added?

`google-re2>=1.1.20251105` vào `pyproject.toml` / `uv.lock`. `cssselect` và `lxml` cần được khai báo trực tiếp trong `pyproject.toml` (hiện tại `cssselect` là transitive qua `scrapling`, `lxml` được dùng trực tiếp nhưng chưa pinned).

---

## Risks / Deferred

- **Risk:** `google-re2` build failed trên macOS ARM hoặc dev container. **Mitigation:** dùng `re` timeout 50ms làm fallback; document rõ.
- **Risk:** Wire dynamic selectors vào `batdongsan/parsers.py` có thể gây hồi quy nếu rule schema thiếu trường. **Mitigation:** merge rule với hardcoded default, feature flag tắt theo mặc định.
- **Risk:** Race condition khi activate version mới. **Mitigation:** unique partial index + transaction với `FOR UPDATE`.
- **Risk:** Worker `@worker_process_init` sync không thể await subscriber async. **Mitigation:** dùng TTL cache 5s làm primary, background thread làm secondary.
- **Risk:** Alembic duplicate heads khi tạo migration. **Mitigation:** chạy `alembic history`/`alembic upgrade head` trước khi commit; tạo merge revision nếu cần.
- **Risk:** `PlatformCircuitBreaker.record_success` hiện không xóa `OPEN` state, chỉ xóa failure counter. **Mitigation:** admin `reset` phải xóa cả `state_key` và `counter_key`; cân nhắc mở rộng `PlatformCircuitBreaker` thêm `trip()`/`reset()`.
- **Deferred:** Wire rule vào `chotot`, `muaban_bds`, `itviec`, `masothue` parsers — làm sau khi `batdongsan` end-to-end xanh.
- **Deferred:** Hỗ trợ XPath selectors — AC chỉ yêu cầu CSS.
- **Deferred:** Historical diff view UI — audit log có `diff_payload` JSON, UI đơn giản hiển thị raw JSON.
- **Deferred:** Auto-fallback khi error rate >20% — v1 ghi metric/alert; auto-rollback version có thể làm sau.
