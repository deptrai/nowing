---
story_key: "26-6"
epic: "epic-26"
story: "26.6"
title: "Telegram Interactive Checkpoint Bot & 1-Click Auto-Refund Dialog"
status: "ready-for-dev"
baseline_commit: "d3c104138"
validated_at: "2026-08-19"
---

# Story 26.6: Telegram Interactive Checkpoint Bot & 1-Click Auto-Refund Dialog

## CRITICAL DESIGN DECISIONS — Resolve Before Dev

1. **Do not stuff UUIDs into Telegram `callback_data`.**
   - Telegram limits `callback_data` to 64 bytes. A raw `dsh_unlock:{mission_id}:{lead_id}:{contact_id}` payload is far too large.
   - **Decision:** Create a mapping table `telegram_checkpoint_messages` with a short `callback_token` (e.g. 16–24 URL-safe characters). The inline keyboard sends `dsh:{action}:{token}`. On callback, look up the row by `callback_token` to recover `workspace_id`, `mission_id`, `lead_id`, `contact_id`, and the original `external_message_id` used for `edit_message`.
   - `callback_token` MUST be unique and have a single-column unique index.

2. **When to send the checkpoint card and how the worker passes the lead.**
   - The card must be sent only after the lead is actually persisted (after `batch_ingest_leads` in the `ingestion` phase). Sending from the `extraction` phase is tempting but the lead does not yet have a stable `lead_id`/`contact_id` and the unlock endpoint would not work.
   - **Decision:** The `dsh-worker` calls a new internal endpoint `POST /v1/dsh/missions/{mission_id}/notify-high-fit` immediately after a successful `batch_ingest_leads`.
   - The worker only knows the `lead_id` (see Decision 6). The backend loads the lead and picks the first `VerifiedContact` with a phone to set `contact_id` on `TelegramCheckpointMessage`.
   - The internal route is mounted on `dsh_internal_router` (prefix `/v1`), NOT `/api/v1/internal/dsh/...`. The public DSH routes live under `/api/v1`, the internal worker routes live under `/v1` (see `app/app.py:1186-1187` and `dsh_routes.py:308`).

3. **Refund is for the *unlock* cost, not the phone-resolution cost, and must use a NEW billing method.**
   - `BillingService.auto_refund_lead` refunds the phone-resolution waterfall cost (`PhoneWaterfallLog`). That is a different ledger and a different amount than a user-initiated `contact_unlock` (1,500 micros).
   - `BillingEventService.record_contact_unlock_refund` already exists and is **unconditional**; it is used by PII opt-out (`app/services/pii/opt_out_service.py:181-194`). Do **not** add a 24h window or 15% cap to it, or opt-out refunds will break.
   - **Decision:** Add a new `BillingEventService.record_contact_unlock_refund_24h` that:
     - Loads the original `contact_unlock` `BillingEvent` and verifies it is within `DSH_TELEGRAM_REFUND_WINDOW_HOURS`.
     - Reuses the same 15% cap pattern as `record_contact_relock` (`_billing_cycle_bounds` + `_count_workspace_events`).
     - Credits 1,500 micros back to the original payer, writes a negative `BillingEvent` with `event_type='contact_unlock_refund'`, refunds member monthly spend, marks `VerifiedContact.is_valid=False` and appends an audit log.

4. **Verification before refund.**
   - The AC says "verifies via Zalo/HLR check". Re-running the full 3-tier waterfall for every refund is expensive and may debit the user.
   - **Decision:** Use the most recent `PhoneWaterfallLog` for the lead as primary evidence.
     - If a log exists and `status='failed'`, treat the number as invalid and refund immediately.
     - If the log is missing, `status='success'`, or inconclusive, run a lightweight HLR/Zalo verification. Add a `verify_only` mode to `PhoneWaterfallService` (or call `_resolve_tier_3_carrier_hlr` directly) that **does not debit** the wallet and only returns `valid|invalid`.
   - If verification says the number is reachable/active, do **not** refund; edit the message to "Số điện thoại vẫn hoạt động — không thể hoàn tiền." and stop.

5. **PII must stay masked until the user explicitly unlocks, and must never be persisted in `TelegramCheckpointMessage.action_payload`.**
   - The Telegram card may only show a masked phone (`0908***456`). The real phone is only revealed after the user clicks `🔓 Mở khóa SĐT` and the backend confirms sufficient credits, just like the web `POST .../contacts/{contact_id}/unlock` flow.
   - `TelegramCheckpointMessage` stores `contact_id` and `status`. The unmasked phone is decrypted on-the-fly from `VerifiedContact` when the message is edited; it is **never** written to `action_payload` or any other JSONB column.

6. **Worker → backend contract for the high-fit lead.**
   - `batch_ingest_leads` currently returns only `lead_ids` (`app/services/lead_batch_service.py:290-296`), and the insertion order is not guaranteed to match the worker's input order.
   - The worker cannot know `contact_id` because `VerifiedContact.id` is generated inside `lead_batch_service.py` and not returned.
   - **Decision:**
     - Extend `BatchLeadIngestResponse` (or the internal service return value) with `lead_id_mapping: dict[str, UUID]` keyed by `value_hmac` so the worker can map its input lead to the persisted `lead_id`.
     - `DshNotifyHighFitRequest` accepts `lead_id: UUID` and an optional `contact_id: UUID | None`. The worker sends `lead_id` only; the backend resolves `contact_id`.
     - The worker selects the highest-fit lead from its local `leads` list using `fit_score >= DSH_TELEGRAM_FIT_SCORE_THRESHOLD` and `phone` present, computes its `value_hmac`, looks up the `lead_id`, and calls the notify endpoint.

7. **Rate limiting for inline callbacks.**
   - The existing `@limiter.limit` in `app/rate_limiter.py` is for FastAPI routes, not the Telegram callback handler.
   - **Decision:** Rate-limit at two layers:
     - The public Telegram webhook route (`/api/v1/gateway/telegram/webhook` or equivalent) keeps the existing `@limiter.limit`/`app/rate_limiter.py` slowapi guard.
     - Inside `handle_callback_query`, for `dsh:*` actions, use the existing `app/gateway/ratelimit.py` token-bucket `acquire_token` with a scope like `telegram:checkpoint:{workspace_id}:{user_id}`, capacity `DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE` (e.g. 60), refill 1 token per second. If `acquire_token` returns `wait_ms > 0`, answer the callback with a brief alert and return.

8. **Telegram callback dispatch parser must be rewritten for 3-part payloads.**
   - The current `handle_callback_query` splits `data.split(":", 1)` and expects `parts[1].isdigit()` (`app/gateway/telegram/callbacks.py:371-406`). It cannot parse `dsh:unlock:<token>` because the token is not a digit and there are two colons.
   - **Decision:** Replace the parser with a 3-part split: `prefix:action:token`. Route `dsh` prefix to `DshTelegramCheckpointService` by `action ∈ {unlock, dossier, skip, call, zalo, refund}`.

9. **User preference for DSH lead notifications.**
   - AC-1 requires "the user has not disabled DSH lead notifications."
   - **Decision:** Use the existing `User.notification_preferences` JSONB with key `{"dsh_high_fit_lead": {"telegram": true}}`. If the key is missing or `telegram` is not `True`, skip the card. The preference is read by the backend before sending.

