---
story_key: "24-1"
epic: "epic-24"
story: "24.1"
title: "Multi-Channel Drip Outreach Campaign Engine (Sequence Backend — Email-first MVP)"
status: "ready-for-dev"
baseline_commit: "6ac305274"
---

# Story 24.1: Multi-Channel Drip Outreach Campaign Engine (Sequence Backend — Email-first MVP)

## Story Overview

As an enterprise sales team, growth marketer, or real-estate agency,  
I want to design, schedule, and execute automated multi-step outreach **Sequences** (Email in MVP; Zalo ZNS and Telegram reserved behind feature gates) with conditional delays, strict Vietnamese legal quiet-hour compliance (08:00 – 21:30 VN Time), and real-time opt-out/reply handling,  
So that high-intent leads generated across Nowing are nurtured automatically into qualified sales conversations without manual repetitive outreach or compliance violations.

> **Scope note (Critical):** This story implements the `Sequence` bounded context defined in AD-39, not a parallel `drip_campaigns` domain. Zalo ZNS and Telegram are **reserved but disabled in MVP** per AD-41 and the unified architecture DEF-102. To enable them, the team must run a `bmad-correct-course` / SCP to re-activate AD-41 first.

---

## Architectural Invariants (INV-AD-39, INV-AD-41, INV-AD-42, INV-AD-43, INV-AD-25, INV-AD-31, INV-24.1, INV-24.2, INV-24.7)

- **INV-AD-39 (Sequence Bounded Context):**
  - Backend domain BẮT BUỘC là `Sequence`, `SequenceStep`, `SequenceEnrollment`, `SequenceEvent`, `SequenceRun`. Không tạo `drip_campaigns` / `campaign_*` tables.
  - `Sequence` là bounded context riêng, **không phải subtype của Automation**.
  - Step type MVP: `send_email`, `wait`, `condition`. Các type `update_lead_score`, `update_crm`, `tag` được giữ trong enum nhưng có thể trả `501 Not Implemented` trong MVP.
  - `SequencerService` owns scheduling, execution, retry, idempotency — reuse Epic 6 Celery pattern.
  - `current_step` là `int` (`step_order`), không dùng UUID `current_step_id`.

- **INV-AD-41 (Channels Deferred out of MVP):**
  - **MVP channel: `email` only.**
  - `zalo`, `telegram`, `linkedin` được giữ trong enum nhưng service/UI từ chối với thông báo `deferred` cho đến khi feature flag bật.
  - Unified architecture DEF-102 xác nhận: *Direct Zalo OA Outbound messaging automation deferred to Sprint 3 post-Closed Beta.*
  - Để bật Zalo/Telegram, phải có quyết định SCP/correct-course mới.

- **INV-AD-42 (Billing Matrix & Wallet):**
  - `TokenUsage` chỉ dùng cho LLM tokens. Mọi sự kiện nghiệp vụ sequence BẮT BUỘC dùng `BillingEvent`.
  - Allowed matrix cho MVP:
    - `SequenceEvent.event_type == 'sent'` → `BillingEvent(event_entity_type='sequence_event', event_type='email_send')`.
    - `SequenceEvent.event_type == 'meeting_booked'` → `OutcomeEvent` + `BillingEvent(event_entity_type='outcome_event', event_type='outcome_meeting_booked')`.
  - Debit tiền **workspace** qua `WorkspaceCreditService.deduct_credits`, không gọi `wallet_credit.apply_debit` trực tiếp.

- **INV-AD-43 (Alert-driven Sequence Enrollment):**
  - Trigger `lead_created` / `lead_scored` BẮT BUỘC đi qua `AlertRule` với `target_sequence_id` (và `target_step_id` nếu cần).
  - Alert engine emit `EnrollmentRequested` event/Celery task; `SequencerService` tạo `SequenceRun` + `SequenceEnrollment`.
  - Không tạo `AutomationRun` cho sequence enrollment.

