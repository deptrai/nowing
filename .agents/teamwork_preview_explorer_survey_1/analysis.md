# Báo cáo Điều tra Kiến trúc & Cơ sở Dữ liệu Epic 21 (Lead Gen Intelligence)

**Người thực hiện**: Teamwork Preview Explorer Survey 1  
**Ngày thực hiện**: 2026-08-15  
**Phạm vi**: `nowing_backend/` (Database Models, Schemas, Migrations, Tenancy AD-31, Provenance AD-44/AD-47, AlertRule/Automation Engine, Intent Signal Detection Story 21.1 & Lead Scoring Story 21.2)

---

## 1. Tổng quan & Tóm tắt cốt lõi (Executive Summary)

Epic 21 (Lead Gen Intelligence) bổ sung năng lực thu thập tín hiệu mua hàng (Intent Signals), tính điểm tiềm năng (Lead Scoring), làm giàu danh bạ (Contact Enrichment), tự động gửi chuỗi tiếp cận (Outbound Sequencer) và đồng bộ CRM (CRM Integration).

Qua điều tra thực tế trong codebase `nowing_backend/`:
1. **DB Models & Migrations**: Các bảng cốt lõi của Story 21.1 & 21.2 đã được định nghĩa trong `app/db.py` và có các migration tương ứng:
   - Migration `190_add_alert_tables.py`: `alert_rules`, `alert_snapshots`, `alert_subscriptions`.
   - Migration `198_add_signal_tables.py`: `signal_events`, `signal_subscriptions`, `billing_events`.
   - Migration `199_add_lead_score_tables.py`: `leads`, `lead_scores`, và cột `workspaces.icp_criteria`.
2. **Tenancy AD-31**: Cô lập dữ liệu đa tầng (Two-Tier Multi-Tenancy) bằng cặp khóa `(workspace_id: Integer, client_id: CITEXT | None)`. Mọi bảng đều có composite index và RLS (Row Level Security) sử dụng transaction-local GUC (`app.workspace_id`, `app.current_client_id`) thông qua hàm `set_request_tenant_context()`.
3. **Provenance AD-44 / AD-47**: `Memory` hỗ trợ lưu vết thực thể UUID thông qua `source_uuid: UUID` và `source_entity_type: String`. Cột `source_id: Integer` giữ nguyên cho chat message/document, `source_run_id: UUID` cho Celery Run. `CapabilityRegistry` là in-process verb registry cung cấp `query_metadata()`, trong đó `lead_extractor` là writer duy nhất ghi `Lead`/`LeadSource`.
4. **AlertRule & Automation Engine (AD-43)**: `AlertRule` là bảng độc lập hạng nhất (`alert_rules`), được Celery Beat task `alert_engine_tick` quét mỗi phút (`crontab(minute="*")`), thực thi capability, tính diff snapshot (`diff_strategy`), và trigger Sequencer qua `target_sequence_id` + `target_step_id` (tạo `SequenceRun` UUID, tuyệt đối không tạo `AutomationRun` integer).
5. **Tích hợp Story 21.1 & 21.2**:
   - Story 21.1 cung cấp 5 signal capabilities (`funding.signal`, `hiring.signal`, `tech_stack.signal`, `executive_move.signal`, `news.signal`), lưu `SignalEvent`, ghi redacted semantic `Memory` (`tags=['lead_signal']`), và hạch toán ví qua `BillingEvent` (`event_entity_type='signal_event'`, `event_type='signal_scan'`).
   - Story 21.2 tính điểm tổng hợp `0.5 * fit_score + 0.5 * intent_score` từ firmographics + `Workspace.icp_criteria` và tín hiệu `SignalEvent` (recency decay), tính `trend`, `converted_similarity` (RAG), lưu `LeadScore`, redacted `Memory` (`tags=['lead_score']`), và `BillingEvent` (`event_entity_type='lead_score'`, `event_type='lead_scoring'`).

---

