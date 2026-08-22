---
story: "24-6"
review_date: "2026-08-22"
reviewers: ["manual-blind", "manual-edge", "manual-acceptance"]
verdict: "APPROVED"
---

# Code Review Findings — Story 24.6: Two-Way AI Outreach Auto-Reply Agent

## Triage Summary

| Bucket | Count |
|--------|-------|
| decision_needed | 0 |
| patch | 0 |
| resolved | 7 |
| defer | 0 |
| dismiss | 1 |

## resolved

### D1: Lead creation policy for unknown hot prospects
- **Location:** `nowing_backend/app/services/auto_reply_agent.py:322-341`
- **AC/INV:** AC-3, AC-2
- **Resolution:** `_get_or_create_lead` now creates a `Lead` record for first-time hot senders so the `[Nhận Tư Vấn]` callback has a valid `lead_id`.

### P1: Multiple debounce Celery tasks scheduled per burst
- **Location:** `nowing_backend/app/services/inbound_debounce_service.py:34-75`
- **AC/INV:** AC-1
- **Resolution:** Added a Redis `...:scheduled` flag so a burst of inbound messages only schedules one `process_auto_reply_buffer` Celery worker.

### P2: `process_auto_reply_buffer_task` resolves `user_id` incorrectly
- **Location:** `nowing_backend/app/tasks/celery_tasks/gateway_tasks.py:198-205`
- **AC/INV:** AC-2
- **Resolution:** Billing user is now resolved from `WorkspaceMembership.is_owner` instead of the broken `session.get(User, workspace.user_id)` branch.

### P3: Hot-lead alert bypasses workspace-telegram binding validation
- **Location:** `nowing_backend/app/services/auto_reply_agent.py:270-274, 305-311`
- **AC/INV:** AC-3, INV-23.11
- **Resolution:** `_dispatch_hot_lead_alert` now uses `_resolve_telegram_chat_and_token` to validate the recipient chat belongs to a bound workspace Telegram channel and resolves the bot token from the bound account or shared fallback.

### P4: `build_lead_telegram_alert` callback data truncated by Telegram 64-byte limit
- **Location:** `nowing_backend/app/services/auto_reply_agent.py:300`
- **AC/INV:** AC-3
- **Resolution:** Callback prefix shortened from `nhan_tu_van:` to `ntv:` and an overflow guard returns `ntv:overflow:` if the data would exceed 64 bytes. `handle_callback_query` updated to accept both prefixes.

### De1: Human-in-the-Loop takeover from CRM not wired
- **Location:** `nowing_backend/app/routes/gateway_webhook_routes.py`
- **AC/INV:** AC-4
- **Resolution:** Added `POST /api/v1/gateway/bindings/{binding_id}/send` route allowing an authenticated workspace member to send a message to an external chat binding. The route pauses AI auto-reply for 24h via `pause_auto_reply(str(binding.id))` after a successful send. Unit test added in `tests/unit/gateway/test_webhook_routes.py::test_send_message_to_binding_pauses_auto_reply`.

## dismissed

### De2: Zalo OA webhook signature verification
- **Location:** `nowing_backend/app/gateway/zalo/webhook.py` / `nowing_backend/app/routes/outbound_routes.py:672`
- **AC/INV:** INV-23.11
- **Resolution:** Signature verification is already fully implemented and wired. `zalo_inbound_webhook` calls `verify_zalo_signature` with `connection.webhook_secret` before processing the event. No change needed.