- **INV-AD-25 / AD-49 (Consent, PII & Redaction):**
  - Chỉ enroll `Lead` có `consent_status != 'none'` và `legal_basis` không null.
  - Dùng `VerifiedContact` làm nguồn PII duy nhất; kiểm tra `consent=True`, `is_valid=True`, `legal_basis` không null.
  - Mọi log, `SequenceEvent.metadata`, `BillingEvent` không chứa PII raw — redact qua `redact_pii(..., context='lead_enrichment')`.
  - Nếu tạo `Memory` từ `SequenceEvent`, set `source_uuid` + `source_entity_type='sequence_event'`.

- **INV-AD-31 (Multi-Tenant PK & RLS):**
  - Mọi bảng mới dùng Composite PK `(id, workspace_id)`, `client_id: CITEXT`, Composite FK, và `FORCE ROW LEVEL SECURITY` với predicate chuẩn:
    ```sql
    workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
    AND client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
    ```

- **INV-24.1 (Quiet Hours & Jitter):**
  - `SequencerService.calculate_step_eta(delay_seconds, from_dt)` tính toán trong timezone `Asia/Ho_Chi_Minh`.
  - Khung gửi: **08:00 – 21:30**. Nếu `target_dt` nằm ngoài, đẩy sang `08:05` ngày tiếp theo + `random(0, 1800)` giây jitter.

- **INV-24.2 (Opt-Out, DNC & ZNS Template Compliance):**
  - Mọi bước gửi BẮT BUỘC kiểm tra `DncComplianceService.is_blocked()` fail-closed trước khi gửi.
  - Khi nhận phản hồi / keyword (`STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE`), hệ thống ngắt sequence, tạo `WorkspaceDncRecord` với `value_hmac`, invalidate DNC cache, hủy các step sau.

- **INV-24.7 (Inbound Interruption & Distributed Concurrency Lock):**
  - `handle_inbound_interruption` dùng Redis lock `sequence:lock:enrollment:{workspace_id}:{enrollment_id}` (TTL 10s).
  - Atomic CAS update trên cột `version` của `SequenceEnrollment`:
    ```sql
    UPDATE sequence_enrollments SET status = :new_status, version = version + 1
    WHERE id = :id AND workspace_id = :workspace_id AND version = :version
    ```

---

## Acceptance Criteria

### 1. Visual Sequence Builder UI
- **Given** an authenticated workspace member,
- **When** the user navigates to `/dashboard/[workspace_id]/automations/campaigns/new`,
- **Then** the UI renders a visual node/timeline editor supporting:
  - Step type `send_email`: chọn template, map variables (`{customer_name}`, `{company}`, `{property_title}`, `{consultant_phone}`).
  - Step type `wait`: cấu hình `wait_duration` (e.g., `2 days` / `48 hours`).
  - Step type `condition`: cấu hình điều kiện rẽ nhánh đơn giản (e.g., "if replied then exit, else continue").
  - Channel selector chỉ hiển thị `email` trong MVP; `zalo`, `telegram`, `linkedin` bị vô hiệu hóa với tooltip "deferred".

### 2. Email-Only MVP & Channel Deferred Gate
- **Given** a sequence step with channel not `email`,
- **When** the backend attempts to execute it,
- **Then** `SequencerService` rejects with `422 DeferredChannelError` unless `SEQUENCER_OUTBOUND_CHANNELS` feature flag explicitly includes the channel.

### 3. Quiet Hours & Anti-Thundering Herd Scheduling
- **Given** an enrollment with next step due at 22:30 (outside 08:00 – 21:30 VN Time),
- **When** `calculate_step_eta()` computes dispatch time,
- **Then** it returns `08:05 + uniform(0, 1800s)` next morning.
- **When** Celery Beat runs `evaluate_sequences` every 1 minute,
- **Then** only `SequenceEnrollment` with `status = 'scheduled'` and `scheduled_at <= now()` are dispatched.

