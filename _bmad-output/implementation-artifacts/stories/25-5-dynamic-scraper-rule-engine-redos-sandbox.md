---
story_key: 25-5-dynamic-scraper-rule-engine-redos-sandbox
status: ready-for-dev
baseline_commit: 0371c1147
epic: 25
story: 5
---

# Story 25.5: Dynamic Scraper Rule Engine & ReDoS Sandbox

**Status:** `ready-for-dev`

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
- `PATCH /api/v1/admin/scraper-rules/{platform}/{version_id}` — kích hoạt/lên version hoặc chỉnh `is_active`.
- `DELETE /api/v1/admin/scraper-rules/{platform}/{version_id}` — xóa một version (không được xóa version đang active nếu nó là version duy nhất).

Payload rule phải chứa JSONB `rule_schema` với các trường:

```json
{
  "selectors": {
    "listing_card": "div.js__card-listing",
    "title": "span.js__card-title",
    "price": "span.re__card-config-price",
    "area": "...",
    "next_page": "..."
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
    "trip_duration_seconds": 300
  }
}
```

> **Ponytail:** Trong v1 chỉ cần lưu và validate schema; việc **áp dụng** selectors động vào parser cụ thể (thay `parsers.py` hardcoded) là optional và được ghi trong AC-6. Đừng phá vỡ parser đang chạy.

### AC-2 — Validation trước khi lưu

**Given** một rule payload được gửi lên,  
**When** backend validate,  
**Then**:

- Mọi CSS selector string trong `selectors.*` được parse qua `cssselect.parse` kết hợp `lxml` (`SelectorSyntaxError` → 422 với detail `Invalid CSS selector: ...`).
- Mọi regex string trong rule (nếu có, ví dụ `next_page` pattern hoặc `title_regex`) được compile bằng `google-re2` (`re2.compile(pattern)`); nếu `google-re2` không cài thì dùng `re.compile` nhưng **bắt buộc benchmark ReDoS < 50ms**.
- `delays.request_ms`, `delays.retry_base_ms`, `retries.max_attempts`, `circuit_breaker.*` phải là số nguyên dương hoặc 0, nằm trong range hợp lý (`request_ms` 0–60000, `retry_base_ms` 0–60000, `max_attempts` 0–10, `error_threshold_pct` 0–100).
- Nếu validation fail, trả về `HTTP 422 Unprocessable Entity` với list lỗi cụ thể.

> **Ponytail:** `google-re2` chưa có trong `pyproject.toml` / `uv.lock`. Thêm `google-re2>=1.1.20251105` vào dependencies. Nếu build C++ extension gặp khó trên local/dev, dùng `re` với sandbox 50ms như fallback có warning log.

### AC-3 — ReDoS Sandbox Benchmark

**Given** một regex string được gửi,  
**When** backend chạy ReDoS benchmark,  
**Then**:

- Dùng `google-re2` nếu có, hoặc `signal`/`asyncio.wait_for` để giới hạn `re.search` trên input độ dài tăng dần (1 KB, 10 KB, 100 KB) trong **< 50 ms** mỗi lần chạy.
- Nếu một trong các lần chạy vượt 50 ms → `HTTP 422` với `code: REDOS_TIMEOUT`.
- Sandbox **không** chạy trong event loop chính (dùng `asyncio.to_thread()` hoặc `concurrent.futures.ThreadPoolExecutor`) để tránh block.
- Input test được random sinh từ charset có liên quan (lowercase ASCII, digits, separators) theo pattern dễ gây backtracking.

### AC-4 — Versioned JSONB Storage + Audit

**Given** một rule hợp lệ,  
**When** lưu thành công,  
**Then**:

- Tạo bảng `scraper_rules` (alembic migration) với các cột:
  - `id` (PK), `platform` (String, indexed), `version` (Integer, default tăng theo platform), `rule_schema` (JSONB, NOT NULL), `is_active` (Boolean, default false), `is_default` (Boolean, default false), `created_by_admin_id` (UUID, FK user), `created_at`, `updated_at`.
  - Unique constraint `(platform, version)`.
  - Partial unique index để chỉ cho **một** `is_active = true` trên mỗi platform (hoặc dùng application-level lock + trigger).
- Mỗi create/update rule đều ghi `AuditEvent` với `action='scraper_rule.create'` / `'scraper_rule.update'`, `actor_id=<admin_uuid>`, `diff_payload={platform, version, rule_schema}` (INV-25.2).

### AC-5 — Redis Pub/Sub Live Invalidation

**Given** một rule active được update hoặc activate version mới,  
**When** transaction commit,  
**Then**:

