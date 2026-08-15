---
story_key: 21-1-intent-signal-detection
status: done
baseline_commit: db50806a
epic: 21
story: 1
---

# Story 21.1: Phát hiện tín hiệu mua hàng (Intent Signal Detection)

## Story

Với tư cách là nhân viên sales,
Tôi muốn phát hiện các tín hiệu mua hàng từ công ty (funding, tuyển dụng, thay đổi tech stack, thay đổi nhân sự cấp cao, tin tức),
Để tôi liên hệ đúng thời điểm.

## Acceptance Criteria

### AC-1 — Phát hiện 5 loại tín hiệu
**Given** một công ty trong workspace đang được theo dõi,
**When** signal capability chạy,
**Then** hệ thống phát hiện và trả về: `signal_type`, `confidence` (0-100), `source_url`, `chunk_id` (UUID pointer đến chainlens-research), `detected_at`.

### AC-2 — Tổng hợp tín hiệu cơ bản
**Given** nhiều tín hiệu cho cùng một công ty,
**When** truy vấn danh sách,
**Then** hiển thị số lượng, loại, recency, và source URLs.

> **Phạm vi:** 21.1 chỉ đếm/lọc tín hiệu. Composite lead score (fit + intent) thuộc **Story 21.2** — KHÔNG xây trong 21.1 để tránh trùng lặp.

### AC-3 — Lưu trữ an toàn
**Given** một tín hiệu được phát hiện,
**When** lưu trữ,
**Then** ghi `SignalEvent` row (`workspace_id`, `client_id`, `company_name`, `signal_type`, `source_url`, `chunk_id`, `confidence`, `detected_at`, `processed`) và một `Memory` row `type=semantic`, `tags=['lead_signal']` chứa redacted summary.
**And** `Memory.source_uuid` = `SignalEvent.id`, `Memory.source_entity_type` = `"SignalEvent"`, `Memory.source_input` = capability/input recipe.
**And** không duplicate full public document vào Nowing.

### AC-4 — Trigger qua AlertRule
**Given** một workspace cấu hình theo dõi funding/hiring/...,
**When** có tín hiệu mới,
**Then** `AlertRule` với `capability_id` thuộc tập `funding.signal | hiring.signal | tech_stack.signal | executive_move.signal | news.signal`, `diff_strategy="new_items"` tự động kích hoạt.
**And** gửi notification qua channels `in_app`, `telegram`, `email`.
**And** nếu `target_sequence_id` được set, emit `EnrollmentRequested` action tới Sequencer (Story 21.4).

### AC-5 — Đăng ký capability với metadata
**Given** một signal source,
**When** đăng ký,
**Then** nó phải là capability với metadata `{"emits_signals": true, "signal_types": ["<type>"]}`, đặt `billing_unit=None` vì signal scan ghi `BillingEvent` (AD-42), không phải `TokenUsage`.

### AC-6 — Metering
**Given** một signal scan chạy,
**When** hoàn thành,
**Then** ghi `BillingEvent` với `event_entity_type="signal_event"`, `event_type="signal_scan"`, `event_id=SignalEvent.id`.
**And** nếu dùng LLM (phân tích nội dung), ghi `TokenUsage` với `usage_type="llm_reasoning"` hoặc tương đương.

### AC-7 — PII / Consent
**Given** tín hiệu có thể chứa thông tin liên hệ,
**When** ghi `Memory`,
**Then** gọi `redact_pii(text, context="lead_enrichment")` trước khi lưu.
**And** 21.1 KHÔNG tạo `Lead` hay `VerifiedContact` — đó là `lead_extractor` capability (Story 21.4).

## Tasks / Subtasks