### 4. Consent & Legal Basis Gate
- **Given** a lead with `consent_status = 'none'` or missing `legal_basis`,
- **When** `SequencerService.enroll_lead()` is called,
- **Then** it logs `enrollment_rejected_consent` and does not create `SequenceEnrollment`.
- **Given** a send step,
- **When** no `VerifiedContact` with `consent=True`, `is_valid=True`, and matching channel value (email) exists,
- **Then** the step is skipped and logged as `skipped_no_consent`.

### 5. Inbound Interruption & Distributed Lock
- **Given** an active enrollment in state `scheduled` or `executing`,
- **When** an inbound event arrives (email reply, Zalo webhook, Telegram inbound) with opt-out keyword or reply,
- **Then** `SequencerService.handle_inbound_interruption()` acquires the Redis lock,
- **Then** performs CAS version update to `responded` or `unsubscribed`,
- **Then** if opt-out, creates `WorkspaceDncRecord(s)` with `value_hmac`, invalidates DNC cache, and aborts future steps.

### 6. Workspace Credit & Billing
- **Given** a billable `send_email` step,
- **When** the step is executed successfully,
- **Then** `WorkspaceCreditService.deduct_credits(workspace_id, attributed_user_id, cost_micros)` is called,
- **Then** `SequenceEvent(event_type='sent', channel='email', cost_micros=...)` is inserted,
- **Then** `BillingEvent(event_entity_type='sequence_event', event_type='email_send', event_id=sequence_event.id)` is inserted.
- **When** the send fails,
- **Then** no `BillingEvent` is created and `SequenceEvent(event_type='failed')` is inserted.

### 7. Alert-Driven Enrollment
- **Given** an `AlertRule` with `target_sequence_id` set and a signal matches,
- **When** the alert engine fires,
- **Then** it emits `EnrollmentRequested` Celery task,
- **Then** `SequencerService.enroll_lead()` creates a `SequenceRun` and `SequenceEnrollment`.

### 8. Sequence Analytics
- **Given** an existing sequence at `/dashboard/[workspace_id]/automations/campaigns/[id]`,
- **When** loading the analytics view,
- **Then** the backend returns `SequenceAnalyticsResponse` with `total_enrolled`, `active_scheduled`, `delivered_count`, `responded_count`, `unsubscribed_count`, `failed_count`, `total_cost_micros`.

---

## Technical Tasks

### 1. Database Schema & Alembic Migration
Create migration `nowing_backend/alembic/versions/225_add_sequence_tables.py` (Revises: current head — hiện tại là `224` / `94cfa0f6f5f9` sau khi resolve multiple heads):

- **`Sequence`**:
  - `id: UUID`, `workspace_id: Integer` (Composite PK `pk_sequence`)
  - `client_id: CITEXT | None` (FK `vertical_clients.client_id`)
  - `created_by_user_id: UUID | None` (FK `user.id`, ondelete="SET NULL")
  - `name: String(200)`, `status: String(50)` (`draft`, `active`, `paused`, `archived`)
  - `trigger_type: String(50)` (`manual`, `lead_created`, `lead_scored`)
  - `channel: String(50)` (default `email`; reserved `zalo`, `telegram`, `linkedin`)
  - `shared: Boolean` (default `false`)
  - `metadata_json: JSONB`, `created_at`, `updated_at`

- **`SequenceStep`**:
  - `id: UUID`, `workspace_id: Integer` (Composite PK `pk_sequence_steps`)
  - `sequence_id: UUID` (Composite FK `sequence(id, workspace_id)`, ondelete="CASCADE")
  - `step_order: Integer`, `step_type: String(50)` (`send_email`, `wait`, `condition`, `update_lead_score`, `update_crm`, `tag`)
  - `channel: String(50) | None` (MVP `email`; reserved future)
  - `template: String | None` (template ID / content reference)
  - `template_params: JSONB | None`
  - `wait_duration: Integer` (seconds, default 0)
  - `condition: JSONB | None` (condition/fallback rules)
  - `created_at`, `updated_at`

