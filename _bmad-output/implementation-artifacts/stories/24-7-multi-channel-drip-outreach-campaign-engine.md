---
story_key: "24-7"
epic: "epic-24"
story: "24.7"
title: "Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence)"
status: "review"
baseline_commit: "4c37acfa9"
---

# Story 24.7: Mở rộng Sequence đa kênh (Zalo ZNS + Telegram + Email Cadence)

## Story Overview

As an enterprise sales team, agency, or growth marketer,
I want to design and launch multi-channel automated drip Sequences (Zalo ZNS, Telegram Bot, and Email) with conditional delays, strict compliance rules, and template variable personalization,
So that high-intent leads discovered across Nowing are automatically nurtured into booked appointments and qualified opportunities without manual repetitive outreach.

> **Scope note (split from 24.1):** Story này **mở rộng bounded context `Sequence` đã có** từ Story 24.1 (`done`), **KHÔNG** tạo thêm bảng `drip_campaigns` / `campaign_*` song song. Story 24.1 đã ship `Sequence` với channel `email` duy nhất và các kênh `zalo`/`telegram` bị tắt sau feature gate `SEQUENCER_OUTBOUND_CHANNELS` (AD-41).
>
> **Multi-channel scope (revised):**
> - **Email**: fully enabled (MVP, Story 24.1).
> - **Telegram Bot**: enable by adding `telegram` to `SEQUENCER_OUTBOUND_CHANNELS`. Telegram adapter (`TelegramAdapter` / `TelegramClient`) and `ExternalChatAccount` platform support already exist from Story 11.1/11.3; this story wires them into `SequencerService`.
> - **Zalo ZNS**: **remain gated by AD-41 / DEF-102**. Story 24.7 prepares the Zalo code path (`_handle_zns_step`, fallback, billing, inbound webhook) but does **not** enable `zalo` in default `SEQUENCER_OUTBOUND_CHANNELS` or on production until AD-41 re-activation closes: Zalo OA business verification, Zalo business messaging ToS review, and Decree 356 compliance sign-off (see ARCHITECTURE-SPINE AD-41 and open question resolution below).
>
> **Gate trước khi merge:** Theo DEF-102, team bắt buộc chạy `bmad-correct-course` / SCP để kích hoạt lại AD-41 và đóng legal/ToS/ZNS-template gates trước khi bật `zalo` trên production. Story 24.7 ships with `zalo` disabled by default and a runtime feature gate, so the code can merge safely and `zalo` can be flipped on later via config + SCP.

## Kiến trúc ràng buộc (Architectural Invariants)

- **AD-39 — Sequence bounded context:**
  `Sequence` là bounded context riêng, không phải subtype của `Automation`. Story 24.7 chỉ mở rộng `SequenceStep`, `SequenceEvent`, `SequencerService` — không tạo bảng mới.

- **AD-41 — Channels deferred out of MVP (gate):**
  Theo `ARCHITECTURE-SPINE.md` §AD-41, `zalo`/`linkedin` remain **deferred in MVP**. `telegram` is not deferred by AD-41 and can be enabled once this story is complete. Story 24.7 therefore:
  - Keeps `zalo` behind the `SEQUENCER_OUTBOUND_CHANNELS` gate and a separate legal gate (`AD_41_REACTIVATED` or explicit SCP sign-off) so it cannot be enabled by accident.
  - Enables `telegram` as an additional supported channel when `SEQUENCER_OUTBOUND_CHANNELS` contains `telegram`.
  - `SequencerService.validate_step_channel()` continues to raise `DeferredChannelError` (422) for any channel not in the configured list.

- **AD-42/AD-48 — Billing matrix:**
  `TokenUsage` chỉ dành cho LLM token. Mọi sự kiện nghiệp vụ sequence dùng `BillingEvent`. Ma trận cho phép:
  - `SequenceEvent.event_type == 'sent', channel == 'email'` → `BillingEvent(event_entity_type='sequence_event', event_type='email_send')`.
  - `SequenceEvent.event_type == 'sent', channel == 'zalo'` → `BillingEvent(event_entity_type='sequence_event', event_type='zns_send')`.
  - `SequenceEvent.event_type == 'sent', channel == 'telegram'` → `BillingEvent(event_entity_type='sequence_event', event_type='telegram_send')` (cost 0 theo mặc định, có thể override bằng `SEQUENCE_TELEGRAM_COST_MICROS`).
  - `SequenceEvent.event_type == 'meeting_booked'` → tạo `OutcomeEvent` + `BillingEvent(event_entity_type='outcome_event', event_type='outcome_meeting_booked')`.

- **AD-43 — Alert-driven sequence enrollment:**
  `AlertRule` là first-class table. `SequencerService.enroll_lead()` tạo `SequenceRun` + `SequenceEnrollment`. Không tạo `AutomationRun`.

