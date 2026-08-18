---
story_key: "24-7"
epic: "epic-24"
story: "24.7"
title: "Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence)"
status: "ready-for-dev"
baseline_commit: "4c37acfa9"
---

# Story 24.7: Mở rộng Sequence đa kênh (Zalo ZNS + Telegram + Email Cadence)

## Story Overview

As an enterprise sales team, agency, or growth marketer,
I want to design and launch multi-channel automated drip Sequences (Zalo ZNS, Telegram Bot, and Email) with conditional delays, strict compliance rules, and template variable personalization,
So that high-intent leads discovered across Nowing are automatically nurtured into booked appointments and qualified opportunities without manual repetitive outreach.

> **Scope note (split from 24.1):** Story này **mở rộng bounded context `Sequence` đã có** từ Story 24.1 (`done`), **KHÔNG** tạo thêm bảng `drip_campaigns` / `campaign_*` song song. Story 24.1 đã ship `Sequence` với channel `email` duy nhất và các kênh `zalo`/`telegram` bị tắt sau feature gate `SEQUENCER_OUTBOUND_CHANNELS` (AD-41). Story 24.7 kích hoạt `zalo` và `telegram`, thêm fallback giữa các kênh, và mở rộng inbound interruption cho webhook Zalo/Telegram.
>
> **Gate trước khi merge:** Theo DEF-102, team bắt buộc chạy `bmad-correct-course` / SCP để kích hoạt lại AD-41 và đóng legal/ToS/ZNS-template gates trước khi bật `zalo` trên production.

## Kiến trúc ràng buộc (Architectural Invariants)

- **AD-39 — Sequence bounded context:**
  `Sequence` là bounded context riêng, không phải subtype của `Automation`. Story 24.7 chỉ mở rộng `SequenceStep`, `SequenceEvent`, `SequencerService` — không tạo bảng mới.

- **AD-41 — Channels deferred out of MVP (gate):**
  Các kênh `zalo` / `telegram` bị tắt theo mặc định. UI/sequencer chỉ cho phép kênh khi `SEQUENCER_OUTBOUND_CHANNELS` config chứa kênh đó. Nếu không, `SequencerService.validate_step_channel()` raise `DeferredChannelError` (422).

- **AD-42/AD-48 — Billing matrix:**
  `TokenUsage` chỉ dành cho LLM token. Mọi sự kiện nghiệp vụ sequence dùng `BillingEvent`. Ma trận cho phép:
  - `SequenceEvent.event_type == 'sent', channel == 'email'` → `BillingEvent(event_entity_type='sequence_event', event_type='email_send')`.
  - `SequenceEvent.event_type == 'sent', channel == 'zalo'` → `BillingEvent(event_entity_type='sequence_event', event_type='zns_send')`.
  - `SequenceEvent.event_type == 'sent', channel == 'telegram'` → `BillingEvent(event_entity_type='sequence_event', event_type='telegram_send')` (cost 0 hoặc cấu hình).
  - `SequenceEvent.event_type == 'meeting_booked'` → tạo `OutcomeEvent` + `BillingEvent(event_entity_type='outcome_event', event_type='outcome_meeting_booked')`.

- **AD-43 — Alert-driven sequence enrollment:**
  `AlertRule` là first-class table. `SequencerService.enroll_lead()` tạo `SequenceRun` + `SequenceEnrollment`. Không tạo `AutomationRun`.

- **AD-25 / AD-49 — Consent, PII & Redaction:**
  Chỉ gửi cho `Lead` có `consent_status` cho phép và `legal_basis` không null. `VerifiedContact` là nguồn PII duy nhất; kiểm tra `consent=True`, `is_valid=True`. Mọi log, `SequenceEvent.event_metadata`, `BillingEvent` không chứa PII raw — redact qua `redact_pii(..., context='lead_enrichment')`.

- **AD-31 / AD-45 — Multi-tenant PK & `client_id`:**
  Không thay đổi cấu trúc PK/FK/RLS của `sequence_*`. `client_id: CITEXT` dùng chuẩn Nowing.