- **`SequenceEnrollment`**:
  - `id: UUID`, `workspace_id: Integer` (Composite PK `pk_sequence_enrollments`)
  - `sequence_id: UUID` (Composite FK `sequence(id, workspace_id)`, ondelete="CASCADE")
  - `lead_id: UUID` (Composite FK `leads(id, workspace_id)`, ondelete="CASCADE")
  - `triggering_lead_id: UUID | None`
  - `triggering_alert_rule_id: UUID | None` (nullable; FK to `alert_rules.id` khi table đã tồn tại)
  - `sequence_run_id: UUID | None` (Composite FK `sequence_run(id, workspace_id)`, ondelete="SET NULL")
  - `status: String(50)` (`enrolled`, `scheduled`, `executing`, `completed`, `responded`, `unsubscribed`, `failed`, `skipped_no_consent`, `skipped_unavailable_channel`)
  - `current_step: Integer` (default 1)
  - `scheduled_at: TIMESTAMP(timezone=True) | None`
  - `last_executed_at: TIMESTAMP(timezone=True) | None`
  - `version: Integer` (default 1, OCC)
  - `error_message: Text | None`
  - `created_at`, `updated_at`

- **`SequenceEvent`**:
  - `id: UUID`, `workspace_id: Integer` (Composite PK `pk_sequence_events`)
  - `enrollment_id: UUID` (Composite FK `sequence_enrollments(id, workspace_id)`, ondelete="CASCADE")
  - `sequence_id: UUID` (Composite FK `sequence(id, workspace_id)`, ondelete="CASCADE")
  - `step_id: UUID | None` (Composite FK `sequence_steps(id, workspace_id)`, ondelete="SET NULL")
  - `event_type: String(50)` (`sent`, `delivered`, `opened`, `replied`, `bounced`, `meeting_booked`, `failed`, `skipped`)
  - `channel: String(50)`
  - `cost_micros: BigInteger` (default 0)
  - `metadata: JSONB` (redacted — template_id, masked recipient, provider message id, status)
  - `created_at`

- **`SequenceRun`**:
  - `id: UUID`, `workspace_id: Integer` (Composite PK `pk_sequence_runs`)
  - `sequence_id: UUID` (Composite FK `sequence(id, workspace_id)`, ondelete="CASCADE")
  - `triggering_lead_id: UUID | None`
  - `triggering_alert_rule_id: UUID | None`
  - `status: String(50)` (`started`, `completed`, `failed`, `cancelled`)
  - `started_at`, `finished_at`, `created_at`, `updated_at`

- **Indexes**:
  - `ix_sequence_enrollments_sched: (workspace_id, status, scheduled_at)`
  - `ix_sequence_steps_order: (workspace_id, sequence_id, step_order)`

- **RLS**: `FORCE ROW LEVEL SECURITY` + policy chuẩn trên cả 5 bảng.

### 2. ORM Models
Update `nowing_backend/app/db.py` with the five models above.

### 3. Core Service — `SequencerService`
Create `nowing_backend/app/services/sequencer_service.py`:

- **`calculate_step_eta(delay_seconds: int, from_dt: datetime | None = None) -> datetime`**: Asia/Ho_Chi_Minh, quiet-hours deferral + jitter.
- **`enroll_leads(session, workspace_id, sequence_id, lead_ids, *, triggered_by_alert_rule_id=None, user_id=None) -> list[SequenceEnrollment]`**:
  - Lọc lead không đạt consent/legal basis.
  - Tạo `SequenceRun` cho batch.
  - Tạo `SequenceEnrollment` với `current_step=1`, `scheduled_at=calculate_step_eta(0)`.
