---
baseline_commit: 757eb0575cf2c0a65c074faf4e07796758b3f1e3
---

# Story 10.5: Anti-Bot / CAPTCHA Screenshot Escalation

Status: done

## Story

As a scraper operator,
I want CAPTCHA or anti-bot blocks to be captured as a screenshot and surfaced in the Inbox for human review,
so that we can audit blocks and decide whether to rotate credentials, proxy, or rate-limit.

## Acceptance Criteria

1. **Given** a scraper fetcher detects a CAPTCHA/anti-bot challenge (HTTP 403/429 with challenge page, HTML containing "captcha", "robot check", or known anti-bot markers),
   **When** the capability executor handles the failure,
   **Then** the system captures a screenshot of the page, uploads it to durable storage, and creates an `AntiBotEscalation` record linking the run id, capability, domain, and screenshot URL. The screenshot capture and escalation creation must run asynchronously so the degraded `ScrapeOutput` can be returned immediately.

2. **Given** an `AntiBotEscalation` record exists,
   **When** an admin opens the admin Inbox,
   **Then** they see the item with metadata (domain, capability, timestamp, screenshot thumbnail, run id, block type, status) and can mark it resolved or trigger a retry.

3. **Given** a scraper hits an anti-bot escalation,
   **When** the capability returns to the user/agent,
   **Then** it returns `degraded=true` with a typed `degradation_reason` (e.g., `bot_detected`, `rate_limited`) and a clear `next_action` guidance (e.g., "Escalated to human review; retry after credentials/proxy rotation"), and does not crash or silently return empty.

4. **Given** the screenshot storage is unavailable,
   **When** the escalation occurs,
   **Then** the `AntiBotEscalation` record is still created without the screenshot, and a counter `anti_bot_screenshot_failure` is emitted.

5. **Given** repeated anti-bot detections on the same domain and capability within a 1-hour window,
   **When** an open escalation already exists for that (workspace_id, domain, capability) tuple,
   **Then** the system updates the existing escalation's `detection_count`, `last_seen_at`, and `screenshot_url` (if a new screenshot was captured) instead of creating duplicate items.

6. **Given** an `AntiBotEscalation` record with a screenshot,
   **When** 30 days pass or the admin marks it resolved,
   **Then** the screenshot object is deleted from durable storage and the record is marked resolved. Escalation metadata is retained for audit.

7. **Given** the admin Inbox exposes screenshot URLs,
   **When** the page renders,
   **Then** the URL is served from a restricted admin-only storage path and is not publicly indexable or searchable. Screenshot is an evidence artifact, not a search corpus (AD-35).

8. **Given** a workspace produces an anti-bot escalation,
   **When** the system records the escalation,
   **Then** only workspace members with Owner, Editor, or superuser role can view/resolve/retry the escalation; admin API endpoints enforce this RBAC.

9. **Given** screenshot capture may contain PII or session tokens from the blocked page,
   **When** the screenshot is stored,
   **Then** it is stored raw in an admin-restricted bucket and is not passed to any LLM/vision pipeline unless explicitly redacted. MVP does not require PII redaction, but the access restriction and retention policy must be documented.

10. **Given** a scraper capability returns `degraded=true` due to anti-bot,
    **When** the main agent consumes the response,
    **Then** the agent does not attempt to call the same blocked URL repeatedly in the same turn and treats `next_action` as guidance.

## Tasks / Subtasks

