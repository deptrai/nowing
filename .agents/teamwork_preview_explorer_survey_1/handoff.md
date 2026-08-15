# Handoff Report — Survey Explorer 1 (Epic 21 Backend Architecture Survey)

## 1. Observation
1. **Database Models & Alembic Migrations**:
   - `nowing_backend/app/db.py`:
     - `SignalEvent` (`app/db.py:4252-4296`): UUID PK `id`, `workspace_id: Integer` (FK workspaces.id), `client_id: CITEXT` (nullable), `company_name: String(200)`, `signal_type: String(50)`, `source_url: Text`, `chunk_id: UUID`, `confidence: Float`, `detected_at: TIMESTAMP(timezone=True)`, `processed: Boolean`.
     - `SignalSubscription` (`app/db.py:4298-4329`): UUID PK `id`, `workspace_id: Integer` (FK workspaces.id, UNIQUE), `client_id: CITEXT`, `signal_types: JSONB`, `notification_channels: JSONB`, `created_by_user_id: UUID`.
     - `BillingEvent` (`app/db.py:4331-4378`): UUID PK `id`, `workspace_id: Integer`, `client_id: CITEXT`, `user_id: UUID`, `event_entity_type: String(50)`, `event_type: String(50)`, `event_id: UUID`, `cost_micros: BigInteger`, `currency: String(3)`, `cost_basis: String(20)`.
     - `Lead` (`app/db.py:4380-4418`): UUID PK `id`, `workspace_id: Integer`, `client_id: CITEXT`, `source: String(100)`, `company_name: String(200)`, `domain: String(255)`, `industry: String(100)`, `company_size: String(50)`, `location: String(100)`, `tech_stack: ARRAY(String)`, `fit_score: Float`, `intent_score: Float`, `composite_score: Float`, `status: String(50)`, `enriched: Boolean`, `consent_status: String(50)`, `legal_basis: String(50)`.
     - `LeadScore` (`app/db.py:4420-4478`): UUID PK `id`, `workspace_id: Integer`, `client_id: CITEXT`, `lead_id: UUID` (FK leads.id), `previous_score_id: UUID` (FK lead_scores.id), `company_name: String(200)`, `score: Float`, `fit_score: Float`, `intent_score: Float`, `classification: String(10)`, `factors_json: JSONB`, `trend: String(10)`, `converted_similarity: Float`, `computed_at: TIMESTAMP(timezone=True)`.
     - `AlertRule` (`app/alerts/persistence/models/alert_rule.py:24-85`): UUID PK `id`, `workspace_id: Integer`, `client_id: CITEXT`, `capability_id: String(200)`, `name: String(200)`, `query: JSONB`, `schedule: String(20)`, `diff_strategy: String(40)`, `threshold: JSONB`, `target_sequence_id: UUID`, `target_step_id: UUID`, `notification_channels: JSONB`, `enabled: Boolean`.
     - `Memory` (`app/db.py:2261-2390`): Integer PK `id`, `workspace_id: Integer`, `client_id: CITEXT`, `source_uuid: UUID`, `source_entity_type: String(100)`, `source_run_id: UUID`, `source_id: Integer`, `source_type: MemorySourceType`.
   - Alembic Migrations:
     - `alembic/versions/190_add_alert_tables.py`: Khởi tạo `alert_rules`, `alert_snapshots`, `alert_subscriptions` và RLS.
     - `alembic/versions/198_add_signal_tables.py`: Khởi tạo `signal_events`, `signal_subscriptions`, `billing_events` và RLS.
     - `alembic/versions/199_add_lead_score_tables.py`: Thêm cột `workspaces.icp_criteria`, tạo bảng `leads`, `lead_scores` và RLS.

2. **Tenancy Enforcement (AD-31)**:
   - `nowing_backend/app/canonical/tenant_context.py:51-106`: `set_request_tenant_context` thiết lập transaction-scoped session configuration qua `SELECT set_config('app.workspace_id', :wid, true)` và `SELECT set_config('app.current_client_id', :cid, true)`.
   - Bảng cơ sở dữ liệu áp dụng RLS policy:
     - Read: `workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int`
     - Write: `workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int AND client_id IS NOT DISTINCT FROM current_setting('app.current_client_id', true)`.
   - Khóa tenancy: `workspace_id` là `Integer` (FK workspaces.id), `client_id` là `CITEXT` natural key của `vertical_clients.client_id` (nullable).
   - Composite indexes phủ kín: `ix_signal_events_workspace_lookup`, `ix_lead_scores_workspace_lookup`, `ix_memories_workspace_id_client_id`, `uq_leads_workspace_company`.