### Task 1: Models & Migration
- [ ] 1.1 Thêm `SignalEvent` vào `nowing_backend/app/db.py` (UUID PK, kế thừa `Base + TimestampMixin`):
  - `id` (UUID, PK, default uuid4)
  - `workspace_id` (Integer, FK workspaces, index)
  - `client_id` (CITEXT, nullable, index)
  - `company_name` (String(200), index)
  - `signal_type` (String(50), index)
  - `source_url` (Text, nullable)
  - `chunk_id` (UUID, nullable, index) — pointer tới chainlens-research
  - `confidence` (Float, nullable=False, default=0.0)
  - `detected_at` (TIMESTAMP, nullable=False, index)
  - `processed` (Boolean, default=False, index)
  - Composite index `(workspace_id, client_id, company_name, signal_type, detected_at)`
  - Unique `(workspace_id, client_id, company_name, signal_type, source_url, detected_at)` ngăn duplicate
- [ ] 1.2 Thêm `SignalSubscription` vào `app/db.py` (workspace-level default cho theo dõi tín hiệu):
  - `id` (UUID, PK)
  - `workspace_id` (Integer, FK, unique)
  - `client_id` (CITEXT, nullable)
  - `signal_types` (JSONB, default list)
  - `notification_channels` (JSONB, default list)
  - `created_by_user_id` (UUID, nullable)
- [ ] 1.3 Thêm `BillingEvent` vào `app/db.py` nếu chưa tồn tại:
  - `id` (UUID, PK)
  - `workspace_id` (Integer, FK, index)
  - `client_id` (CITEXT, nullable, index)
  - `user_id` (UUID, nullable, index)
  - `event_entity_type` (String(50), index)
  - `event_type` (String(50), index)
  - `event_id` (UUID, index)
  - `cost_micros` (BigInteger)
  - `currency` (String(3), default="USD")
  - `cost_basis` (String(20), default="estimated")
  - Partial unique index `(event_id) WHERE event_entity_type='outcome_event'` (AD-42)
- [ ] 1.4 Alembic migration `194_add_signal_tables.py` (hoặc next available): tạo 3 bảng trên, mở rộng `MemorySourceType` nếu cần (đã có `SIGNAL` trong code hiện tại).
- [ ] 1.5 Thêm `signal_detected` vào `NotificationType` (`app/notifications/types.py`) và `CATEGORY_TYPES["status"]` (`app/notifications/constants.py`).

### Task 2: Signal Detection Service
- [ ] 2.1 Tạo `app/lead_intelligence/signals/__init__.py` và `service.py`:
  - `SignalDetectionService.detect(session, ctx, company_name, signal_type, **kwargs) -> SignalOutput`
  - Chịu trách nhiệm gọi external source, parse kết quả, tạo `SignalEvent`, ghi `Memory` redacted, ghi `BillingEvent`, debit wallet nếu `SIGNAL_SCAN_MICROS_PER_SIGNAL > 0`.
  - Retry: max 3 lần exponential backoff cho external API; circuit breaker khi rate limit.
  - Xử lý lỗi: trả về `SignalOutput(degraded=True, degradation_reasons=[...], items=[])`.
- [ ] 2.2 Tạo `app/lead_intelligence/signals/schemas.py`:
  - `SignalInput` (company_name, domain, lookback_days=30, confidence_threshold=0.0)
  - `SignalOutput` (items: list[SignalEventRead], cost_micros: int, degraded: bool, degradation_reasons: list[str] | None)
  - `SignalEventRead` (id, workspace_id, client_id, company_name, signal_type, source_url, chunk_id, confidence, detected_at, processed)
- [ ] 2.3 Tạo `app/services/billing_event_service.py` (hoặc `app/lead_intelligence/services/billing_event_service.py`):
  - `record_signal_scan(session, signal_event_id, workspace_id, client_id, user_id, cost_micros)`
  - Gọi `wallet_credit.check_balance` + `wallet_credit.apply_debit` cho owner.
  - Viết `BillingEvent` row.

### Task 3: Capability Packages
- [ ] 3.1 Tạo 5 capability package theo mẫu `app/capabilities/<platform>/<verb>/`:
  - `app/capabilities/funding/signal/definition.py` → `funding.signal`
  - `app/capabilities/hiring/signal/definition.py` → `hiring.signal`
  - `app/capabilities/tech_stack/signal/definition.py` → `tech_stack.signal`
  - `app/capabilities/executive_move/signal/definition.py` → `executive_move.signal`
  - `app/capabilities/news/signal/definition.py` → `news.signal`