- **AD-25 / AD-49 — Consent, PII & Redaction:**
  Chỉ gửi cho `Lead` có `consent_status` cho phép và `legal_basis` không null. `VerifiedContact` là nguồn PII duy nhất; kiểm tra `consent=True`, `is_valid=True`. Định danh kênh chat (`telegram_chat_id`, `zalo_user_id`) được lưu trong cột `external_chat_ids` JSONB mới trên `VerifiedContact` (non-PII technical identifiers, không phá vỡ PK/FK/RLS). Mọi log, `SequenceEvent.event_metadata`, `BillingEvent` không chứa PII raw — redact qua `redact_pii(..., context='lead_enrichment')`.

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
- **Then** UI hiển thị `VisualCadenceBuilder` với channel selector:
  - `email` luôn khả dụng.
  - `telegram` khả dụng khi nằm trong `SEQUENCER_OUTBOUND_CHANNELS`.
  - `zalo` hiển thị `disabled` với tooltip "Deferred — AD-41 / DEF-102" cho đến khi SCP re-activation gỡ gate.
- **Then** kênh được chọn sẽ điều khiển `channel` và `step_type` của step mới (`send_email`, `send_telegram`, `send_zalo`).
- **Then** mỗi step bao gồm:
  - `channel`: `email` | `zalo` | `telegram`.
  - `step_type`: `send_email` | `send_telegram` | `send_zalo` | `wait` | `condition` | `update_lead_score` | `update_crm` | `tag`.
  - `template`:
    - `email`: `subject`, `body`, variable mapping.
    - `zalo`: `template_id` (pre-approved), `template_data` mapping.
    - `telegram`: `text`, `parse_mode` (MarkdownV2/HTML), variable mapping.
  - `fallback_channels`: danh sách kênh dự phòng theo thứ tự ưu tiên do người dùng cấu hình (ví dụ `["telegram", "email"]` cho step `zalo`). Mặc định `["email"]` cho `zalo`/`telegram`, `[]` cho `email`.
  - `wait_duration_seconds` và `condition_config` như hiện tại.

### AC-2 — Feature-Flag Channel Validation
- **Given** `SEQUENCER_OUTBOUND_CHANNELS` config là `email` (mặc định),
- **When** backend cố gắng thực thi step có `channel=zalo` hoặc `channel=telegram`,
- **Then** `SequencerService.validate_step_channel()` từ chối với `422 DeferredChannelError`.
- **Given** config là `email,telegram`,
- **When** thực thi `telegram` hoặc `email`,
- **Then** cho phép và điều phối đến handler tương ứng.
- **Given** config là `email,zalo,telegram` **và** `AD-41` re-activation gate đã đóng (hoặc env `AD_41_REACTIVATED=true` trên non-prod),
- **When** thực thi `zalo`,
- **Then** cho phép; nếu gate chưa đóng thì vẫn từ chối `422 DeferredChannelError` kể cả khi `zalo` có trong list.

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
  2. Kiểm tra `VerifiedContact` phù hợp kênh:
     - `zalo`: `phone` (dùng `normalize_phone_e164`) hoặc `external_chat_ids.zalo_user_id`.
     - `telegram`: `external_chat_ids.telegram_chat_id` (ưu tiên) hoặc `phone` (nếu workspace có gửi qua phone→Telegram lookup).
     Contact phải có `consent=True`, `is_valid=True`.
  3. Gọi `DncComplianceService.is_blocked()` với `phone` (fail-closed) cho cả ba kênh nếu có phone.
  4. Nếu thiếu contact phù hợp, thiếu consent, hoặc DNC block, ghi `SequenceEvent(event_type='skipped', event_subtype='no_contact' | 'no_consent' | 'dnc_blocked')` và chuyển bước tiếp theo.

### AC-5 — Multi-Channel Send with Fallback
- **Given** step `zalo` với `fallback_channels = ["telegram", "email"]` và lead có đủ thông tin,
- **When** `ZnsClient.send_zns_template()` trả về lỗi permanent (`phone_not_registered`, `rate_limit`, `ZnsDncViolationError`, `ZnsDispatchError`) và không phải `ZnsTimeWindowViolationError`,
- **Then** `SequencerService` thử kênh tiếp theo trong `fallback_channels`:
  - `telegram`: gửi qua `TelegramAdapter.send_message` với token từ `ExternalChatAccount` (platform=telegram) của workspace.
  - `email`: gửi qua `_send_email_smtp`.
- **When** `ZnsClient.send_zns_template()` raise `ZnsTimeWindowViolationError`,
- **Then** không fallback; reschedule enrollment tới thời điểm hợp lệ tiếp theo và ghi `SequenceEvent(event_type='failed', event_subtype='time_window_violation')`.
- **Then** nếu tất cả kênh đều unavailable, ghi `SequenceEvent(event_type='failed', event_subtype='all_channels_unavailable')`.