- **INV-24.1 — Quiet hours & Jitter:**
  `SequencerService.calculate_step_eta()` tính theo `Asia/Ho_Chi_Minh`. Khung gửi: **08:00 – 21:30**. Nếu `target_dt` ngoài khung, đẩy sang **08:05 ngày tiếp theo + `random(0, 1800)` giây jitter**. Với `zalo`, `ZnsClient.send_zns_template()` cũng có time-gate riêng; `SequencerService` phải bắt `ZnsTimeWindowViolationError` và reschedule thay vì fail.

- **INV-24.2 — Opt-Out, DNC & ZNS Template Compliance:**
  Mọi bước gửi bắt buộc kiểm tra `DncComplianceService.is_blocked()` fail-closed. Zalo ZNS bắt buộc dùng `template_id` đã được VNG phê duyệt. Nhận phản hồi `STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE` → ngắt sequence, tạo `WorkspaceDncRecord` với `value_hmac`, invalidate DNC cache, hủy các bước sau.

- **INV-24.7 — Inbound interruption & distributed concurrency lock:**
  `handle_inbound_interruption` dùng Redis lock `sequence:lock:enrollment:{workspace_id}:{enrollment_id}` (TTL 10s) và CAS update trên cột `version` của `SequenceEnrollment`.

## Acceptance Criteria

### AC-1 — Multi-Channel Cadence Builder UI
- **Given** workspace member đã xác thực,
- **When** user mở `/dashboard/[workspace_id]/automations/campaigns/new`,
- **Then** UI hiển thị `VisualCadenceBuilder` với channel selector cho phép chọn `email`, `zalo` (ZNS), `telegram` khi kênh nằm trong `SEQUENCER_OUTBOUND_CHANNELS`; kênh bị tắt hiển thị tooltip "deferred".
- **Then** mỗi step bao gồm:
  - `channel`: `email` | `zalo` | `telegram`.
  - `template`:
    - `email`: `subject`, `body`, variable mapping.
    - `zalo`: `template_id` (pre-approved), `template_data` mapping.
    - `telegram`: `text`, `parse_mode` (MarkdownV2/HTML), variable mapping.
  - `fallback_channels`: danh sách kênh dự phòng theo thứ tự ưu tiên (ví dụ `["telegram", "email"]` cho step `zalo`).
  - `wait_duration_seconds` và `condition_config` như hiện tại.

### AC-2 — Feature-Flag Channel Validation
- **Given** `SEQUENCER_OUTBOUND_CHANNELS` config là `email` (mặc định),
- **When** backend cố gắng thực thi step có `channel=zalo`,
- **Then** `SequencerService.validate_step_channel()` từ chối với `422 DeferredChannelError`.
- **Given** config là `email,zalo,telegram`,
- **When** thực thi các kênh trên,
- **Then** cho phép và điều phối đến handler tương ứng.

### AC-3 — Quiet Hours & Anti-Thundering Herd Scheduling
- **Given** enrollment có bước tiếp theo đến hạn lúc 22:30 (ngoài 08:00 – 21:30 VN Time),
- **When** `calculate_step_eta()` tính thời gian gửi,
- **Then** trả về `08:05 + uniform(0, 1800s)` sáng hôm sau.
- **When** `ZnsClient.send_zns_template()` raise `ZnsTimeWindowViolationError` (ví dụ worker chạy ngoài khung),
- **Then** `SequencerService` bắt exception, tính lại `scheduled_at` theo quiet hours, và ghi `SequenceEvent(event_type='failed', event_subtype='time_window_violation')` không tạo `BillingEvent`.

### AC-4 — Consent & DNC Pre-Check Đa Kênh
- **Given** step `zalo` hoặc `telegram`,
- **When** `SequencerService` chuẩn bị gửi,
- **Then**:
  1. Kiểm tra `lead.consent_status` và `lead.legal_basis`.
  2. Kiểm tra `VerifiedContact` phù hợp kênh (`phone` cho `zalo`, `telegram_chat_id` hoặc `phone` cho `telegram`) có `consent=True`, `is_valid=True`.
  3. Gọi `DncComplianceService.is_blocked()` với `phone` (fail-closed).
  4. Nếu thiếu consent hoặc DNC block, ghi `SequenceEvent(event_type='skipped', event_subtype='no_consent' | 'dnc_blocked')` và chuyển bước tiếp theo.