- [ ] 3.2 Mỗi package có `definition.py`, `executor.py`, `schemas.py`, `__init__.py`:
  - `definition.py` đăng ký capability với `input_schema=SignalInput`, `output_schema=SignalOutput`, `executor=build_signal_executor(signal_type)`, `billing_unit=None`, `metadata={"emits_signals": true, "signal_types": ["<type>"]}`.
  - `executor.py` nhận payload, gọi `SignalDetectionService.detect(...)`.
- [ ] 3.3 Thêm import 5 packages vào `app/capabilities/__init__.py`.

### Task 4: AlertRule Integration
- [ ] 4.1 Tạo `app/alerts/engine/strategies/signal_new_items.py` hoặc reuse `app/alerts/engine/diff.py` `new_items` — không cần diff mới.
- [ ] 4.2 Đảm bảo `execute_alert_rule` nhận diện được 5 signal capabilities (đã register).
- [ ] 4.3 Cập nhật `app/alerts/engine/notify.py` để xử lý `notification_channels` chứa `signal_detected` / `alert_run_complete` với thông tin signal.
- [ ] 4.4 Stub Sequencer: nếu `AlertRule.target_sequence_id` set, gọi `SequencerService.request_enrollment(alert_rule, new_item_ids)` (full implementation thuộc Story 21.4; 21.1 chỉ emit action).

### Task 5: Signal Sources (MVP)
- [ ] 5.1 **Funding**: gọi Crunchbase API v4 hoặc TechCrunch RSS feed. Cần config `CRUNCHBASE_API_KEY` (optional). Nếu thiếu key, trả `degraded=true`.
- [ ] 5.2 **Hiring**: consume `vn_jobs.aggregate` capability Chunk[] hoặc các job scraper (`vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape`) — không scrape trực tiếp.
- [ ] 5.3 **Tech stack**: website change detection — fetch homepage, extract tech keywords (Wappalyzer-lite hoặc static detection). Dùng hash HTML so sánh.
- [ ] 5.4 **Executive move**: LinkedIn / company about page scrape — **deferred nếu ToS chưa sign-off**. Trong MVP trả degraded `{"degraded": true, "degradation_reasons": ["executive_move deferred pending ToS review"]}`.
- [ ] 5.5 **News**: NewsAPI hoặc RSS feeds. Cần `NEWSAPI_KEY` (optional).

### Task 6: REST API
- [ ] 6.1 Tạo `app/routes/signals_routes.py`:
  - `GET /workspaces/{id}/signals` — list với pagination (`limit/offset`), filter (`signal_type`, `company_name`, `from_date`, `to_date`, `confidence_min`), sort (`detected_at DESC`).
  - `POST /workspaces/{id}/signals/detect` — trigger manual detection (tạo AlertRule one-off hoặc gọi capability trực tiếp).
  - `GET /workspaces/{id}/signals/subscriptions` — get `SignalSubscription`.
  - `PUT /workspaces/{id}/signals/subscriptions` — update `SignalSubscription` và đồng bộ `AlertRule` mặc định cho từng signal type.
- [ ] 6.2 RBAC: workspace owner/member; RLS via `workspace_id` + `client_id`.

### Task 7: MCP Tools
- [ ] 7.1 Tạo `nowing_mcp/mcp_server/features/signals/__init__.py` và `tools.py`:
  - `nowing_list_signals`
  - `nowing_subscribe_signals`
  - `nowing_detect_signals`
- [ ] 7.2 Import `signals` và gọi `signals.register(mcp, client, context)` trong `nowing_mcp/mcp_server/server.py`.
- [ ] 7.3 Thêm tool names vào `nowing_backend/app/mcp_tools.py` `MCP_TOOL_CATALOG` với group `LEAD_INTELLIGENCE`.
- [ ] 7.4 Cập nhật `nowing_mcp/mcp_server/selfcheck.py` `EXPECTED_TOOLS`.