- **`enroll_lead(session, workspace_id, sequence_id, lead_id, *, triggering_alert_rule_id=None, sequence_run_id=None) -> SequenceEnrollment`**: single enrollment.
- **`evaluate_pending_enrollments(session)`**: query due enrollments and dispatch `execute_sequence_step` Celery tasks.
- **`execute_enrollment_step(session, enrollment_id, workspace_id)`**:
  - Acquire Redis lock.
  - CAS update `version` from `scheduled` -> `executing`.
  - Load current `SequenceStep` by `step_order == enrollment.current_step`.
  - If `step_type == 'wait'`: advance `current_step`, compute next `scheduled_at`, set `scheduled`.
  - If `step_type == 'send_email'`:
    - Check `Lead`/`VerifiedContact` consent.
    - Resolve email via `VerifiedContactEncryption.decrypt_contact`.
    - Check DNC.
    - Verify channel is allowed (MVP email only).
    - Call `WorkspaceCreditService.deduct_credits` for `cost_micros`.
    - Render subject/body from `template` + `template_params` (redacted in logs).
    - Send via `asyncio.to_thread(_send_email_smtp, ...)`.
    - Insert `SequenceEvent('sent'/'failed'/'bounced'/'skipped')`.
    - Insert `BillingEvent('sequence_event', 'email_send')` on success.
    - Advance `current_step`, compute next `scheduled_at`, set `scheduled` or `completed`.
  - If `step_type == 'condition'`: evaluate JSON condition, decide next `current_step`.
- **`handle_inbound_interruption(session, workspace_id, *, phone=None, email=None, text=None, channel=None)`**:
  - Detect opt-out keywords.
  - Find active `SequenceEnrollment(s)` by `lead -> verified_contacts` or direct match.
  - Redis lock + CAS version update.
  - Create `WorkspaceDncRecord` with `value_hmac`.
  - Invalidate DNC cache.
  - Update enrollment to `unsubscribed`/`responded` and cancel future steps.
- **`get_sequence_analytics(session, workspace_id, sequence_id) -> dict`**: aggregate metrics.

### 4. Celery Tasks & Beat Schedule
Create `nowing_backend/app/automations/tasks/sequence_tasks.py`:

```python
@celery_app.task(name="evaluate_sequences")
def evaluate_sequences_task() -> None:
    return run_async_celery_task(_evaluate_impl)

@celery_app.task(name="execute_sequence_step", bind=True, max_retries=3)
def execute_sequence_step_task(self, enrollment_id: str, workspace_id: int) -> None:
    return run_async_celery_task(
        lambda: _execute_step_impl(UUID(enrollment_id), workspace_id)
    )
```

Update `nowing_backend/app/celery_app.py`:
- Add `app.automations.tasks.sequence_tasks` vào `include`.
- Add `evaluate_sequences` vào `beat_schedule` mỗi 1 phút.
- Add `execute_sequence_step` vào `task_routes` (default queue nếu cần).

### 5. REST API Routes & Schemas
- `nowing_backend/app/schemas/sequence.py`: `SequenceCreate`, `SequenceUpdate`, `SequenceRead`, `SequenceStepCreate`, `SequenceStepRead`, `SequenceEnrollRequest`, `SequenceAnalyticsResponse`.
- `nowing_backend/app/routes/sequence_routes.py`:
  - `POST /api/v1/workspaces/{workspace_id}/sequences`
  - `GET /api/v1/workspaces/{workspace_id}/sequences`
  - `GET /api/v1/workspaces/{workspace_id}/sequences/{id}`
  - `PUT /api/v1/workspaces/{workspace_id}/sequences/{id}`
  - `POST /api/v1/workspaces/{workspace_id}/sequences/{id}/enroll`
  - `POST /api/v1/workspaces/{workspace_id}/sequences/{id}/pause`
  - `POST /api/v1/workspaces/{workspace_id}/sequences/{id}/resume`
  - `GET /api/v1/workspaces/{workspace_id}/sequences/{id}/analytics`