10. **Unlock callback must set `VerifiedContact.is_unlocked` and `pii_access_audit_logs`, not just bill.**
    - `BillingEventService.record_contact_unlock` only records the billing event. The web `unlock_contact` route sets `is_unlocked=True`, decrypts PII, and appends `pii_access_audit_logs` (`app/routes/lead_batch_routes.py:277-291`).
    - **Decision:** Either extract a shared `ContactUnlockService` (recommended) that both the route and the Telegram callback call, or have `DshTelegramCheckpointService` perform the same steps explicitly. Reusing the same service prevents divergence.
    - `unlock_contact` returns `409 CONFLICT` when `is_valid=False` or `consent_status='withdrawn'` (`app/routes/lead_batch_routes.py:234-238`), not `403`. The Telegram callback must map `409` to a distinct error message.

11. **Use `TelegramAdapter.edit_message`, not `editMessageText`.**
    - The adapter method is `edit_message` (`app/gateway/telegram/adapter.py:165-188`). It supports both `chat_id+message_id` and `inline_message_id`. The underlying client calls `edit_message_text`, but the adapter wrapper is the public API.

## Story

As a mobile sales rep using Telegram,
I want to receive a 3-second glanceable lead card when a DSH mission discovers a high-fit lead, with inline buttons to unlock the phone, view a dossier, or skip,
So that I can act on hot leads immediately from my phone without opening the Nowing web app, and get an automatic refund if the unlocked number turns out to be invalid.

---

## Acceptance Criteria

### AC-1 — High-fit lead checkpoint card after mission ingestion (AD-104, AD-105)

- **Given** a DSH mission has reached the `ingestion` phase and `batch_ingest_leads` has succeeded,
- **When** at least one ingested lead has `fit_score >= DSH_TELEGRAM_FIT_SCORE_THRESHOLD` and a phone,
- **Then** the `dsh-worker` selects the highest-fit lead from its input list, resolves the persisted `lead_id` via the `lead_id_mapping` returned by `batch_ingest_leads`, and calls `POST /v1/dsh/missions/{mission_id}/notify-high-fit` with `DshNotifyHighFitRequest(lead_id=..., contact_id=None)`,
- **And** the backend:
  1. Verifies `X-Dsh-Worker-Secret` and a workspace-scoped PAT (same as `patch_dsh_mission_checkpoint`).
  2. Loads `mission` and `lead`, then picks the first `VerifiedContact` with `phone IS NOT NULL` as `contact_id`.
  3. Loads `mission.user_id` and resolves the most recent active Telegram `ExternalChatBinding` for that user + workspace, where `ExternalChatAccount.platform='telegram'`, `state='bound'`, and account health is not `FAILING`.
  4. Checks `User.notification_preferences["dsh_high_fit_lead"]["telegram"] == True`; if the preference is missing it defaults to **enabled**, but if explicitly `False`, skip silently.
  5. Sends a Telegram message with a structured MarkdownV2 card:
     - Header: `🎯 Lead mới — {company_name}` (escaped)
     - `Fit score: {fit_score}/100`
     - `SĐT: {masked_phone}` (`0908***456`)
     - `Nguồn: {source} | {domain}`
     - Inline keyboard: `[🔓 Mở khóa SĐT] [🌐 Xem Dossier] [❌ Bỏ qua]`
  6. Persists a `TelegramCheckpointMessage` row with `status='sent'`, a unique `callback_token`, `external_message_id`, `external_peer_id`, `mission_id`, `lead_id`, `contact_id`, `workspace_id`, `user_id`.
- **And** only **one** checkpoint card is sent per mission. If multiple leads qualify, the one with the highest `fit_score` is chosen; ties broken by `created_at DESC` (or worker input order).
- **And** the worker swallows non-fatal errors from the notify endpoint so a Telegram failure does not fail the DSH mission.

### AC-2 — 1-Click unlock and inline edit (AD-105, AD-110)

- **Given** a checkpoint card with `status='sent'` and the user clicks `[🔓 Mở khóa SĐT]`,
- **When** the callback is dispatched,
- **Then** the backend:
  1. Authenticates the user through the existing `ExternalChatBinding` and checks `LEADS_WRITE` permission for the workspace.
  2. Loads `TelegramCheckpointMessage` by `callback_token`, then loads `VerifiedContact` with `FOR UPDATE`.
  3. Runs the same unlock service used by `POST .../contacts/{contact_id}/unlock`:
     - Fail-closed DNC check (`DncComplianceService`).
     - If `contact.is_valid=False` or `consent_status='withdrawn'`, raise `409 CONFLICT`.
     - Check wallet balance (`User.credit_micros_balance >= 1_500`). If insufficient, raise `402 PAYMENT_REQUIRED`.
     - Decrypt PII, set `is_unlocked=True`, append `pii_access_audit_logs` entry with `access_type='unlock'`, `reason='telegram_unlock'`, `user_id`, `workspace_id`, `lead_id`, `contact_id`, `timestamp`, `ip_address`.
     - Call `BillingEventService.record_contact_unlock` to debit 1,500 micros.
  4. On success, calls `TelegramAdapter.edit_message` to show:
     - `✅ Đã mở khóa SĐT — {unmasked_phone}`
     - `💳 -1.5 credits`
     - Inline keyboard: `[📲 Gọi điện] [💬 Zalo] [🛡️ Báo số sai / Hoàn tiền]`
  5. Updates `TelegramCheckpointMessage.status = 'unlocked'` and `unlocked_at = now()`.
- **And** on `402 Payment Required`, edit the message to "Không đủ credits. Nạp thêm tại ..." without revealing PII.
- **And** on `403` (DNC blocked), edit the message to "Số điện thoại bị chặn bởi DNC."
- **And** on `409` (purged / withdrawn consent), edit the message to "Liên hệ này đã bị rút lại đồng ý hoặc đánh dấu không hợp lệ."

### AC-3 — Dossier and skip actions

- **Given** a checkpoint card,
- **When** the user clicks `[🌐 Xem Dossier]`,
- **Then** the bot edits the same message to append a concise dossier:
  - `Công ty: {company_name}`
  - `Domain: {domain}`
  - `Fit: {fit_score} | Intent: {intent_score}`
  - `Nguồn: {source_url}`
  - Deep-link: `[Mở trong Nowing]({NEXT_FRONTEND_URL}/workspaces/{workspace_id}/leads/{lead_id})`
- **And** all MarkdownV2 reserved characters in dynamic fields are escaped via `escape_markdown_v2`.
- **And** the original action buttons (`Mở khóa`, `Bỏ qua`) remain available below the dossier.

- **Given** a checkpoint card,
- **When** the user clicks `[❌ Bỏ qua]`,
- **Then** the bot edits the message to "Bạn đã bỏ qua lead này." and updates `TelegramCheckpointMessage.status = 'dismissed'`.

### AC-4 — 1-Click auto-refund for invalid numbers (AD-110)