## 2. Chi tiết Database Models, Schemas & Alembic Migrations

### 2.1. Danh mục các bảng và Models liên quan (`nowing_backend/app/db.py`)

| Bảng (Table) | Model Class | Primary Key | Khóa ngoại (Foreign Keys) & Tenancy | Mục đích & Đặc điểm | Vị trí trong code |
|---|---|---|---|---|---|
| `signal_events` | `SignalEvent` | `id: UUID` | `workspace_id: Integer` (FK workspaces.id), `client_id: CITEXT` (nullable) | Lưu vết tín hiệu mua hàng (`signal_type`, `company_name`, `confidence`, `detected_at`, `chunk_id`, `source_url`, `processed`). | `app/db.py:4252-4296` |
| `signal_subscriptions` | `SignalSubscription` | `id: UUID` | `workspace_id: Integer` (FK workspaces.id, UNIQUE), `client_id: CITEXT`, `created_by_user_id: UUID` | Cấu hình mặc định tín hiệu và kênh thông báo của workspace. | `app/db.py:4298-4329` |
| `billing_events` | `BillingEvent` | `id: UUID` | `workspace_id: Integer`, `client_id: CITEXT`, `user_id: UUID` (FK user.id, nullable) | Sổ cái (ledger) chuẩn cho các sự kiện kinh doanh non-LLM (`event_entity_type`, `event_type`, `event_id`, `cost_micros`, `cost_basis`). | `app/db.py:4331-4378` |
| `leads` | `Lead` | `id: UUID` | `workspace_id: Integer`, `client_id: CITEXT` | Prospect/Lead (`company_name`, `domain`, `industry`, `company_size`, `location`, `tech_stack`, `fit_score`, `intent_score`, `composite_score`, `status`, `enriched`, `consent_status`, `legal_basis`). | `app/db.py:4380-4418` |
| `lead_scores` | `LeadScore` | `id: UUID` | `workspace_id: Integer`, `client_id: CITEXT`, `lead_id: UUID` (FK leads.id), `previous_score_id: UUID` | Snapshot điểm tiềm năng lead (`score`, `fit_score`, `intent_score`, `classification`, `factors_json`, `trend`, `converted_similarity`, `computed_at`). | `app/db.py:4420-4478` |
| `alert_rules` | `AlertRule` | `id: UUID` | `workspace_id: Integer`, `client_id: CITEXT` | Saved searches & alert rules (`capability_id`, `name`, `query`, `schedule`, `cron`, `diff_strategy`, `threshold`, `target_sequence_id`, `target_step_id`, `notification_channels`, `enabled`). | `app/alerts/persistence/models/alert_rule.py:24-85` |
| `alert_snapshots` | `AlertSnapshot` | `id: UUID` | `alert_rule_id: UUID` (FK alert_rules.id) | Snapshot kết quả và diff (`snapshot_json`, `run_status`, `degradation_reasons`, `new_items_count`, `changed_items_count`, `removed_items_count`). | `app/alerts/persistence/models/alert_snapshot.py:16-56` |
| `alert_subscriptions` | `AlertSubscription` | `id: UUID` | `workspace_id: Integer`, `user_id: UUID`, `alert_rule_id: UUID` | Đăng ký nhận thông báo alert của từng user (`channels`, `enabled`). | `app/alerts/persistence/models/alert_subscription.py:17-57` |
| `memories` | `Memory` | `id: Integer` | `workspace_id: Integer`, `client_id: CITEXT`, `created_by_id: UUID`, `research_thread_id: Integer` | Bộ nhớ vector dài hạn (`content`, `embedding`, `type`, `source_type`, `source_id`, `source_run_id`, `source_uuid`, `source_entity_type`, `source_capability`, `source_input`, `tags`, `confidence`). | `app/db.py:2261-2390` |
| `workspaces` | `Workspace` | `id: Integer` | (Root Workspace entity) | Bổ sung cột `icp_criteria: JSONB` để cấu hình tiêu chí Ideal Customer Profile. | `app/db.py:900+`, `alembic/versions/199_add_lead_score_tables.py:35-38` |

