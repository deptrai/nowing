---
story_key: "24-1"
epic: "epic-24"
story: "24.1"
title: "Multi-Channel Drip Outreach Campaign Engine (Sequence Backend — Email-first MVP)"
status: in-progress
baseline_commit: "1b75d8fc4"
---

# Story 24.1: Công cụ chiến dịch tiếp cận tự động đa kênh (Drip Outreach Sequence — Email-first MVP)

## Câu chuyện

**As a** enterprise sales team, growth marketer, or real-estate agency,  
**I want** to design, schedule, and execute automated multi-step outreach **Sequences** (Email in MVP; Zalo ZNS and Telegram reserved behind feature gates) with conditional delays, strict Vietnamese legal quiet-hour compliance (08:00 – 21:30 VN Time), and real-time opt-out/reply handling,  
**So that** high-intent leads generated across Nowing are nurtured automatically into qualified sales conversations without manual repetitive outreach or compliance violations.

### Lưu ý phạm vi tuyệt đối

- Story này xây dựng **bounded context `Sequence`** (`Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, `SequenceRun`) theo **AD-39**, **KHÔNG** tạo thêm miền `drip_campaigns` / `campaign_*` song song.
- **Kênh MVP duy nhất là `email`**. `zalo`, `telegram`, `linkedin` được giữ trong enum nhưng backend/UI từ chối với thông báo `deferred` cho đến khi feature flag bật, theo **AD-41** và **DEF-102** ("Direct Zalo OA Outbound messaging automation deferred to Sprint 3 post-Closed Beta").
- Muốn bật Zalo/Telegram sau này, team **bắt buộc** chạy `bmad-correct-course` / SCP để kích hoạt lại AD-41 và đóng legal/ToS gate.

## Kiến trúc ràng buộc (Architectural Invariants)

- **AD-39 — Sequence bounded context:**  
  `Sequence` là bounded context riêng, **không phải subtype của `Automation`**. Chỉ tái sử dụng mô hình scheduler/Celery của Epic 6, **không tái sử dụng schema `Automation` / `AutomationRun`**. Step type MVP: `send_email`, `wait`, `condition`. Các type `update_lead_score`, `update_crm`, `tag` được giữ trong enum nhưng có thể trả `501 Not Implemented` trong MVP. `current_step` là `int` (`step_order`), không dùng UUID.

- **AD-41 — Channels deferred out of MVP:**  
  `zalo` / `linkedin` / `telegram` bị tắt. UI/sequencer từ chối với `422 DeferredChannelError` nếu feature flag `SEQUENCER_OUTBOUND_CHANNELS` không chứa kênh đó.

- **AD-42 — Billing matrix:**  
  `TokenUsage` chỉ dành cho LLM token. Mọi sự kiện nghiệp vụ sequence dùng `BillingEvent`. Ma trận cho phép:
  - `SequenceEvent.event_type == 'sent'` → `BillingEvent(event_entity_type='sequence_event', event_type='email_send')`.
  - `SequenceEvent.event_type == 'meeting_booked'` → tạo `OutcomeEvent` + `BillingEvent(event_entity_type='outcome_event', event_type='outcome_meeting_booked')`.
  - `{delivered, opened, replied, bounced}` → cập nhật `SequenceEnrollment` và gửi notification, **không** tạo `BillingEvent`.

- **AD-43 — Alert-driven sequence enrollment:**  
  `AlertRule` là first-class table. `sequence_enrollment` **không phải** notification channel; đó là action phát `EnrollmentRequested` event/Celery task, rồi `SequencerService` tạo `SequenceRun` + `SequenceEnrollment`. Alert engine **không** tạo `AutomationRun`.

- **AD-25 / AD-49 — Consent, PII & Redaction:**  
  Chỉ enroll `Lead` có `consent_status != 'none'` và `legal_basis` không null. `VerifiedContact` là nguồn PII duy nhất cho outreach; kiểm tra `consent=True`, `is_valid=True`, `legal_basis` không null. Mọi log, `SequenceEvent.metadata`, `BillingEvent` không chứa PII raw — redact qua `redact_pii(..., context='lead_enrichment')`. Nếu tạo `Memory` từ `SequenceEvent`, set `source_uuid` + `source_entity_type='sequence_event'`.

- **AD-31 / AD-45 — Multi-tenant PK & `client_id`:**  
  Mọi bảng mới dùng Composite PK `(id, workspace_id)`, `client_id: CITEXT`, Composite FK, và `FORCE ROW LEVEL SECURITY` với predicate chuẩn:
  ```sql
  workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
  AND client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
  ```
  **Cảnh báo:** `Lead.client_id` hiện đang là `text` do migration `94cfa0f6f5f9` downgrade về `text` để tương thích Zero sync. Các bảng `sequence_*` mới nên dùng `CITEXT` theo AD-45; tuy nhiên nếu cần đưa vào `zero_publication` thì phải xử lý tương thích kiểu dữ liệu với Zero (xem `94cfa0f6f5f9` và `_bmad-output/planning-artifacts/architecture/...`).

- **AD-46 — Client scope của `AlertRule.target` và `Sequence`:**  
  `AlertRule.client_id` phải khớp `Sequence.client_id` trừ khi `Sequence.shared = true` và `client_id IS NULL`. `SequenceRun` / `SequenceEnrollment` `client_id` luôn là `Lead.client_id` của lead kích hoạt.

- **AD-47 — `Capability` metadata & `Memory` UUID provenance:**  
  `CapabilityRegistry.query_metadata` / `query_metadata_for` là read path chuẩn. Nếu tạo `Memory` từ `SequenceEvent`/`OutcomeEvent`, set `source_uuid` + `source_entity_type`.

- **AD-48 — Billing matrix:**  
  Chỉ `sent` tạo `BillingEvent` `sequence_event`/`email_send`. `meeting_booked` tạo `OutcomeEvent` + `BillingEvent` `outcome_event`/`outcome_meeting_booked`.

- **INV-24.1 — Quiet hours & Jitter:**  
  `SequencerService.calculate_step_eta(delay_seconds, from_dt)` tính theo `Asia/Ho_Chi_Minh`. Khung gửi: **08:00 – 21:30**. Nếu `target_dt` ngoài khung, đẩy sang **08:05 ngày tiếp theo + `random(0, 1800)` giây jitter**.

- **INV-24.2 — Opt-Out, DNC & ZNS Template Compliance:**  
  Mọi bước gửi bắt buộc kiểm tra `DncComplianceService.is_blocked()` fail-closed. Nhận phản hồi `STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE` → ngắt sequence, tạo `WorkspaceDncRecord` với `value_hmac`, invalidate DNC cache, hủy các bước sau.

- **INV-24.7 — Inbound interruption & distributed concurrency lock:**  
  `handle_inbound_interruption` dùng Redis lock `sequence:lock:enrollment:{workspace_id}:{enrollment_id}` (TTL 10s) và CAS update trên cột `version` của `SequenceEnrollment`.

## Tiêu chí chấp nhận (Acceptance Criteria)

### AC-1 — Giao diện xây dựng Sequence trực quan
- **Given** workspace member đã xác thực,
- **When** user mở `/dashboard/[workspace_id]/automations/campaigns/new`,
- **Then** UI hiển thị visual node/timeline editor hỗ trợ:
  - `send_email`: chọn template, map biến (`{customer_name}`, `{company}`, `{property_title}`, `{consultant_phone}`).
  - `wait`: cấu hình `wait_duration` (ví dụ `2 days` / `48 hours`).
  - `condition`: điều kiện rẽ nhánh đơn giản (ví dụ "if replied then exit, else continue").
  - Channel selector chỉ hiển thị `email`; `zalo`, `telegram`, `linkedin` bị vô hiệu hóa với tooltip "deferred".

### AC-2 — Email-only MVP & Channel Deferred Gate
- **Given** sequence step có channel khác `email`,
- **When** backend cố gắng thực thi,
- **Then** `SequencerService` từ chối với `422 DeferredChannelError` trừ khi `SEQUENCER_OUTBOUND_CHANNELS` feature flag chứa kênh đó.

### AC-3 — Quiet Hours & Anti-Thundering Herd Scheduling
- **Given** enrollment có bước tiếp theo đến hạn lúc 22:30 (ngoài 08:00 – 21:30 VN Time),
- **When** `calculate_step_eta()` tính thời gian gửi,
- **Then** trả về `08:05 + uniform(0, 1800s)` sáng hôm sau.
- **When** Celery Beat chạy `evaluate_sequences` mỗi 1 phút,
- **Then** chỉ đưa vào hàng đợi các `SequenceEnrollment` có `status = 'scheduled'` và `scheduled_at <= now()`.

### AC-4 — Consent & Legal Basis Gate
- **Given** lead có `consent_status = 'none'` hoặc thiếu `legal_basis`,
- **When** `SequencerService.enroll_lead()` được gọi,
- **Then** log `enrollment_rejected_consent` và không tạo `SequenceEnrollment`.
- **Given** send step,
- **When** không tồn tại `VerifiedContact` với `consent=True`, `is_valid=True`, và email khớp,
- **Then** skip bước và log `skipped_no_consent`.

### AC-5 — Inbound Interruption & Distributed Lock
- **Given** enrollment đang ở trạng thái `scheduled` hoặc `executing`,
- **When** inbound event đến (email reply, Zalo webhook, Telegram inbound) chứa opt-out keyword hoặc reply,
- **Then** `SequencerService.handle_inbound_interruption()` acquire Redis lock, thực hiện CAS version update sang `responded` hoặc `unsubscribed`, và nếu opt-out thì tạo `WorkspaceDncRecord(s)` với `value_hmac`, invalidate DNC cache, hủy các bước tương lai.

### AC-6 — Billing & Credit Flow
- **Given** billable `send_email` step,
- **When** bước thực thi thành công,
- **Then**:
  1. Insert `SequenceEvent(event_type='sent', channel='email', cost_micros=...)` và update `SequenceEnrollment` (status, current_step, scheduled_at, version CAS) trong cùng `AsyncSession`.
  2. Gọi `BillingEventService.record_sequence_send(...)` là thao tác **cuối cùng** của session để ghi `BillingEvent(event_entity_type='sequence_event', event_type='email_send', event_id=sequence_event.id, cost_micros=..., cost_basis='actual')`. Method này tự động enforce per-seat spend cap qua `WorkspaceCreditService.record_spend` rồi debit `User.credit_micros_balance` qua `wallet_credit.apply_debit` (AD-8/AD-42). Không gọi `WorkspaceCreditService.record_spend` riêng từ `SequencerService`.
  3. `record_sequence_send` phải **idempotent theo `sequence_event_id`**: nếu `BillingEvent` đã tồn tại thì **return existing** thay vì raise `ValueError`, để Celery retry không crash.
  4. `wallet_credit.apply_debit` gọi `session.commit()` bên trong (`wallet_credit.py:111`), do đó commit toàn bộ `SequenceEvent`, `SequenceEnrollment`, `BillingEvent` cùng lúc.
- **When** gửi thất bại hoặc pre-check/debit thất bại,
- **Then** không tạo `BillingEvent`; insert `SequenceEvent(event_type='failed', event_subtype='insufficient_credits' | 'smtp_error' | ...)` tùy lý do; rollback session.

### AC-7 — Alert-Driven Enrollment
- **Given** `AlertRule` có `target_sequence_id` và signal khớp,
- **When** alert engine kích hoạt,
- **Then** emit `EnrollmentRequested` Celery task; `SequencerService.enroll_lead()` tạo `SequenceRun` và `SequenceEnrollment`.

### AC-8 — Sequence Analytics
- **Given** sequence đã tồn tại tại `/dashboard/[workspace_id]/automations/campaigns/[id]`,
- **When** mở analytics view,
- **Then** backend trả `SequenceAnalyticsResponse` với `total_enrolled`, `active_scheduled`, `delivered_count`, `responded_count`, `unsubscribed_count`, `failed_count`, `total_cost_micros`.

## Công việc / Subtasks

### 1. Database Schema & Alembic Migration
- [ ] Tạo migration `nowing_backend/alembic/versions/225_add_sequence_tables.py` (Revises: `224`, head hiện tại `224` / `94cfa0f6f5f9`).
- [ ] Thêm 5 bảng với Composite PK `(id, workspace_id)`, `client_id: CITEXT` (lưu ý tương thích Zero nếu sync), `created_at`, `updated_at`, `FORCE ROW LEVEL SECURITY`:
  - `sequence`: `id`, `workspace_id`, `client_id`, `name`, `description`, `status` (`active`/`paused`/`archived`), `shared` (bool), `created_by_user_id`, `entry_step_order` (mặc định 1).
  - `sequence_steps`: `id`, `workspace_id`, `client_id`, `sequence_id`, `step_order` (int), `step_type` (`send_email`/`wait`/`condition`/`update_lead_score`/`update_crm`/`tag`), `channel`, `template` (JSONB: template_id + variable mapping), `wait_duration_seconds` (int), `condition_config` (JSONB: branch predicate + next step order), `is_enabled`.
  - `sequence_enrollments`: `id`, `workspace_id`, `client_id`, `sequence_id`, `lead_id`, `sequence_run_id`, `current_step` (int), `status` (`scheduled`/`executing`/`paused`/`responded`/`unsubscribed`/`failed`/`completed`), `scheduled_at`, `version` (int, default 0, OCC), `last_event_at`.
  - `sequence_events`: `id`, `workspace_id`, `client_id`, `enrollment_id`, `sequence_id`, `step_id`, `event_type` (`sent`/`delivered`/`opened`/`replied`/`bounced`/`meeting_booked`/`failed`/`skipped`), `event_subtype`, `channel`, `cost_micros`, `metadata` (JSONB), `provider_msg_id`.
  - `sequence_runs`: `id`, `workspace_id`, `client_id`, `sequence_id`, `triggering_alert_rule_id`, `status` (`running`/`completed`/`cancelled`), `started_at`, `completed_at`.
- [ ] Đảm bảo `triggering_alert_rule_id` nullable; FK `alert_rules.id` deferred nếu table chưa sẵn sàng.
- [ ] Tạo indexes: `ix_sequence_enrollments_sched (workspace_id, status, scheduled_at)`, `ix_sequence_steps_order (workspace_id, sequence_id, step_order)`, `ix_sequence_events_enrollment (workspace_id, enrollment_id, event_type)`.
- [ ] Kiểm tra kiểu `client_id`: `leads.client_id` hiện là `text` do Zero sync; quyết định CITEXT/text cho `sequence_*` phải tương thích với Zero publication plan (nếu cần Zero sync, tham khảo `94cfa0f6f5f9`).

### 2. ORM Models
- [ ] Cập nhật `nowing_backend/app/db.py` thêm 5 model trên.
- [ ] Khai báo enum/status, composite FK đến `leads` và `vertical_clients`.

### 3. Core Service — `SequencerService`
- [ ] Tạo `nowing_backend/app/services/sequencer_service.py`:
  - `calculate_step_eta(delay_seconds, from_dt=None)` — timezone `Asia/Ho_Chi_Minh`, quiet hours, jitter.
  - `enroll_leads(session, workspace_id, sequence_id, lead_ids, *, triggered_by_alert_rule_id=None, user_id=None)`.
  - `enroll_lead(session, workspace_id, sequence_id, lead_id, *, triggering_alert_rule_id=None, sequence_run_id=None)`.
  - `evaluate_pending_enrollments(session)` — query due, dispatch Celery.
  - `execute_enrollment_step(session, enrollment_id, workspace_id)` — Redis lock, CAS, send_email/wait/condition.
  - `handle_inbound_interruption(session, workspace_id, *, phone=None, email=None, text=None, channel=None)`.
  - `get_sequence_analytics(session, workspace_id, sequence_id)`.

### 4. Celery Tasks & Beat Schedule
- [ ] Tạo `nowing_backend/app/automations/tasks/sequence_tasks.py` với `evaluate_sequences` và `execute_sequence_step`.
- [ ] Thêm `app.automations.tasks.sequence_tasks` vào `include` trong `nowing_backend/app/celery_app.py`.
- [ ] Thêm `evaluate_sequences` vào `beat_schedule` mỗi 1 phút.

### 5. REST API Routes & Schemas
- [ ] Tạo `nowing_backend/app/schemas/sequence.py`.
- [ ] Tạo `nowing_backend/app/routes/sequence_routes.py` với CRUD + enroll/pause/resume/analytics.
- [ ] Register route trong `nowing_backend/app/routes/__init__.py` (hoặc `app.py` nếu cần).

### 6. BillingEvent Service Extension
- [ ] Mở rộng `nowing_backend/app/services/billing_event_service.py`:
  - Thêm `record_sequence_send(session, *, sequence_event_id, workspace_id, client_id, user_id, cost_micros, cost_basis='actual')` gọi `_record_business_event(event_entity_type='sequence_event', event_type='email_send')`.
  - Thêm `record_outcome_meeting_booked(session, *, outcome_event_id, workspace_id, client_id, user_id, cost_micros, cost_basis='actual')` gọi `_record_business_event(event_entity_type='outcome_event', event_type='outcome_meeting_booked')`.
- [ ] Đảm bảo `record_sequence_send` idempotent theo `sequence_event_id`: nếu `BillingEvent` đã tồn tại thì **return existing row** thay vì raise `ValueError`, để retry-safe với Celery.
- [ ] Verification: `ruff check app/services/billing_event_service.py`, `pytest tests/unit/services/test_billing_event_service.py`.

### 7. Inbound Webhook & Notification Integration
- [ ] Mở rộng `NotificationType` / channel constants trong `app/notifications/types.py` và `app/notifications/constants.py` với `email_reply`, `email_delivered`, `email_bounced`.
- [ ] Tích hợp `SequencerService.handle_inbound_interruption` từ `app/gateway/zalo/webhook.py`, `app/gateway/telegram/callbacks.py`, `app/gateway/inbox_processor.py` (hoặc route email SES webhook/IMAP idle).
- [ ] Đảm bảo positive-reply/delivery/bounce notifications reuse Story 11.1 notification dispatcher.

### 8. Frontend UI
- [ ] Tạo/cập nhật `nowing_web/contracts/types/sequence.types.ts`.
- [ ] Tạo `nowing_web/lib/apis/sequence-api.service.ts`.
- [ ] Tạo `nowing_web/components/automations/VisualCadenceBuilder.tsx`.
- [ ] Tạo pages:
  - `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/page.tsx` (list)
  - `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/new/page.tsx` (builder)
  - `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/[sequence_id]/page.tsx` (analytics)
- [ ] UX navigation: `/dashboard/[id]/campaigns` theo `EXPERIENCE.md`; channel selector chỉ bật `email`.

### 9. Tests
- [ ] `nowing_backend/tests/unit/services/test_sequencer_service.py`.
- [ ] `nowing_backend/tests/integration/services/test_sequence_scheduler.py`.
- [ ] Frontend typecheck & biome cho các file đã động.

## Dev Notes & Architecture Guardrails

### 1. Existing Services to Reuse
- **Email SMTP:** `_send_email_smtp(to_email, subject, body)` trong `app/alerts/engine/notify.py:119` là sync; wrap bằng `asyncio.to_thread`.
- **DNC:** `DncComplianceService` trong `app/lead_intelligence/dnc/service.py:56`; phương thức `is_blocked(workspace_id, phone, email, domain, tax_id, session=None)` trả về `DncCheckResult` fail-closed. Dùng `hash_phone_hmac`, `normalize_email`, `normalize_phone_e164` từ `app/lead_intelligence/dnc/normalizer.py`.
- **PII Encryption:** `VerifiedContactEncryption` trong `app/services/pii/verified_contact_encryption.py:37` với `decrypt_contact` để giải mã PII cho send path; `redact_pii(..., context='lead_enrichment')` trong `app/services/pii/redact.py:71` cho log/metadata.
- **Billing Ledger (canonical path):** `BillingEventService` trong `app/services/billing_event_service.py:18` là canonical path cho business-event ledger. Thêm method `record_sequence_send(session, *, sequence_event_id, workspace_id, client_id, user_id, cost_micros, cost_basis='actual')` gọi `_record_business_event(event_entity_type='sequence_event', event_type='email_send')`. `BillingEventService._record_business_event` tự động gọi `WorkspaceCreditService.record_spend` để enforce per-seat cap rồi `wallet_credit.apply_debit` debit `User.credit_micros_balance` (AD-8). Không gọi `wallet_credit.apply_debit` trực tiếp từ `SequencerService`.
- **Workspace Credit Pool (không dùng cho sequence send):** `WorkspaceCreditService.deduct_credits` trong `app/services/workspace_credit_service.py:121` trừ `Workspace.credit_micros_balance`, chỉ dùng cho manual/refund hoặc pipeline CRM (Story 24.3). Để tuân thủ AD-42/AD-48, **KHÔNG** gọi `deduct_credits` cho sequence send; dùng `BillingEventService` để debit user wallet và dùng `record_spend` chỉ để kiểm tra per-seat cap.
- **Celery Async Helper:** `run_async_celery_task` / `get_celery_session_maker` trong `app/tasks/celery_tasks.py`.
- **Redis:** `get_redis_client` trong `app/redis_client.py:15`.
- **AlertRule:** `app/alerts/persistence/models/alert_rule.py:24` đã có `target_sequence_id`, `target_step_id`; `app/alerts/engine/execute.py:88` cần được mở rộng để emit `EnrollmentRequested` khi rule khớp.

### 2. Cảnh báo "không tái phát triển" (Anti-Reinvention)
- Không viết scheduler riêng; dùng Celery Beat pattern của Epic 6 (`app/celery_app.py:290`, `app/automations/tasks/execute_run.py:18`).
- Không tạo bảng `drip_campaigns`, `campaign_steps`; dùng tên bảng `sequence_*` theo AD-39.
- Không để `TokenUsage` ghi nhận business event; mọi chi phí sequence dùng `BillingEvent`.
- Không hard-code danh sách lead source; query `LeadSource` cache và `CapabilityRegistry.query_metadata('emits_leads')` theo AD-44/AD-47.
- Không tạo `AutomationRun` cho alert-driven enrollment; dùng `SequenceRun`.

### 3. Quiet Hours Formula (`Asia/Ho_Chi_Minh`)

```python
from datetime import datetime, time, timedelta
import random
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def calculate_step_eta(delay_seconds: int, from_dt: datetime | None = None) -> datetime:
    if from_dt is None:
        from_dt = datetime.now(VN_TZ)
    elif from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(VN_TZ)
    else:
        from_dt = from_dt.astimezone(VN_TZ)

    target_dt = from_dt + timedelta(seconds=delay_seconds)
    current_minute = target_dt.hour * 60 + target_dt.minute
    start_minute = 8 * 60
    end_minute = 21 * 60 + 30

    if start_minute <= current_minute <= end_minute:
        return target_dt

    jitter_seconds = random.randint(0, 1800)
    if current_minute < start_minute:
        next_send = datetime.combine(target_dt.date(), time(hour=8, minute=5), tzinfo=VN_TZ)
    else:
        next_day = target_dt.date() + timedelta(days=1)
        next_send = datetime.combine(next_day, time(hour=8, minute=5), tzinfo=VN_TZ)
    return next_send + timedelta(seconds=jitter_seconds)
```

### 4. Redis Distributed Lock + Optimistic CAS

```python
redis_client = await get_redis_client()
async with redis_client.lock(
    f"sequence:lock:enrollment:{workspace_id}:{enrollment.id}",
    timeout=10.0,
    blocking=True,
    blocking_timeout=2.0,
):
    stmt = (
        update(SequenceEnrollment)
        .where(
            SequenceEnrollment.id == enrollment.id,
            SequenceEnrollment.workspace_id == workspace_id,
            SequenceEnrollment.version == current_version,
        )
        .values(
            status="executing",
            version=current_version + 1,
            updated_at=datetime.now(UTC),
        )
    )
    result = await session.execute(stmt)
    if result.rowcount == 0:
        logger.info("Enrollment %s already transitioned; skipping", enrollment.id)
        return
```

### 5. Inbound Opt-Out DNC Registration

```python
async def _register_opt_out_dnc(session, workspace_id, phone=None, email=None):
    dnc_service = DncComplianceService()
    if phone:
        e164 = normalize_phone_e164(phone)
        if e164:
            p_hash = hash_phone_hmac(e164, secret_key=dnc_service.secret_key)
            session.add(WorkspaceDncRecord(
                workspace_id=workspace_id,
                record_type="phone",
                value=f"{e164[:4]}****{e164[-3:]}",
                value_hmac=p_hash,
                reason="Inbound STOP/HUY opt-out",
                source="inbound_sequence_opt_out",
            ))
    if email:
        norm_mail = email.strip().lower()
        m_hash = hash_phone_hmac(norm_mail, secret_key=dnc_service.secret_key)
        session.add(WorkspaceDncRecord(
            workspace_id=workspace_id,
            record_type="email",
            value=redact_pii(norm_mail, context="lead_enrichment").text,
            value_hmac=m_hash,
            reason="Inbound STOP/HUY opt-out",
            source="inbound_sequence_opt_out",
        ))
    await session.commit()
    await dnc_service.invalidate_workspace_cache(workspace_id)
```

### 6. Billing & Credit Flow

```python
from app.services.billing_event_service import BillingEventService
from app.services import wallet_credit

# 1. Xác định user chịu trách nhiệm tài chính
attributed_user_id = sequence.created_by_user_id or workspace.user_id

# 2. Pre-check số dư ví trước khi gửi (fail sớm, không gửi nếu thiếu tiền)
if cost_micros > 0:
    try:
        await wallet_credit.check_balance(session, attributed_user_id, cost_micros)
    except wallet_credit.InsufficientCreditsError:
        return SequenceEvent(
            ..., event_type="failed", event_subtype="insufficient_credits",
            metadata={"reason": f"required {cost_micros}"},
        )

# 3. Gửi email (asyncio.to_thread(_send_email_smtp, ...))
...

# 4. Ghi SequenceEvent(sent) và update Enrollment trong cùng session
sequence_event = SequenceEvent(
    workspace_id=workspace_id,
    client_id=client_id,
    enrollment_id=enrollment.id,
    sequence_id=sequence.id,
    step_id=step.id,
    event_type="sent",
    channel="email",
    cost_micros=cost_micros,
    metadata={
        "template_id": step.template,
        "recipient": redacted_email,
        "provider_msg_id": msg_id,
    },
)
session.add(sequence_event)
await session.flush()  # lấy sequence_event.id

# 5. Update enrollment trước khi gọi billing; tất cả được commit cùng lúc
enrollment.status = "scheduled"
enrollment.current_step = next_step_order
enrollment.scheduled_at = next_eta
enrollment.version += 1

# 6. Ghi ledger + debit user wallet (record_spend enforce per-seat cap, rồi apply_debit)
# LƯU Ý: `wallet_credit.apply_debit` gọi `session.commit()` bên trong, nên đây là thao tác CUỐI.
billing_event = await BillingEventService().record_sequence_send(
    session=session,
    sequence_event_id=sequence_event.id,
    workspace_id=workspace_id,
    client_id=client_id,
    user_id=attributed_user_id,
    cost_micros=cost_micros,
    cost_basis="actual",
)
```

**Rào cản tài chính:**
- Sequence send **debit user wallet** (`User.credit_micros_balance`) thông qua `BillingEventService`, **không phải** `WorkspaceCreditService.deduct_credits` (workspace pool).
- `BillingEventService._record_business_event` đã gọi `WorkspaceCreditService.record_spend` để enforce per-seat spend cap trước khi `wallet_credit.apply_debit` (Story 24.3). `SequencerService` không gọi `record_spend` riêng.
- `record_sequence_send` phải retry-safe: nếu `BillingEvent` đã tồn tại cho `sequence_event_id` thì **return existing** thay vì raise, để Celery retry không crash.
- Nếu pre-check thất bại hoặc gửi thất bại, mark `SequenceEvent(event_type='failed', ...)` và **không** tạo `BillingEvent`.
- Nếu `record_sequence_send` thất bại sau khi email đã gửi (do cap / debit race), mark `SequenceEvent(event_type='failed', event_subtype='billing_failed')` và để admin reconcile; đây là edge-case hiếm nhờ pre-check.
- Với `meeting_booked`, tạo `OutcomeEvent` trước rồi gọi `BillingEventService.record_outcome_meeting_booked(outcome_event_id=..., ...).

### 7. Consent / Legal Basis Pre-Check

```python
if lead.consent_status == "none" or not lead.legal_basis:
    logger.info("Rejecting enrollment: lead %s lacks consent/legal basis", lead.id)
    return None

contact = await _resolve_verified_contact(session, lead, channel="email")
if not contact or not contact.consent or not contact.legal_basis:
    logger.info("Skipping step: no consented contact for lead %s", lead.id)
    return SequenceEvent(..., event_type="skipped", event_subtype="no_consent")
```

- `VerifiedContact.email` được lưu encrypted at rest (`app/services/pii/verified_contact_encryption.py`). Dùng `decrypt_contact` hoặc `decrypt` trước khi gửi.
- `redact_pii` chỉ dùng cho log/metadata; **không** redact raw `VerifiedContact.email`.

### 8. AlertRule Integration
- `app/alerts/engine/execute.py` hiện tại gọi `notify_alert_run` sau khi diff xong. Cần bổ sung: nếu `alert_rule.target_sequence_id` được set và diff có `new_items`, emit `EnrollmentRequested` Celery task cho từng item mới.
- `EnrollmentRequested` task gọi `SequencerService.enroll_lead` với `triggering_alert_rule_id=alert_rule.id`, `target_step_id` nếu có.
- Không tạo `AutomationRun` trong đường này.

### 9. Migration Number
- Head hiện tại: `224` (`224_add_unique_constraint_leads_value_hmac.py`); down_revision `94cfa0f6f5f9`. Dùng `225` hoặc revision ngẫu nhiên kế tiếp sau khi chạy `alembic revision --autogenerate`.

## Ghi chú cấu trúc dự án (Project Structure Notes)

- Các bảng mới phải nằm trong `nowing_backend/app/db.py` theo pattern Epic 21 (UUID `id`, Integer `workspace_id`, CITEXT `client_id`, composite PK/FK, RLS).
- `SequencerService` đặt tại `nowing_backend/app/services/sequencer_service.py` để tách khỏi `app/automations/` (AD-39: Sequence không phải Automation subtype).
- Celery tasks đặt tại `nowing_backend/app/automations/tasks/sequence_tasks.py` để tái sử dụng pattern task/include/beat của Epic 6.
- Routes đặt tại `nowing_backend/app/routes/sequence_routes.py`; schemas tại `nowing_backend/app/schemas/sequence.py`.
- Frontend components đặt tại `nowing_web/components/automations/`, pages dưới `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/` (UX hiện tại dùng route `/campaigns`; API dùng `/sequences`).
- Không tạo thêm `app/campaigns/` hoặc `app/drip/`; mọi code sequence phải dùng namespace `sequence_*`.

## Tham khảo (References)

- Epic 24 / Story 24.1: `_bmad-output/planning-artifacts/epics.md` dòng 3093–3121.
- AD-39, AD-41, AD-42, AD-43, AD-46, AD-48, AD-49: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` dòng 1125–1367.
- AD-25: `ARCHITECTURE-SPINE.md` dòng 692–705.
- AD-31, AD-45: `ARCHITECTURE-SPINE.md` dòng 766–785, 1284–1296.
- DEF-102: `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` dòng 298.
- PRD FR-66, FR-68, FR-69: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` dòng 585–615, 991–1008.
- UX Lead Intelligence Panel: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md` (Campaign/Sequences tab, Empty State, Channel CTA).
- UX Navigation: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md` dòng 37–38, 74.
- Code: `nowing_backend/app/db.py:4436` (`BillingEvent`), `4483` (`Lead`), `4999` (`VerifiedContact`).
- Code: `nowing_backend/app/services/workspace_credit_service.py:84` (`WorkspaceCreditService.deduct_credits`).
- Code: `nowing_backend/app/services/pii/verified_contact_encryption.py:37`, `nowing_backend/app/services/pii/redact.py:71`.
- Code: `nowing_backend/app/lead_intelligence/dnc/service.py:56` (`DncComplianceService`).
- Code: `nowing_backend/app/alerts/engine/notify.py:119` (`_send_email_smtp`), `nowing_backend/app/alerts/engine/execute.py:88` (`execute_alert_rule`), `nowing_backend/app/alerts/persistence/models/alert_rule.py:24`.
- Code: `nowing_backend/app/celery_app.py:180` (`include`), `290` (`beat_schedule`).
- Code: `nowing_backend/alembic/versions/224_add_unique_constraint_leads_value_hmac.py` (head); `94cfa0f6f5f9_fix_lead_tables_zero_sync_client_id_and_.py` (Zero client_id type downgrade).

## Lệnh xác minh (Verification Commands)

```bash
# Backend lint
cd nowing_backend
uv run ruff check app/db.py app/services/sequencer_service.py app/services/billing_event_service.py app/automations/tasks/sequence_tasks.py app/routes/sequence_routes.py app/schemas/sequence.py app/alerts/engine/execute.py

# Migrations
uv run alembic upgrade head

# Unit + integration tests
uv run pytest tests/unit/services/test_sequencer_service.py tests/unit/services/test_billing_event_service.py -q
uv run pytest tests/integration/services/test_sequence_scheduler.py -q

# Frontend typecheck & biome lint
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check app/dashboard/\[workspace_id\]/automations/campaigns/ components/automations/VisualCadenceBuilder.tsx lib/apis/sequence-api.service.ts
```

## Kinh nghiệm từ story trước (Previous Story Intelligence)

- **Story 24.2 (Waterfall Phone & MST):** Tái sử dụng `hash_phone_hmac`, `normalize_phone_e164`, DNC cache invalidation, và pattern `VerifiedContact`.
- **Story 24.3 (Team CRM & Shared Credit):** Dùng `WorkspaceCreditService.deduct_credits` và cột `version` OCC cho concurrency.
- **Story 11.1 (Telegram Notification Foundation):** Tái sử dụng notification dispatcher; mở rộng channel constants với `email_reply`, `email_delivered`, `email_bounced`.
- **Story 8.7 (Auto-Extract Spend Cap):** Spend-cap / wallet pre-check pattern; MVP chỉ cần `WorkspaceCreditService`.

## Dev Agent Record

### Agent Model Used
Gemini 3.7 Flash (High) / BMAD Context Engine

### File List
- `nowing_backend/alembic/versions/225_add_sequence_tables.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/services/sequencer_service.py`
- `nowing_backend/app/automations/tasks/sequence_tasks.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/app/schemas/sequence.py`
- `nowing_backend/app/routes/sequence_routes.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/alerts/engine/execute.py`
- `nowing_backend/app/gateway/zalo/webhook.py`
- `nowing_backend/app/gateway/telegram/callbacks.py`
- `nowing_backend/app/gateway/inbox_processor.py`
- `nowing_backend/app/notifications/types.py`
- `nowing_backend/app/notifications/constants.py`
- `nowing_backend/tests/unit/services/test_sequencer_service.py`
- `nowing_backend/tests/integration/services/test_sequence_scheduler.py`
- `nowing_web/contracts/types/sequence.types.ts`
- `nowing_web/lib/apis/sequence-api.service.ts`
- `nowing_web/components/automations/VisualCadenceBuilder.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/page.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/new/page.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/[sequence_id]/page.tsx`

## Challenge Log (grill-me)

Thực hiện: Grill Me 4 câu hỏi trên story 24.1.

### Q1 — Logic đã tồn tại?

Không tìm thấy bảng/service `Sequence*` trong backend.
- `AlertRule` đã có `target_sequence_id` / `target_step_id` (`nowing_backend/app/alerts/persistence/models/alert_rule.py:76-85`, từ Story 12.6). Không cần tạo lại trong migration 225.
- `Automation`/`AutomationRun` tồn tại (`nowing_backend/app/automations/persistence/models/...`) nhưng AD-39/ARCHITECTURE-SPINE cấm tái sử dụng schema; chỉ tái dùng pattern Celery/scheduler.
- Các helper sẵn có: `_send_email_smtp` (`app/alerts/engine/notify.py:118`), `DncComplianceService.is_blocked` (`app/lead_intelligence/dnc/service.py:220`), `BillingEventService`/`_record_business_event` (`app/services/billing_event_service.py:124`), `WorkspaceCreditService` (`app/services/workspace_credit_service.py:84`), `NotificationService` (`app/notifications/service/facade.py:24`), `celery_app` beat schedule (`app/celery_app.py:180,290`).

Verdict: **Không duplicate logic Sequence**, nhưng phải điều chỉnh migration để không tạo lại cột `AlertRule.target_sequence_id`.

### Q2 — Có alternative đơn giản hơn?

- Mở rộng `Automation`/`AutomationRun` để làm Sequence: bị từ chối rõ ràng bởi AD-39 (`AutomationRun.id` int, `TokenUsage.run_id` UUID; schema mismatch).
- Gọi `WorkspaceCreditService.deduct_credits` trực tiếp + tự tạo `BillingEvent`: `BillingEventService._record_business_event` đã gói idempotency, `record_spend`, `wallet_credit.apply_debit`, do đó thêm `record_sequence_send` là đúng pattern và ngắn hơn.
- Tự viết SMTP client mới: `_send_email_smtp` đã tồn tại, nên wrap bằng `asyncio.to_thread` (đúng như story ghi chú).

Verdict: **Không có alternative đơn giản hơn** mà không vi phạm AD-39.

### Q3 — Edge cases bị bỏ sót (Pattern 3)

- [ ] Boundary quiet hours: 08:00:00 và 21:30:00 là inclusive hay exclusive? `calculate_step_eta` cần rõ.
- [ ] `from_dt` timezone-naive/aware và default `None` xử lý thế nào?
- [ ] `condition` step: branch predicate không match thì đi bước nào? (default next step? exit?)
- [ ] Template variable missing: bỏ trống, giữ placeholder, hay raise?
- [ ] Lead có nhiều `VerifiedContact` email: chọn cái nào? (highest confidence / first / fail-closed)
- [ ] `Scheduled_at` trong quá khứ khi `evaluate_sequences` chạy: xử lý immediately hay reschedule?
- [ ] Idempotency khi Celery retry `execute_enrollment_step`: tránh duplicate `SequenceEvent.sent` và duplicate `BillingEvent`.
- [ ] Double `evaluate_sequences` Celery Beat: cần distributed lock để tránh double-dispatch.
- [ ] Redis lock TTL 10s cho `handle_inbound_interruption` không extend nếu operation chậm.
- [ ] Opt-out keyword matching: case-insensitive? tiếng Việt dấu? "hủy" vs "huy"? "unsubscribe"?

### Q4 — Failure modes chưa được định nghĩa (Pattern 2, 4)

- [x] **Resolved — Transaction boundary / money:** `record_sequence_send` phải là thao tác cuối cùng trong session sau khi `SequenceEvent` và `SequenceEnrollment` đã staged. `wallet_credit.apply_debit` gọi `session.commit()` bên trong (`wallet_credit.py:111`) nên tất cả các thay đổi được commit cùng lúc. Pre-check `wallet_credit.check_balance` trước khi gửi. Nếu gửi thành công nhưng `record_sequence_send` thất bại do cap/debit, mark `SequenceEvent(event_type='failed', event_subtype='billing_failed')` và để admin reconcile.
- [x] **Resolved — Retry duplicate billing:** `record_sequence_send` idempotent theo `sequence_event_id`: nếu `BillingEvent` đã tồn tại thì return existing row, không raise `ValueError`, để Celery retry an toàn.
- [ ] Postgres xuống / query `evaluate_sequences` lỗi: retry policy chưa rõ.
- [ ] Redis xuống khi acquire lock `handle_inbound_interruption`: fail open (vẫn xử lý) hay fail closed (bỏ qua)?
- [ ] SMTP timeout / connection error: `_send_email_smtp` không set timeout; các exception `smtplib.SMTPException`/`OSError` cần catch và log `SequenceEvent(event_type='failed')`.
- [ ] `WorkspaceCreditService.record_spend` raise `SpendCapExceededError` khi vượt cap: sequence pause, skip step, hay fail?
- [ ] `record_sequence_send` với `cost_micros=0`: `_record_business_event` vẫn tạo `BillingEvent` và `apply_debit` no-op. Có cần `BillingEvent` cho 0-cost?
- [ ] Feature flag `SEQUENCER_OUTBOUND_CHANNELS` chưa có trong `app.config` — cần định nghĩa.
- [ ] `client_id` CITEXT của `sequence_*` vs `Lead.client_id` text sau migration `94cfa0f6f5f9`: Composite FK `sequence_enrollments.lead_id` + `client_id` có thể mismatch kiểu. Cần quyết định rõ CITEXT/text tại thời điểm implement.

### Triage

| Finding | Severity | Action |
|---|---|---|
| `AlertRule.target_sequence_id` đã tồn tại | Non-critical | Sửa task migration, không thêm cột trùng |
| Quiet-hour / condition / template edge cases | Non-critical | Thêm vào test skeleton ở `test-first-atdd` |
| Transaction boundary `wallet_credit.apply_debit` commit sớm | **Resolved** | AC-6 + Dev Note 6: `record_sequence_send` gọi cuối cùng sau khi `SequenceEvent` và `SequenceEnrollment` đã staged; pre-check `wallet_credit.check_balance` trước khi gửi; nếu billing thất bại sau khi gửi thì mark `SequenceEvent.failed(event_subtype='billing_failed')`. |
| Retry duplicate `BillingEvent` | **Resolved** | `record_sequence_send` idempotent: return existing `BillingEvent` thay vì raise `ValueError`; Celery retry safe. |
| Redis lock / SMTP / Postgres failure modes | Non-critical | Thêm vào test skeleton và error-handling spec |

### Kết luận

Story 24.1 đã rõ ràng về bounded context và reuse helper. 2 critical gap liên quan billing transaction boundary và retry idempotency đã được clarify trong AC-6, Task 6, và Dev Note 6. Các vấn đề còn lại là edge cases / failure modes non-critical cần bổ sung vào test skeleton ở bước `test-first-atdd`. **Có thể tiếp tục pipeline.**

---

### Review Findings — Backend API / tests / migration chunk

Reviewers: Blind Hunter (adversarial) + Edge Case Hunter + Acceptance Auditor. Diff chunk: `3449a631e..105f7e1f8` restricted to migration 225, `sequence_routes.py`, `schemas/sequence.py`, `routes/__init__.py`, tests.

#### decision-needed
(đã giải quyết — chuyển thành patch bên dưới theo best practice AD-31)

#### patch
- [x] [Review][Patch] `client_id` kiểu `Text` thay vì `CITEXT` trên 5 bảng `sequence_*` — theo best practice AD-31, đổi sang `CITEXT` trong migration và ORM. Lưu ý: `leads.client_id` vẫn là `text` do Zero sync; nếu sau này cần composite FK sang `leads` thì phải migration đổi `leads.client_id` thành `CITEXT`. Location: `225_add_sequence_tables.py:67,87,113,136,169` / `app/db.py:6111,6159,6202,6236,6312`.

#### patch
- [x] [Review][Patch] `sequence_routes.py` gọi sai signature `check_workspace_access(auth_ctx, workspace_id)` — thiếu `session`, sẽ `TypeError` ở runtime ở tất cả 11 route. Mọi route khác trong repo gọi `check_workspace_access(session, auth, workspace_id)`. Location: `sequence_routes.py:56,121,144,183,277,304,330,348,366,392,415`.
- [x] [Review][Patch] `pause_sequence`/`resume_sequence` thiếu `set_request_tenant_context(session, auth_ctx, workspace_id)` — RLS client_id bị bypass. Location: `sequence_routes.py:330-337,348-355`.
- [x] [Review][Patch] `sequence_runs.triggering_alert_rule_id` thiếu FK `alert_rules.id` — AD-43 yêu cầu `AlertRule` là first-class table; bảng đã tồn tại. Location: `225_add_sequence_tables.py:115-121` / `app/db.py:6204`.
- [x] [Review][Patch] `sequence_enrollments` thiếu unique constraint `(workspace_id, sequence_id, lead_id)` — cho phép duplicate enrollment. Location: `225_add_sequence_tables.py:131-161` / `app/db.py:6231-6251`.
- [x] [Review][Patch] `create_sequence`/`update_sequence` không validate `step_order` duy nhất trong sequence — duplicate step_order gây undefined execution. Location: `sequence_routes.py:86-102` và `234-248`.
- [x] [Review][Patch] `SequenceCreate`/`SequenceUpdate` không validate `entry_step_order` tồn tại trong `steps`. Location: `sequence_routes.py:80-81,205-206`.
- [x] [Review][Patch] `schemas/sequence.py` dùng `str` thay vì `Literal`/enum cho `status`, `step_type`, `channel`, `event_type` — API chấp nhận giá trị không hợp lệ. Location: `schemas/sequence.py:13-15,50,62-64,99,116-118`.
- [x] [Review][Patch] `tests/integration/routes/test_sequence_routes.py` mock `check_workspace_access` và `set_request_tenant_context` — che giấu lỗi signature (#1). Cần thêm test integration không mock hoặc kiểm tra signature. Location: `tests/integration/routes/test_sequence_routes.py:58,117,161,210`.

#### notes / cross-chunk (not triaged in this chunk)
- `AC-7`/`AD-43` alert-driven enrollment được implement trong `app/alerts/engine/execute.py` (nằm ngoài chunk này) — finding "missing" là false positive do chunk hóa.
- Logic `handle_inbound_interruption`, `get_due_enrollments`, billing/commit, consent/DNC, PII redaction nằm trong `app/services/sequencer_service.py` (core chunk) — sẽ review ở chunk tiếp theo.
- `SequenceEventRead.event_metadata` vs cột DB `metadata` là mapping đúng (SQLAlchemy `Column("metadata", ...)` + Pydantic `populate_by_name=True`) — dismiss.

#### Patching log — 2026-08-17
- Đã apply toàn bộ 9 patch findings ở chunk 1.
- Verification: `ruff check` 0 errors; `pytest tests/integration/routes/test_sequence_routes.py` 4/4 pass; `pytest tests/unit/services/test_sequencer_service.py tests/integration/services/test_sequence_scheduler.py` 24/24 pass.
- Còn lại: review chunk 2 (`app/services/sequencer_service.py`, `app/services/billing_event_service.py`, `app/automations/tasks/sequence_tasks.py`) và chunk 3 (frontend) sẽ chạy tiếp.

#### Patching log — 2026-08-17 (chunk 2)
- Apply patch core:
  - `handle_inbound_interruption` tìm đúng `SequenceEnrollment` qua `VerifiedContact` thay vì chọn bừa (AC-5 / INV-24.7).
  - `enroll_lead` validate `lead.workspace_id == workspace_id`, chỉ cho phép `consent_status` trong `ENROLLABLE_CONSENT_STATUSES` và `legal_basis` hợp lệ (AC-4 / AD-25 / AD-49).
  - `get_due_enrollments` nhận `workspace_id` filter, `evaluate_pending_enrollments` query per-workspace trước khi dispatch (chống cross-workspace leak).
  - `_resolve_verified_contact` filter theo `channel` (email/phone) và chỉ lấy contact có trường tương ứng.
  - `_handle_condition_step` bổ sung `opened` / `delivered` vào context để condition branching đúng.
  - `execute_enrollment_step` set tenant context sau khi load enrollment; `execute_sequence_step` task set `workspace_id` GUC.
  - `_send_email_smtp` thêm `SMTP_TIMEOUT_SECONDS` config (default 30s).
- Tests: cập nhật `_FakeSession.execute` signature, `test_inbound_*` mock `_resolve_inbound_contact`, `test_evaluate_pending_enrollments` setup cho per-workspace query.
- Verification: `ruff check` 0 errors; `pytest tests/unit/services/test_sequencer_service.py tests/integration/services/test_sequence_scheduler.py tests/integration/routes/test_sequence_routes.py` 32/32 pass.
- Còn lại: chunk 3 frontend review nếu cần.

