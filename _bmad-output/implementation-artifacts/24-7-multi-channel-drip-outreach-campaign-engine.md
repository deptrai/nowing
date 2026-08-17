---
story_key: "24-7"
epic: "epic-24"
story: "24.7"
title: "Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence)"
status: "backlog"
baseline_commit: "538b8bf06"
---

# Story 24.7: Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence)

## Story Overview

As an enterprise sales team, agency or growth marketer,
I want to design and launch multi-channel automated drip campaigns (Zalo ZNS, Telegram Bot, and Email) with conditional delays, strict compliance rules, and AI-personalized content,
So that leads discovered across Nowing are automatically nurtured into booked appointments and qualified opportunities without manual repetitive outreach.

> **Scope note (split from 24.1):** This story captures the **multi-channel expansion** of drip outreach. Story 24.1 ships the `Sequence` email-first MVP (`done`) in bounded context `Sequence` per AD-39. This story reintroduces the full `drip_campaigns` / `campaign_*` bounded context and enables Zalo ZNS + Telegram + Email. Before starting it, the team must run a `bmad-correct-course` / SCP to re-activate AD-41 and close legal/ToS/ZNS-template gates per DEF-102.

---

## Architectural Invariants (INV-24.1, INV-24.2, INV-23.11, INV-24.4, INV-24.7)

- **INV-24.1 (Stateful Cadence Scheduler & Quiet Hours Deferral):** Multi-channel outbound drip steps BẮT BUỘC lưu trạng thái execution step trong bảng `campaign_steps` và schedule qua Celery Beat / Redis delayed sets. Khung giờ gửi tin tuân thủ nghiêm ngặt **08:00 – 21:30 (Asia/Ho_Chi_Minh)** theo Nghị định 91/2020/NĐ-CP. Mọi tin nhắn đến hạn ngoài khung giờ BẮT BUỘC tự động lùi `eta` thực thi sang `08:05` sáng hôm sau kèm Jitter ngẫu nhiên (`random(0, 1800s)` ~ 0 - 30 phút) để phân tán tải, tránh thundering herd làm sập rate limit của đối tác.
- **INV-24.2 (Opt-Out, DNC & ZNS Template Compliance):** Mọi bước gửi outbound BẮT BUỘC kiểm tra trạng thái qua `DncComplianceService.is_blocked()` (`workspace_dnc_records` và `global_dnc_records`) theo nguyên tắc Fail-closed. Gửi Zalo ZNS BẮT BUỘC sử dụng `template_id` đã được VNG phê duyệt; chat tự do chỉ được phép trong cửa sổ 24 giờ kể từ khi prospect chủ động tương tác. Khi nhận webhook phản hồi từ khách hàng hoặc từ khóa hủy đăng ký (`STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE`), hệ thống BẮT BUỘC ngắt campaign ngay lập tức, thêm vào `WorkspaceDncRecord` (kèm `value_hmac`), xóa Redis DNC cache qua `dnc_service.invalidate_workspace_cache(workspace_id)`, và hủy mọi scheduled step tiếp theo.
- **INV-23.11 / INV-21.3 (Multi-Tenant Composite PK & RLS Isolation):** Mọi bảng dữ liệu chiến dịch BẮT BUỘC sử dụng Composite Primary Key `(id, workspace_id)` và hỗ trợ `client_id: CITEXT` cho vertical clients. Mọi Foreign Key Constraint liên kết giữa các bảng chiến dịch BẮT BUỘC là Composite Foreign Key `ForeignKeyConstraint(["campaign_id", "workspace_id"], ["drip_campaigns.id", "drip_campaigns.workspace_id"], ondelete="CASCADE")`. Kích hoạt PostgreSQL Row-Level Security (RLS) với policy chuẩn của Nowing.
- **INV-24.4 (Wallet Balance, Quota Verification & User Attribution):** Bảng `drip_campaigns` BẮT BUỘC lưu `created_by_user_id: UUID | None` để định danh chủ sở hữu chiến dịch. Với các kênh tính phí (như Zalo ZNS ~ 300 VND / msg), BẮT BUỘC thực hiện kiểm tra số dư ví `wallet_credit.check_balance(session, user_id, cost_micros)` trước khi gửi, và ghi nhận `BillingEvent` chi tiết sau khi gửi thành công.
- **INV-24.7 (Inbound Interruption & Distributed Concurrency Lock):** Xử lý ngắt campaign dùng Redis Distributed Lock `campaign:lock:enrollment:{workspace_id}:{enrollment_id}` (TTL 10s) kết hợp Optimistic Concurrency Control (OCC) qua cột `version`.