### AC-5 — Multi-Channel Send with Fallback
- **Given** step `zalo` với `fallback_channels = ["telegram", "email"]` và lead có đủ thông tin,
- **When** `ZnsClient.send_zns_template()` trả về lỗi permanent (`phone_not_registered`, `rate_limit`, hoặc `ZnsTimeWindowViolationError` ngoài khung),
- **Then** `SequencerService` thử kênh tiếp theo trong `fallback_channels`:
  - `telegram`: gửi qua `TelegramAdapter.send_message` với token từ `ExternalChatAccount` (platform=telegram) của workspace.
  - `email`: gửi qua `_send_email_smtp`.
- **Then** nếu tất cả kênh đều unavailable, ghi `SequenceEvent(event_type='failed', event_subtype='all_channels_unavailable')`.

### AC-6 — Zalo ZNS Send & Billing
- **Given** billable `send` step `channel=zalo`,
- **When** `SequencerService` thực thi,
- **Then** trước khi gọi `ZnsClient`:
  1. Xác định `attributed_user_id = sequence.created_by_user_id hoặc workspace.user_id`.
  2. Pre-check số dư ví `wallet_credit.check_balance(session, attributed_user_id, cost_micros)`.
  3. Chuẩn hóa phone E.164 qua `normalize_phone_e164()`.
- **When** gọi `ZnsClient.send_zns_template()`,
- **Then** truyền `cost_micros=0` và `user_id=None` để `ZnsClient` không tự debit wallet/tạo `BillingEvent` (tránh duplicate ledger).
- **When** Zalo API trả về thành công,
- **Then** tạo `SequenceEvent(event_type='sent', channel='zalo', cost_micros=..., provider_msg_id=..., event_metadata={template_id, recipient_phone_redacted})` và gọi `BillingEventService.record_sequence_send(..., event_type='zns_send')` để ghi ledger + debit wallet + enforce per-seat cap.
- **When** gọi thất bại,
- **Then** không tạo `BillingEvent`; fallback hoặc ghi `SequenceEvent(event_type='failed')`.

### AC-7 — Telegram Bot Send & Billing
- **Given** step `channel=telegram`,
- **When** `SequencerService` thực thi,
- **Then** tìm `ExternalChatAccount` của workspace với `platform=telegram`, lấy token qua `account_token()`, khởi tạo `TelegramAdapter(token)`, và gọi `send_message(external_peer_id=recipient_telegram_chat_id, text=interpolated_text, parse_mode=...)`.
- **Then** tạo `SequenceEvent(event_type='sent', channel='telegram', cost_micros=cost_telegram, provider_msg_id=external_message_id)`.
- **Then** gọi `BillingEventService.record_sequence_send(..., event_type='telegram_send')`. `cost_micros` mặc định `0` trừ khi cấu hình giá khác.
- **When** gửi thất bại do `RetryAfter`,
- **Then** Celery task retry theo exponential backoff; không tính là permanent failure.

### AC-8 — Inbound Interruption from Zalo & Telegram
- **Given** enrollment đang ở trạng thái `scheduled` hoặc `executing`,
- **When** inbound webhook từ Zalo OA hoặc Telegram Bot chứa reply hoặc opt-out keyword (`STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE`),
- **Then** handler gọi `SequencerService.handle_inbound_interruption()` với `channel`, `phone`, `email`, `text`.
- **Then** `handle_inbound_interruption` acquire Redis lock, thực hiện CAS version update sang `responded` hoặc `unsubscribed`.
- **Then** nếu opt-out, tạo `WorkspaceDncRecord` với `value_hmac`, invalidate DNC cache, hủy các bước tương lai.