### Task 8: Configuration
- [ ] 8.1 Thêm config keys vào `app/config/__init__.py`:
  - `SIGNAL_SCAN_MICROS_PER_SIGNAL` (default 0 — tắt billing)
  - `CRUNCHBASE_API_KEY` (default "")
  - `NEWSAPI_KEY` (default "")
  - `SIGNAL_EXECUTIVE_MOVE_ENABLED` (default False)
- [ ] 8.2 Thêm `.env.example` entries.

### Task 9: Tests
- [ ] 9.1 Unit tests `tests/unit/lead_intelligence/test_signal_detection.py` — mock external API, test `SignalDetectionService`, `BillingEventService`.
- [ ] 9.2 Unit tests `tests/unit/capabilities/test_signal_capabilities.py` — test 5 capability executors.
- [ ] 9.3 Integration tests `tests/integration/alerts/test_signal_alert_rules.py` — tạo AlertRule với `funding.signal`, chạy `execute_alert_rule`, assert `new_items_count`, notification.
- [ ] 9.4 Schema/migration tests.
- [ ] 9.5 Target coverage 90%.

## Dev Notes

### Architecture Patterns & Constraints

- **AD-31:** Mọi bảng Epic 21 có `client_id: CITEXT` nullable + index.
- **AD-33 / Story 6.8:** Alert Engine là first-class table, dùng Celery Beat (`app/celery_app.py` beat schedule `alert_engine_tick` mỗi phút). KHÔNG dùng APScheduler.
- **AD-37:** Signal detection là AlertRule template type, không phải Celery task/service mới. Logic nằm trong capability executor.
- **AD-35 / AD-27:** Nowing không giữ full public document. `SignalEvent` chỉ lưu pointer `chunk_id`/`source_url`; `Memory` lưu redacted summary.
- **AD-25 / AD-49:** Gọi `redact_pii(..., context="lead_enrichment")` trước khi ghi `Memory`. `VerifiedContact` là PII vault, thuộc 21.3.
- **AD-42:** `BillingEvent` là canonical ledger cho non-LLM business event. `TokenUsage` chỉ cho LLM. Không thêm `BillingUnit` mới cho signal.
- **AD-43:** `sequence_enrollment` không phải notification channel. Alert rule với `target_sequence_id` emit `EnrollmentRequested`.
- **AD-44 / AD-47:** `Capability.metadata` hỗ trợ `emits_signals`, `signal_types`.
- **AD-18:** Signal data được ghi vào `Memory` workspace-scoped (không lưu raw public corpus).

### Source Tree Components to Touch

```
nowing_backend/
├── app/
│   ├── db.py                        # UPDATE: add SignalEvent, SignalSubscription, BillingEvent
│   ├── config/__init__.py           # UPDATE: signal config keys
│   ├── lead_intelligence/
│   │   ├── __init__.py
│   │   ├── signals/
│   │   │   ├── __init__.py
│   │   │   ├── service.py           # SignalDetectionService
│   │   │   ├── schemas.py
│   │   │   └── detectors/           # per-source detector logic
│   │   │       ├── funding.py
│   │   │       ├── hiring.py
│   │   │       ├── tech_stack.py
│   │   │       ├── executive_move.py
│   │   │       └── news.py
│   │   └── services/
│   │       └── billing_event_service.py
│   ├── capabilities/
│   │   ├── __init__.py              # UPDATE: import 5 signal packages
│   │   ├── funding/signal/          # funding.signal capability
│   │   ├── hiring/signal/           # hiring.signal capability
│   │   ├── tech_stack/signal/       # tech_stack.signal capability
│   │   ├── executive_move/signal/   # executive_move.signal capability
│   │   └── news/signal/             # news.signal capability
│   ├── routes/
│   │   └── signals_routes.py        # NEW
│   ├── notifications/
│   │   ├── types.py                 # UPDATE: add signal_detected
│   │   └── constants.py             # UPDATE: add signal_detected to status category
│   └── mcp_tools.py                 # UPDATE: add signal tools to MCP_TOOL_CATALOG
├── alembic/versions/
│   └── 194_add_signal_tables.py     # NEW
├── tests/
│   ├── unit/lead_intelligence/test_signal_detection.py
│   ├── unit/capabilities/test_signal_capabilities.py
│   └── integration/alerts/test_signal_alert_rules.py
└── nowing_mcp/
    └── mcp_server/
        ├── server.py                # UPDATE: import + register signals
        ├── features/signals/        # NEW
        │   ├── __init__.py
        │   └── tools.py
        └── selfcheck.py             # UPDATE: EXPECTED_TOOLS
```