---

## Acceptance Criteria

### 1. Visual Cadence Builder UI
- **Given** an authenticated user with workspace membership in a Nowing Workspace,
- **When** the user navigates to `/dashboard/[workspace_id]/automations/campaigns/new`,
- **Then** the UI renders a visual drag-and-drop / node timeline editor supporting multi-channel step configurations:
  - `Step 1 (Outbound Channel)`: Select channel (`Zalo ZNS`, `Telegram Bot`, `Email`), choose pre-approved template ID, and map variables (`{customer_name}`, `{company}`, `{property_title}`, `{consultant_phone}`).
  - `Step 2 (Conditional Delay)`: Configure delay duration (e.g. `2 days` / `48 hours`), evaluated against `Asia/Ho_Chi_Minh` timezone.
  - `Step 3 (Follow-up & Fallback)`: Configure follow-up steps if no response received, or specify fallback channels (`fallback_channel`) if the primary channel is unavailable.

### 2. Quiet Hours & Anti-Thundering Herd Scheduling
- **Given** a campaign enrollment with a step due at 22:30 (outside 08:00 – 21:30 VN Time),
- **When** the cadence scheduler calculates the step dispatch time,
- **Then** `DripCampaignSchedulerService.calculate_step_eta()` automatically defers execution to `08:05 + uniform(0, 1800)` seconds next morning (UTC+7).
- **When** Celery Beat runs the periodic evaluator `evaluate_drip_campaign_cadences_task` every 1 minute,
- **Then** only enrollments with `status = 'scheduled'` and `scheduled_at <= now()` are dispatched to the async worker queue.

### 3. Inbound Interruption & Distributed Concurrency Lock
- **Given** an active campaign enrollment in state `scheduled` or `executing`,
- **When** an inbound webhook arrives from Zalo OA, Telegram, or Email containing a reply or opt-out keyword (`STOP`, `HUY`, `NGUNG`, `UNSUBSCRIBE`),
- **Then** `DripCampaignSchedulerService.handle_inbound_interruption()` acquires a Redis distributed lock `campaign:lock:enrollment:{workspace_id}:{enrollment_id}` (TTL 10s),
- **Then** executes an atomic Compare-And-Swap (CAS) state transition on `version`:
  `UPDATE campaign_enrollments SET status = 'responded' (or 'unsubscribed'), version = version + 1 WHERE id = :id AND workspace_id = :workspace_id AND version = :version`,
- **Then** if opt-out, creates a `WorkspaceDncRecord` (with HMAC hash `hash_phone_hmac`), triggers `dnc_service.invalidate_workspace_cache(workspace_id)`, and aborts all future scheduled steps.

### 4. Multi-Channel Delivery Fallback & Error Resilience
- **Given** a scheduled step targeting Zalo ZNS,
- **When** Zalo OpenAPI returns an error indicating the phone is not registered on Zalo (`phone_not_registered`) or rate limit is reached,
- **Then** the engine automatically attempts delivery via the configured fallback channel (e.g. `Email` if lead has email) or marks the execution log as `skipped_unavailable_channel` without crashing the entire campaign batch.

### 5. Dynamic Lead & VerifiedContact Variable Resolution
- **Given** a template configured with parameters (`{customer_name}`, `{phone}`, `{email}`, `{company}`),
- **When** the step payload is constructed for an enrolled lead,
- **Then** the engine queries the associated `VerifiedContact` records for the lead first to obtain decrypted contact details (`name`, `phone`, `email`); if not found, it gracefully falls back to `Lead.company_name`, `Lead.location`, `Lead.tax_id`.