- Backend publish một message lên Redis Pub/Sub channel `scraper_config_updated` với payload JSON `{"platform": "batdongsan", "version": 7, "is_active": true, "updated_at": "..."}`.
- Mỗi Celery worker process (hoặc API process) subscribe channel này hoặc poll theo TTL cache < 1s; khi nhận được message, invalidate in-memory cache và reload rule từ DB.
- Cung cấp endpoint `GET /api/v1/admin/scraper-rules/{platform}/refresh` để force refresh (dùng Redis `PUBLISH`) và kiểm tra worker cache.

> **Ponytail:** Có thể dùng Redis Pub/Sub trong `app/redis_client.py:get_redis_client()` hoặc `celery_app` broadcast. V1 ưu tiên **Pub/Sub + in-process cache**; Celery worker subscribe trong `@worker_process_init` hoặc tại nơi cần config. Đừng restart worker.

### AC-6 — Wire rule vào scraper worker (optional v1, prefer behind feature flag)

**Given** một platform scraper task chạy (ví dụ `batdongsan.scrape`),  
**When** nó cần selectors/delays,  
**Then**:

- Ưu tiên `rule_schema` từ active `ScraperRule` nếu `is_active=true` và `USE_DYNAMIC_SCRAPER_RULES=true`.
- Nếu không có rule active hoặc feature flag tắt, fallback về hardcoded config hiện tại (đảm bảo không hồi quy).
- Tích hợp ít nhất một platform trong v1 (khuyến nghị `batdongsan` vì parser đã dùng BeautifulSoup + CSS selectors) để chứng minh end-to-end.

### AC-7 — Emergency Circuit Breaker

**Given** admin bật `Emergency Circuit Breaker: Trip` trên một platform,  
**When** backend nhận toggle,  
**Then**:

- Set `circuit_breaker.tripped = true` trong active rule hoặc tạo row `scraper_circuit_breakers(platform, tripped_at, tripped_by)`.
- Ngay lập tức publish `scraper_config_updated` với `circuit_breaker.tripped=true`.
- Celery worker gặp `tripped=true` thì skip enqueue/execution các task scraper của platform đó và trả `degraded` với `reason: circuit_breaker_tripped`.
- Admin có thể `Reset` circuit breaker từ UI; reset cũng publish event.

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
  - [ ] Tạo migration `add_scraper_rules_table.py` với bảng `scraper_rules` và `scraper_circuit_breakers` (nếu tách riêng).
  - [ ] Thêm indexes: `ix_scraper_rules_platform_version` (unique), `ix_scraper_rules_platform_active` (partial unique `is_active = true`).
  - [ ] Đảm bảo `rule_schema` là JSONB NOT NULL.

- [ ] **Task 2: ReDoS & CSS Selector Validation Service**
  - [ ] Tạo `app/services/scraper_rule_validator.py`:
    - `validate_css_selectors(selectors: dict[str, str])` dùng `cssselect.parse` + `lxml.etree` dummy document (hoặc `lxml.html.fromstring("<html></html>")`).
    - `validate_regexes(patterns: list[str])` dùng `google-re2` nếu có, hoặc `re` với `asyncio.to_thread()` + `asyncio.wait_for(timeout=0.05)`.
    - `benchmark_redos(pattern, test_inputs)` trả về max ms hoặc raise `ReDoSTimeoutError`.
  - [ ] Thêm `google-re2>=1.1.20251105` vào `pyproject.toml` và chạy `uv lock`.

- [ ] **Task 3: Scraper Rule CRUD Service**
  - [ ] Tạo `app/services/scraper_rules_service.py`:
    - `get_rules(session, limit, offset)`.
    - `get_active_rule(session, platform)`.
    - `create_rule(session, platform, rule_schema, auth)` — tạo version mới, set active nếu là version đầu tiên.
    - `activate_rule(session, platform, version_id, auth)` — deactivate cũ, activate mới, publish Redis event.
    - `delete_rule(session, platform, version_id)` — không cho xóa version active duy nhất.
    - `toggle_circuit_breaker(session, platform, trip: bool, auth)`.
    - Ghi `AuditEvent` mỗi lần mutate.
  - [ ] Maintain in-memory cache với TTL ngắn hoặc Redis Pub/Sub invalidation.

- [ ] **Task 4: Redis Pub/Sub Listener**
  - [ ] Tạo `app/services/scraper_rule_pubsub.py`:
    - `publish_rule_update(redis, platform, version, is_active, circuit_breaker_tripped)`.
    - `start_rule_subscriber(redis, callback)` — async task subscribe `scraper_config_updated`.
    - `invalidate_rule_cache(platform)`.
  - [ ] Tích hợp vào `app/celery_app.py` worker bootstrap (`@worker_process_init`) hoặc `app/main.py` startup nếu API cần cache.