- Register in `nowing_backend/app/routes/__init__.py` (no changes needed in `app.py` since it includes the aggregated `crud_router`).

### 6. Inbound Webhook & Notification Integration
- `nowing_backend/app/gateway/zalo/webhook.py`: forward opt-out/reply events to `SequencerService.handle_inbound_interruption`.
- `nowing_backend/app/gateway/telegram/callbacks.py` (hoặc webhook route nếu có): forward to `SequencerService.handle_inbound_interruption`.
- Email: add `email_reply`, `email_delivered`, `email_bounced` to the notification channel enum/constants and route inbound email events via the Story 11.1 notification dispatcher to `SequencerService`.
- `nowing_backend/app/gateway/inbox_processor.py`: route inbound text events to `SequencerService` when applicable.

### 7. Frontend UI
- `nowing_web/contracts/types/sequence.types.ts`
- `nowing_web/lib/apis/sequence-api.service.ts`
- `nowing_web/components/automations/VisualCadenceBuilder.tsx`:
  - Step type selector: `send_email`, `wait`, `condition`.
  - Channel dropdown: `email` enabled; `zalo`/`telegram`/`linkedin` disabled with "deferred" tooltip.
  - Template variable mapper.
- Pages:
  - `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/page.tsx` (list)
  - `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/new/page.tsx` (builder)
  - `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/[sequence_id]/page.tsx` (analytics)
  - *(Optional: rename `campaigns` -> `sequences` để đồng bộ; nếu giữ `campaigns`, add route alias hoặc gọi API `/sequences` từ page `campaigns`.)*

### 8. Tests
- `nowing_backend/tests/unit/services/test_sequencer_service.py`
- `nowing_backend/tests/integration/services/test_sequence_scheduler.py`

---

## Dev Notes & Architecture Guardrails

### 1. Existing Services to Reuse
- **Email SMTP:** `_send_email_smtp` from `app.alerts.engine.notify` (sync, wrap with `asyncio.to_thread`).
- **DNC:** `DncComplianceService` từ `app.lead_intelligence.dnc.service`; `hash_phone_hmac` / `normalize_phone_e164` từ `app.lead_intelligence.dnc.normalizer`.
- **PII Encryption:** `VerifiedContactEncryption` từ `app.services.pii.verified_contact_encryption` để decrypt contact fields; `redact_pii` từ `app.services.pii.redact` cho log/metadata.
- **Workspace Credit:** `WorkspaceCreditService` từ `app.services.workspace_credit_service`.
- **Billing Ledger:** `BillingEvent` ORM model; tham khảo `app.services.billing_event_service` cho pattern ghi ledger.
- **Celery Async Helper:** `run_async_celery_task` / `get_celery_session_maker` từ `app.tasks.celery_tasks`.
- **Redis:** `get_redis_client` từ `app.redis_client`.

### 2. Quiet Hours Formula (Asia/Ho_Chi_Minh)
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

### 3. Redis Distributed Lock + Optimistic CAS
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

### 4. Inbound Opt-Out DNC Registration
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

### 5. Billing & Credit Flow
```python
# 1. Pre-check / debit workspace
attributed_user_id = sequence.created_by_user_id or workspace.user_id
credit_result = await WorkspaceCreditService(session=session).deduct_credits(
    workspace_id=workspace_id,
    user_id=attributed_user_id,
    amount_micros=cost_micros,
    description=f"Sequence {sequence.id} step {step.step_order}",
)

# 2. Send email
...

# 3. Record event & billing
sequence_event = SequenceEvent(
    workspace_id=workspace_id,
    client_id=client_id,
    enrollment_id=enrollment.id,
    sequence_id=sequence.id,
    step_id=step.id,
    event_type="sent",
    channel="email",
    cost_micros=cost_micros,
    metadata={"template_id": step.template, "recipient": redacted_email, "provider_msg_id": msg_id},
)
session.add(sequence_event)
session.add(BillingEvent(
    workspace_id=workspace_id,
    client_id=client_id,
    user_id=attributed_user_id,
    event_entity_type="sequence_event",
    event_type="email_send",
    event_id=sequence_event.id,
    cost_micros=cost_micros,
    currency="USD",
    cost_basis="actual",
))
```