### 6. Funnel Analytics & Conversion Metrics
- **Given** an existing campaign at `/dashboard/[workspace_id]/automations/campaigns/[id]`,
- **When** loading the analytics view,
- **Then** the backend aggregates `CampaignAnalyticsResponse` with `total_enrolled`, `active_scheduled`, `delivered_count`, `responded_count`, `unsubscribed_count`, and `total_cost_micros`.

---

## Technical Tasks

### 1. Database Schema & Alembic Migration
- [ ] Create Alembic migration `nowing_backend/alembic/versions/<next>_add_drip_campaigns_tables.py`:
  - `drip_campaigns`, `campaign_steps`, `campaign_enrollments`, `campaign_execution_logs` với Composite PK `(id, workspace_id)`, `client_id: CITEXT`, Composite FK, indexes, RLS policies.
- [ ] Update `nowing_backend/app/db.py` với ORM Models: `DripCampaign`, `CampaignStep`, `CampaignEnrollment`, `CampaignExecutionLog`.

### 2. Core Service & Engine Architecture
- [ ] Tạo `nowing_backend/app/services/drip_campaign_service.py` — `DripCampaignSchedulerService` với `calculate_step_eta`, `enroll_leads`, `evaluate_pending_cadences`, `execute_enrollment_step`, `handle_inbound_interruption`, `get_campaign_analytics`.

### 3. Celery Tasks & Beat Schedule
- [ ] Tạo `nowing_backend/app/automations/tasks/drip_campaign_tasks.py` với `evaluate_drip_campaign_cadences` và `execute_drip_campaign_step`.
- [ ] Cập nhật `nowing_backend/app/celery_app.py` include list, `beat_schedule`, `task_routes`.

### 4. REST API Routes & Schemas
- [ ] Pydantic Schemas `nowing_backend/app/schemas/drip_campaign.py` (CRUD, enroll, pause, resume, analytics).
- [ ] API Router `nowing_backend/app/routes/drip_campaign_routes.py` — `/api/v1/workspaces/{workspace_id}/campaigns/[...]`.
- [ ] Register routes in `nowing_backend/app/routes/__init__.py` and `app/app.py`.

### 5. Inbound Webhook Integration
- [ ] Tích hợp `DripCampaignSchedulerService.handle_inbound_interruption` từ `app/gateway/inbox_processor.py`, `app/gateway/zalo/webhook.py`, `app/gateway/telegram/callbacks.py`.

### 6. Frontend UI & Visual Cadence Builder
- [ ] Contracts & Types `nowing_web/contracts/types/drip-campaign.types.ts`.
- [ ] API Client `nowing_web/lib/apis/drip-campaigns-api.service.ts`.
- [ ] Mở rộng `nowing_web/components/automations/VisualCadenceBuilder.tsx` để bật `zalo_zns`, `telegram`, `email`, template ID, fallback channel.
- [ ] Pages: list, builder, analytics sử dụng `drip_campaigns` API.

---

## Dev Notes & Architecture Guardrails

- **Không tái tạo `Sequence`:** Story này dùng bounded context `drip_campaigns` / `campaign_*` riêng. Nếu cần tương thích 24.1, cân nhắc migration hoặc adapter từ `Sequence` → `drip_campaigns`.
- **Zalo ZNS Client:** Import `ZnsClient` và `is_zns_sending_window_open` từ `app.gateway.zalo.zns_client`.
- **DNC Compliance:** Import `DncComplianceService` từ `app.lead_intelligence.dnc.service`; `hash_phone_hmac`, `normalize_phone_e164` từ `app.lead_intelligence.dnc.normalizer`.
- **Telegram Adapter:** Import `TelegramAdapter` từ `app.gateway.telegram.adapter`.
- **Email SMTP Dispatcher:** Reuse `_send_email_smtp` pattern từ `app.alerts.engine.notify`.
- **Wallet Credit:** Import `check_balance` và `apply_debit` từ `app.services.wallet_credit`.