### Key Dependencies

| Dependency | Purpose | Note |
|---|---|---|
| Celery Beat (existing) | Scheduler cho AlertRule | `app/celery_app.py` + `app/alerts/engine/tick.py` |
| `app/alerts/engine/execute.py` | Execute alert rule + diff | Capability output phải có `.items` list, mỗi item có `id` hoặc `source_id` |
| `app/alerts/engine/diff.py` | `new_items` diff | Compare `source_ids` giữa snapshots |
| `app/capabilities/core` | Capability registry + context | Hỗ trợ `metadata` |
| `app/services/wallet_credit.py` | Debit wallet | `check_balance`, `apply_debit` |
| `app/services/pii/redact.py` | Redact trước khi ghi Memory | context `lead_enrichment` |
| Crunchbase API v4 | Funding signals | Optional, cần `CRUNCHBASE_API_KEY` |
| NewsAPI / RSS | News signals | Optional, cần `NEWSAPI_KEY` |
| `vn_jobs.aggregate` / job scrapers | Hiring signals | Consume Chunk[] |

### Signal Types & Detection Methods

| Signal Type | Capability ID | Nguồn | Phương pháp | Tần suất |
|---|---|---|---|---|
| funding | `funding.signal` | Crunchbase, TechCrunch | API / RSS | Daily |
| hiring | `hiring.signal` | `vn_jobs.aggregate`, các job scraper | Consume Chunk[] | Daily |
| tech_stack | `tech_stack.signal` | Company website | HTML hash + tech keyword | Daily |
| executive_move | `executive_move.signal` | LinkedIn, company page | Scraper (deferred nếu ToS) | Daily |
| news | `news.signal` | NewsAPI, RSS | API + RSS | Daily |

### Retry & Error Handling

- External API: max 3 retries, exponential backoff (1s, 2s, 4s).
- Rate limit (HTTP 429): circuit breaker trong window 60s, trả `degraded=true`.
- Wallet insufficient: kiểm tra trước khi gọi external API; nếu thiếu, trả `degraded=true`, `degradation_reasons=["insufficient_wallet"]`.
- Missing API key: `degraded=true`, `degradation_reasons=["crunchbase_api_key_missing"]`.

### Pagination / Filter / Sort

`GET /workspaces/{id}/signals` query params:
- `limit` (int, default 20, max 100)
- `offset` (int, default 0)
- `signal_type` (string)
- `company_name` (string, ILIKE)
- `from_date` / `to_date` (ISO 8601)
- `confidence_min` (float, 0-100)
- `sort` (`detected_at_desc` | `detected_at_asc` | `confidence_desc`)

### Retention

- `SignalEvent` retention mặc định 90 ngày. Thêm config `SIGNAL_EVENT_RETENTION_DAYS` (default 90). Cleanup deferred nếu chưa có retention worker.

### Out of Scope for 21.1

- Composite lead scoring → Story 21.2
- `Lead` / `LeadSource` / `VerifiedContact` → Stories 21.3–21.4
- Sequencer / `SequenceRun` / `Sequence` implementation → Story 21.4 (21.1 chỉ emit `EnrollmentRequested` stub)
- CRM integration → Story 21.5
- Zalo / LinkedIn outbound → Story 21.6
- Outcome-based pricing / `PricingPlan` → Story 21.7

### UX Integration

- Signal events hiển thị ở Data Panel tab "Signals" (per `ux-contract-lead-intelligence-panel.md` N3, N7).
- Filter chips: `signal_type`, date range, `confidence`.

### References