### AC-6 — Zalo ZNS Send & Billing
- **Given** billable `send` step `channel=zalo`,
- **When** `SequencerService` thực thi,
- **Then** trước khi gọi `ZnsClient`:
  1. Xác định `attributed_user_id = sequence.created_by_user_id hoặc workspace.user_id`.
  2. Pre-check số dư ví `wallet_credit.check_balance(session, attributed_user_id, cost_micros)` với `cost_micros = config.SEQUENCE_ZNS_COST_MICROS or 300`.
  3. Chuẩn hóa phone E.164 qua `normalize_phone_e164()`.
- **When** gọi `ZnsClient.send_zns_template()`,
- **Then** truyền `cost_micros=0` và `user_id=None` để `ZnsClient` không tự debit wallet/tạo `BillingEvent` (tránh duplicate ledger). `ZnsClient` vẫn tạo `ZaloMessageLog` và `session.commit()` bên trong; do đó `SequencerService` phải `flush()` `SequenceEvent` trước khi gọi `ZnsClient`.
- **When** Zalo API trả về thành công,
- **Then** tạo `SequenceEvent(event_type='sent', channel='zalo', cost_micros=..., provider_msg_id=..., event_metadata={template_id, recipient_phone_redacted})` và gọi `BillingEventService.record_sequence_send(..., event_type='zns_send')` để ghi ledger + debit wallet + enforce per-seat cap.
- **When** gọi thất bại,
- **Then** không tạo `BillingEvent`; fallback hoặc ghi `SequenceEvent(event_type='failed')`.
- **When** `ZnsClient` raise `ZnsTimeWindowViolationError`,
- **Then** reschedule enrollment (không fallback trừ khi quiet hours kéo dài quá ngưỡng cấu hình, mặc định 24h).

### AC-7 — Telegram Bot Send & Billing
- **Given** step `channel=telegram`,
- **When** `SequencerService` thực thi,
- **Then** tìm `ExternalChatAccount` của workspace với `platform=telegram` và `is_active=True`, lấy token qua `account_token()`, khởi tạo `TelegramAdapter(token)`, và gọi `send_message(external_peer_id=recipient_telegram_chat_id, text=interpolated_text, parse_mode=...)`.
- **Then** tạo `SequenceEvent(event_type='sent', channel='telegram', cost_micros=cost_telegram, provider_msg_id=external_message_id)`.
- **Then** gọi `BillingEventService.record_sequence_send(..., event_type='telegram_send')`. `cost_micros = config.SEQUENCE_TELEGRAM_COST_MICROS or 0`.
- **When** gửi thất bại do `RetryAfter` (dù `TelegramClient._send_once` đã retry 3 lần),
- **Then** propagate exception để Celery task `execute_sequence_step` retry theo exponential backoff; không tính là permanent failure.
- **When** gửi thất bại do `BadRequest` (parse mode),
- **Then** thử lại với `parse_mode=None`; nếu vẫn fail thì đánh dấu permanent failure và fallback.

### AC-8 — Inbound Interruption from Zalo & Telegram
- **Given** enrollment đang ở trạng thái `scheduled` hoặc `executing`,
- **When** inbound webhook từ Zalo OA hoặc Telegram Bot chứa reply hoặc opt-out keyword (`STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE`),
- **Then** handler gọi `SequencerService.handle_inbound_interruption()` với keyword args `channel`, `phone`, `email`, `telegram_chat_id` (nếu `channel='telegram'`), `zalo_user_id` (nếu `channel='zalo'`), `text`.
- **Then** `handle_inbound_interruption` acquire Redis lock, thực hiện CAS version update sang `responded` hoặc `unsubscribed`.
- **Then** nếu opt-out, tạo `WorkspaceDncRecord` với `value_hmac`, invalidate DNC cache, hủy các bước tương lai.
- **Then** integration point chính xác:
  - **Zalo:** `app/gateway/zalo/webhook.py` mở rộng `handle_zalo_webhook_event` để, sau khi tìm lead, gọi `SequencerService.handle_inbound_interruption(..., channel='zalo', phone=sender_phone, zalo_user_id=sender_id, text=text_content)`.
  - **Telegram:** `app/gateway/inbox_processor.py` mở rộng `_dispatch_inbound_event` hoặc `TelegramGatewayCommands` để, sau khi `adapter.parse_inbound`, nếu `parsed.external_peer_id` khớp `VerifiedContact.external_chat_ids.telegram_chat_id` của lead trong workspace, gọi `SequencerService.handle_inbound_interruption(..., channel='telegram', telegram_chat_id=parsed.external_peer_id, text=parsed.text)`. Telegram inbound cho leads chưa bound với user cần được xử lý trước khi bị từ chối vì `ExternalChatBinding` không tồn tại.

