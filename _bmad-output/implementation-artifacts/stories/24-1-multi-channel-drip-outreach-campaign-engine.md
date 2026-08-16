---
story_key: "24-1"
epic: "epic-24"
story: "24.1"
title: "Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence)"
status: "ready-for-dev"
baseline_commit: "6ac305274"
---

# Story 24.1: Multi-Channel Drip Outreach Campaign Engine (Zalo ZNS + Telegram + Email Cadence)

## Story Overview

As an enterprise sales team, agency or growth marketer,
I want to design and launch multi-channel automated drip campaigns (Zalo ZNS, Telegram Bot, and Email) with conditional delays, strict compliance rules, and AI-personalized content,
So that leads discovered across Nowing are automatically nurtured into booked appointments and qualified opportunities without manual repetitive outreach.

---

## Architectural Invariants (INV-24.1, INV-24.2, INV-23.11)
- **INV-24.1 (Stateful Cadence Scheduler & Quiet Hours Deferral):** Bảng `campaign_steps` lưu trữ trạng thái execution step, dispatch qua Celery Beat / Redis delayed sets. Khung giờ gửi tin tuân thủ **08:00 – 21:30 (Asia/Ho_Chi_Minh)**. Tin nhắn đến hạn ngoài khung giờ BẮT BUỘC tự động lùi `eta` thực thi sang `08:05` sáng hôm sau kèm Jitter (`random(0, 1800s)`).
- **INV-24.2 (Opt-Out, DNC & ZNS Template Compliance):** Gửi Zalo ZNS BẮT BUỘC dùng template ID đã được duyệt; chat tự do chỉ trong cửa sổ tương tác 24h. Khi nhận phản hồi `STOP` / `HUY`, hủy campaign ngay lập tức. Mọi bước gửi tin BẮT BUỘC kiểm tra `workspace_dnc_records` và `global_dnc_records` (Fail-closed).

---

## Acceptance Criteria

1. **Visual Cadence Builder UI:**
   - **Given** an active lead list in Nowing Workspace,
   - **When** a user navigates to `/dashboard/[workspace_id]/automations/campaigns/new`,
   - **Then** the UI provides a visual drag-and-drop cadence editor to configure:
     - `Step 1`: Instant pre-approved Zalo ZNS Template / Telegram Bot message with dynamic variable mapping (`{customer_name}`, `{company}`, `{property_title}`).
     - `Step 2`: Conditional Wait (e.g. 48h) evaluated with `Asia/Ho_Chi_Minh` timezone.
     - `Step 3`: Follow-up Email or Internal Sales Task assignment.

2. **Sending Window & Anti-Thundering Herd Enforcement:**
   - **Given** a scheduled step due at 22:00 (quiet hours),
   - **When** the cadence evaluator runs,
   - **Then** it defers task execution to `08:05 + uniform(0, 1800)` seconds next morning, preventing instant rate-limit collapse on external APIs.

3. **Inbound Interruption & Distributed Concurrency:**
   - **Given** an active campaign enrollment,
   - **When** the prospect replies via Zalo OA or Telegram OR sends opt-out keyword (`STOP`/`HUY`),
   - **Then** Redis distributed lock `campaign:lock:enrollment:{id}` and `SELECT FOR UPDATE` mark the enrollment as `responded` / `unsubscribed`, permanently halting all subsequent scheduled steps.

4. **Multi-Channel Delivery Fallback:**
   - **Given** a lead whose phone number is not registered on Zalo or ZNS quota is exceeded,
   - **When** Step 1 fails with a permanent error,
   - **Then** the engine automatically falls back to Step 1.Email (if available) or marks the step as `skipped_unavailable_channel` without crashing the campaign.

---

## Technical Tasks

### Backend Implementation
- [ ] Alembic Migration: Tạo bảng `drip_campaigns`, `campaign_steps`, `campaign_enrollments`, `campaign_execution_logs` với Composite Primary Key `(id, workspace_id)` và RLS policy.
- [ ] Service: Xây dựng `DripCampaignSchedulerService` (`nowing_backend/app/services/drip_campaign_service.py`) quản lý Celery Beat scheduling và time-window calculation.
- [ ] Concurrency & Lock: Tích hợp Redis distributed lock trong `InboundWebhookInterceptor` để xử lý race condition giữa reply webhook và scheduled step.
- [ ] DNC Enforcement: Tích hợp `dnc_service.check_is_dnc(workspace_id, phone)` fail-closed trước mọi outbound dispatch.

### Frontend Implementation
- [ ] Components: Xây dựng `VisualCadenceBuilder` trong `nowing_web/components/automations/VisualCadenceBuilder.tsx` với timeline flow steps và live ZNS variable preview.
- [ ] Page: Đấu nối route `nowing_web/app/dashboard/[workspace_id]/automations/campaigns/page.tsx`.

---

## Verification Commands

```bash
# Backend unit & integration tests
cd nowing_backend
uv run ruff check app/services/drip_campaign_service.py app/routes/drip_campaign_routes.py tests/unit/automations/test_drip_campaigns.py
uv run pytest tests/unit/automations/test_drip_campaigns.py -q
uv run pytest tests/integration/automations/test_drip_campaign_scheduler.py -q

# Frontend typecheck and lint
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check app/dashboard/\[workspace_id\]/automations/campaigns/ components/automations/VisualCadenceBuilder.tsx
```
