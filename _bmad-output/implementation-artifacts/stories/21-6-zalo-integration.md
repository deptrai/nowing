---
baseline_commit: b1f688eee31cff54ede82d9a11a836815cdd827f
---

# Story 21.6: Zalo Integration (Vietnam Market)

Status: in-progress

## Story

As a Vietnamese salesperson,
I want to communicate with leads via Zalo,
Because 81% of Vietnamese professionals use Zalo as their primary messaging platform.

## Acceptance Criteria

- Given a Zalo OA connection, when configured, then outreach sequences can include Zalo messages
- Given a lead with Zalo contact, when outreach is triggered, then personalized Zalo messages are sent
- Given a Zalo reply, when received, then it's logged in the lead's activity timeline
- Given Zalo messaging, when sent, then it complies with Zalo business messaging policies and Decree 356

## Tasks / Subtasks

- [x] Task 1: Zalo OA Connection
  - [x] 1.1 Create `ZaloConnection` model (id, workspace_id, oa_id, access_token_encrypted)
  - [x] 1.2 Zalo OA OAuth flow setup
  - [x] 1.3 Token refresh mechanism
- [x] Task 2: Zalo Messaging & Assisted Co-pilot
  - [x] 2.1 Assisted Outbound Co-pilot (`https://zalo.me/{clean_phone}` + AI Draft + Clipboard)
  - [x] 2.2 Send personalized Zalo messages & ZNS via OA OpenAPI
  - [x] 2.3 Receive replies via webhook & detect buying intent
  - [x] 2.4 Log messages in `zalo_message_logs` activity timeline
  - [x] 2.5 Telegram Bot rich alerts with quick action buttons
- [x] Task 3: Compliance & Resilience
  - [x] 3.1 Decree 356 consent management guardrail
  - [x] 3.2 Unsubscribe/opt-out handling
  - [x] 3.3 Rate limiting (20 msg/min/OA) via Redis leaky/token bucket

## Dev Notes

- **AD-41:** Zalo integration for Vietnam market
- **AD-SOC-7:** Vietnam Assisted Outbound Co-pilot (Deep-link & Telegram Bot Alert)
- **Source:** `app/gateway/zalo/`, `app/routes/outbound_routes.py`, `components/leads/zalo-outreach-button.tsx`

### References

- [Source: epics.md §FR-68]
- [Source: epic21-architecture-update.md §AD-41]

## Dev Agent Record

### Agent Model Used

Antigravity Dev Agent (Claude 3.7 Sonnet / Gemini 2.5 Pro)

### File List

**Backend:**
- `app/db.py`: Added `ZaloConnection` and `ZaloMessageLog` models, workspace/lead relationships.
- `alembic/versions/212_add_zalo_gateway_tables.py`: Migration 212 creating `zalo_connections` and `zalo_message_logs`.
- `app/gateway/zalo/__init__.py`: Package exports for Zalo gateway.
- `app/gateway/zalo/client.py`: `ZaloClient` with rate limiter (20/min), token refresh, phone normalization, AI draft generator.
- `app/gateway/zalo/telegram_alerts.py`: Telegram rich lead alert builder with MarkdownV2 formatting and inline deep-link keyboard.
- `app/gateway/zalo/webhook.py`: Webhook signature verification, Vietnamese buying intent detection, inbound event processor.
- `app/routes/outbound_routes.py`: REST routes for Zalo draft, ZNS sending, OA connection CRUD, webhook, Telegram alerts.
- `app/routes/__init__.py`: Registered `outbound_router`.
- `app/tasks/phone_waterfall_worker.py`: Fixed `set_request_tenant_context` import.
- `tests/unit/gateway/test_zalo_gateway.py`: Unit test suite (20 tests passed).
- `tests/integration/gateway/test_zalo_outbound_pipeline.py`: Integration test suite (4 tests passed).
- `tests/integration/conftest.py`: Added safe PostGIS extension check.

**Frontend:**
- `contracts/types/leads.types.ts`: Zod schemas & TypeScript types for Zalo draft, ZNS request/response.
- `lib/apis/leads-api.service.ts`: API client methods `getZaloDraft` and `sendZns`.
- `components/leads/zalo-outreach-button.tsx`: Assisted Zalo Outbound Co-pilot button with AI script modal.
- `components/leads/lead-intelligence-table.tsx`: Lead intelligence table with integrated Zalo Action column.
- `components/leads/LeadCard.tsx`: Integrated Zalo Outreach Button into Lead card footer.

### Verification Results

```bash
# Backend unit & integration tests
uv run pytest tests/unit/gateway/test_zalo_gateway.py -q
# -> 20 passed in 0.22s

uv run pytest tests/integration/gateway/test_zalo_outbound_pipeline.py -q
# -> 4 passed in 2.83s

# Backend linter
ruff check app/gateway/zalo app/routes/outbound_routes.py tests/unit/gateway/test_zalo_gateway.py tests/integration/gateway/test_zalo_outbound_pipeline.py
# -> All checks passed!

# Frontend type check & linter
pnpm tsc --noEmit
# -> 0 errors

pnpm exec biome check components/leads/zalo-outreach-button.tsx components/leads/lead-intelligence-table.tsx components/leads/LeadCard.tsx contracts/types/leads.types.ts lib/apis/leads-api.service.ts
# -> 0 errors, all files formatted cleanly
```