### AC-9 — Per-Channel Analytics
- **Given** sequence đã tồn tại tại `/dashboard/[workspace_id]/automations/campaigns/[id]`,
- **When** mở analytics view,
- **Then** backend trả `SequenceAnalyticsResponse` với `total_enrolled`, `active_scheduled`, `delivered_count`, `responded_count`, `unsubscribed_count`, `failed_count`, `total_cost_micros`, và breakdown theo `channel`.

## Công việc / Subtasks

### 1. Config & Feature Flag
- [ ] Thêm `SEQUENCER_OUTBOUND_CHANNELS` vào `nowing_backend/app/config/__init__.py` (hoặc nơi tương ứng) với default `"email"`. Có thể override qua env var.
- [ ] Cập nhật `nowing_backend/app/services/sequencer_service.py` `ALLOWED_OUTBOUND_CHANNELS` để fallback về config.

### 2. Database Schema (nếu cần)
- [ ] Migration bổ sung cột vào `verified_contacts` hoặc tạo bảng `sequence_contact_channels`:
  - `telegram_chat_id` (String, nullable).
  - `zalo_user_id` / `zalo_phone` (String, nullable).
  - `channel` + `external_peer_id` để lưu recipient ID cho từng kênh.
  - Hoặc thêm trực tiếp `telegram_chat_id` và `zalo_user_id` vào `verified_contacts` nếu không phá vỡ RLS/Zero.
- [ ] Nếu dùng JSONB `template`, thêm `fallback_channels` vào schema `SequenceStep` mà không cần migration riêng (`template` đã là JSONB).

### 3. Schema Mở Rộng
- [ ] `nowing_backend/app/schemas/sequence.py`:
  - `SequenceChannel = Literal["email", "zalo", "telegram"]`.
  - `SequenceStepType = Literal["send_email", "send_zalo", "send_telegram", "wait", "condition", ...]`.
  - `SequenceStepBase.template` hỗ trợ `template_id` (ZNS), `template_data`, `fallback_channels`, `parse_mode`.
  - `SequenceEventRead.channel` chấp nhận `email` | `zalo` | `telegram`.
  - `SequenceAnalyticsResponse` thêm `channel_breakdown: dict[str, int] | None` (optional).

### 4. Core Service — `SequencerService`
- [ ] `nowing_backend/app/services/sequencer_service.py`:
  - Mở rộng `validate_step_channel` đọc `SEQUENCER_OUTBOUND_CHANNELS` từ config.
  - Refactor `_handle_send_email_step` thành `_handle_send_step` với dispatch theo `step.channel`.
  - Thêm `_handle_zns_step`, `_handle_telegram_step`.
  - Thêm `_attempt_fallback(step, enrollment, failed_channel, exception)`.
  - Mở rộng `_resolve_verified_contact` để trả về `phone`, `email`, `telegram_chat_id`, `zalo_user_id`.
  - Cập nhật `handle_inbound_interruption` để xử lý `channel` từ Zalo/Telegram.
  - Cập nhật `calculate_step_eta` không đổi.

### 5. Billing Event Service
- [ ] `nowing_backend/app/services/billing_event_service.py`:
  - Mở rộng `record_sequence_send` thêm tham số `event_type: str = "email_send"` để hỗ trợ `"zns_send"`, `"telegram_send"`.
  - Đảm bảo vẫn idempotent theo `sequence_event_id`.

### 6. Zalo ZNS Integration
- [ ] Tái sử dụng `app.gateway.zalo.zns_client.ZnsClient.send_zns_template()`.
- [ ] Từ `SequencerService`, gọi với `cost_micros=0` và `user_id=None` để tránh duplicate ledger.
- [ ] Bắt `ZnsTimeWindowViolationError` để reschedule (không tính là permanent failure cần fallback, trừ khi ngoài quiet hours kéo dài).
- [ ] Bắt `ZnsDncViolationError`, `ZnsDispatchError` để quyết định fallback hoặc skip.