- `_bmad-output/planning-artifacts/epics.md` §Epic 21, Story 21.1, Story 21.2
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-63
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` AD-31, AD-33, AD-35, AD-37, AD-38, AD-42, AD-43, AD-44, AD-47
- `_bmad-output/planning-artifacts/architecture/epic21-architecture-update.md`
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md`
- `_bmad-output/implementation-artifacts/stories/6-8-generic-alert-engine.md`
- `_bmad-output/implementation-artifacts/stories/11-1-telegram-notification-foundation.md`
- `nowing_backend/app/alerts/engine/tick.py`
- `nowing_backend/app/alerts/engine/execute.py`
- `nowing_backend/app/capabilities/core/types.py`
- `nowing_backend/app/capabilities/core/store.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/mcp_tools.py`
- `nowing_mcp/mcp_server/server.py`

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

### Timestamp

Created: 2026-08-10
Last Updated: 2026-08-15

---

## Challenge Log (grill-me)

> Grill-me challenge phase — dùng `mcp__vibervn-context-engine__codebase-retrieval` + `mcp__serena__find_referencing_symbols` theo `bmad-nowing-grill-me` skill.
> Communication language: Việt Nam. Document output language: Việt Nam.

### Q1 — Is this already implemented?

Không tìm thấy logic `SignalEvent`, `SignalDetectionService`, `BillingEvent`, hay `lead_intelligence` nào trong `nowing_backend/`.

- `SignalEvent` table: không tồn tại trong `app/db.py`.
- `BillingEvent` table: không tồn tại trong `app/db.py` (architecture mô tả nó là bảng mới).
- `app/lead_intelligence/` directory: chưa tồn tại.
- Capability `*.signal`: không có trong `CapabilityRegistry` hiện tại.
- Function `detect buying signals` / `lead score` / `intent signal`: không có implementation.

**Kết luận:** Không có duplicate logic. Nhưng có nhiều **existing primitives** nên reuse thay vì viết mới:
- `app/alerts/engine/tick.py` + `execute.py` + `diff.py` (alert engine)
- `app/capabilities/core/store.py` `Capability` metadata (AD-44)
- `app/services/pii/redact.py` `redact_pii(..., context="lead_enrichment")` (AD-25)
- `app/services/wallet_credit.py` `check_balance` / `apply_debit` (AD-8)
- `app/services/token_tracking_service.py` `record_token_usage` cho LLM cost
- `app/notifications/types.py` + `constants.py` cho notification type
- `nowing_mcp/mcp_server/features/scrapers/` pattern cho MCP tool registration

### Q2 — Is there a simpler alternative?

| Lựa chọn | Đơn giản hơn? | Đánh giá |
|---|---|---|
| Một capability `lead_intelligence.signal` với `signal_type` input | Có (1 executor) | **Từ chối:** AD-37 yêu cầu `capability_id` riêng `funding.signal`, `hiring.signal`, ... cho `AlertRule`. Nhưng có thể dùng 1 shared executor. |
| Ghi signal cost vào `TokenUsage` với `usage_type="signal_scan"` | Có (không cần `BillingEvent`) | **Từ chối:** AD-42 cấm thêm business event mới vào `TokenUsage`. `BillingEvent` là bắt buộc. |
| Dùng `app/canonical/services/canonical_pii.py` thay vì `redact_pii` | Có (cho dict-structured) | **Từ chối:** `canonical_pii` dành cho `bds_listing`/`vn_job` structured data; signal summary là text nên `app/services/pii/redact.py` `context="lead_enrichment"` đúng hơn. |
| Dùng `MemoryExtractionService` pattern cho LLM summary | Có | **Ghi chú reuse:** `app/services/memory/extraction.py` có idempotency, LLM call, parse JSON, `record_token_usage` — tái sử dụng pattern cho signal summary nhưng KHÔNG dùng trực tiếp vì signal detection cần source-specific fetch. |

**Kết luận:** Không có alternative nào đơn giản hơn mà vẫn tuân thủ AD-37/AD-42. Nên proceed với 5 capability + `BillingEvent` mới, nhưng **tái sử dụng** `AlertRule` engine, `CapabilityRegistry`, `redact_pii`, `wallet_credit`, `NotificationService`.

### Q3 — Edge cases spec misses (Pattern 3)