### Review Findings

Generated from code review run on 2026-08-15. Full layer reports:
- Blind Hunter: `_bmad-output/review-artifacts/21-6-blind-hunter.md`
- Edge Case Hunter: `_bmad-output/review-artifacts/21-6-edge-case-hunter.md`
- Acceptance Auditor: `_bmad-output/review-artifacts/21-6-acceptance-auditor.md`

#### Decision Needed
- [ ] [Review][Decision] `ZaloClient` conflates OAuth `app_secret` with `webhook_secret`. Need design: add `app_secret_encrypted` to `ZaloConnection`, or rely on global `ZALO_APP_SECRET`? `client.py:197-198`
- [ ] [Review][Decision] Webhook verification currently bypasses when secret empty and uses global `ZALO_APP_SECRET`. Should it fail-closed in production and use per-OA `webhook_secret`? `webhook.py:64-65`
- [ ] [Review][Decision] Story says "AI Draft" but implementation is a hard-coded template. Use LLM or rename to "template-assisted draft"? `client.py:69-152`
- [ ] [Review][Decision] `send_zns_message` does not select a specific OA if workspace has multiple active `ZaloConnection`. Require `oa_id` or add `is_primary` flag? `outbound_routes.py:292-297`
- [ ] [Review][Decision] No endpoint to deactivate or revoke a Zalo OA connection (`upsert` always `is_active=True`). `outbound_routes.py:470-471`

#### Patch
- [ ] [Review][Patch] Webhook falls back to hard-coded `workspace_id = 1` and alerts on every `user_send_text`. Reject unknown OA, alert only on buying intent, deduplicate on `msg_id`. `webhook.py:113-122,167-176`
- [ ] [Review][Patch] Webhook matches lead by `company_name.ilike(sender_id)` (Zalo user id) instead of phone/`zalo_user_id`. `webhook.py:134-143`
- [ ] [Review][Patch] Webhook does not validate JSON body shape or prevent replay/timestamp attacks. `webhook.py:52-85,574-583`
- [ ] [Review][Patch] `verify_zalo_signature` returns `True` when secret is empty. `webhook.py:64-65`
- [ ] [Review][Patch] `recipient_phone` set to Zalo `sender_id`, not an actual phone. `webhook.py:146-151`
- [ ] [Review][Patch] `format_vietnam_phone` fallback accepts arbitrary digits and produces invalid `84`-prefixed numbers. `client.py:55-60`
- [ ] [Review][Patch] `refresh_access_token` does not validate JSON response is a dict. `client.py:250-267`
- [ ] [Review][Patch] `send_cs_message` does not refresh the access token. `client.py:350-375`
- [ ] [Review][Patch] Duplicate `@router.post` decorators on `zalo-draft`, `zns-send`, and `telegram-alert` handlers. `outbound_routes.py:168-177,244-253,505-513`
- [ ] [Review][Patch] `send_zns_message` consent guard treats any non-empty `legal_basis` as consent and `opted_out` still passes. `outbound_routes.py:271-275`
- [ ] [Review][Patch] Frontend `znsSendRequestSchema` defaults `consent_confirmed=true`, contradicting backend default. `contracts/types/leads.types.ts:156`
- [ ] [Review][Patch] `send_zns_message` uses `error_code == 0` but Zalo may return string `"0"`. `outbound_routes.py:338-344`
- [ ] [Review][Patch] `send_zns_message` picks arbitrary active OA and has no idempotency on `tracking_id`. `outbound_routes.py:292-297,330-335`
- [ ] [Review][Patch] `ZaloMessageLog` stores raw `template_data` and webhook payloads without redaction. `outbound_routes.py:324-325` / `webhook.py:157-158`
- [ ] [Review][Patch] `TelegramAlertRequest.chat_id` has no workspace ownership/validation. `outbound_routes.py:111-114,538-548`
- [ ] [Review][Patch] ZNS send API exists but `zalo-outreach-button.tsx` only deep-links; no UI calls `sendZns`. Add send action or remove API if not used. `zalo-outreach-button.tsx`

#### Deferred
- [x] [Review][Defer] `leads_routes.py` awaits sync `has_permission` with 4 args (pre-existing 21.3 issue, unrelated to 21.6) — `leads_routes.py:640-645,691`
- [x] [Review][Defer] Phone waterfall worker `asyncio.run` and refund exception swallow (21.3 scope) — `tasks/phone_waterfall_worker.py:69,109-116`
- [x] [Review][Defer] Missing migration for `VerifiedContact`/`PhoneWaterfallLog` model changes (21.3 scope) — `app/db.py`
- [x] [Review][Defer] `app/db.py` reintroduces top-level `SpatialPlanningZone` circular import (10.8 scope) — `app/db.py:4762`
- [x] [Review][Defer] SQLAlchemy `cascade="delete-orphan"` vs migration `ON DELETE SET NULL` for `ZaloMessageLog` FKs — `app/db.py:5157-5161,5222-5224`
- [x] [Review][Defer] `PhoneResolutionResponse` hard-codes 1.5 credits for async `pending` (21.3 scope) — `leads_routes.py:595-602`