### 7. Telegram Bot Integration
- [ ] Tìm `ExternalChatAccount` của workspace (`platform=telegram`) qua service/registry.
- [ ] Khởi tạo `TelegramAdapter(token)` hoặc `TelegramClient(token)`.
- [ ] Gọi `send_message(external_peer_id=telegram_chat_id, text=..., parse_mode=...)`.
- [ ] Xử lý `RetryAfter` bằng Celery retry; `BadRequest` do parse mode → fallback sang plain text.

### 8. Inbound Webhook Integration
- [ ] `nowing_backend/app/gateway/zalo/webhook.py`:
  - Gọi `SequencerService.handle_inbound_interruption()` khi nhận reply/opt-out từ prospect đã enroll vào sequence.
- [ ] `nowing_backend/app/gateway/telegram/callbacks.py` (hoặc `app/gateway/inbox_processor.py`):
  - Parse `ParsedInboundEvent` từ `TelegramAdapter.parse_inbound()`.
  - Gọi `handle_inbound_interruption` với `channel='telegram'`, `external_peer_id`, `text`.

### 9. Celery Tasks
- [ ] Không cần tạo task mới. `execute_sequence_step` và `evaluate_sequences` trong `nowing_backend/app/automations/tasks/sequence_tasks.py` đã sẵn sàng. Có thể cần cập nhật `max_retries` / retry backoff cho Telegram.

### 10. Frontend UI
- [ ] `nowing_web/contracts/types/sequence.types.ts`:
  - Cập nhật `SequenceChannel`, `SequenceStepType`, `SequenceStep['template']`.
- [ ] `nowing_web/lib/apis/sequence-api.service.ts`: không đổi endpoint.
- [ ] `nowing_web/components/automations/VisualCadenceBuilder.tsx`:
  - Bật channel selector theo `SEQUENCER_OUTBOUND_CHANNELS`.
  - Thêm ZNS template ID picker, template variable mapper cho Zalo.
  - Thêm Telegram message composer, parse mode selector.
  - Thêm fallback channel ordering UI.
- [ ] Cập nhật Playwright test `tests/automations/campaign-sequence-builder.spec.ts`.

### 11. Tests
- [ ] `nowing_backend/tests/unit/services/test_sequencer_service.py`: unit test `_handle_send_step` với mock `ZnsClient` và `TelegramAdapter`.
- [ ] `nowing_backend/tests/integration/services/test_sequence_scheduler.py`: integration test quiet hours, fallback.
- [ ] Frontend typecheck & biome.

## Dev Notes & Architecture Guardrails

### 1. Existing Services to Reuse
- **Zalo ZNS:** `ZnsClient.send_zns_template()` trong `nowing_backend/app/gateway/zalo/zns_client.py:156`. Đã có time-gate, DNC check, wallet pre-check, template schema validation, `BillingEvent` nội bộ. Khi gọi từ `SequencerService`, truyền `cost_micros=0` và `user_id=None` để tránh duplicate ledger.
- **Telegram Bot:** `TelegramAdapter.send_message()` trong `nowing_backend/app/gateway/telegram/adapter.py:148` sử dụng `TelegramClient` (`python-telegram-bot>=22.7`). Token lấy từ `ExternalChatAccount` qua `app/gateway/registry.py:resolve_platform_bundle` hoặc `app/gateway/accounts.py:account_token`.
- **DNC:** `DncComplianceService.is_blocked()` trong `nowing_backend/app/lead_intelligence/dnc/service.py:56` fail-closed. Dùng `hash_phone_hmac`, `normalize_phone_e164`, `normalize_email` từ `app/lead_intelligence/dnc/normalizer.py`.
- **PII Encryption:** `VerifiedContactEncryption` trong `nowing_backend/app/services/pii/verified_contact_encryption.py:37` để giải mã PII; `redact_pii(..., context='lead_enrichment')` trong `app/services/pii/redact.py:71` cho log/metadata.
- **Billing Ledger:** `BillingEventService.record_sequence_send()` trong `nowing_backend/app/services/billing_event_service.py:93`. Cần mở rộng `event_type` để hỗ trợ `zns_send`/`telegram_send`.
- **Wallet Credit:** `wallet_credit.check_balance()` và `wallet_credit.apply_debit()` trong `nowing_backend/app/services/wallet_credit.py:50`. `apply_debit` gọi `session.commit()` bên trong, nên `BillingEventService.record_sequence_send` phải là thao tác cuối cùng trong session.
- **Workspace Credit Pool:** `WorkspaceCreditService.record_spend()` trong `nowing_backend/app/services/workspace_credit_service.py:294` được `BillingEventService._record_business_event` gọi để enforce per-seat cap; `SequencerService` không gọi trực tiếp.
- **Redis & Celery:** `get_redis_client` trong `nowing_backend/app/redis_client.py:15`; `run_async_celery_task` trong `nowing_backend/app/tasks/celery_tasks.py`.