- **Given** an unlocked checkpoint card and the user clicks `[🛡️ Báo số sai / Hoàn tiền]` within `DSH_TELEGRAM_REFUND_WINDOW_HOURS` of `TelegramCheckpointMessage.unlocked_at`,
- **When** the workspace's `contact_unlock_refund` count is `< 15%` of total `contact_unlock` events in the current billing cycle,
- **Then** the backend:
  1. Loads the original `contact_unlock` `BillingEvent` and confirms `now - created_at <= 24 hours`. If expired, return the 24h expired message.
  2. Verifies the number:
     - Load the most recent `PhoneWaterfallLog` for `contact_id`.
     - If `status='failed'`, treat as invalid.
     - If missing, `success`, or inconclusive, run `PhoneWaterfallService` in `verify_only` mode (no debit). If it returns `valid|active`, do **not** refund.
  3. If the number is confirmed invalid/unreachable and the 15% cap is not exhausted:
     - Credits 1,500 micros back to the original payer wallet via `wallet_credit.apply_credit`.
     - Refunds member monthly spend via `WorkspaceCreditService.refund_member_spend`.
     - Writes a negative `BillingEvent` with `event_type='contact_unlock_refund'`, `event_entity_type='verified_contact'`, `cost_micros=-1_500`.
     - Marks `VerifiedContact.is_valid=False`, `verification_status='invalid'`, `invalid_reason='telegram_refund'`, `refunded_at=now()`.
     - Appends a `pii_access_audit_logs` entry with `access_type='refund'`, `user_id`, `reason='invalid_number'`, `timestamp`, `contact_id`, `lead_id`, `workspace_id`.
  4. Edits the message to `✅ Đã hoàn tiền +1.5 credits — SĐT đã được đánh dấu không hợp lệ.`
  5. Updates `TelegramCheckpointMessage.status = 'refunded'` and `refunded_at = now()`.
- **And** if verification says the number is still reachable, edit the message to `❌ Không thể hoàn tiền: số điện thoại vẫn hoạt động.`
- **And** if the 15% cap is exhausted, edit the message to `❌ Không thể hoàn tiền: đã hết hạn mức hoàn tiền tự động tháng này.`
- **And** if the 24h window has passed, edit the message to `❌ Đã hết hạn 24h để báo số sai.`
- **And** the refund method is idempotent: a second refund for the same `contact_id` returns the existing refund `BillingEvent` without double-crediting.

### AC-5 — PII, audit, auth, and rate limits

- **Given** the checkpoint flow,
- **Then**:
  - Raw phone/email/name never appears in any Telegram message until the user explicitly unlocks the contact.
  - Every unlock and refund appends to `VerifiedContact.pii_access_audit_logs`.
  - The flow respects workspace RBAC: only a bound Telegram user with `LEADS_WRITE` can unlock or refund.
  - `POST /v1/dsh/missions/{mission_id}/notify-high-fit` is guarded by `X-Dsh-Worker-Secret` and a workspace-scoped PAT, consistent with `patch_dsh_mission_checkpoint` in `dsh_routes.py`.
  - The public Telegram webhook route uses the existing `app/rate_limiter.py` `@limiter.limit` guard.
  - Inside `handle_callback_query`, `dsh:*` callbacks enforce a per-workspace+user token-bucket rate limit via `app/gateway/ratelimit.py:acquire_token` (capacity `DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE`, refill 1 token/second). When the bucket is empty, answer the callback with a rate-limit alert.
  - `TelegramCheckpointMessage.callback_token` has a unique constraint and is looked up with `SELECT ... FOR UPDATE` to prevent callback replay race conditions.

### AC-6 — Tests and verification

- **Given** the updated backend,
- **When** the test suite runs,
- **Then**:
  - `ruff check` and `ruff format` pass on all touched Python files.
  - `pytest tests/unit/gateway/telegram/test_telegram_callbacks.py -q` passes with new `dsh_*` callback tests.
  - `pytest tests/unit/services/test_dsh_telegram_checkpoint_service.py -q` passes.
  - `pytest tests/unit/services/test_billing_event_service.py -q` passes for `record_contact_unlock_refund_24h` (24h window, 15% cap, idempotency).
  - `pytest tests/integration/routes/test_dsh_telegram_checkpoint.py -q` passes: worker calls notify endpoint, card sent, callback unlock edits message, dossier/skip/refund callbacks, 409/403/402 error paths.
  - `pytest tests/integration/routes/test_dsh_telegram_checkpoint_refund.py -q` passes: 24h refund, cap exhausted, invalid number verification, verification-returns-valid case.
  - Alembic migration for `telegram_checkpoint_messages` applies cleanly against an empty database and against real data.

---

## Source Artifacts & Traceability

| Artifact | Path | Relevant Lines | What it provides |
|---|---|---|---|
| Epics & Stories | `_bmad-output/planning-artifacts/epics.md` | 3394–3406 | Story 26.6 text and ACs. |
| Architecture Invariants | `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` | 104–145, 174–187 | AD-102 sidecar, AD-104 CDC, AD-105 PII vault, AD-110 anti-fraud refund cap, two-tier unlock UX. |
| Previous story (Two-Tier Phone Unlock) | `_bmad-output/implementation-artifacts/26-5-split-canvas-glass-box-mission-control-two-tier-phone-unlock-shimmer-influx.md` | full file | Unlock/relock endpoint contracts, masking, audit, refund cap patterns. |
| Telegram gateway adapter | `nowing_backend/app/gateway/telegram/adapter.py` | 22–146, 148–201, 203–220 | `parse_inbound`, `send_message`, `edit_message`, `edit_message_reply_markup`, `answer_callback_query`. |
| Telegram client | `nowing_backend/app/gateway/telegram/client.py` | 86–160, 241–252 | `send_message`, `edit_message_text`, `answer_callback_query`. |
| Telegram callback dispatch | `nowing_backend/app/gateway/telegram/callbacks.py` | 336–406 | `handle_callback_query` currently only handles `view_run:{int}` and `rerun:{int}`; must be extended to 3-part `dsh:{action}:{token}`. |
| Telegram command bundle | `nowing_backend/app/gateway/telegram/commands.py` | 396–464 | `TelegramGatewayCommands` wiring to `handle_callback_query`. |
| Inbox processor routing | `nowing_backend/app/gateway/inbox_processor.py` | 448–493 | Dispatches `callback_query` to `bundle.commands.handle_callback_query`. |
| Telegram formatting | `nowing_backend/app/gateway/telegram/formatting.py` | 18–26, 61–77 | `escape_markdown_v2`, `chunk_message`. |
| Telegram notification pattern | `nowing_backend/app/automations/services/telegram_notifications.py` | 116–243 | `resolve_telegram_binding_for_run`, user `notification_preferences` check, MarkdownV2 send. |
| Rate limiter (route) | `nowing_backend/app/rate_limiter.py` | 33–39 | SlowAPI `limiter` used by FastAPI route decorators. |
| Gateway rate limit (callbacks) | `nowing_backend/app/gateway/ratelimit.py` | 88–134 | Token-bucket `acquire_token` already used by Telegram onboarding; reuse for `dsh:*` callbacks. |
| DSH worker | `nowing_backend/app/tasks/dsh_worker.py` | 129–211, 410–451 | `DshRestClient` (`patch_checkpoint`, `batch_ingest_leads`), `ingestion` phase. |
| DSH mission service | `nowing_backend/app/services/dsh_mission_service.py` | 60–148, 182–228 | `create_mission`, `update_checkpoint`, `list_missions_for_workspace`. |
| DSH routes | `nowing_backend/app/routes/dsh_routes.py` | 38–85, 282–353 | `require_dsh_worker`, `PATCH /v1/dsh/missions/{mission_id}/checkpoint` — new endpoint uses same auth. |
| DSH schemas | `nowing_backend/app/schemas/dsh.py` | 1–131 | Existing mission schemas; add `DshNotifyHighFitRequest/Response`. |
| Lead batch service | `nowing_backend/app/services/lead_batch_service.py` | 220–296 | `ingest_batch`, `hmac_to_id` mapping, verified_contacts creation. |
| Lead batch routes | `nowing_backend/app/routes/lead_batch_routes.py` | 184–328, 331–443 | `unlock_contact`/`relock_contact`, `ContactUnlockResponse`, error codes 402/403/409. |
| Billing event service | `nowing_backend/app/services/billing_event_service.py` | 72–186, 187–293 | `record_contact_unlock`, `record_contact_relock` (has 15% cap + 24h/60s window pattern). |
| Billing service (24h SLA refund) | `nowing_backend/app/services/billing_service.py` | 58–212 | `auto_refund_lead` pattern for phone waterfall refunds; **do not reuse for contact unlock refund**. |
| Phone waterfall service | `nowing_backend/app/services/phone_waterfall_service.py` | 55–173, 180–220, 375–423 | Normalization, carrier validation, `_resolve_tier_3_carrier_hlr` for HLR/Zalo verification. |
| Phone waterfall worker | `nowing_backend/app/tasks/phone_waterfall_worker.py` | 81–116 | `auto_refund_lead_task` Celery pattern. |
| Report invalid phone route | `nowing_backend/app/routes/leads_routes.py` | 761–799 | `report_invalid_phone_endpoint` and `PhoneRefundResponse` (waterfall refund, not unlock). |
| Lead / contact models | `nowing_backend/app/db.py` | 4633–4653, 5164–5243 | `Lead`, `VerifiedContact` (PII, unlock, audit, consent). |
| DshMission model | `nowing_backend/app/db.py` | 3727–3809 | `DshMission.id`, `workspace_id`, `user_id`, `payload`, `checkpoint`. |
| ExternalChatBinding model | `nowing_backend/app/db.py` | 1027–1125 | Telegram binding and account platform. |
| PhoneWaterfallLog model | `nowing_backend/app/db.py` | 5256–5279 | Log for HLR/Zalo verification evidence. |
| BillingEvent model | `nowing_backend/app/db.py` | 4613–4630 | Ledger for unlock/refund events. |
| LeadRead schema | `nowing_backend/app/lead_intelligence/schemas.py` | 38–91 | Fields to render in Telegram card. |
| PII masking | `nowing_backend/app/services/pii/mask.py` | 13–62 | `mask_phone`, `mask_email`, `mask_name`. |
| Verified contact encryption | `nowing_backend/app/services/pii/verified_contact_encryption.py` | full file | Fernet/TokenEncryption; only unlock endpoints may decrypt. |
| Workspace credit service | `nowing_backend/app/services/workspace_credit_service.py` | 294–330, 425–489, 491–520 | `record_spend`, `refund_credits`, `refund_member_spend`. |
| Wallet credit | `nowing_backend/app/services/wallet_credit.py` | 126–150+ | `apply_credit` / `apply_debit` wallet primitives. |
| Config | `nowing_backend/app/config/__init__.py` | 666–685 | DSH worker config block to extend. |