- [ ] **Task 5: Backend Admin Routes**
  - [ ] Tạo `app/routes/admin_scraper_rules_routes.py` với prefix `/api/v1/admin/scraper-rules`.
  - [ ] Tất cả endpoints dùng `_auth: AuthContext = Depends(require_superuser)`.
  - [ ] Tạo Pydantic schemas trong `app/schemas/admin_scraper_rules.py` (`Create`, `Update`, `Read`, `ListResponse`).
  - [ ] Wire router vào `app/routes/__init__.py`.

- [ ] **Task 6: Frontend Admin Page**
  - [ ] Tạo `nowing_web/app/admin/scrapers/rules/page.tsx`.
  - [ ] Thêm nav link trong `nowing_web/app/admin/admin-shell.tsx`.
  - [ ] Tạo `nowing_web/lib/apis/admin-scraper-rules-api.service.ts`.
  - [ ] Tạo các components: rule list, rule editor (JSON/form), circuit breaker toggle, validation error display.
  - [ ] Gate superuser theo pattern `scraper-accounts/page.tsx`.

- [ ] **Task 7: Wiring to Scraper Worker (optional v1, behind `USE_DYNAMIC_SCRAPER_RULES` flag)**
  - [ ] Chọn một platform (`batdongsan`) để đọc `rule_schema.selectors` từ `ScraperRulesService` trong `fetch.py` / `parsers.py`.
  - [ ] Fallback về hardcoded selectors khi rule thiếu hoặc flag tắt.
  - [ ] Cập nhật `circuit_breaker` check trong `app/tasks/lead_scrapers.py` hoặc platform executor.

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
- **AuditEvent:**
  - `nowing_backend/app/db.py:6273-6294` — model `AuditEvent` (`action`, `actor_id`, `diff_payload` JSONB).
  - `nowing_backend/app/routes/admin_telemetry_routes.py` — cách ghi audit cho DLQ purge.
- **Platform parser selectors (hardcoded today):**
  - `nowing_backend/app/proprietary/platforms/batdongsan/parsers.py:234-260` — `soup.select("div.js__card-listing")`, `select_one("a.js__product-link-for-product-id")`, `select_one("span.js__card-title")`, `select_one("span.re__card-config-price")`.
  - `nowing_backend/app/proprietary/platforms/chotot/fetch.py:62-` — `_CATEGORY_CONFIG` dict config, nhưng không dùng CSS selectors.
- **Admin UI patterns:**
  - `nowing_web/app/admin/scraper-accounts/page.tsx` — tabs, tables, modals, toggles.
  - `nowing_web/lib/apis/scraper-platform-accounts-api.service.ts` — API service pattern với Zod.
  - `nowing_web/app/admin/admin-shell.tsx` — thêm nav link.
- **JSONB config versioning pattern:**
  - `nowing_backend/app/db.py:1002-1029` — `ScraperPlatformAccount.usage_state` JSONB.
  - `nowing_backend/app/db.py` các bảng `SearchSourceConnector`, `Workspace` có `config` JSONB — tham khảo cách lưu/merge.

### Key Decisions

1. **Versioned rule storage:** Mỗi platform có nhiều version nhưng chỉ một active. Tạo version mới khi admin save; activate/deactivate không xóa history. Đảm bảo audit và rollback.
2. **ReDoS engine:** Ưu tiên `google-re2` vì linear-time guarantee. Nếu build phức tạp, dùng Python `re` trong thread với 50 ms timeout; `google-re2` vẫn được recommend cho production.
3. **CSS selector validation:** Dùng `cssselect.parse` kết hợp với `lxml.html.fromstring("<html></html>")` và `cssselect.HTMLTranslator()` để xác nhận selector hợp lệ. Không cần match real DOM.
4. **Cache invalidation:** Dùng Redis Pub/Sub `scraper_config_updated` thay vì database polling. Worker/API cache invalidate ngay khi nhận message. Cache TTL backup 5s nếu Pub/Sub fail.
5. **Circuit breaker:** Lưu trong `rule_schema` hoặc bảng riêng. Khi tripped, worker trả `degraded` thay vì crash. Kết hợp với `anti_bot_escalations` pattern nếu cần.
6. **Feature flag:** `USE_DYNAMIC_SCRAPER_RULES` (default `false` hoặc `true` tùy PO) để giảm rủi ro hồi quy khi wire vào parser.

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
  app/services/scraper_rule_validator.py
  app/services/scraper_rules_service.py
  app/services/scraper_rule_pubsub.py
  app/routes/admin_scraper_rules_routes.py
  app/schemas/admin_scraper_rules.py
  app/routes/__init__.py  (add include_router)

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
- `rule_schema` JSONB nên tương thích với cả `selectors` CSS, `delays`, `retries`, `circuit_breaker`. Để lại room cho extension (`headers`, `user_agent`, `cookies`).
- Dùng `shadcn/ui` components có sẵn: `table`, `card`, `dialog`, `button`, `badge`, `switch`, `select`, `input`, `textarea`, `tabs`, `sonner` toast.

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
- Admin UI patterns: `nowing_web/app/admin/scraper-accounts/page.tsx`, `admin-shell.tsx`, `lib/apis/scraper-platform-accounts-api.service.ts`.
- `google-re2` PyPI docs: <https://pypi.org/project/google-re2/> (latest `1.1.20251105`).
- `cssselect` docs: <https://cssselect.readthedocs.io/>.