### 2. Anti-Reinvention
- Không tạo bảng `drip_campaigns` / `campaign_steps`; dùng `sequence_*`.
- Không viết Zalo/Telegram client mới; dùng `ZnsClient` và `TelegramAdapter`.
- Không để `TokenUsage` ghi nhận business event; mọi chi phí sequence dùng `BillingEvent` qua `BillingEventService`.
- Không tạo `AutomationRun` cho sequence; dùng `SequenceRun`.

### 3. Quiet Hours Formula (unchanged)

Tham khảo `nowing_backend/app/services/sequencer_service.py:81-110`.

### 4. Redis Distributed Lock + Optimistic CAS (unchanged)

Tham khảo `nowing_backend/app/services/sequencer_service.py:342-444`.

### 5. Billing Flow Pattern for Multi-Channel

```python
from app.services.billing_event_service import BillingEventService
from app.services import wallet_credit

attributed_user_id = sequence.created_by_user_id or workspace.user_id

# 1. Pre-check wallet
if cost_micros > 0:
    try:
        await wallet_credit.check_balance(session, attributed_user_id, cost_micros)
    except wallet_credit.InsufficientCreditsError:
        return SequenceEvent(
            ..., event_type="failed", event_subtype="insufficient_credits"
        )

# 2. Send via channel adapter (no internal billing)
# ZnsClient: cost_micros=0, user_id=None
# TelegramAdapter: free or config cost

# 3. SequenceEvent + enrollment update staged
sequence_event = SequenceEvent(
    workspace_id=workspace_id,
    client_id=client_id,
    enrollment_id=enrollment.id,
    sequence_id=sequence.id,
    step_id=step.id,
    event_type="sent",
    channel=step.channel,  # "zalo" | "telegram" | "email"
    cost_micros=cost_micros,
    event_metadata={"template_id": ..., "recipient": redacted_contact, "provider_msg_id": msg_id},
)
session.add(sequence_event)
await session.flush()

# 4. Update enrollment
enrollment.status = "scheduled"
enrollment.current_step = next_step_order
enrollment.scheduled_at = next_eta
enrollment.version += 1

# 5. Record ledger (last operation because apply_debit commits)
billing_event = await BillingEventService().record_sequence_send(
    session=session,
    sequence_event_id=sequence_event.id,
    workspace_id=workspace_id,
    client_id=client_id,
    user_id=attributed_user_id,
    cost_micros=cost_micros,
    cost_basis="actual",
    event_type=step.channel_event_type,  # "email_send" | "zns_send" | "telegram_send"
)
```

### 6. Zalo ZNS Pattern

```python
from app.gateway.zalo.zns_client import ZnsClient, ZnsTimeWindowViolationError

zns_client = ZnsClient()
try:
    result = await zns_client.send_zns_template(
        session=session,
        workspace_id=workspace_id,
        phone=contact.phone,
        template_id=step.template["template_id"],
        template_data=step.template["template_data"],
        lead_id=lead.id,
        cost_micros=0,        # disable internal billing
        user_id=None,         # SequencerService handles wallet
    )
    provider_msg_id = result["msg_id"]
except ZnsTimeWindowViolationError:
    # Reschedule
    next_eta = calculate_step_eta(delay_seconds=3600, from_dt=datetime.now(VN_TZ))
    ...
except ZnsDispatchError as exc:
    # Try fallback
    ...
```