### AC-9 — Per-Channel Analytics
- **Given** sequence đã tồn tại tại `/dashboard/[workspace_id]/automations/campaigns/[id]`,
- **When** mở analytics view,
- **Then** backend trả `SequenceAnalyticsResponse` với `total_enrolled`, `active_scheduled`, `delivered_count`, `responded_count`, `unsubscribed_count`, `failed_count`, `total_cost_micros`, và breakdown theo `channel`.

## Công việc / Subtasks

### 1. Config & Feature Flag
- [ ] Thêm các biến sau vào `nowing_backend/app/config/__init__.py` (class `Config`):
  - `SEQUENCER_OUTBOUND_CHANNELS: str = os.getenv("SEQUENCER_OUTBOUND_CHANNELS", "email")`  # comma-separated: email,telegram,zalo
  - `SEQUENCE_EMAIL_COST_MICROS: int = _env_int("SEQUENCE_EMAIL_COST_MICROS", 500)`
  - `SEQUENCE_ZNS_COST_MICROS: int = _env_int("SEQUENCE_ZNS_COST_MICROS", 300)`
  - `SEQUENCE_TELEGRAM_COST_MICROS: int = _env_int("SEQUENCE_TELEGRAM_COST_MICROS", 0)`
  - `AD_41_REACTIVATED: bool = os.getenv("AD_41_REACTIVATED", "FALSE").upper() == "TRUE"`  # production guard for Zalo
  - `SEQUENCE_ZNS_MAX_RESCHEDULE_HOURS: int = _env_int("SEQUENCE_ZNS_MAX_RESCHEDULE_HOURS", 24)`  # ngưỡng quiet hours kéo dài trước khi fallback
- [ ] Cập nhật `nowing_backend/app/services/sequencer_service.py` `ALLOWED_OUTBOUND_CHANNELS` để fallback về `[c.strip() for c in config.SEQUENCER_OUTBOUND_CHANNELS.split(",")]`.
- [ ] Cập nhật `validate_step_channel` để từ chối `zalo` khi `config.AD_41_REACTIVATED` là `False`, ngay cả khi kênh có trong `SEQUENCER_OUTBOUND_CHANNELS`.

### 2. Database Schema
- [ ] Migration `226_add_verified_contact_external_chat_ids.py`:
  - Thêm cột `external_chat_ids` (JSONB, nullable, default `{}`, server_default `'{}'::jsonb`) vào `verified_contacts`.
  - Cột này lưu technical identifiers cho từng kênh: `{"telegram": "123456789", "zalo": "zalo_user_id"}`. Không chứa PII cá nhân (email/phone), nên không cần mã hóa. Không thay đổi PK/FK/RLS (AD-31/AD-45).
  - Cập nhật `nowing_backend/app/db.py` `VerifiedContact.external_chat_ids`.
  - Cập nhật PII redaction: `redact_pii` bỏ qua `external_chat_ids`; đảm bảo `VerifiedContact` vẫn là PII vault.
- [ ] Nếu dùng JSONB `template`, thêm `fallback_channels` vào schema `SequenceStep` mà không cần migration riêng (`template` đã là JSONB).

### 3. Schema Mở Rộng
- [ ] `nowing_backend/app/schemas/sequence.py`:
  - `SequenceChannel = Literal["email", "zalo", "telegram"]`.
  - `SequenceStepType = Literal["send_email", "send_zalo", "send_telegram", "wait", "condition", "update_lead_score", "update_crm", "tag"]`.
  - `SequenceStepBase.template` hỗ trợ `subject`/`body` (email), `template_id`/`template_data` (ZNS), `text`/`parse_mode` (telegram), `fallback_channels` (list[str]).
  - `SequenceEventRead.channel` chấp nhận `email` | `zalo` | `telegram`.
  - `SequenceAnalyticsResponse` thêm `channel_breakdown: dict[str, int] | None = None`.
- [ ] `nowing_web/contracts/types/sequence.types.ts`:
  - Cập nhật `sequenceStepSchema` tương ứng: `step_type` z.enum, `channel` z.enum, `template` z.record(z.string(), z.any()).

### 4. Core Service — `SequencerService`
- [ ] `nowing_backend/app/services/sequencer_service.py`:
  - Mở rộng `validate_step_channel` đọc `SEQUENCER_OUTBOUND_CHANNELS` từ config; từ chối `zalo` khi `AD_41_REACTIVATED` False.
  - Refactor `_handle_send_email_step` thành `_handle_send_step` với dispatch theo `step.channel` (gọi `_handle_email_step`, `_handle_zns_step`, `_handle_telegram_step`).
  - Thêm `_handle_zns_step`, `_handle_telegram_step`, `_handle_email_step`.
  - Thêm `_attempt_fallback(step, enrollment, failed_channel, exception)`.
  - Mở rộng `_resolve_verified_contact` để trả về `phone`, `email`, `external_chat_ids` (telegram/zalo).
  - Cập nhật `handle_inbound_interruption(..., telegram_chat_id: str | None = None, zalo_user_id: str | None = None)` để xử lý `channel` từ Zalo/Telegram; `_resolve_inbound_contact` thử match bằng phone, email, `telegram_chat_id`, `zalo_user_id`.
  - Giữ `calculate_step_eta` không đổi.