3. **Provenance Tracking (AD-44 / AD-47)**:
   - `Memory.source_uuid` và `Memory.source_entity_type` lưu con trỏ trực tiếp đến thực thể UUID (`SignalEvent`, `LeadScore`, v.v.). `Memory.source_id` giữ nguyên kiểu `Integer` cho document/chat. `Memory.source_run_id` chỉ lưu Celery Run ID.
   - `MemorySourceType` enum (`app/db.py:588-602`) đã có các giá trị: `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`.
   - `CapabilityRegistry` (`app/capabilities/core/store.py:12-56`) cung cấp `query_metadata(key)` và `query_metadata_for(name, key)`. `lead_extractor` là writer độc quyền ghi `Lead` và `LeadSource`.

4. **AlertRule & Automation Engine (AD-43)**:
   - `app/celery_app.py:356-360`: Celery Beat task `alert-engine-tick` chạy mỗi phút gọi `alert_engine_tick` (`app/alerts/engine/tick.py:28-48`).
   - `app/alerts/engine/execute.py:88-208`: Thực thi capability, diff snapshot (`new_items`), ghi `AlertSnapshot`, gửi thông báo qua `notify_alert_run`.
   - Tích hợp Sequencer qua `target_sequence_id` + `target_step_id` -> phát sinh domain action `EnrollmentRequested` tới `SequencerService` để sinh `SequenceRun` (UUID), không tạo `AutomationRun` (Integer).

5. **Test Execution Result**:
   - Chạy lệnh: `uv run --active pytest tests/unit/lead_intelligence/ -q`
   - Kết quả: `40 passed, 7 warnings in 1.11s` (100% passed).

## 2. Logic Chain
1. Từ quan sát 1 & 2: Kiến trúc schema DB của Nowing cho Epic 21 tuân thủ triệt để AD-31 bằng việc sử dụng `workspace_id: Integer` làm partition cấp 1 và `client_id: CITEXT` làm partition cấp 2, kết hợp composite index và RLS policy với transaction-local GUC.
2. Từ quan sát 3: Việc tách rời `source_uuid: UUID` + `source_entity_type: str` khỏi `source_id: Integer` trong bảng `memories` và `MemoryRepository` đáp ứng chính xác AD-44 và AD-47, tránh hiện tượng ép kiểu (type coercion) hoặc làm hỏng dữ liệu chat/document kế thừa.
3. Từ quan sát 4: Bảng `alert_rules` độc lập cùng bộ diff/tick engine định kỳ cho phép phát hiện tín hiệu mua hàng tự động theo thời gian thực và kích hoạt Sequencer một cách tách biệt với `AutomationRun`.
4. Từ quan sát 5: Các unit tests hiện tại của Story 21.1 và 21.2 đã chạy thành công 100%, chứng minh tính toàn vẹn của logic tính điểm, phát hiện tín hiệu, hạch toán ví và ghi vết bộ nhớ.

## 3. Caveats
- Các migration 198 và 199 đã được tạo sẵn trong nhánh làm việc nhưng kiểm thử tích hợp (`pytest tests/integration/lead_intelligence/`) yêu cầu kết nối cơ sở dữ liệu PostgreSQL thực tế có extension pgvector và citext (đang được kiểm thử ở unit mock level).
- Các kênh bên ngoài như LinkedIn và Zalo được đặt ở trạng thái deferred trong MVP theo AD-41, chỉ hỗ trợ Email cho Outbound Sequencer.
- Tín hiệu `executive_move` trả về degraded mode khi chưa hoàn tất phê duyệt ToS / legal theo AC của Story 21.1.

## 4. Conclusion
- Kiến trúc cơ sở dữ liệu, phân vùng Tenancy (AD-31), cơ chế Provenance (AD-44/AD-47), và Alert Engine (AD-43) trong `nowing_backend/` đã được thiết kế và triển khai hoàn toàn nhất quán với Architecture Spine và các story specs của Epic 21.
- Story 21.1 (Intent Signal Detection) và Story 21.2 (Lead Scoring) đã có nền tảng vững chắc và sẵn sàng cho các bước kiểm thử tích hợp (integration tests) và mở rộng cho Stories 21.3 - 21.7.

## 5. Verification Method
1. **Chạy Unit Tests**:
   ```bash
   cd nowing_backend
   uv run --active pytest tests/unit/lead_intelligence/ -q
   ```
2. **Kiểm tra cú pháp & Format (Linter/Formatter)**:
   ```bash
   cd nowing_backend
   ruff check app/lead_intelligence app/alerts alembic/versions/198_add_signal_tables.py alembic/versions/199_add_lead_score_tables.py
   ```
3. **Kiểm tra Migration Database (yêu cầu PostgreSQL test instance)**:
   ```bash
   cd nowing_backend
   uv run alembic upgrade head
   uv run pytest tests/integration/lead_intelligence/ -q
   ```
4. **Điều kiện vô hiệu hóa (Invalidation conditions)**:
   - Nếu có bất kỳ migration nào sử dụng `UUID` cho `workspace_id` hoặc `Text` thay cho `CITEXT` cho `client_id`.
   - Nếu `Memory.source_id` nhận giá trị UUID được ép kiểu.
   - Nếu `AlertRule` lưu trong `Automation.definition` thay vì bảng `alert_rules`.