- [ ] Detect anti-bot/CAPTCHA in scraper runs (AC: #1, #3)
  - [ ] Extend `app/utils/crawl/classifier.py` `BlockType` classification to emit the matched marker; ensure all anti-bot `BlockType` values are surfaced on `CrawlOutcome`.
  - [ ] Update `app/proprietary/web_crawler/connector.py` `CrawlOutcome` to include a `screenshot_png: bytes | None` field, populated by the browser tier before the page is closed when an anti-bot block is detected.
  - [ ] Update `app/proprietary/web_crawler/connector.py` `crawl_url` to call the screenshot helper for anti-bot outcomes and return the bytes in `CrawlOutcome`.
  - [ ] Update platform scraper executors (`app/capabilities/batdongsan/scrape/executor.py`, `app/capabilities/chotot/scrape/executor.py`, `app/capabilities/muaban_bds/scrape/executor.py`, `app/capabilities/topcv/scrape/executor.py`, `app/capabilities/itviec/scrape/executor.py`) to map anti-bot `BlockType` to `degraded=true`, `degradation_reason="bot_detected"` (or `rate_limited` for 429), and `next_action` guidance.
  - [ ] Update each scraper's `ScrapeOutput` schema (e.g., `app/capabilities/batdongsan/scrape/schemas.py`) to add `next_action: str | None = None`.
  - [ ] Add telemetry counter `anti_bot_detection_total` with labels `capability`, `block_type`, `domain` (bounded) in `app/observability/metrics.py`.

- [ ] Capture and upload screenshot (AC: #1, #4, #6, #7)
  - [ ] Add `capture_screenshot(page: Page, run_id: str) -> bytes` helper in `app/proprietary/web_crawler/screenshot.py` (browser tier per `AD-20`); use `page.screenshot()` and return PNG bytes.
  - [ ] Add `app/services/anti_bot_escalation.py::upload_screenshot(bytes, workspace_id, run_id) -> str | None` that writes to durable storage using `app/file_storage/service.py::store_document_file` with the prefix `anti_bot_screenshots/{workspace_id}/{run_id}.png`. The existing storage backends are Local and Azure; add an S3/MinIO backend only if required by the deployment.
  - [ ] On storage failure, log warning, emit `anti_bot_screenshot_failure` counter, and proceed to create the `AntiBotEscalation` record without a screenshot URL (AC #4).
  - [ ] Implement screenshot retention: delete the stored object after 30 days or when the escalation is resolved (AC #6).

- [ ] Create `AntiBotEscalation` persistence (AC: #1, #2, #5, #8)
  - [ ] Add Alembic migration for `anti_bot_escalations` table with columns: `id` (int PK), `run_id` (UUID, index, FK to `Run.id`), `workspace_id` (int, FK, index), `capability` (text), `domain` (text), `block_type` (text), `screenshot_url` (text, nullable), `status` (enum: open/resolved/retry), `detection_count` (int, default 1), `last_seen_at` (timestamp), `metadata` (JSONB), `created_at`, `resolved_at`. Add a partial unique index on `(workspace_id, domain, capability)` where `status = 'open'` for grouping.
  - [ ] Add `AntiBotEscalation` model to `app/db.py` with the same columns and a `run` relationship to `Run`.
  - [ ] Add `app/services/anti_bot_escalation.py::create_or_update_escalation(session, run_id, workspace_id, capability, domain, block_type, screenshot_url, metadata)` that creates a new row or updates `detection_count` and `last_seen_at` if an open row exists for the same `(workspace_id, domain, capability)` (AC #5).
  - [ ] Create the escalation from an async Celery task (via `app/capabilities/core/async_runner.py`) so the scraper return path is not blocked (AD-17 / AD-19).

- [ ] Admin Inbox UI / routes (AC: #2, #6, #8)
  - [ ] Create `app/routes/admin_anti_bot_escalation_routes.py` with `GET /admin/anti-bot-escalations` (list, filter by workspace/domain/status), `GET /admin/anti-bot-escalations/{id}`, `POST /admin/anti-bot-escalations/{id}/resolve`, `POST /admin/anti-bot-escalations/{id}/retry`. All endpoints require admin/superuser or workspace Owner/Editor RBAC.
  - [ ] Add Pydantic schemas `AntiBotEscalationRead`, `AntiBotEscalationListResponse`, `AntiBotEscalationResolveRequest`.
  - [ ] Mount router in `app/routes/__init__.py` under admin routes.
  - [ ] Add `nowing_web/app/admin/anti-bot-escalations/` page listing items with thumbnail, domain, capability, timestamp, run id, block type, status, and actions (resolve/retry). Use the screenshot URL directly in an `<img>` tag and update CSP `img-src` to allow the storage domain.
  - [ ] Add audit logging for resolve/retry actions (who, when, escalation id).

- [ ] Retry flow (AC: #2)
  - [ ] On admin "retry", enqueue a Celery task to re-run the same `Run` input with a fresh proxy/credential via `app/capabilities/core/async_runner.py` or the existing capability run queue. The retry run should reference `parent_run_id` (add the column to `Run` if needed) to avoid duplicate billing.
  - [ ] Mark escalation `status=resolved` when admin clicks resolve and delete the screenshot if retention policy requires.

- [ ] Metrics & cost (AC: #1, #4)
  - [ ] Add `anti_bot_detection_total` and `anti_bot_screenshot_failure` counters to `app/observability/metrics.py`.
  - [ ] Track screenshot storage bytes per workspace; consult `app/services/token_tracking_service.py` or PM/Architect to add a billing unit if one does not already exist.

- [ ] Tests
  - [ ] Unit test `classify_block` returns correct `BlockType` for sample Cloudflare/captcha HTML.
  - [ ] Unit test `capture_screenshot` helper returns PNG bytes and handles page errors.
  - [ ] Unit test `create_or_update_escalation` groups open escalations by `(workspace_id, domain, capability)`.
  - [ ] Integration test anti-bot scraper run creates `AntiBotEscalation` row with screenshot URL.
  - [ ] Integration test storage-unavailable path still creates row and emits `anti_bot_screenshot_failure`.
  - [ ] Integration test admin list/resolve/retry endpoints enforce RBAC.
  - [ ] Integration test agent receives `degraded=true` with `next_action` when a scraper is blocked.

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-19` (`ARCHITECTURE-SPINE.md:473-551`) — anti-bot/CAPTCHA capability lives in Nowing; escalation must run **async/enrichment** through the existing async door (`AD-17`), not inline in deep research, to avoid blocking `NFR-9` State B.
  - `AD-20` (`ARCHITECTURE-SPINE.md:555-576`) — screenshot-as-evidence uses the existing browser tier (`patchright`/`playwright` `page.screenshot`); do **not** adopt a visual-RAG stack. Screenshot storage uses a dedicated `anti_bot_screenshots/{workspace_id}/{run_id}.png` namespace, separate from document storage.
  - `AD-16` (`ARCHITECTURE-SPINE.md` §license boundary) — bypass/detect/tuning logic stays in `app/proprietary/` (BSL 1.1); the escalation table, admin API, metrics, and `app/services/anti_bot_escalation.py` live in Apache-2.0 code outside `app/proprietary/`.
  - `AD-3` (`ARCHITECTURE-SPINE.md:193-197`) — scraper capabilities self-register routes; anti-bot escalation is not a new capability but a cross-cutting observability/escalation service.
  - `AD-34` / `AD-35` — screenshots are evidence artifacts, not searchable corpus; do not index them into `Memory` or `ResearchThread`.
  - `AD-25` — be aware screenshots may contain PII; store them admin-restricted and do not feed them to LLM/vision without explicit redaction.

- Source tree components to touch
  - `nowing_backend/alembic/versions/` — `anti_bot_escalations` migration
  - `nowing_backend/app/db.py` — `AntiBotEscalation` model (and `Run.parent_run_id` if needed)
  - `nowing_backend/app/utils/crawl/classifier.py` — `BlockType` classification
  - `nowing_backend/app/proprietary/web_crawler/connector.py` — `CrawlOutcome` and `crawl_url`
  - `nowing_backend/app/proprietary/web_crawler/screenshot.py` — new screenshot helper
  - `nowing_backend/app/services/anti_bot_escalation.py` — upload, create/update, retry service
  - `nowing_backend/app/file_storage/service.py` — `store_document_file` pattern
  - `nowing_backend/app/file_storage/backends/` — storage backend for screenshot bytes (Local/Azure/S3 as needed)
  - `nowing_backend/app/capabilities/batdongsan/scrape/executor.py`, `chotot/`, `muaban_bds/`, `topcv/`, `itviec/` — executor and `ScrapeOutput` schema updates
  - `nowing_backend/app/capabilities/core/runs.py` — `Run` recording
  - `nowing_backend/app/capabilities/core/async_runner.py` — async run door and retry task
  - `nowing_backend/app/routes/admin_anti_bot_escalation_routes.py` — admin routes
  - `nowing_backend/app/routes/__init__.py` — mount
  - `nowing_backend/app/observability/metrics.py` — `anti_bot_*` counters
  - `nowing_web/app/admin/anti-bot-escalations/` — admin page

- Testing standards summary
  - Unit tests in `tests/unit/utils/crawl/test_classifier.py`, `tests/unit/services/test_anti_bot_escalation.py`, and `tests/unit/proprietary/web_crawler/test_screenshot.py`
  - Integration tests in `tests/integration/routes/test_admin_anti_bot_escalation.py`
  - Integration tests in `tests/integration/capabilities/test_scraper_anti_bot.py`
  - Use mocked `page.screenshot` for unit tests; use the existing storage backend test bucket for integration tests
  - Assert `degraded=true` and `next_action` in `ScrapeOutput` for anti-bot markers

### Project Structure Notes

- Alignment with unified project structure
  - Anti-bot escalation is a service under `app/services/`, admin routes under `app/routes/admin_*_routes.py`, and admin UI under `nowing_web/app/admin/`.
  - Screenshot capture stays in the proprietary web crawler (`app/proprietary/web_crawler/screenshot.py`); the escalation record, admin API, storage service, and metrics are Apache-2.0.

- Detected conflicts or variances
  - `WebCrawlerConnector` currently does not expose a screenshot capture helper or `screenshot_png` on `CrawlOutcome`; this story adds both.
  - `ScrapeOutput` schemas vary per capability; add `next_action` consistently across all scraper executors touched by HR/BĐS verticals.
  - The admin Inbox is a dedicated `AntiBotEscalation` admin page, not the user notifications inbox.
  - Retry on admin action must not duplicate `Run` billing; re-run should use `parent_run_id` (add the column to `Run` if needed).
  - Existing storage backends are Local and Azure; the story uses the generic `store_document_file` API and only adds S3/MinIO if required by the deployment.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 10.5]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-3, AD-16, AD-17, AD-19, AD-20, AD-25, AD-34, AD-35]
- [Source: `_bmad-output/planning-artifacts/architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v8.md` §3.2 — `Story 10.5` is open P0 for AD-19]
- [Source: `nowing_backend/app/utils/crawl/classifier.py` §BlockType, classify_block]
- [Source: `nowing_backend/app/proprietary/web_crawler/connector.py` §CrawlOutcome, crawl_url]
- [Source: `nowing_backend/app/capabilities/batdongsan/scrape/executor.py` §build_scrape_executor]
- [Source: `nowing_backend/app/capabilities/batdongsan/scrape/schemas.py` §ScrapeOutput]

### Review Findings (Code Review 2026-08-09)

#### decision_needed

- [x] [Review][Patch] ~~Có cần capture screenshot cho platform scrapers không?~~ — Quyết định: thêm screenshot cho platform scrapers (batdongsan/chotot/muaban_bds/itviec/topcv). `nowing_backend/app/capabilities/batdongsan/scrape/executor.py:388`
- [x] [Review][Patch] ~~Làm thế nào để screenshot URL thực sự admin-only?~~ — Quyết định: dùng signed URL. `nowing_backend/app/services/anti_bot_escalation.py:35`
- [x] [Review][Patch] ~~Trạng thái `retry` nghĩa là gì trong state machine?~~ — Quyết định: khi retry run hoàn thành, tự động chuyển escalation về `open`. `nowing_backend/app/routes/admin_anti_bot_escalation_routes.py:175`
- [x] [Review][Defer] ~~Có thêm billing unit cho screenshot storage ngay không?~~ — Quyết định: defer sang epic cost tracking / PM-Architect. `nowing_backend/app/services/token_tracking_service.py`

#### patch

- [ ] [Review][Patch] Migration thiếu partial unique index và CHECK status — Cần unique index trên `(workspace_id, domain, capability) WHERE status='open'` và `CHECK (status IN ('open','resolved','retry'))`. Hiện tại chỉ có index thường trên 4 cột. `nowing_backend/alembic/versions/197_anti_bot_escalations.py:90-95`
- [ ] [Review][Patch] Race condition trong `create_or_update_escalation` — SELECT rồi INSERT, không `FOR UPDATE` hay unique constraint. Concurrent call có thể tạo duplicate. `nowing_backend/app/services/anti_bot_escalation.py:101-113`
- [ ] [Review][Patch] `_anti_bot_blocks` cache không thread-safe và không dọn dẹp — Dict global không lock, async concurrent có thể corrupt; TTL chỉ dọn khi access, gây leak. Cần `asyncio.Lock` và periodic cleanup/size limit. `nowing_backend/app/capabilities/core/access/agent.py:127`
- [ ] [Review][Patch] Screenshot qua Celery broker không validate size — Base64 PNG có thể vài MB, vượt broker message limit. Cần kiểm tra kích thước trước khi encode/gửi và khi decode. `nowing_backend/app/tasks/celery_tasks/anti_bot_escalation_tasks.py:74-76`
- [ ] [Review][Patch] Retention task xóa screenshot nhưng không đổi status resolved — AC #6 yêu cầu record đánh dấu resolved sau 30 ngày. Hiện tại chỉ set `screenshot_url=None`. `nowing_backend/app/tasks/celery_tasks/anti_bot_escalation_tasks.py:132`
- [ ] [Review][Patch] Frontend admin page chỉ cho superuser — AC #8 yêu cầu Owner/Editor/superuser. Page check `isSuperuser` và từ chối workspace owner/editor. `nowing_web/app/admin/anti-bot-escalations/page.tsx:36`
- [ ] [Review][Patch] Thiếu `Run.parent_run_id` cho retry billing — Spec yêu cầu retry run reference `parent_run_id` để tránh duplicate billing. Cần thêm column và truyền vào `start_async_run`. `nowing_backend/app/db.py:3306`, `nowing_backend/app/routes/admin_anti_bot_escalation_routes.py:187-195`
- [ ] [Review][Patch] Thiếu audit logging resolve/retry — Spec yêu cầu log who/when/escalation id. Hiện chỉ lưu `resolved_by` trong metadata. `nowing_backend/app/routes/admin_anti_bot_escalation_routes.py:152, 218-221`
- [ ] [Review][Patch] CSP `img-src` chưa cấu hình cho storage domain — Admin page hiển thị screenshot URL nhưng `next.config.ts`/middleware không cho phép storage domain trong `img-src`. `nowing_web/next.config.ts:45`
- [ ] [Review][Patch] Retention task load tất cả rows vào memory — Query không pagination, có thể OOM. Cần batch/limit. `nowing_backend/app/tasks/celery_tasks/anti_bot_escalation_tasks.py:108-114`
- [ ] [Review][Patch] Update screenshot mới không xóa file cũ — `create_or_update_escalation` ghi đè `screenshot_url` nhưng không `backend.delete(storage_key)` cũ, gây orphan storage. `nowing_backend/app/services/anti_bot_escalation.py:119-120`
- [ ] [Review][Patch] Key screenshot collision khi một run có nhiều blocked pages — `_screenshot_key` chỉ dùng `workspace_id/run_id`, nếu `web.crawl` gặp nhiều page anti-bot thì ghi đè. Cần thêm URL hash/sequence. `nowing_backend/app/services/anti_bot_escalation.py:31`
- [ ] [Review][Patch] Thiếu validate input length và domain extraction — `capability` max 100, `domain` max 500, `host_of` có thể empty; base64 decode có thể fail. Cần guard. `nowing_backend/app/services/anti_bot_escalation.py:83`, `nowing_backend/app/capabilities/web/crawl/executor.py:219`, `nowing_backend/app/proprietary/web_crawler/url_policy.py:162`
- [ ] [Review][Patch] Thiếu tests bắt buộc — Thiếu unit test `classify_block`, `capture_screenshot`, integration test storage-failure, agent degraded response. `tests/unit/utils/crawl/test_classifier.py`, `tests/unit/proprietary/web_crawler/test_screenshot.py`, `tests/integration/capabilities/test_scraper_anti_bot.py`
- [ ] [Review][Patch] `_maybe_escalate` guard không nhất quán giữa các executor — batdongsan chỉ check `run_id`, itviec/topcv check cả `ctx` và `run_id`. Cần standardize. `nowing_backend/app/capabilities/batdongsan/scrape/executor.py:53-62`
- [ ] [Review][Patch] Screenshot capture failure không phân biệt với "không cần screenshot" — `maybe_capture_screenshot` trả None trong cả hai trường hợp, không emit `anti_bot_screenshot_failure` khi exception. `nowing_backend/app/proprietary/web_crawler/screenshot.py`

#### defer

- [x] [Review][Defer] Billing tracking cho screenshot storage — Cần quyết định PM/Architect về billing unit; chưa có trong token_tracking_service. `nowing_backend/app/services/token_tracking_service.py` — deferred, cần epic cost tracking
- [x] [Review][Defer] Hardcoded TTL 30 giây và SHA256 cache key — Có thể chuyển vào config hoặc dùng hash đơn giản hơn, nhưng không gây lỗi chức năng. `nowing_backend/app/capabilities/core/access/agent.py:126` — deferred, optimization
- [x] [Review][Defer] Inconsistent `next_action` pattern giữa platform executors — batdongsan/chotot/muaban inline string, itviec/topcv dùng helper. Không ảnh hưởng runtime. `nowing_backend/app/capabilities/batdongsan/scrape/executor.py:377` — deferred, style cleanup
- [x] [Review][Defer] Missing rate limiting trên admin endpoints — Pre-existing pattern, không riêng story này. `nowing_backend/app/routes/admin_anti_bot_escalation_routes.py` — deferred, platform-wide
- [x] [Review][Defer] Workspace/Run cascade delete không xóa screenshot — Pre-existing; cần trigger/cleanup chung. `nowing_backend/alembic/versions/197_anti_bot_escalations.py:30` — deferred, storage lifecycle
- [x] [Review][Defer] `escalation_metadata` alias `metadata` gây confusion — Schema dùng alias, model dùng `escalation_metadata`. Hoạt động đúng nhưng khó đọc. `nowing_backend/app/schemas/anti_bot_escalation.py` — deferred, naming cleanup

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List