---

## Technical Context — Already BUILT

- **Telegram gateway is production-ready.** Inbound webhooks, long-poll, callback parsing, `send_message`, `edit_message`, `answer_callback_query` are all implemented and used by automations and `/start` pairing (`app/gateway/telegram/`).
- **DSH worker writes checkpoint through authenticated REST.** The sidecar never touches the database directly; it uses `DshRestClient.patch_checkpoint` and `batch_ingest_leads` (Story 26.2).
- **Internal DSH routes live under `/v1`.** Public DSH routes live under `/api/v1`. The worker's `DshRestClient` calls `/v1/dsh/missions/{mission_id}/...` (`app/tasks/dsh_worker.py:129-138` and `app/app.py:1186-1187`).
- **Unlock/relock endpoints and billing ledger exist (Story 26.5).** `POST .../contacts/{contact_id}/unlock` debits 1,500 micros, decrypts PII, appends audit logs, and returns `402`/`403`/`409`. `POST .../relock` refunds in a 60s window and uses a 15% cap. `BillingEventService.record_contact_relock` demonstrates the exact pattern needed for the 24h/15% refund cap (`app/services/billing_event_service.py:245-267`).
- **`BillingEventService.record_contact_unlock_refund` is unconditional and used by PII opt-out.** Do **not** modify it. Add `record_contact_unlock_refund_24h` for Telegram's 24h/15% cap.
- **`BillingService.auto_refund_lead` refunds the *phone-resolution* cost, not the *contact unlock* cost.** It is a useful reference for refund mechanics but must not be called from the Telegram refund flow.
- **Phone waterfall resolution exists (Story 21.3).** `PhoneWaterfallService.resolve_lead_phone` normalizes Vietnamese mobile numbers, runs tiered resolution, and writes `PhoneWaterfallLog` with carrier / confidence / status. It does not currently have a `verify_only` mode — add one or use `_resolve_tier_3_carrier_hlr` directly.
- **24h auto-refund SLA exists for phone resolution (Story 21.3).** `BillingService.auto_refund_lead` and `report_invalid_phone_endpoint` handle invalid numbers, but they refund the *waterfall* cost, not the *contact unlock* cost.
- **PII masking and encryption are centralized.** `mask_phone`/`mask_email`/`mask_name` and `VerifiedContactEncryption` are the only approved ways to display or decrypt PII.
- **`User.notification_preferences` is a JSONB.** Use it for the DSH Telegram opt-in: `{"dsh_high_fit_lead": {"telegram": true}}`.

---

## Gaps & Implementation Hints

- **No worker trigger for high-fit lead notifications.** `app/tasks/dsh_worker.py` currently has no Telegram checkpoint call. Add a `DshRestClient.notify_high_fit_lead(mission_id, lead_id, contact_id=None)` and a backend `POST /v1/dsh/missions/{mission_id}/notify-high-fit` route on `dsh_internal_router`.
- **No `lead_id` mapping returned from `batch_ingest_leads`.** The response (`app/services/lead_batch_service.py:290-296`) only returns `lead_ids`. Extend the internal service return value / response with `lead_id_mapping: dict[str, UUID]` (keyed by `value_hmac`) so the worker can map its selected high-fit lead to the persisted `lead_id`.
- **No mapping table for Telegram message → lead/contact.** Add `TelegramCheckpointMessage` in `app/db.py` plus an Alembic migration. Required because `callback_data` is limited to 64 bytes and `edit_message` needs the original `message_id`.
- **No 24h/15% cap refund for `contact_unlock` events.** `BillingEventService.record_contact_unlock_refund` is unconditional (no SLA window, no 15% cap) and is used by PII opt-out. Add a NEW `record_contact_unlock_refund_24h` method.
- **Refund verification must not re-charge the user.** Do not call the full `PhoneWaterfallService.resolve_lead_phone` (that debits). Use the latest `PhoneWaterfallLog` or add a `verify_only=True` mode / call `_resolve_tier_3_carrier_hlr` directly.
- **Telegram callback dispatch needs a 3-part parser.** `app/gateway/telegram/callbacks.py` currently only knows `view_run:` and `rerun:` with 2-part, digit payloads. Replace with generic `dsh:{action}:{token}` parsing.
- **No configuration for fit-score threshold / refund cap.** Add `DSH_TELEGRAM_FIT_SCORE_THRESHOLD = 80`, `DSH_TELEGRAM_REFUND_CAP_PCT = 0.15`, `DSH_TELEGRAM_REFUND_WINDOW_HOURS = 24`, `DSH_TELEGRAM_MAX_LEADS_PER_MISSION = 1`, `DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE = 60` to `app/config/__init__.py`.
- **No shared unlock service.** Refactor `app/routes/lead_batch_routes.py:unlock_contact` to delegate to a new `app/services/contact_unlock_service.py:unlock_contact` so the Telegram callback can reuse the exact same logic without copying code.
- **No DSH lead notification preference key.** Decide on `User.notification_preferences["dsh_high_fit_lead"]["telegram"]`. Missing = enabled; `False` = disabled.
- **No rate-limit for inline callbacks other than the route-level limiter.** Use `app/gateway/ratelimit.py:acquire_token` inside `handle_callback_query` for `dsh:*` callbacks with scope `telegram:checkpoint:{workspace_id}:{user_id}` and a per-minute capacity.
- **No `DshNotifyHighFitRequest/Response` schemas.** Add to `app/schemas/dsh.py`.

