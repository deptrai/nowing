story_key: 23-2-official-zalo-oa-webhook-and-zns-template-automation
status: done
baseline_commit: 14d9eb4729cfa97ba8d6c70281b37a1c49618a80
epic: 23
story: 2
---

# Story 23.2: Official Zalo OA Webhook & ZNS Template Automation Hub

Status: done

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

- [x] **Task 1: Backend Zalo Webhook & Fast-ACK Pipeline (`nowing_backend/app/gateway/zalo/`)**
  - [x] Implement `raw_body` HMAC-SHA256 signature verification in `app/gateway/zalo/webhook.py`.
  - [x] Implement timestamp anti-replay check (<= 300 seconds).
  - [x] Implement non-blocking Celery dispatch task `app/gateway/zalo/tasks.py::process_zalo_inbox_event`.
  - [x] Handle event types: `user_send_text`, `user_send_image`, `follow`, `unfollow`, `oa_send_text_success`.

- [x] **Task 2: ZNS Client & Template Service (`nowing_backend/app/gateway/zalo/zns_client.py`)**
  - [x] Implement `ZnsClient` integrating Zalo OpenAPI v3 (`POST https://business.openapi.zalo.me/message/template`).
  - [x] Implement dynamic variable substitution & validation against template parameter schemas.
  - [x] Enforce time-gate validator (08:00 <= current_vn_time <= 21:30).
  - [x] Connect DNC verification check before API invocation.

- [x] **Task 3: Backend Routes & Schemas (`nowing_backend/app/routes/zns_routes.py`)**
  - [x] `GET /api/v1/workspaces/{id}/zns/templates`: list approved templates from Zalo OA.
  - [x] `POST /api/v1/workspaces/{id}/zns/send`: validate quota, time window, DNC, send message, record `BillingEvent`.
  - [x] `GET /api/v1/workspaces/{id}/zns/logs`: history of sent ZNS messages and delivery statuses.

- [x] **Task 4: Frontend Split-Pane ZNS Modal (`nowing_web/components/leads/zns-outreach-modal.tsx`)**
  - [x] Create split-pane dialog (Left: form inputs, Right: simulated mobile viewport).
  - [x] Implement live variable preview with auto-fill from `lead.name`, `lead.phone`, `lead.metadata`.
  - [x] Implement legal sending window banner & DNC badge.
  - [x] Integrate with `lib/apis/zns-api.service.ts` and mutate via React Query.

- [x] **Task 5: Automated Testing & Verification**
  - [x] Unit tests: HMAC signature verification with valid and invalid secrets, replay timestamp attacks.
  - [x] Integration tests: Webhook fast ACK < 100ms, ZNS send flow with mocked Zalo OpenAPI v3.
  - [x] Time-window unit tests: 07:59 (rejected), 08:01 (allowed), 21:29 (allowed), 21:31 (rejected).

### Review Findings
- [x] [Review][Patch] SEC-01: Remove hardcoded fallback secret in zns_routes.py [nowing_backend/app/routes/zns_routes.py:88-92]
- [x] [Review][Patch] FIN-01: Only debit wallet credit and emit BillingEvent on successful Zalo API dispatch [nowing_backend/app/gateway/zalo/zns_client.py:171-258]
- [x] [Review][Patch] SEC-02: Enforce mandatory timestamp presence and <= 300s freshness window [nowing_backend/app/routes/zns_routes.py:67-74, nowing_backend/app/gateway/zalo/webhook.py:150-155]
- [x] [Review][Patch] INT-01: Idempotency by (workspace_id, external_message_id) & commit DB before alert [nowing_backend/app/gateway/zalo/webhook.py:241-305]
- [x] [Review][Patch] SEC-03: Strip signature prefix 'mac=' / 'sha256=' from webhook signature [nowing_backend/app/gateway/zalo/webhook.py:160]
- [x] [Review][Patch] REL-01: Call validate_template_params before sending in ZnsClient [nowing_backend/app/gateway/zalo/zns_client.py:140-205]
- [x] [Review][Patch] UI-01: Dynamic template parameter inputs based on selected template schema in modal [nowing_web/components/leads/zns-outreach-modal.tsx]
- [x] [Review][Patch] REL-02: Add Celery retry config and session error handling [nowing_backend/app/gateway/zalo/tasks.py:18-42]
- [x] [Review][Patch] REL-03: Handle naive vs aware UTC datetime cleanly in time-gate check [nowing_backend/app/gateway/zalo/zns_client.py:46-47]

---

## Dev Agent Record

### Implementation Notes
- **Backend:**
  - Implemented `verify_zalo_signature` supporting direct `raw_body` HMAC-SHA256 & official Zalo MAC algorithms with prefix stripping.
  - Implemented `check_timestamp_freshness` for anti-replay verification (<= 300s window) supporting both second and millisecond timestamps.
  - Implemented `process_zalo_inbox_event` Celery task with exponential backoff retries and session rollback resilience.
  - Implemented `ZnsClient` with sending window time-gate (08:00–21:30 VN Time), `DncComplianceService` blacklist checks, dynamic template schema validation, post-dispatch credit debit, and `BillingEvent` tracking.
  - Mounted `zns_routes` under `/api/v1/workspaces/{workspace_id}/` for webhook, templates, send, and logs.
- **Frontend:**
  - Created `znsApiService` in `lib/apis/zns-api.service.ts`.
  - Created `ZnsOutreachModal` in `components/leads/zns-outreach-modal.tsx` with dynamic template schema inputs, mobile mockup preview, and anti-spam guardrail banners.
- **Testing:**
  - 11 unit & integration tests pass with 100% success rate.
  - Ruff formatting and Biome checks pass cleanly.

### File List
- `nowing_backend/app/gateway/zalo/webhook.py` (modified)
- `nowing_backend/app/gateway/zalo/tasks.py` (new)
- `nowing_backend/app/gateway/zalo/zns_client.py` (new)
- `nowing_backend/app/schemas/zns.py` (new)
- `nowing_backend/app/routes/zns_routes.py` (new)
- `nowing_backend/app/routes/__init__.py` (modified)
- `nowing_backend/tests/unit/gateway/test_zalo_webhook_hmac.py` (new)
- `nowing_backend/tests/unit/gateway/test_zns_client.py` (new)
- `nowing_backend/tests/integration/gateway/test_zalo_webhook_e2e.py` (new)
- `nowing_web/lib/apis/zns-api.service.ts` (new)
- `nowing_web/components/leads/zns-outreach-modal.tsx` (new)
- `nowing_web/tests/leads/zns-outreach-modal.spec.ts` (new)

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
uv run ruff check app/gateway/zalo app/routes/zns_routes.py app/schemas/zns.py
uv run ruff format --check app/gateway/zalo app/routes/zns_routes.py app/schemas/zns.py

# 3. Frontend Biome Check
cd ../nowing_web
pnpm exec biome check components/leads/zns-outreach-modal.tsx lib/apis/zns-api.service.ts
```