- **Boundary:** `confidence_threshold`/`confidence` nằm ngoài [0, 100]; `lookback_days <= 0`; `limit`/`offset` âm hoặc > max; `from_date > to_date`; `cost_micros` âm.
- **Null/empty:** `company_name` trống/whitespace; `source_url` null; `chunk_id` null vì source không phải chainlens; `SignalSubscription.signal_types = []`; `AlertRule.query = {}`.
- **Duplicate:** unique constraint `(workspace_id, client_id, company_name, signal_type, source_url, detected_at)` có thể trùng khi API trả cùng sự kiện 2 lần (idempotency cần rõ).
- **Concurrent:** Hai alert rule cùng workspace cùng chạy → double `SignalEvent`, double `BillingEvent` debit. Cần unique constraint + idempotency key.
- **Client scope:** `client_id` null vs set; `AlertRule.client_id` phải match `Sequence.client_id` (AD-46). 
- **Multi-signal overlap:** Cùng một company, cùng `signal_type`, nguồn khác nhau → lưu cả 2 hay chỉ 1? (source_url là một phần unique key).
- **Zero billing:** `SIGNAL_SCAN_MICROS_PER_SIGNAL = 0` → vẫn ghi `BillingEvent` với `cost_micros=0` hay bỏ qua?
- **Pagination edge:** `offset` lớn hơn tổng records; `limit=0`.

### Q4 — Failure modes unspecified (Pattern 2, 4)

| Dependency | Failure | Expected behavior chưa specify |
|---|---|---|
| Crunchbase/NewsAPI/website | Timeout / 429 / 5xx / key missing | Trả `SignalOutput(degraded=true, degradation_reasons=["..."])`, KHÔNG ghi `BillingEvent`, không lưu `SignalEvent` rỗng |
| `chainlens-research` `POST /v1/ingest/scraper` | 5xx / timeout | Signal vẫn lưu nhưng `chunk_id` null, `source_url` giữ nguyên |
| Postgres | Connection lost giữa `SignalEvent` insert và `BillingEvent` insert | Rollback toàn bộ; không để `SignalEvent` mồ côi không billing |
| Redis | Down (rate limiter) | Dùng in-memory fallback per-worker, không block signal detection |
| LLM (summary) | 5xx / timeout / malformed JSON | Dùng rule-based summary hoặc bỏ qua `Memory` row, không retry vô hạn |
| `wallet_credit.check_balance` | Raises / user not found | Fail-closed: `degraded=true`, `degradation_reasons=["insufficient_wallet"]` |
| `wallet_credit.apply_debit` | Thành công sau `BillingEvent` nhưng debit lỗi | Cần đảm bảo `BillingEvent` và debit trong cùng transaction hoặc compensation |
| `AlertRule` capability lookup | `capability_id` not registered | `execute_alert_rule` raise `ValueError` (existing behavior); log và disable rule? |
| Capability output | `items` thiếu `id`/`source_id` | `execute_alert_rule` raise `ValueError` từ `_validate_items` |
| `NotificationService` / `TelegramAdapter` | Fail | Notification ghi lỗi, không làm fail alert run |
| Concurrent `BillingEvent` debit | Double debit cùng `SignalEvent.id` | Partial unique/index + `apply_debit` idempotency cần test |

### Triage

| Finding | Severity | Action |
|---|---|---|
| Không có duplicate logic | — | Proceed |
| Không có simpler alternative hợp lệ | — | Proceed (tuân AD-37/AD-42) |
| Edge case gap (Q3) | Non-critical | Thêm vào test skeleton ở `bmad-nowing-test-first-atdd` |
| Failure mode gap (Q4) | Non-critical | Thêm error-path tests; chú ý Pattern 2 (Over-Mocking) + Pattern 4 (Arithmetic) + Pattern 6 (SQL Mock) khi viết test |
| P0 surface | **Token tracking / quota / credit** + **RAG/connector sync** | Sẽ cần integration test Postgres thật và cosmic-ray gate sau dev |

**Verdict:** Clean — proceed to `bmad-nowing-test-first-atdd`. Không cần HALT.