### 5. Billing Event Service
- [ ] `nowing_backend/app/services/billing_event_service.py`:
  - Mở rộng `record_sequence_send` thêm tham số `event_type: str = "email_send"` để hỗ trợ `"zns_send"`, `"telegram_send"`.
  - Đảm bảo vẫn idempotent theo `(event_entity_type, event_type, event_id, workspace_id)`; gọi lại cùng `sequence_event_id` + cùng `event_type` trả về `BillingEvent` hiện có.

### 6. Zalo ZNS Integration
- [ ] Tái sử dụng `app.gateway.zalo.zns_client.ZnsClient.send_zns_template()`.
- [ ] Từ `SequencerService`, gọi với `cost_micros=0` và `user_id=None` để tránh duplicate ledger. Lưu ý: `ZnsClient` tự `session.commit()` bên trong, nên `SequencerService` phải `flush()` `SequenceEvent` trước khi gọi.
- [ ] Bắt `ZnsTimeWindowViolationError` để reschedule (không tính là permanent failure cần fallback, trừ khi ngoài quiet hours kéo dài).
- [ ] Bắt `ZnsDncViolationError`, `ZnsDispatchError` để quyết định fallback hoặc ghi `failed`.
- [ ] Lấy `ZaloConnection` active của workspace trong `SequencerService` trước khi gọi; nếu không có, đánh dấu `failed` / `no_zalo_connection`.

### 7. Telegram Bot Integration
- [ ] Tìm `ExternalChatAccount` của workspace (`platform=telegram`, `is_active=True`). Nếu `is_system_account=True`, dùng `TELEGRAM_SHARED_BOT_TOKEN` (xem `account_token()`).
- [ ] Khởi tạo `TelegramAdapter(token)`.
- [ ] Gọi `send_message(external_peer_id=telegram_chat_id, text=interpolated_text, parse_mode=...)`.
- [ ] Xử lý `RetryAfter` bằng Celery retry (task `execute_sequence_step` đã có `max_retries=3`, có thể tăng lên 5 cho Telegram); `BadRequest` do parse mode → thử lại với `parse_mode=None`, sau đó fallback.

### 8. Inbound Webhook Integration
- [ ] `nowing_backend/app/gateway/zalo/webhook.py`:
  - Sau khi `handle_zalo_webhook_event` tìm `lead`, gọi `SequencerService.handle_inbound_interruption(..., channel='zalo', phone=sender_phone, zalo_user_id=sender_id, text=text_content)`.
  - Đảm bảo xử lý idempotent: nếu đã gọi `handle_inbound_interruption` cho `external_message_id`, không gọi lại.
- [ ] `nowing_backend/app/gateway/inbox_processor.py`:
  - Trong `_dispatch_inbound_event`, sau khi `adapter.parse_inbound`, trước khi reject vì `binding is None`, kiểm tra `parsed.external_peer_id` có khớp `VerifiedContact.external_chat_ids.telegram_chat_id` của lead trong workspace.
  - Nếu khớp, gọi `SequencerService.handle_inbound_interruption(..., channel='telegram', telegram_chat_id=parsed.external_peer_id, text=parsed.text)`.
  - Nếu binding tồn tại, tiếp tục flow chat agent hiện tại; sequence interruption xử lý song song hoặc được gọi trước khi chuyển sang chat agent.

### 9. Celery Tasks
- [ ] Không cần tạo task mới. `execute_sequence_step` và `evaluate_sequences` trong `nowing_backend/app/automations/tasks/sequence_tasks.py` đã sẵn sàng. Có thể cần cập nhật `max_retries` / retry backoff cho Telegram.

### 10. Frontend UI
- [ ] `nowing_web/contracts/types/sequence.types.ts`:
  - Cập nhật `SequenceChannel`, `SequenceStepType`, `SequenceStep['template']`.
  - Đảm bảo `template` record hỗ trợ `fallback_channels: string[]`.
- [ ] `nowing_web/lib/apis/sequence-api.service.ts`: không đổi endpoint.
- [ ] `nowing_web/components/automations/VisualCadenceBuilder.tsx`:
  - Sửa `handleAddStep` để tạo step theo `selectedChannel` (`send_email`/`send_telegram`/`send_zalo`).
  - Bật channel selector theo `SEQUENCER_OUTBOUND_CHANNELS`; `zalo` luôn disabled với tooltip AD-41.
  - Thêm ZNS template ID picker, template variable mapper cho Zalo (disabled).
  - Thêm Telegram message composer, parse mode selector (`MarkdownV2`, `HTML`, `None`).
  - Thêm fallback channel ordering UI cho mỗi step.