### 7. Telegram Pattern

```python
from app.gateway.registry import resolve_platform_bundle
from app.db import ExternalChatAccount

account = await session.execute(
    select(ExternalChatAccount).where(
        ExternalChatAccount.workspace_id == workspace_id,
        ExternalChatAccount.platform == "telegram",
        ExternalChatAccount.is_active.is_(True),
    )
).scalar_one_or_none()
if not account:
    raise FallbackRequiredError("no_telegram_account")

bundle = resolve_platform_bundle(account)
result = await bundle.adapter.send_message(
    external_peer_id=contact.telegram_chat_id,
    text=interpolated_text,
    parse_mode=step.template.get("parse_mode", "MarkdownV2"),
)
provider_msg_id = result.external_message_id
```

### 8. Fallback Decision Tree

- `phone_not_registered`, `invalid_phone` → fallback.
- `rate_limit` từ Zalo → thử lại sau backoff hoặc fallback nếu vượt retry.
- `ZnsTimeWindowViolationError` → reschedule (không fallback) vì tất cả kênh đều chịu quiet hours.
- `InsufficientCreditsError` → dừng toàn bộ enrollment, ghi `failed`.
- Telegram `RetryAfter` → Celery retry.
- Telegram `BadRequest` (parse mode) → thử lại với `parse_mode=None`; nếu vẫn fail thì fallback.

### 9. Inbound Interruption

Tham khảo `nowing_backend/app/services/sequencer_service.py:756-882`. Mở rộng để nhận `channel='zalo'` hoặc `channel='telegram'` từ webhook, truyền `text` để detect opt-out keywords.

## Ghi chú cấu trúc dự án (Project Structure Notes)

- Tất cả thay đổi backend nằm trong namespace `sequence_*`: `app/db.py`, `app/schemas/sequence.py`, `app/routes/sequence_routes.py`, `app/services/sequencer_service.py`, `app/automations/tasks/sequence_tasks.py`.
- Không tạo `app/campaigns/` hoặc `app/drip/`.
- Frontend nằm trong `nowing_web/components/automations/VisualCadenceBuilder.tsx` và `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/`.
- Migration Alembic tiếp theo sau `225_add_sequence_tables.py` (hiện tại head `225` tùy thuộc nhánh develop).

## Tham khảo (References)

- Epic 24 / Story 24.7: `_bmad-output/planning-artifacts/epics.md` dòng 3190-3202.
- Story 24.1 implementation: `_bmad-output/implementation-artifacts/stories/24-1-multi-channel-drip-outreach-campaign-engine.md`.
- AD-39, AD-41, AD-42, AD-43, AD-48, AD-49: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`.
- Code: `nowing_backend/app/db.py:6094-6338` (`Sequence*` models).
- Code: `nowing_backend/app/services/sequencer_service.py`.
- Code: `nowing_backend/app/services/billing_event_service.py:93` (`record_sequence_send`).
- Code: `nowing_backend/app/gateway/zalo/zns_client.py:156` (`send_zns_template`).
- Code: `nowing_backend/app/gateway/telegram/adapter.py:148` (`send_message`).
- Code: `nowing_backend/app/gateway/registry.py:112` (`resolve_platform_bundle`).
- Code: `nowing_backend/app/lead_intelligence/dnc/service.py:56` (`DncComplianceService`).
- Code: `nowing_backend/app/services/wallet_credit.py:50` (`check_balance`/`apply_debit`).

## Lệnh xác minh (Verification Commands)

```bash
# Backend lint
cd nowing_backend
uv run ruff check app/services/sequencer_service.py app/services/billing_event_service.py app/schemas/sequence.py app/routes/sequence_routes.py app/db.py app/gateway/zalo/zns_client.py app/gateway/telegram/adapter.py app/automations/tasks/sequence_tasks.py

# Migrations
uv run alembic upgrade head

# Unit + integration tests
uv run pytest tests/unit/services/test_sequencer_service.py tests/unit/services/test_billing_event_service.py -q
uv run pytest tests/integration/services/test_sequence_scheduler.py -q

