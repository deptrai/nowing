story_key: 23-2-official-zalo-oa-webhook-and-zns-template-automation
status: ready-for-dev
baseline_commit: 14d9eb4729cfa97ba8d6c70281b37a1c49618a80
epic: 23
story: 2
---

# Story 23.2: Official Zalo OA Webhook & ZNS Template Automation Hub

Status: ready-for-dev

<!-- Note: Governed by FR-90, INV-23.7, INV-23.8, INV-23.9, and Architecture Spine: architecture-epic23-lead-infrastructure.md -->

## Story

As a sales operations lead and growth marketer,
I want to connect official Zalo Official Account (OA) Webhooks with HMAC signature verification and send automated ZNS (Zalo Notification Service) templates directly to verified prospects, with two-way reply logging and strict anti-spam compliance,
So that outreach response rates increase by 4x over cold email while fully complying with Nghị định 91/2020/NĐ-CP and protecting OA reputation.

---

## Acceptance Criteria

### AC-1 — Fast ACK & Replay-Resistant HMAC-SHA256 Webhook Receiver
**Given** an incoming webhook POST event from Zalo OA server to `/api/v1/workspaces/{workspace_id}/gateways/zalo/webhook`,
**When** the request arrives,
**Then** the backend extracts `raw_body = await request.body()` before JSON parsing and validates the `X-Zalo-Signature` against `hmac.new(oa_secret.encode(), raw_body, hashlib.sha256).hexdigest()`.
**And** verifies `timestamp` delta <= 300s to prevent replay attacks.
**And** returns `HTTP 200 OK {"status": "ok"}` in < 100ms, enqueuing the raw payload to Celery task `process_zalo_inbox_event.delay(workspace_id, event_dict)`.

### AC-2 — Split-Pane ZNS Template Modal & Dynamic Variable Mapping
**Given** an authenticated user inspecting a lead record with an unlocked, verified Vietnamese mobile number (`09xx`, `08xx`, `03xx`, `07xx`),
**When** clicking the `⚡ Gửi ZNS` button on the lead row or detail pane,
**Then** Nowing opens a Split-Pane Modal displaying:
  1. Left pane: Template selector (`ZnsTemplateSelect`), dynamic variable inputs (`{customer_name}`, `{property_name}`, `{price}`, `{consultant_phone}`), and credit cost estimate (300đ / 0.3 credits).
  2. Right pane: Live mobile viewport mockup rendering the exact ZNS message layout with Zalo blue header and CTA button.
**And** sending is strictly disabled if outside the legal sending window (**08:00 – 21:30** Vietnam Time / UTC+7) or if the phone number is on the National DNC blacklist (Nghị định 91/2020/NĐ-CP).

### AC-3 — Two-Way Conversation Sync & Auto Lead Status Transition
**Given** an outbound ZNS message successfully dispatched,
**When** the recipient responds with a message on Zalo within the 48h active session window,
**Then** the webhook processes the `user_send_text` event, writes a row to `zalo_message_logs`, and updates `Lead.status = 'responded'`.
**And** triggers a real-time notification to the workspace owner (`LeadResponseNotification`) with the prospect's reply text.

### AC-4 — Quota & Cost Metering Integration
**Given** a ZNS message dispatch request,
**When** executed via `ZaloClient.send_zns_template`,
**Then** the system debits the workspace credit balance via `wallet_credit.apply_debit` (300 `cost_micros` / 0.3 credits), records a `BillingEvent` with `service_name = 'zns_outreach'`, and records the official Zalo `msg_id` in `outbound_messages`.

---

## Tasks / Subtasks

- [ ] **Task 1: Backend Zalo Webhook & Fast-ACK Pipeline (`nowing_backend/app/gateway/zalo/`)**
  - [ ] Implement `raw_body` HMAC-SHA256 signature verification in `app/gateway/zalo/webhook.py`.
  - [ ] Implement timestamp anti-replay check (<= 300 seconds).
  - [ ] Implement non-blocking Celery dispatch task `app/gateway/zalo/tasks.py::process_zalo_inbox_event`.
  - [ ] Handle event types: `user_send_text`, `user_send_image`, `follow`, `unfollow`, `oa_send_text_success`.

- [ ] **Task 2: ZNS Client & Template Service (`nowing_backend/app/gateway/zalo/zns_client.py`)**
  - [ ] Implement `ZnsClient` integrating Zalo OpenAPI v3 (`POST https://business.openapi.zalo.me/message/template`).
  - [ ] Implement dynamic variable substitution & validation against template parameter schemas.
  - [ ] Enforce time-gate validator (08:00 <= current_vn_time <= 21:30).
  - [ ] Connect DNC verification check before API invocation.

- [ ] **Task 3: Backend Routes & Schemas (`nowing_backend/app/routes/zns_routes.py`)**
  - [ ] `GET /api/v1/workspaces/{id}/zns/templates`: list approved templates from Zalo OA.
  - [ ] `POST /api/v1/workspaces/{id}/zns/send`: validate quota, time window, DNC, send message, record `BillingEvent`.
  - [ ] `GET /api/v1/workspaces/{id}/zns/logs`: history of sent ZNS messages and delivery statuses.

- [ ] **Task 4: Frontend Split-Pane ZNS Modal (`nowing_web/components/leads/zns-outreach-modal.tsx`)**
  - [ ] Create split-pane dialog (Left: form inputs, Right: simulated mobile viewport).
  - [ ] Implement live variable preview with auto-fill from `lead.name`, `lead.phone`, `lead.metadata`.
  - [ ] Implement legal sending window banner & DNC badge.
  - [ ] Integrate with `lib/apis/zns-api.service.ts` and mutate via React Query.

- [ ] **Task 5: Automated Testing & Verification**
  - [ ] Unit tests: HMAC signature verification with valid and invalid secrets, replay timestamp attacks.
  - [ ] Integration tests: Webhook fast ACK < 100ms, ZNS send flow with mocked Zalo OpenAPI v3.
  - [ ] Time-window unit tests: 07:59 (rejected), 08:01 (allowed), 21:29 (allowed), 21:31 (rejected).

---

## Dev Agent Guardrails & Architectural Invariants

- **INV-23.7 (Raw Body HMAC):** Tuyệt đối không parse `request.json()` trước khi tính HMAC. Phải đọc `await request.body()`.
- **INV-23.8 (Fast Webhook ACK):** Webhook endpoint phải trả về `HTTP 200 OK` trong vòng dưới 100ms. Mọi xử lý nặng đẩy vào Celery.
- **INV-23.9 (Nghị định 91 Compliance):** Chỉ gửi ZNS từ 08:00 đến 21:30. Tuyệt đối không gửi vào số trong danh sách DNC.

---

## Verification Commands

```bash
# 1. Backend Tests for Zalo Webhook & ZNS Client
cd nowing_backend
uv run pytest tests/unit/gateway/test_zalo_webhook_hmac.py tests/unit/gateway/test_zns_client.py tests/integration/gateway/test_zalo_webhook_e2e.py -q

# 2. Lint & Format
ruff check app/gateway/zalo app/routes/zns_routes.py app/schemas/zns.py
ruff format app/gateway/zalo app/routes/zns_routes.py app/schemas/zns.py

# 3. Frontend Typecheck & Biome
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/leads/zns-outreach-modal.tsx lib/apis/zns-api.service.ts
```