- [ ] Cập nhật Playwright test `tests/automations/campaign-sequence-builder.spec.ts` (thêm test `telegram` step; `zalo` deferred tooltip).

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
- **Billing Ledger:** `BillingEventService.record_sequence_send()` trong `nowing_backend/app/services/billing_event_service.py:584`. Cần mở rộng `event_type` để hỗ trợ `zns_send`/`telegram_send`.
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

# Resolve per-channel cost from config (default: email 500, zalo 300, telegram 0)
cost_micros = {
    "email": getattr(config, "SEQUENCE_EMAIL_COST_MICROS", 500),
    "zalo": getattr(config, "SEQUENCE_ZNS_COST_MICROS", 300),
    "telegram": getattr(config, "SEQUENCE_TELEGRAM_COST_MICROS", 0),
}.get(step.channel, 0)

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
# _send_email_async: cost handled by BillingEventService

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
channel_event_type = {
    "email": "email_send",
    "zalo": "zns_send",
    "telegram": "telegram_send",
}[step.channel]
billing_event = await BillingEventService().record_sequence_send(
    session=session,
    sequence_event_id=sequence_event.id,
    workspace_id=workspace_id,
    client_id=client_id,
    user_id=attributed_user_id,
    cost_micros=cost_micros,
    cost_basis="actual",
    event_type=channel_event_type,
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
telegram_chat_id = (contact.external_chat_ids or {}).get("telegram")
if not telegram_chat_id:
    raise FallbackRequiredError("no_telegram_chat_id")

result = await bundle.adapter.send_message(
    external_peer_id=telegram_chat_id,
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

- Epic 24 / Story 24.7: `_bmad-output/planning-artifacts/epics.md` dòng 3190-3202. **Note:** `epics.md` INV-24.1 may still use old `campaign_*`/`DripCampaignSchedulerService` terminology; Story 24.1 has already implemented the `Sequence` bounded context (`Sequence`/`SequenceStep`/`SequencerService`), so 24.7 builds on that. Use this story file and the actual code as the source of truth.
- Story 24.1 implementation: `_bmad-output/implementation-artifacts/stories/24-1-multi-channel-drip-outreach-campaign-engine.md`.
- AD-39, AD-41, AD-42, AD-43, AD-48, AD-49: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`.
- Code: `nowing_backend/app/db.py:6433-6725` (`Sequence*` and `Zalo*` models), `5240-5350` (`VerifiedContact`, sẽ thêm `external_chat_ids`).
- Code: `nowing_backend/app/services/sequencer_service.py`.
- Code: `nowing_backend/app/services/billing_event_service.py:584` (`record_sequence_send`).
- Code: `nowing_backend/app/gateway/zalo/zns_client.py:156` (`send_zns_template`).
- Code: `nowing_backend/app/gateway/telegram/adapter.py:148` (`send_message`).
- Code: `nowing_backend/app/gateway/registry.py:112` (`resolve_platform_bundle`).
- Code: `nowing_backend/app/lead_intelligence/dnc/service.py:56` (`DncComplianceService`).
- Code: `nowing_backend/app/services/wallet_credit.py:50` (`check_balance`/`apply_debit`).
- Code: `nowing_backend/app/gateway/accounts.py:20` (`account_token`).

## Lệnh xác minh (Verification Commands)

```bash
# Backend lint
cd nowing_backend
uv run ruff check app/config/__init__.py app/services/sequencer_service.py app/services/billing_event_service.py app/schemas/sequence.py app/routes/sequence_routes.py app/db.py app/gateway/zalo/zns_client.py app/gateway/zalo/webhook.py app/gateway/telegram/adapter.py app/gateway/telegram/callbacks.py app/gateway/inbox_processor.py app/automations/tasks/sequence_tasks.py

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

## Quyết định kiến trúc đã chốt

1. **DEF-102 / AD-41 re-activation:** Theo `ARCHITECTURE-SPINE.md` §AD-41 (dated 2026-08-11), `zalo` vẫn **DEFERRED** cho đến khi Zalo OA business verification, Zalo business messaging ToS review, và Decree 356 compliance sign-off hoàn thành. Story 24.7 **chuẩn bị code path Zalo** nhưng không enable `zalo` mặc định. Để bật production cần:
   - Chạy `bmad-correct-course` / SCP ghi nhận AD-41 re-activation.
   - Set env `AD_41_REACTIVATED=true` (hoặc sửa `config.AD_41_REACTIVATED`) **và** thêm `zalo` vào `SEQUENCER_OUTBOUND_CHANNELS`.
   - `ZaloConnection` model đã tồn tại (`nowing_backend/app/db.py:5777`); `is_active=True` chưa đủ, cần thêm quy trình verify OA business account (ngoài scope story 24.7, thuộc SCP).

2. **Telegram recipient ID:** Thêm **một cột `external_chat_ids: JSONB`** vào `VerifiedContact`. Lý do:
   - `VerifiedContact` là authoritative PII vault cho outreach (AD-25/AD-49).
   - `email`/`phone` đã là PII cá nhân; `telegram_chat_id`/`zalo_user_id` là technical platform identifiers, không cần mã hóa.
   - JSONB cho phép mở rộng kênh mới mà không cần migration thêm cột.
   - Không phá vỡ PK/FK/RLS (AD-31/AD-45); `VerifiedContact` PK hiện là `id` UUID, thêm cột nullable JSONB không ảnh hưởng.

3. **Telegram bot token per workspace:** `ExternalChatAccount` đã hỗ trợ `platform=telegram` (`nowing_backend/app/db.py:880`, `app/gateway/accounts.py:20-27`). `account_token()` trả về `TELEGRAM_SHARED_BOT_TOKEN` nếu `is_system_account=True`, hoặc giải mã `encrypted_credentials` nếu workspace có tài khoản riêng. Workspace kết nối qua existing Telegram connector/BYO flow (Story 11.1/11.3).

4. **Zalo OA token per workspace:** `ZaloConnection` đã có bảng (`nowing_backend/app/db.py:5777-5827`) với `access_token_encrypted`, `refresh_token_encrypted`, `is_active`. `ZnsClient` tự resolve `ZaloConnection` active trong `send_zns_template` (`nowing_backend/app/gateway/zalo/zns_client.py:199-208`).

5. **Cost matrix:** Cấu hình per-channel qua env vars:
   - `SEQUENCE_EMAIL_COST_MICROS` = 500 (default)
   - `SEQUENCE_ZNS_COST_MICROS` = 300 (default, ăn khớp `ZNS_DEFAULT_COST_MICROS`)
   - `SEQUENCE_TELEGRAM_COST_MICROS` = 0 (default)

6. **Fallback ordering:** Do **user cấu hình** trong `step.template["fallback_channels"]` (danh sách string). Mặc định:
   - `zalo`: `["telegram", "email"]`
   - `telegram`: `["email"]`
   - `email`: `[]`

7. **Inbound webhook routing:**
   - **Zalo:** `app/gateway/zalo/webhook.py` `handle_zalo_webhook_event` là entry point. Mở rộng để gọi `SequencerService.handle_inbound_interruption` sau khi tìm lead.
   - **Telegram:** `app/gateway/inbox_processor.py` `_dispatch_inbound_event` là entry point. Phải xử lý unbound messages từ lead trước khi reject; nếu `parsed.external_peer_id` khớp `VerifiedContact.external_chat_ids.telegram_chat_id`, gọi `SequencerService.handle_inbound_interruption`. Telegram `callbacks.py` chỉ xử lý inline-keyboard callback queries, không phải inbound text messages.

8. **AI personalization:** Story 24.7 MVP **không dùng LLM** để generate copy từng lead. Chỉ dùng `interpolate_template_variables()` (đã có trong `SequencerService`) để thay thế biến `{customer_name}`, `{company}`, `{property_title}`, `{consultant_phone}`. Tích hợp `llm_service` cho per-lead generation là out-of-scope; để lại cho story sau nếu PRD FR-66 yêu cầu.

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

### Review Findings

- [x] [Review][Patch] Deduplicate and normalize channel names in fallback execution [`nowing_backend/app/services/sequencer_service.py:250`]
- [x] [Review][Patch] Validate non-empty phone string and guard channel-specific contact requirements in compliance check [`nowing_backend/app/services/sequencer_service.py:185`]
- [x] [Review][Patch] Implement `_send_zns_step` and `_send_telegram_step` and wire into `execute_enrollment_step` [`nowing_backend/app/services/sequencer_service.py:293-352`]
- [x] [Review][Patch] Wire fallback execution into the real send path [`nowing_backend/app/services/sequencer_service.py:490-570`]
- [x] [Review][Patch] Add `event_type` parameter to `BillingEventService.record_sequence_send` [`nowing_backend/app/services/billing_event_service.py:584-610`]
- [x] [Review][Patch] Add multi-channel config variables and AD-41 re-activation gate [`nowing_backend/app/config/__init__.py`, `nowing_backend/app/services/sequencer_service.py:172-183`]
- [x] [Review][Patch] Extend backend schema for multi-channel step types, channels, events, analytics [`nowing_backend/app/schemas/sequence.py`]
- [x] [Review][Patch] Add `external_chat_ids` JSONB column to `VerifiedContact` and use in contact resolution [`nowing_backend/app/db.py`, `nowing_backend/app/services/sequencer_service.py`]
- [x] [Review][Patch] Complete `handle_inbound_interruption` signature/logic and wire webhooks [`nowing_backend/app/services/sequencer_service.py`, `nowing_backend/app/gateway/zalo/webhook.py`, `nowing_backend/app/gateway/inbox_processor.py`]
- [x] [Review][Patch] Enforce AD-41 / `SEQUENCER_OUTBOUND_CHANNELS` gating in `VisualCadenceBuilder` and add missing multi-channel template fields [`nowing_web/components/automations/VisualCadenceBuilder.tsx`]
- [x] [Review][Patch] Restrict `channel` and `fallback_channels` to channel enum in `sequence.types.ts` [`nowing_web/contracts/types/sequence.types.ts`]
- [x] [Review][Patch] Ensure `BillingEvent` / `SequenceEvent` are committed for zero-cost sends [`nowing_backend/app/services/billing_event_service.py`, `nowing_backend/app/services/sequencer_service.py`]
- [x] [Review][Patch] Fix `DncComplianceService.is_blocked` call signature in `check_outbound_compliance` [`nowing_backend/app/services/sequencer_service.py`]
- [x] [Review][Patch] Guard negative `delay_seconds` in `calculate_step_eta` [`nowing_backend/app/services/sequencer_service.py:90-121`]
- [x] [Review][Patch] Raise Celery `max_retries` for Telegram `RetryAfter` [`nowing_backend/app/automations/tasks/sequence_tasks.py:35`]
- [x] [Review][Patch] Add `channel_breakdown` to analytics schema and UI [`nowing_web/app/dashboard/[workspace_id]/automations/campaigns/[sequence_id]/page.tsx`, `nowing_backend/app/schemas/sequence.py`, `nowing_backend/app/services/sequencer_service.py`]
- [x] [Review][Patch] Fix Zalo webhook lead matching to use `VerifiedContact.external_chat_ids.zalo_user_id` [`nowing_backend/app/gateway/zalo/webhook.py`]
- [x] [Review][Patch] Prevent `wait`/`condition` steps from inheriting `selectedChannel` [`nowing_web/components/automations/VisualCadenceBuilder.tsx`]
- [x] [Review][Patch] Remove or wire `get_billing_event_for_step` with correct costs [`nowing_backend/app/services/sequencer_service.py:280-292`]
- [x] [Review][Defer] Cross-cutting `billing_event_service.py` refund/relock changes are pre-existing and not introduced by Story 24.7 [`nowing_backend/app/services/billing_event_service.py`] — deferred, pre-existing

### Code Review Findings (Re-review 2026-08-22)

- [x] [Review][Patch] `cost_micros` not recalculated for fallback channel billing / event cost [`nowing_backend/app/services/sequencer_service.py:537-546`]
- [x] [Review][Patch] Zalo webhook lead matching by `sender_phone` does not normalize E164 before querying `VerifiedContact.phone` [`nowing_backend/app/gateway/zalo/webhook.py:194-204`]
- [x] [Review][Patch] Telegram dispatch path does not perform DNC/compliance check [`nowing_backend/app/services/sequencer_service.py:1054-1070`]
- [x] [Review][Patch] Inbound interruption lock key uses raw phone/email/zalo_user_id as Redis key segment [`nowing_backend/app/services/sequencer_service.py:1295-1303`]
- [x] [Review][Patch] `VisualCadenceBuilder` silently ignores invalid `template_data` JSON while editing Zalo step [`nowing_web/components/automations/VisualCadenceBuilder.tsx:440-448`]

### Change Log

- **2026-07-25 (validation):** Scope clarified: `zalo` stays gated by AD-41/DEF-102; `telegram` can be enabled via config; email remains default.
- **2026-07-25 (validation):** Open questions resolved: `external_chat_ids` JSONB on `VerifiedContact`; per-channel cost config; Telegram/Zalo inbound routing; no LLM personalization in MVP.
- **2026-07-25 (validation):** AC and subtasks updated to reflect `AD_41_REACTIVATED`, `SEQUENCE_*_COST_MICROS`, `external_chat_ids`, `handle_inbound_interruption` signature, and `BillingEventService.record_sequence_send` event_type expansion.
- **2026-08-22 (code-review):** 3-layer adversarial review completed. Re-review after previous "done" status found 18 patch items and 1 deferred item; story re-opened to `in-progress`. Full triage in `review-24-7-triaged-findings.md`.
- **2026-08-22 (patch-application):** All 18 patch findings applied. Backend: multi-channel config, `VerifiedContact.external_chat_ids`, schema expansion, `_send_zns_dispatch` / `_send_telegram_dispatch`, fallback orchestration, billing `event_type`, DNC call signature, `handle_inbound_interruption` CAS + webhook wiring, channel analytics, Celery retries. Frontend: `VisualCadenceBuilder` gating/template fields, `sequence.types.ts` enum restrictions, analytics page channel breakdown. Verification: ruff, `tsc --noEmit`, biome, and 34 backend tests green.
- **2026-08-22 (re-review):** 5 re-review findings applied and re-tested: fallback cost recalculation, Zalo webhook phone normalization, Telegram DNC check, hashed inbound interruption lock key, VisualCadenceBuilder invalid `template_data` JSON feedback. Added regression assertion for fallback channel cost. Re-review clean.