### 2.2. Chi tiết Alembic Migrations
- **`alembic/versions/190_add_alert_tables.py`**:
  - Tạo `alert_rules`, `alert_snapshots`, `alert_subscriptions`.
  - Tạo index `ix_alert_rules_due` trên `(workspace_id, enabled, next_fire_at) WHERE enabled = true`.
  - Áp dụng RLS policies với `_create_rls()`.
- **`alembic/versions/198_add_signal_tables.py`**:
  - Tạo bảng `signal_events` với unique constraint `uq_signal_events_unique_signal` trên `(workspace_id, client_id, company_name, signal_type, source_url, detected_at)`.
  - Tạo composite index `ix_signal_events_workspace_lookup` trên `(workspace_id, client_id, company_name, signal_type, detected_at)`.
  - Tạo bảng `signal_subscriptions` với unique constraint trên `workspace_id`.
  - Tạo bảng `billing_events` với index `ix_billing_events_event_lookup` và partial unique indexes:
    - `ix_billing_events_signal_unique` trên `(event_id) WHERE event_entity_type = 'signal_event' AND event_type = 'signal_scan'`.
    - `ix_billing_events_outcome_unique` trên `(event_id) WHERE event_entity_type = 'outcome_event' AND event_type = 'outcome'`.
  - Áp dụng RLS policies trên `signal_events`, `signal_subscriptions`, `billing_events`.
- **`alembic/versions/199_add_lead_score_tables.py`**:
  - `op.add_column("workspaces", Column("icp_criteria", JSONB, nullable=True))`.
  - Tạo bảng `leads` với unique constraint `uq_leads_workspace_company` trên `(workspace_id, client_id, company_name)`.
  - Tạo bảng `lead_scores` với index `ix_lead_scores_workspace_lookup` trên `(workspace_id, client_id, lead_id, computed_at DESC)`.
  - Áp dụng RLS policies trên `leads` và `lead_scores`.

---

## 3. Tenancy Enforcement under AD-31

### 3.1. Nguyên tắc cốt lõi (Core Principles)
- **Kiểu dữ liệu Tenancy**:
  - `workspace_id` luôn là **`Integer`** (FK `workspaces.id`), tuyệt đối **không** dùng `UUID`.
  - `client_id` luôn là **`CITEXT`** (case-insensitive text) trỏ đến natural key của `vertical_clients.client_id`, nullable (`NULL` = Nowing internal / web app). Tuyệt đối **không** dùng `UUID` surrogate.
- **Tính trực giao (Orthogonal Isolation)**:
  - Dữ liệu của các vertical partner (như BDS AI) nằm trong cùng một workspace nhưng được phân tách nghiêm ngặt bởi `client_id`. Truy vấn của vertical client `X` chỉ được thấy dòng có `client_id = 'X'`. Truy vấn nội bộ Nowing chỉ được thấy dòng có `client_id IS NULL`.

### 3.2. Thiết kế Composite Indexes
Để tối ưu hóa hiệu năng và ngăn chặn full-table scan trong môi trường multi-tenant:
- `signal_events`: `Index("ix_signal_events_workspace_lookup", "workspace_id", "client_id", "company_name", "signal_type", "detected_at")` (`app/db.py:4258-4265`).
- `lead_scores`: `Index("ix_lead_scores_workspace_lookup", "workspace_id", "client_id", "lead_id", "computed_at")` (`app/db.py:4428-4435`).
- `memories`: `Index("ix_memories_workspace_id_client_id", "workspace_id", "client_id")` (`app/db.py:2291-2294`).
- `billing_events`: `Index("ix_billing_events_event_lookup", "event_entity_type", "event_type", "event_id")` (`app/db.py:4337-4342`).

