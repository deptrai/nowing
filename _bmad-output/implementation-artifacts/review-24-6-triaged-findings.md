---
story: "24-6"
review_date: "2026-08-22"
reviewers: ["manual-blind", "manual-edge", "manual-acceptance"]
verdict: "CHANGES REQUESTED"
---

# Code Review Findings — Story 24.6: Two-Way AI Outreach Auto-Reply Agent

## Triage Summary

| Bucket | Count |
|--------|-------|
| decision_needed | 1 |
| patch | 4 |
| defer | 2 |
| dismiss | 0 |

## decision_needed

### D1: Lead creation policy for unknown hot prospects — RESOLVED
- **Location:** `nowing_backend/app/services/auto_reply_agent.py:322-341`
- **AC/INV:** AC-3, AC-2
- **Decision:** Create a `Lead` record on first hot inbound so the `[Nhận Tư Vấn]` callback has a valid `lead_id`.

## patch

### P1: Multiple debounce Celery tasks scheduled per burst
- **Location:** `nowing_backend/app/services/inbound_debounce_service.py:34-75`
- **AC/INV:** AC-1
- **Severity:** medium
- **Detail:** Every `buffer_inbound_message` call schedules a fresh Celery task with `countdown=3s`. A burst of 5 messages in <3s creates 5 overlapping `process_auto_reply_buffer` tasks. The Redis lock prevents double-flush, but 4 of the 5 workers will wastefully acquire the lock, see an empty buffer, and return. Prefer a single timer keyed by `(channel, sender_id)` (e.g., `setex` a `...:scheduled` key and only `send_task` when the key is newly set) to reduce Celery load.

### P2: `process_auto_reply_buffer_task` resolves `user_id` incorrectly
- **Location:** `nowing_backend/app/tasks/celery_tasks/gateway_tasks.py:198-205`
- **AC/INV:** AC-2 (token usage attribution)
- **Severity:** medium
- **Detail:** The else branch attempts `await session.get(User, workspace.user_id)` when `workspace.user_id` is falsy, which will always be `None` because the same `workspace.user_id` is used as the argument. The workspace owner should be resolved from `workspace_memberships` (owner/admin role) or `workspace.user_id` should be the owning user. This causes `user_id=None` to be passed to `record_token_usage`, breaking cost attribution and the `user_id` non-null constraint if enforced.

### P3: Hot-lead alert bypasses workspace-telegram binding validation
- **Location:** `nowing_backend/app/services/auto_reply_agent.py:270-274, 305-311`
- **AC/INV:** AC-3, INV-23.11 (authorization)
- **Severity:** medium
- **Detail:** `_dispatch_hot_lead_alert` sends directly to `workspace.auto_reply_recipient_chat_id` using `config.TELEGRAM_SHARED_BOT_TOKEN` without validating that the chat ID belongs to a bound Telegram channel in the workspace. An owner can enter an arbitrary chat ID and the shared bot will message it. This is a minor authorization/anti-spam gap. Use `send_telegram_lead_alert` (which validates `ExternalChatBinding`) or enforce that `recipient_chat_id` matches a bound `external_thread_id`.

### P4: `build_lead_telegram_alert` callback data truncated by Telegram 64-byte limit
- **Location:** `nowing_backend/app/services/auto_reply_agent.py:300`
- **AC/INV:** AC-3
- **Severity:** low
- **Detail:** Telegram `callback_data` is limited to 64 bytes. The string `nhan_tu_van:{thread_id}:{lead_id}` is currently safe because `thread_id` is the binding `id` (a few digits) and `lead_id` is a UUID (36 chars) — total ~65-70 chars. If `thread_id` grows (e.g., external provider thread string) or prefixes change, the button will silently fail. Defensively shorten by encoding `lead_id` as an integer/index or warn on length; at minimum assert `len(callback_data) <= 64` in tests.

## defer

### De1: Human-in-the-Loop takeover from CRM not wired
- **Location:** `nowing_backend/app/gateway/inbox_processor.py:562-589` and outbound message path
- **AC/INV:** AC-4
- **Detail:** AC-4 requires that when a human sales rep sends a message from the Nowing CRM Inbox or directly on the channel, the thread is flagged as human-controlled and `auto_reply_paused` is set for 24h. The current diff wires the inbound side only. The outbound "human sends message" path is pre-existing/out of this diff and not connected to `pause_auto_reply`. Defer to a follow-up 24.6b or CRM inbox story.

### De2: Zalo OA webhook signature verification
- **Location:** `nowing_backend/app/gateway/zalo/webhook.py`
- **AC/INV:** INV-23.11
- **Detail:** Already listed as deferred in the story file; no changes to Zalo webhook in this diff.

## dismissed

None.