---

## Project Structure Notes

### New backend files
- `nowing_backend/app/services/dsh_telegram_checkpoint_service.py` — `DshTelegramCheckpointService` to build and send the card, handle unlock/dossier/skip/refund callbacks, and persist `TelegramCheckpointMessage`.
- `nowing_backend/app/services/contact_unlock_service.py` — shared `unlock_contact` logic used by both `lead_batch_routes.py` and the Telegram flow.
- `nowing_backend/app/services/billing_event_service.py` — add `record_contact_unlock_refund_24h` method (do not rename/change existing `record_contact_unlock_refund`).
- `nowing_backend/alembic/versions/XXX_add_telegram_checkpoint_messages_table.py` — migration for `telegram_checkpoint_messages`.
- `nowing_backend/tests/unit/gateway/telegram/test_telegram_callbacks.py` — extend with `dsh_*` callback tests.
- `nowing_backend/tests/unit/services/test_dsh_telegram_checkpoint_service.py` — build card, mask PII, pick high-fit lead, notification preference.
- `nowing_backend/tests/integration/routes/test_dsh_telegram_checkpoint.py` — integration tests for the full flow.
- `nowing_backend/tests/integration/routes/test_dsh_telegram_checkpoint_refund.py` — 24h refund, cap, verification cases.

### Files to modify
- `nowing_backend/app/db.py` — add `TelegramCheckpointMessage` model.
- `nowing_backend/app/config/__init__.py` — add `DSH_TELEGRAM_*` config keys.
- `nowing_backend/app/services/lead_batch_service.py` — return `lead_id_mapping` from `ingest_batch` so the worker can resolve `lead_id`.
- `nowing_backend/app/tasks/dsh_worker.py` — call `notify_high_fit_lead` after `batch_ingest_leads` success; add `notify_high_fit_lead` to `DshRestClient`.
- `nowing_backend/app/routes/dsh_routes.py` — add `POST /v1/dsh/missions/{mission_id}/notify-high-fit` (internal, worker-only, on `dsh_internal_router`).
- `nowing_backend/app/routes/lead_batch_routes.py` — refactor `unlock_contact` to call `ContactUnlockService`; optionally add `POST .../contacts/{contact_id}/refund-invalid` for web parity or keep it Telegram-only.
- `nowing_backend/app/gateway/telegram/callbacks.py` — dispatch `dsh:{action}:{token}` callbacks.
- `nowing_backend/app/rate_limiter.py` — no change unless the public Telegram route needs a stricter limit.
- `nowing_backend/app/schemas/dsh.py` — add `DshNotifyHighFitRequest` and `DshNotifyHighFitResponse`.

### No frontend changes
This story is backend-only. The mobile UX is delivered entirely through Telegram inline keyboards.

---

## `TelegramCheckpointMessage` DB Contract (add to `app/db.py`)

```python
class TelegramCheckpointMessage(Base, TimestampMixin):
    """Maps a Telegram inline-keyboard message to a lead/contact for DSH checkpoints."""

    __tablename__ = "telegram_checkpoint_messages"

    __table_args__ = (
        UniqueConstraint("callback_token", name="uq_telegram_checkpoint_callback_token"),
        Index("ix_telegram_checkpoint_callback_token", "callback_token"),
        Index("ix_telegram_checkpoint_message_peer", "external_message_id", "external_peer_id"),
        Index("ix_telegram_checkpoint_workspace_mission", "workspace_id", "mission_id"),
        Index("ix_telegram_checkpoint_workspace_lead", "workspace_id", "lead_id"),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_telegram_checkpoint_lead_id_workspace_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    callback_token = Column(String(24), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="sent")

    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    mission_id = Column(UUID(as_uuid=True), ForeignKey("dsh_missions.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("verified_contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)

    external_message_id = Column(Text, nullable=True)
    external_peer_id = Column(Text, nullable=True)

    unlocked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    refunded_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Safe metadata only (e.g. {"dossier_visible": true}). NEVER store unmasked PII here.
    action_payload = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
```

---

## P0 Surface Assessment

- **Credit wallet and billing events** — P0 (unlock, refund, cap).
- **PII display and masking** — P0.
- **DNC / consent gating** — P0.
- **Telegram callback auth / workspace scoping** — P0.
- **New DB table with FKs** — P0 (migration correctness).

Per `nowing-quality-pipeline.md`, integration tests on real Postgres are P0-gated, and billing/PII changes require the P0 human-review gate.

---

## Tasks / Subtasks

### Backend

- [ ] **Task B0: Lead batch response mapping (AC-1)**
  - [ ] Extend `BatchLeadIngestResponse` / internal `ingest_batch` return to include `lead_id_mapping: dict[str, UUID]` keyed by `value_hmac`.
  - [ ] Update tests that assert the response shape.

- [ ] **Task B1: Schema & migration (AC-5, AC-6)**
  - [ ] Add `TelegramCheckpointMessage` to `app/db.py` with the contract above.
  - [ ] Create Alembic migration `XXX_add_telegram_checkpoint_messages_table.py`.
  - [ ] Add unique constraint on `callback_token`.
  - [ ] Add indexes on `callback_token`, `(external_message_id, external_peer_id)`, `(workspace_id, mission_id)`, and `(workspace_id, lead_id)`.

- [ ] **Task B2: Config (AC-1, AC-4)**
  - [ ] Add `DSH_TELEGRAM_FIT_SCORE_THRESHOLD = 80`, `DSH_TELEGRAM_REFUND_CAP_PCT = 0.15`, `DSH_TELEGRAM_REFUND_WINDOW_HOURS = 24`, `DSH_TELEGRAM_MAX_LEADS_PER_MISSION = 1`, `DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE = 60` to `app/config/__init__.py`.

- [ ] **Task B3: DSH worker trigger (AC-1)**
  - [ ] In `app/tasks/dsh_worker.py`, after successful `batch_ingest_leads`, pick the highest-fit lead with `fit_score >= threshold` and `phone` from the worker's input list.
  - [ ] Map it to `lead_id` via `lead_id_mapping` returned by `batch_ingest_leads`.
  - [ ] Add `DshRestClient.notify_high_fit_lead(mission_id, lead_id, contact_id=None)`.
  - [ ] Call it once per mission; swallow non-fatal errors.

- [ ] **Task B4: Internal notify endpoint (AC-1, AC-5)**
  - [ ] Add `POST /v1/dsh/missions/{mission_id}/notify-high-fit` on `dsh_internal_router` in `app/routes/dsh_routes.py`.
  - [ ] Guard by `require_dsh_worker` + `_require_pat_workspace_scope`.
  - [ ] Load lead, resolve contact, resolve Telegram binding for `mission.user_id`, check `User.notification_preferences`, build and send card, persist `TelegramCheckpointMessage`.

- [ ] **Task B5: Shared contact unlock service (AC-2, AC-5)**
  - [ ] Extract `unlock_contact` core logic from `app/routes/lead_batch_routes.py` into `app/services/contact_unlock_service.py`.
  - [ ] Refactor route to delegate; both route and `DshTelegramCheckpointService` use the same service.