# Frontend typecheck & biome lint
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check app/dashboard/\[workspace_id\]/automations/campaigns/ components/automations/VisualCadenceBuilder.tsx lib/apis/sequence-api.service.ts contracts/types/sequence.types.ts
```

## Kinh nghiệm từ story trước (Previous Story Intelligence)

- **Story 24.1 (Sequence Email-first MVP):** Đã xây dựng `Sequence` bounded context, `SequencerService`, Celery tasks, UI `VisualCadenceBuilder`, Playwright E2E. Các bug đã fix: `client_id` type mismatch, `MissingGreenlet` do thiếu `selectinload`, RLS, wallet debit. Commit `4c37acfa9`.
- **Story 24.2 (Waterfall Phone & MST):** Tái sử dụng `DncComplianceService`, `hash_phone_hmac`, `normalize_phone_e164`, `VerifiedContact`.
- **Story 24.3 (Team CRM & Shared Credit):** `WorkspaceCreditService.record_spend` enforce per-seat cap qua `BillingEventService._record_business_event`.

## Câu hỏi mở cần giải quyết trước implement

1. **DEF-102 / AD-41 re-activation:** Legal/ToS/ZNS template approval đã pass chưa? Cần `bmad-correct-course` trước khi bật `zalo`.
2. **Telegram recipient ID:** `VerifiedContact` hiện chỉ có `email` và `phone`. Cần thêm `telegram_chat_id`/`zalo_user_id` trực tiếp vào `VerifiedContact` hay tạo bảng riêng? Quyết định ảnh hưởng migration.
3. **Telegram bot token per workspace:** `ExternalChatAccount` đã hỗ trợ `platform=telegram`? Cần xác nhận cách workspace tạo/kết nối tài khoản.
4. **Zalo OA token per workspace:** `ZaloConnection` đã có bảng? Lấy OA access token từ đâu?
5. **Cost matrix:** Zalo ZNS mặc định `300 VND/msg` (`ZNS_DEFAULT_COST_MICROS`). Telegram miễn phí? Email cost hiện tại 500 micros? Cần config per channel.
6. **Fallback ordering:** Fallback mặc định là `zalo → telegram → email` hay do user cấu hình?
7. **Inbound webhook routing:** Zalo/Telegram webhook hiện đi vào `inbox_processor` hay `callbacks`? Cần xác định integration point chính xác để gọi `handle_inbound_interruption`.
8. **AI personalization:** AC đề cập "AI-personalized copy". Story 24.7 MVP có dùng LLM generate nội dung mỗi lead hay chỉ template variable substitution? Nếu dùng LLM, cần tích hợp `llm_service` và cost estimation.

## Dev Agent Record

### Agent Model Used

{to be filled during dev-story}

### Debug Log References

{to be filled during dev-story}

### Completion Notes List

{to be filled during dev-story}

### File List

- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/schemas/sequence.py`
- `nowing_backend/app/services/sequencer_service.py`
- `nowing_backend/app/services/billing_event_service.py`
- `nowing_backend/app/gateway/zalo/zns_client.py`
- `nowing_backend/app/gateway/telegram/adapter.py`
- `nowing_backend/app/gateway/telegram/client.py`
- `nowing_backend/app/gateway/registry.py`
- `nowing_backend/app/gateway/accounts.py`
- `nowing_backend/app/gateway/zalo/webhook.py`
- `nowing_backend/app/gateway/telegram/callbacks.py`
- `nowing_backend/app/gateway/inbox_processor.py`
- `nowing_backend/app/automations/tasks/sequence_tasks.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/tests/unit/services/test_sequencer_service.py`
- `nowing_backend/tests/integration/services/test_sequence_scheduler.py`
- `nowing_web/contracts/types/sequence.types.ts`
- `nowing_web/lib/apis/sequence-api.service.ts`
- `nowing_web/components/automations/VisualCadenceBuilder.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/new/page.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/[sequence_id]/page.tsx`
- `nowing_web/tests/automations/campaign-sequence-builder.spec.ts`

### Change Log

{to be filled during dev-story}