### 3.3. Cơ chế Row-Level Security (RLS) & GUC Context
PostgreSQL RLS được kích hoạt ở mức Database (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`):
- **Read Policy**:
  ```sql
  CREATE POLICY table_tenant_read_policy ON <table>
      AS PERMISSIVE FOR SELECT TO PUBLIC
      USING (table.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int);
  ```
- **Write Policy**:
  ```sql
  CREATE POLICY table_tenant_write_policy ON <table>
      AS PERMISSIVE FOR ALL TO PUBLIC
      USING (
          table.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int
          AND table.client_id IS NOT DISTINCT FROM current_setting('app.current_client_id', true)
      )
      WITH CHECK (
          table.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int
          AND table.client_id IS NOT DISTINCT FROM current_setting('app.current_client_id', true)
      );
  ```
- **Transaction-Scoped Context Setting (`app/canonical/tenant_context.py:51-106`)**:
  Hàm `set_request_tenant_context(session, workspace_id, client_id, agent_id, run_id, memory_id, user_id)` thực thi:
  ```python
  await session.execute(
      text("SELECT set_config('app.workspace_id', :wid, true)"),
      {"wid": "" if workspace_id is None else str(workspace_id)},
  )
  await session.execute(
      text("SELECT set_config('app.current_client_id', :cid, true)"),
      {"cid": client_id or ""},
  )
  ```
  `is_local=true` (tham số thứ 3 của `set_config`) đảm bảo giá trị chỉ tồn tại trong transaction hiện tại, tự động dọn sạch khi `COMMIT`/`ROLLBACK`, chống rò rỉ tenant context khi tái sử dụng connection pool.

---

## 4. Provenance Tracking under AD-44 / AD-47

### 4.1. Phân định Entity Pointer vs Run Pointer trong `Memory`
Trước Epic 21, các entity ID của chat message/document là `Integer`, được lưu trong `Memory.source_id`. Epic 21 giới thiệu các entity có khóa chính là `UUID` (`SignalEvent`, `LeadScore`, `Lead`, `EnrichmentRequest`, `SequenceEvent`, `OutcomeEvent`).
Quy tắc bất biến theo AD-44 / AD-47:
- **`Memory.source_uuid: UUID | None`** (`app/db.py:2359`) và **`Memory.source_entity_type: String | None`** (`app/db.py:2360`): Lưu con trỏ trực tiếp đến thực thể nguồn UUID.
- **`Memory.source_id: Integer | None`** (`app/db.py:2348`): Giữ nguyên kiểu Integer cho `document` và `chat_message`. Tuyệt đối **không** cast/pad UUID thành Integer.
- **`Memory.source_run_id: UUID | None`** (`app/db.py:2355`): Chỉ trỏ tới execution run (Celery / Run log), phục vụ audit/idempotency.
- **`Memory.source_type` (`MemorySourceType`)**: Mở rộng enum (`app/db.py:588-602`):
  `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`, `DOCUMENT`, `CHAT_MESSAGE`, `SCRAPER_RUN`, `MANUAL`, `UNKNOWN`.

### 4.2. In-Process `CapabilityRegistry` vs Workspace `LeadSource`
- **`CapabilityRegistry` (`app/capabilities/core/store.py:12-56`)**:
  - Là in-process Python registry chứa các `Capability` verbs đã được import và đăng ký.
  - Cung cấp phương thức chuẩn:
    - `CapabilityRegistry.query_metadata(key: str) -> dict[str, Any]` (trả về `{capability_name: metadata_value}`).
    - `CapabilityRegistry.query_metadata_for(name: str, key: str) -> Any | None`.
  - Canonical metadata keys:
    - `emits_signals: bool`
    - `signal_types: list[str]`
    - `emits_leads: bool`
    - `lead_extractor: bool`
    - `requires_pii_redaction_context: str`
- **`LeadSource` (Cache)**:
  - Là bảng cache dẫn xuất (derived cache) theo từng workspace, cập nhật bởi pipeline ingestion.
  - **Đơn vị ghi duy nhất**: Capability `lead_extractor` (`metadata={"lead_extractor": true}`) là **writer duy nhất** được phép ghi vào `Lead` và `LeadSource`.

---

## 5. AlertRule & Automation Engine

### 5.1. Kiến trúc `AlertRule` (AD-43)
- `AlertRule` là bảng độc lập hạng nhất (`alert_rules`), không bị nhúng thành JSON bên trong `Automation.definition`.
- Cấu trúc:
  - `capability_id`: Tên verb trong `CapabilityRegistry` (ví dụ `funding.signal`, `hiring.signal`, `vn_jobs.aggregate`).
  - `query`: JSONB payload đầu vào cho capability.
  - `diff_strategy`: Thuật toán so sánh snapshot (`new_items`, `price_change`, `threshold_cross`, `trend_detect`).
  - `notification_channels`: Kênh thông báo thực sự (`in_app`, `telegram`, `email`).
  - `target_sequence_id` & `target_step_id`: UUID FK trỏ đến `Sequence.id` và `SequenceStep.id`.

### 5.2. Celery Beat Scheduler & Tick Engine (`app/alerts/engine/`)
1. **Periodic Tick (`app/celery_app.py:356-360`)**:
   Celery Beat cấu hình job `alert-engine-tick` chạy mỗi phút gọi `alert_engine_tick` (`app/alerts/engine/tick.py`).
2. **Claim & Execute (`app/alerts/engine/tick.py:34-80`, `app/alerts/engine/execute.py:88-208`)**:
   - `_claim_due_rules`: Lock các rules đến hạn (`enabled = true` và `next_fire_at <= now()`), tính toán `next_fire_at` mới theo cron/interval.
   - `execute_alert_rule`:
     - Lấy capability từ `CapabilityRegistry.get(alert_rule.capability_id)`.
     - Chạy `execute_with_context(capability.executor, payload, ctx)`.
     - So sánh snapshot hiện tại với snapshot trước đó bằng `diff_snapshots(diff_strategy, prev, current, threshold)`.
     - Ghi `AlertSnapshot` với số lượng `new_items_count`, `changed_items_count`, `removed_items_count`.
     - Gửi thông báo qua `notify_alert_run` (`in_app`, `telegram`).

### 5.3. Tích hợp Sequencer Action vs Automation Engine (AD-43 / AD-46)
- **Không phải notification channel**: `sequence_enrollment` không được khai báo trong `notification_channels`.
- **Tách biệt Run Model**:
  - Khi `target_sequence_id` có giá trị, Alert Engine phát sinh domain event / Celery task `EnrollmentRequested` tới `SequencerService`.
  - `SequencerService` khởi tạo **`SequenceRun` (UUID)**, tuyệt đối **không** tạo `AutomationRun` (Integer).
  - Scope kiểm tra theo AD-46: Nếu `Sequence.shared = false`, `AlertRule.client_id` phải khớp với `Sequence.client_id`.

---

## 6. Phân tích Tích hợp Intent Signal Detection (Story 21.1) & Lead Scoring (Story 21.2)

### 6.1. Story 21.1: Intent Signal Detection Pipeline
```
[External Sources: Crunchbase/RSS/Scraper] 
        │
        ▼
[SignalDetectionService.detect()] 
        ├──> 1. Kiểm tra số dư ví (Wallet pre-check via wallet_credit.check_balance)
        ├──> 2. Ghi bảng `signal_events` (Unique check & insert)
        ├──> 3. Redact PII (redact_pii(summary, context="lead_enrichment"))
        ├──> 4. Ghi bảng `memories` (type=semantic, tags=['lead_signal'], source_uuid=signal.id, source_entity_type="SignalEvent")
        └──> 5. Ghi bảng `billing_events` (event_entity_type="signal_event", event_type="signal_scan", cost_micros)
```
- **5 Signal Capabilities**:
  - `funding.signal`: Tín hiệu gọi vốn qua Crunchbase API v4 hoặc RSS feed.
  - `hiring.signal`: Tuyển dụng qua aggregate job chunks (`vn_jobs.aggregate`).
  - `tech_stack.signal`: Phát hiện thay đổi tech stack qua HTML fingerprint / tech keywords.
  - `executive_move.signal`: Biến động nhân sự cấp cao (degraded khi ToS chưa phê duyệt).
  - `news.signal`: Tin tức thị trường qua NewsAPI / RSS.
- **REST Endpoints (`app/routes/signals_routes.py`)**:
  - `GET /workspaces/{id}/signals` (lọc theo `signal_type`, `company_name`, `from_date`, `confidence_min`).
  - `POST /workspaces/{id}/signals/detect` (trigger scan thủ công).
  - `GET/PUT /workspaces/{id}/signals/subscriptions` (quản lý cấu hình đăng ký tín hiệu).

### 6.2. Story 21.2: Lead Scoring & Prioritization Engine
```
[Leads Table & Workspace ICP] + [SignalEvent / Memory('lead_signal')]
                           │
                           ▼
             [LeadScoringService.score()]
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
    [Fit Score (0-100)]         [Intent Score (0-100)]
    (Firmographics vs ICP)      (Signal Strength × Recency Decay)
             └─────────────┬─────────────┘
                           ▼
              Composite Score = 0.5 × Fit + 0.5 × Intent
              Classification: Hot (80-100), Warm (50-79), Cold (0-49)
              Trend: Improving / Stable / Declining (vs previous_score)
              Converted Similarity: RAG match vs converted leads
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
 [Save LeadScore]   [Write Memory]    [Record BillingEvent]
 (lead_scores row)  (redacted summary, (event_entity_type='lead_score',
                     tags=['lead_score'], event_type='lead_scoring')
                     source_uuid=score.id)
```

- **Query Patterns & Scoring Invariants**:
  - Fit calculation: So khớp `Lead.industry`, `Lead.company_size`, `Lead.location`, `Lead.tech_stack` với `Workspace.icp_criteria["weights"]` và target criteria.
  - Intent calculation: Tổng hợp điểm của từng `SignalEvent` nhân với hệ số suy giảm thời gian (Recency Decay: $\le 7$ ngày = 1.0, $\le 30$ ngày = 0.7, $\le 90$ ngày = 0.4, cũ hơn = 0.1).
  - Hạn chế ghi PII: Tóm tắt điểm số trước khi ghi vào `Memory` được chạy qua `redact_pii(..., context='lead_enrichment')`.

---

## 7. Đánh giá Mức độ Sẵn sàng & Kế hoạch Tiếp theo (Readiness & Next Steps)

1. **Schema & Models**: Bảng `signal_events`, `signal_subscriptions`, `billing_events`, `leads`, `lead_scores`, `alert_rules`, `memories` đã được đồng bộ chuẩn chỉnh trong `app/db.py` và migrations 190, 198, 199.
2. **Repository & Service Layer**: `MemoryRepository` đã hỗ trợ đầy đủ `source_uuid`, `source_entity_type`, `client_id`, `agent_id`.
3. **Engine Core**: `SignalDetectionService` và `LeadScoringService` đã triển khai logic hạch toán ví `wallet_credit`, ghi `BillingEvent`, `Memory` provenance và tuân thủ chặt chẽ AD-31, AD-42, AD-44, AD-47.
4. **Các bước tiếp theo cho Orchestrator**:
   - Tiến hành xác minh test suite toàn diện (`pytest tests/unit/lead_intelligence/ tests/integration/lead_intelligence/ -q`).
   - Kết nối frontend Data Panel / Leads UI hiển thị Score breakdown và Signal timeline.
   - Triển khai các stories tiếp theo của Epic 21 (Story 21.3 Contact Enrichment & PII Governance, Story 21.4 Sequencer, Story 21.5 CRM Write-Back, Story 21.7 ROI Tracking).