- [ ] **Task B6: Checkpoint card formatting & sending (AC-1, AC-3)**
  - [ ] Create `DshTelegramCheckpointService.build_card(lead, contact)` returning MarkdownV2 text + inline keyboard.
  - [ ] Mask phone/email/name until unlock; escape all dynamic MarkdownV2 text.
  - [ ] Use `TelegramAdapter.send_message` with `parse_mode='MarkdownV2'` and `reply_markup`.
  - [ ] Implement `show_dossier(token)` and `skip(token)` callbacks that use `TelegramAdapter.edit_message`.

- [ ] **Task B7: Unlock callback (AC-2)**
  - [ ] Implement `dsh:unlock:{token}` dispatch.
  - [ ] Call `ContactUnlockService.unlock_contact(...)`; capture `402`/`403`/`409`.
  - [ ] On success, decrypt phone on-the-fly and `TelegramAdapter.edit_message` to show unmasked phone + call/Zalo/refund buttons.
  - [ ] On error, edit message to the appropriate Vietnamese/English copy and do not reveal PII.

- [ ] **Task B8: Refund callback (AC-4)**
  - [ ] Add `BillingEventService.record_contact_unlock_refund_24h` with 24h window and 15% cap, reusing `_billing_cycle_bounds` and `_count_workspace_events`.
  - [ ] Verify invalid via latest `PhoneWaterfallLog.status='failed'` or `PhoneWaterfallService.verify_only`.
  - [ ] On success: credit wallet, refund member spend, write negative `BillingEvent`, set `VerifiedContact.is_valid=False`, append audit log.
  - [ ] On verification-returns-valid / cap exhausted / 24h expired, edit message with the correct copy.

- [ ] **Task B9: Callback dispatch wiring (AC-1 to AC-4)**
  - [ ] Extend `app/gateway/telegram/callbacks.py` `handle_callback_query` to parse `dsh:{action}:{token}`.
  - [ ] Enforce per-workspace/user token-bucket rate limit for `dsh:*` callbacks via `app/gateway/ratelimit.py:acquire_token`.
  - [ ] Route to `DshTelegramCheckpointService` methods.
  - [ ] Always `answer_callback_query` to clear the spinner.

### Tests

- [ ] **Task T1: Unit tests**
  - [ ] `tests/unit/gateway/telegram/test_telegram_callbacks.py`: parse `dsh:unlock:{token}`, `dsh:refund:{token}`, `dsh:dossier:{token}`, `dsh:skip:{token}` dispatch.
  - [ ] `tests/unit/services/test_dsh_telegram_checkpoint_service.py`: build card, mask PII, pick high-fit lead, notification preference skip.
  - [ ] `tests/unit/services/test_billing_event_service.py`: refund 24h window, 15% cap, idempotency, no-op when verification returns valid.

- [ ] **Task T2: Integration tests**
  - [ ] `tests/integration/routes/test_dsh_telegram_checkpoint.py`: worker calls notify endpoint, card sent, callback unlock edits message, 402/403/409 paths, dossier/skip callbacks.
  - [ ] `tests/integration/routes/test_dsh_telegram_checkpoint_refund.py`: 24h refund, cap exhausted, invalid number verification, verification-returns-valid case.

- [ ] **Task T3: Quality gates**
  - [ ] `ruff check app/db.py app/config/__init__.py app/services/lead_batch_service.py app/tasks/dsh_worker.py app/routes/dsh_routes.py app/routes/lead_batch_routes.py app/gateway/telegram/callbacks.py app/services/dsh_telegram_checkpoint_service.py app/services/contact_unlock_service.py app/services/billing_event_service.py app/schemas/dsh.py`
  - [ ] `ruff format` on same.
  - [ ] `uv run alembic upgrade head` and `uv run alembic downgrade -1` clean.

### Review Findings (Chunk 1 — core implementation)

Review ngày 2026-08-19. Tổng hợp từ 3 layer: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

#### Decision cần người dùng

- [x] [Review][Decision] **Group chat / shared device: chỉ cho phép callback từ direct chat (`binding.external_peer_kind == "direct"`).** Trong group chat, bất kỳ ai nhấn inline keyboard cũng thực hiện unlock/skip/refund với quyền của owner; tạm chặn yêu cầu chat riêng để tránh rủi ro tài chính. `nowing_backend/app/gateway/telegram/callbacks.py:350-395`

#### Patch (high)

- [x] [Review][Patch] **TelegramAdapter khởi tạo thiếu bot token, card không thể gửi.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:278`
- [x] [Review][Patch] **`send_message` trả về `PlatformSendResult` nhưng code kiểm tra `dict`, `external_message_id` không được lưu.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:280-287`
- [x] [Review][Patch] **Refund credit wallet trước khi persist `BillingEvent`, gây race double-credit / mất event.** `nowing_backend/app/services/billing_event_service.py:412`
- [x] [Review][Patch] **`record_contact_relock` và `record_contact_unlock_refund_24h` return event của nhau, conflate ledger.** `nowing_backend/app/services/billing_event_service.py:228-236,348-356`
- [x] [Review][Patch] **DSH worker fallback về `ingest_res["lead_ids"][0]` khi HMAC mapping miss, thông báo sai lead.** `nowing_backend/app/tasks/dsh_worker.py:468-471`
- [x] [Review][Patch] **Block gửi Telegram nằm trong `try/except` của ingestion; lỗi notification làm ingestion fail.** `nowing_backend/app/tasks/dsh_worker.py:439-504`
- [x] [Review][Patch] **Không có idempotency/unique guard "một mission một card", worker retry có thể spam nhiều card.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:260-272` và `nowing_backend/app/db.py:3819-3837`
- [x] [Review][Patch] **Refund verification quá sơ sài, không gọi HLR/Zalo `verify_only`; active number có thể bị hoàn tiền.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:586-607`

#### Patch (medium)

- [x] [Review][Patch] **Binding query không lọc `revoked_at`/`suspended_at` và `health_status` so sánh sai case.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:192-209`
- [x] [Review][Patch] **`fit_score` 0.0 bị coi là missing, hiển thị 80.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:75`
- [x] [Review][Patch] **Re-unlock sau relock miễn phí nhưng API vẫn báo `cost_micros=1500`.** `nowing_backend/app/services/contact_unlock_service.py:92-102` và `nowing_backend/app/services/billing_event_service.py:91-102`
- [x] [Review][Patch] **`handle_skip_callback` ghi đè trạng thái `unlocked`/`refunded`, không xóa inline keyboard.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:539-578`
- [x] [Review][Patch] **Refund callback không từ chối card chưa unlock.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:639-660`
- [x] [Review][Patch] **Scope rate-limit callback `dsh:*` không đúng `telegram:checkpoint:{workspace_id}:{user_id}`.** `nowing_backend/app/gateway/telegram/callbacks.py:350-355`
- [x] [Review][Patch] **Dossier deep-link URL chỉ escape `)` và `\`, dễ hỏng MarkdownV2.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:499-507`
- [x] [Review][Patch] **`handle_refund_callback` parse thông báo lỗi bằng substring thay vì exception type cụ thể.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:718-728`
- [x] [Review][Patch] **`handle_unlock_callback` bắt `InsufficientCreditsError` dead code (đã bị `ContactUnlockService` bắn HTTPException 402).** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:410-426`
- [x] [Review][Patch] **`_handle_dsh_callback` không catch exception từ service handlers, `answer_callback_query` bị gọi 2 lần.** `nowing_backend/app/gateway/telegram/callbacks.py:397-437`
- [x] [Review][Patch] **Malformed `dsh:` callback không được trả lời rõ ràng, spinner treo.** `nowing_backend/app/gateway/telegram/callbacks.py:476-489`
- [x] [Review][Patch] **Notify endpoint không validate `contact_id` thuộc về `lead_id`.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:226-253`
- [x] [Review][Patch] **`select_high_fit_lead` sort có thể crash với mixed types / string `fit_score`.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:112-151`
- [x] [Review][Patch] **15% cap bị bỏ qua khi `unlock_count=0` ở billing cycle mới (cross-cycle refund).** `nowing_backend/app/services/billing_event_service.py:400-406`
- [x] [Review][Patch] **Audit log refund thiếu `lead_id` (AC-4 yêu cầu).** `nowing_backend/app/services/billing_event_service.py:430-440`
- [x] [Review][Patch] **Config `DSH_TELEGRAM_REFUND_CAP_PCT` dùng `float(os.getenv)` sẽ crash nếu env rỗng/không phải số.** `nowing_backend/app/config/__init__.py:689-691`
- [x] [Review][Patch] **Card sau unlock thiếu nút "📲 Gọi điện" (AC-2).** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:380-392`
- [x] [Review][Patch] **`should_send_telegram_notification` trả `True` khi `user is None`.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:153-156`
- [x] [Review][Patch] **Chọn contact không lọc `phone IS NOT NULL` và bỏ cuộc nếu contact đầu tiên invalid/withdrawn.** `nowing_backend/app/services/dsh_telegram_checkpoint_service.py:235-249`