### 6. Consent / Legal Basis Pre-Check
```python
if lead.consent_status == "none" or not lead.legal_basis:
    logger.info("Rejecting enrollment: lead %s lacks consent/legal basis", lead.id)
    return None

contact = await _resolve_verified_contact(session, lead, channel="email")
if not contact or not contact.consent or not contact.legal_basis:
    logger.info("Skipping step: no consented contact for lead %s", lead.id)
    return SequenceEvent(..., event_type="skipped", event_subtype="no_consent")
```

### 7. AlertRule Integration (Deferred if table not ready)
If `alert_rules` table chưa tồn tại:
- Giữ `triggering_alert_rule_id` là nullable UUID không FK.
- Tạo follow-up migration hoặc task để add FK sau khi Story 12.6 / Epic 6 alert engine hoàn thành.
- Implement trigger `lead_created` / `lead_scored` bằng cách listen vào `Lead` / `LeadScore` post-commit events hoặc webhook tạm thời, rồi chuyển sang `AlertRule` khi có.

### 8. Migration Number
- Không dùng `224` (đã có `224_add_unique_constraint_leads_value_hmac.py`).
- Dùng `225` hoặc next free revision sau `alembic heads`.

---

## Verification Commands

```bash
# Backend lint
uv run ruff check app/db.py app/services/sequencer_service.py app/automations/tasks/sequence_tasks.py app/routes/sequence_routes.py app/schemas/sequence.py

# Migrations
uv run alembic upgrade head

# Unit + integration tests
uv run pytest tests/unit/services/test_sequencer_service.py -q
uv run pytest tests/integration/services/test_sequence_scheduler.py -q

# Frontend typecheck & biome lint
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check app/dashboard/\[workspace_id\]/automations/campaigns/ components/automations/VisualCadenceBuilder.tsx lib/apis/sequence-api.service.ts
```

---

## Previous Story Intelligence

- **Story 24.2 (Waterfall Phone & MST):** Reuse `hash_phone_hmac`, `normalize_phone_e164`, DNC cache/invalidation, and `VerifiedContact` patterns.
- **Story 24.3 (Team CRM & Shared Credit):** Use `WorkspaceCreditService.deduct_credits` and OCC `version` column for concurrency.
- **Story 11.1 (Telegram Notification Foundation):** Reuse notification dispatcher; extend channel constants with `email_reply`, `email_delivered`, `email_bounced`.
- **Story 8.7 (Auto-Extract Spend Cap):** Spend-cap / wallet pre-check pattern can inspire budget-aware throttling, but MVP only needs `WorkspaceCreditService`.

---

## Dev Agent Record

### Agent Model Used
Gemini 3.7 Flash (High) / BMad Context Engine

### File List
- `nowing_backend/alembic/versions/225_add_sequence_tables.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/services/sequencer_service.py`
- `nowing_backend/app/automations/tasks/sequence_tasks.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/app/schemas/sequence.py`
- `nowing_backend/app/routes/sequence_routes.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/gateway/zalo/webhook.py`
- `nowing_backend/app/gateway/telegram/callbacks.py`
- `nowing_backend/app/gateway/inbox_processor.py`
- `nowing_backend/app/notifications/constants.py`
- `nowing_backend/tests/unit/services/test_sequencer_service.py`
- `nowing_backend/tests/integration/services/test_sequence_scheduler.py`
- `nowing_web/contracts/types/sequence.types.ts`
- `nowing_web/lib/apis/sequence-api.service.ts`
- `nowing_web/components/automations/VisualCadenceBuilder.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/page.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/new/page.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/[sequence_id]/page.tsx`