---

## Lệnh xác minh (Verification Commands)

```bash
# Backend lint & typecheck (targeted)
cd nowing_backend
uv run ruff check app/services/scraper_rule_validator.py app/services/scraper_rules_service.py app/services/scraper_rule_pubsub.py app/routes/admin_scraper_rules_routes.py app/schemas/admin_scraper_rules.py tests/unit/services/test_scraper_rule_validator.py tests/integration/routes/test_admin_scraper_rules.py
uv run ruff format app/services/scraper_rule_validator.py app/services/scraper_rules_service.py app/services/scraper_rule_pubsub.py app/routes/admin_scraper_rules_routes.py app/schemas/admin_scraper_rules.py tests/unit/services/test_scraper_rule_validator.py tests/integration/routes/test_admin_scraper_rules.py
uv run pytest tests/unit/services/test_scraper_rule_validator.py tests/integration/routes/test_admin_scraper_rules.py -q

# Frontend typecheck & biome
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/admin/scrapers/rules/page.tsx lib/apis/admin-scraper-rules-api.service.ts components/admin/scraper-rules/RuleList.tsx components/admin/scraper-rules/RuleEditor.tsx components/admin/scraper-rules/CircuitBreakerToggle.tsx components/admin/scraper-rules/ValidationErrors.tsx

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

Top-level keys: `selectors` (dict[str, str]), `delays` (`request_ms`, `retry_base_ms`), `retries` (`max_attempts`, `statuses`), `circuit_breaker` (`error_threshold_pct`, `min_calls`, `trip_duration_seconds`, `tripped`). Pydantic schema validate cấu trúc.

### Q7 — Where does the admin UI live?

`nowing_web/app/admin/scrapers/rules/page.tsx`, nav link trong `nowing_web/app/admin/admin-shell.tsx`. Theo pattern `/admin/scraper-accounts`.

### Q8 — How to test ReDoS sandbox?

Unit test với pattern `(a+)+$` trên input `"a" * 30 + "!"`; Python `re` sẽ timeout >50ms, `google-re2` sẽ trả `False` nhanh. Cả hai đều phải raise 422.

### Q9 — What about TopCV / ItViec?

Story AC ghi "Batdongsan, Chotot, TopCV, Muaban". `topcv` chưa có code trong `app/proprietary/platforms/` (chỉ có `itviec`). V1 tập trung wire `batdongsan` và tạo CRUD cho tất cả platform slug; wire parser cho các platform khác có thể deferred hoặc dùng feature flag.

### Q10 — What dependencies need to be added?

`google-re2>=1.1.20251105` vào `pyproject.toml` / `uv.lock`. `cssselect` và `lxml` đã có.

---

## Risks / Deferred

- **Risk:** `google-re2` build failed trên macOS ARM hoặc dev container. **Mitigation:** dùng `re` timeout 50ms làm fallback; document rõ.
- **Risk:** Wire dynamic selectors vào `batdongsan/parsers.py` có thể gây hồi quy nếu rule schema thiếu trường. **Mitigation:** merge rule với hardcoded default, feature flag tắt theo mặc định.
- **Risk:** Race condition khi activate version mới. **Mitigation:** unique partial index + transaction với `FOR UPDATE`.
- **Deferred:** Wire rule vào `chotot`, `muaban_bds`, `itviec`, `masothue` parsers — làm sau khi `batdongsan` end-to-end xanh.
- **Deferred:** Hỗ trợ XPath selectors — AC chỉ yêu cầu CSS.
- **Deferred:** Historical diff view UI — audit log có `diff_payload` JSON, UI đơn giản hiển thị raw JSON.