---

## Dev Notes

### Architecture Compliance & Invariants

- **AD-102 (Decoupled Sidecar):** The worker does not talk to Telegram or the DB directly. It calls `POST /v1/dsh/missions/{mission_id}/notify-high-fit` and lets the backend handle Telegram.
- **AD-104 (Zero-Cache CDC):** No Zero-Cache changes are needed; the card is pushed outbound via Telegram API.
- **AD-105 (PII Vault):** Only the `ContactUnlockService` decrypts PII. The Telegram card stores masked values and `contact_id`. The unmasked phone is only revealed after a successful unlock and is never persisted in `TelegramCheckpointMessage.action_payload`.
- **AD-110 (Anti-Fraud Refund):** The 15% auto-refund cap is a *separate* budget from the 60s accidental-relock cap in Story 26.5. Track it with `event_type='contact_unlock_refund'` vs `event_type='contact_unlock'` in the same billing cycle.

### Existing Code to Reuse

- `app/gateway/telegram/adapter.py` and `client.py` for send/edit.
- `app/automations/services/telegram_notifications.py:resolve_telegram_binding_for_run` to find the right binding and `notification_preferences` pattern.
- `app/routes/lead_batch_routes.py:unlock_contact` and `relock_contact` for the unlock/audit pattern — refactor into `ContactUnlockService`.
- `app/services/billing_event_service.py` for wallet debit/credit and ledger; reuse the 15% cap pattern in `record_contact_relock`.
- `app/services/phone_waterfall_service.py` for HLR/Zalo verification (add `verify_only` mode or call `_resolve_tier_3_carrier_hlr`).
- `app/services/pii/mask.py` for all masked display.
- `app/services/pii/verified_contact_encryption.py` for PII decryption.

### Testing Hints

- Use `TelegramAdapter` with a `FakeTelegramClient` (or monkeypatch `send_message`/`edit_message`) to capture `reply_markup` and `text`.
- The callback tests must verify `edit_message` is called with the correct `external_peer_id` and `external_message_id` from the stored `TelegramCheckpointMessage`.
- For refund cap tests, create multiple `contact_unlock` `BillingEvent` rows and assert the cap blocks the Nth refund; also assert that `status='failed'` in the most recent `PhoneWaterfallLog` short-circuits verification.
- For 24h window tests, patch `datetime.now(UTC)` to exceed 24h and assert the refund is blocked with the correct message copy.

### Important Pitfalls

- Do **not** reuse `BillingService.auto_refund_lead` for the Telegram contact-unlock refund — it refunds the phone-resolution waterfall cost, not 1,500 micros.
- Do **not** add the 24h/15% cap to `BillingEventService.record_contact_unlock_refund` — it is used by PII opt-out and must stay unconditional.
- Do **not** store unmasked phone/email in `TelegramCheckpointMessage.action_payload` — decrypt from `VerifiedContact` on each edit.
- Do **not** mount the internal notify endpoint under `/api/v1` — it must be under `/v1` with `dsh_internal_router`.
- Do **not** assume `batch_ingest_leads` returns `contact_id`; the backend resolves it from `lead_id`.

---

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **No pre-built `DshTelegramCheckpointService` or `ContactUnlockService`.** These will be new.
- **Existing Telegram notification pattern found:** `send_automation_run_telegram_notification` in `nowing_backend/app/automations/services/telegram_notifications.py:142-243` already uses `resolve_telegram_binding_for_run` + `TelegramAdapter.send_message(..., parse_mode="MarkdownV2")`. **Recommendation:** reuse that binding-resolution and message-send flow for the DSH card.
- **Existing callback dispatcher found:** `handle_callback_query` in `nowing_backend/app/gateway/telegram/callbacks.py:336-406` only supports `view_run:{int}` and `rerun:{int}`. It must be **extended**, not replaced.
- **Existing unlock logic found:** `unlock_contact` in `nowing_backend/app/routes/lead_batch_routes.py:190-328` contains the full DNC check, PII decryption, audit log, and `BillingEventService.record_contact_unlock` call. **If the Telegram callback copies this code, it creates a duplicate.** The story already proposes extracting a `ContactUnlockService` — this should be mandatory, not optional.
- **Existing 15% cap + window pattern found:** `BillingEventService.record_contact_relock` in `nowing_backend/app/services/billing_event_service.py:187-293` already implements the billing-cycle 15% cap and time-window check. The new `record_contact_unlock_refund_24h` should reuse or extract a shared helper instead of rewriting the same accounting.
- **Existing `PhoneWaterfallLog` is available** (`nowing_backend/app/db.py:5256-5327`) with `contact_id`, `status`, `phone_hash`. Reuse it for refund evidence.
- **Warning:** `BillingEventService.record_contact_unlock_refund` (`app/services/billing_event_service.py:100-186`) is unconditional and is used by `OptOutService` (`app/services/pii/opt_out_service.py:157-207`). Do **not** add the 24h/15% cap to it.

### Q2 — Is there a simpler alternative?

- **Rate limiter for callbacks: RESOLVED — use `app/gateway/ratelimit.py`.** The existing `nowing_backend/app/gateway/ratelimit.py:88-134` already provides a Redis token-bucket `acquire_token`/`wait_for_token` and is already used by Telegram onboarding. For `dsh:*` callbacks, use scope `f"telegram:checkpoint:{workspace_id}:{user_id}"` (or `binding.id`), capacity `DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE` (e.g. 60), refill 1 token/second. When the bucket is empty, answer the callback with a brief rate-limit alert.
- **`callback_token` generation:** Use `secrets.token_urlsafe(16)` (stdlib) instead of a custom generator.
- **Mission / contact loading:** Reuse `DshMissionService.get_mission_for_workspace` and `LeadBatchService`/`VerifiedContact` queries instead of writing raw SQL.
- **Masking / PII:** `app/services/pii/mask.py` and `app/services/pii/verified_contact_encryption.py` already exist and should be the only paths used.
- **Telegram formatting:** `app/gateway/telegram/formatting.py` already has `escape_markdown_v2` and `chunk_message`. Reuse it.

### Q3 — Edge cases the spec misses (Pattern 3)

- **Token / mapping table collisions:**
  - Concurrent `POST /v1/dsh/missions/{mission_id}/notify-high-fit` calls (at-least-once worker) could insert two `TelegramCheckpointMessage` rows. Need unique constraint on `mission_id` or an idempotent `SELECT ... FOR UPDATE` to enforce "one card per mission."
  - `callback_token` must be unique across the table; verify with `SELECT FOR UPDATE` before send.
- **Lead selection:**
  - Exact `fit_score == DSH_TELEGRAM_FIT_SCORE_THRESHOLD` (>= is specified, but test at the boundary).
  - Multiple leads tie on `fit_score`; tie-breaker `created_at DESC` is mentioned but the worker may not know `created_at`.
  - Lead has multiple `VerifiedContact` rows with phone; which one is picked? (Story says "first" — define order: `created_at ASC` or contact with `is_valid=True` first.)
  - Lead has only email (no phone) — worker filter + backend fallback should skip.
- **Contact state at send time:**
  - `VerifiedContact.is_valid=False` or `consent_status='withdrawn'` at the moment the backend sends the card. Should the card be sent at all? If not, the endpoint should return 200/ignored and not send.
  - `VerifiedContact.is_unlocked=True` before the card is sent (e.g., re-ingested lead). The card should probably show the unmasked phone immediately with no charge, or the unlock button should be a no-op.
- **User / binding:**
  - `DshMission.user_id` is `None`.
  - `User` exists but has no bound Telegram account.
  - `User.notification_preferences` has malformed JSON (e.g., `"dsh_high_fit_lead": false` instead of `{"telegram": true}`).
  - `ExternalChatBinding` is `revoked`/`suspended` after the card was sent; the callback still arrives with a snapshot binding. Should re-check `state` in the handler.
- **Refund accounting:**
  - 24h window boundary (exactly 24h or 24h + 1s).
  - 15% cap: `unlock_count=0` vs `unlock_count=1` (cap = 1); first refund allowed, second blocked. Need tests at the boundary.
  - Second refund click while the first is in flight — idempotency of `record_contact_unlock_refund_24h`.
  - Refund verification with `PhoneWaterfallLog.status='failed'` but `contact_id` is `None` (failed logs do not store contact). Need to fall back to the stored `TelegramCheckpointMessage.contact_id`.
  - `PhoneWaterfallLog.status='blocked_by_dnc'` or `'degraded'` — should these be treated as invalid for refund? The spec only mentions `failed`.
  - Verification returns `valid` but the user still says the number is invalid. There is no human-review escalation in the spec.
- **DNC / consent after unlock:**
  - User clicks unlock, contact is blocked by DNC (race). The unlock route returns 403. The callback must map this to a Vietnamese error message.
  - User clicks unlock after contact was already purged/withdrawn (409). Need a distinct message.
- **Callback data:**
  - Callback token + action length must stay ≤ 64 bytes. Need an assertion in tests.
  - Unknown / malformed `dsh:xxx:{token}` payload should be answered and ignored.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- **Telegram API failures:**
  - `TelegramAdapter.send_message`/`edit_message` may raise `BadRequest` (parse/keyboard too large) or `RetryAfter`. The client has MarkdownV2/keyboard fallbacks, but the service must catch, log, and not crash the webhook.
  - Invalid/deleted Telegram bot token; message send fails. Should the DSH mission fail? No — the worker should swallow the error.
  - Message is too old to edit. Need a fallback to `send_message` with the updated card.
- **Database / Redis failures:**
  - Insert `TelegramCheckpointMessage` fails due to unique `callback_token` or FK. Should retry once with a new token.
  - `session.commit()` fails after the Telegram message was already sent. This leaves an orphan message with no DB row. **Ordering:** persist the row (with `external_message_id=None`) first, then send, then update `external_message_id`.
  - Redis unavailable for rate limiting. `app/gateway/ratelimit.py` falls back to per-process memory (`_memory_fallback_acquire`) when Redis is down. The callback should still be rate-limited in-process; test the fallback path.
- **Verification provider failures:**
  - `PhoneWaterfallService._resolve_tier_3_carrier_hlr` is only a passive prefix heuristic; it does not perform a live HLR/Zalo query. If it returns `valid`, the number could still be dead. The spec's "HLR/Zalo check" may be misleading. If a real provider is added later, the `verify_only` mode must handle provider timeout/down and fail closed (do not refund if uncertain).
  - `PhoneWaterfallLog` is often missing for DSH-ingested leads (no phone resolution was run). The fallback to `_resolve_tier_3_carrier_hlr` will run for every refund.
- **Billing / wallet failures:**
  - `wallet_credit.apply_credit` fails because the original payer user was deleted. Should still refund? Spec says credit original payer. If not found, credit the user who clicked? Need a fallback.
  - `WorkspaceCreditService.refund_member_spend` returns 0 if membership not found. This is non-fatal; wallet credit is the primary refund.
  - `BillingEventService.record_contact_unlock` raises `402`/`422`/`ValueError`. The Telegram callback must catch and edit the message, not crash.
  - Original `contact_unlock` `BillingEvent` not found (e.g., data inconsistency). Cannot refund; should edit "Không tìm thấy giao dịch mở khóa." and stop.
- **Auth / scoping failures:**
  - `X-Dsh-Worker-Secret` missing/invalid → 403.
  - PAT missing or not scoped to workspace → 403.
  - Callback from a forwarded message: the `callback_token` lookup must verify that the inbound `ExternalChatBinding` matches the `TelegramCheckpointMessage.user_id`/`external_peer_id` to prevent one user from acting on another user's card.
  - User loses `LEADS_WRITE` permission between card send and callback click → 403.

### Triage

| Finding | Severity | Action |
|---|---|---|
| Q2: existing `app/gateway/ratelimit.py` token-bucket is a simpler/more consistent alternative for callback rate limiting | **Resolved** | Use `app/gateway/ratelimit.py:acquire_token` with scope `telegram:checkpoint:{workspace_id}:{user_id}`, capacity `DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE`, refill 1 token/second. Rate-limiter decision resolved. |
| Q1: `unlock_contact` route contains full unlock logic; must extract `ContactUnlockService` to avoid duplicate in Telegram callback | Non-critical | Continue, but make `ContactUnlockService` extraction mandatory in story. |
| Q1: `record_contact_relock` already has 15% cap/window pattern; `record_contact_unlock_refund_24h` should share a helper | Non-critical | Continue, add a `_refund_contact_unlock_with_cap` helper or similar. |
| Q3: many boundary/concurrent/edge cases missing (token collision, cap boundary, DNC race, callback data size) | Non-critical | Continue, add to test-first ATDD skeleton and mutation tests. |
| Q4: verification is only prefix heuristic; live HLR/Zalo provider down / false positives not specified | Non-critical | Continue, document in test plan and consider a follow-up story for live HLR. |
| Q4: Telegram API / DB commit ordering can orphan the card | Non-critical | Continue, ensure tests cover the "DB first, then send, then update" order. |

## Review Findings

#### decision-needed
*None — resolved during validation.*

#### patch
*None yet.*

#### defer
*None yet.*

---

## Dev Agent Record

### Agent Model Used

*(Filled by dev agent during implementation.)*

### Debug Log References

*(Filled by dev agent during implementation.)*

### Completion Notes List

*(Filled by dev agent during implementation.)*

### File List

*(Filled by dev agent during implementation.)*
