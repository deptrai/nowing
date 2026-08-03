# Edge Case Hunter Findings — Story 11.1: Telegram Notification Foundation

## Findings

### 1. In-app notification title can exceed `VARCHAR(200)` and fail
- **Severity:** high
- **File:** `nowing_backend/app/automations/services/telegram_notifications.py` (~L149)
- **Evidence:**
  - `title = f"Automation '{automation.name}' {status_label}"`
  - `Notification.title` is `Column(String(200), nullable=False)` (`nowing_backend/app/notifications/persistence/models.py` ~L57)
  - `Automation.name` is `Column(String(200), nullable=False)` (`nowing_backend/app/automations/persistence/models/automation.py` ~L41)
- **Why not handled:** No truncation. A 200-character automation name produces a ~225-character title, causing a DB `DataError` (or `StringDataRightTruncation`). Because `NotificationService.create_notification` is called before the Telegram try/except, the in-app notification insert fails and no Telegram is attempted; the whole notification is lost.

### 2. Malformed `notification_preferences` can crash the notification Celery task
- **Severity:** high
- **File:** `nowing_backend/app/automations/services/telegram_notifications.py` (~L166-167)
- **Evidence:**
  - `preferences = user.notification_preferences or {}`
  - `if not preferences.get("automation_run_complete", {}).get("telegram"):`
- **Why not handled:** It assumes `automation_run_complete` is always a `dict`. If a user stores `{"automation_run_complete": true}` or any non-dict (e.g. via `/users/me` or a direct DB update), the second `.get("telegram")` raises `AttributeError`. By that point the in-app notification has already been committed, so the user gets the in-app notification but no Telegram, and the Celery task logs an exception.

### 3. `/users/me` allows `notification_preferences: null` despite a non-nullable DB column
- **Severity:** medium
- **File:**
  - `nowing_backend/app/schemas/users.py` (~L22)
  - `nowing_backend/app/routes/users_routes.py` (~L42-51)
  - `nowing_backend/app/db.py` (~L2736, L2891)
- **Evidence:**
  - `class UserUpdate(...): notification_preferences: dict[str, Any] | None = None`
  - `User.notification_preferences = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))`
- **Why not handled:** The new `/me/notification-preferences` endpoint always passes a dict, but the existing `/me` PATCH can receive `notification_preferences: null`. `BaseUserManager.update` will attempt to set the column to `NULL`, causing a `NOT NULL` constraint violation / 500.

### 4. Concurrent `/me/notification-preferences` updates can lose keys
- **Severity:** medium
- **File:** `nowing_backend/app/routes/users_routes.py` (~L20-31, L54-71)
- **Evidence:**
  - `_merge_notification_preferences` reads `auth.user.notification_preferences` at request time
  - It merges in memory, then calls `user_manager.update(..., UserUpdate(notification_preferences=merged), ...)` to overwrite the whole column
- **Why not handled:** The read-merge-write is not atomic. Two overlapping patches with different top-level keys can each merge against a stale snapshot; the later `UPDATE` overwrites the earlier one. No `SELECT FOR UPDATE` or optimistic lock is used.

### 5. Notification task has a very short TTL / can be killed mid-send
- **Severity:** medium
- **File:**
  - `nowing_backend/app/automations/runtime/executor.py` (~L31)
  - `nowing_backend/app/automations/tasks/notify_run_complete.py` (~L25-26)
- **Evidence:**
  - `notify_telegram_run_complete.apply_async(args=(run_id,), expires=30)`
  - `@celery_app.task(..., soft_time_limit=30, time_limit=60, ...)`
- **Why not handled:** `expires=30` discards the task if it isn't consumed within 30 s (busy broker/worker), silently dropping the notification. The 30/60 s limits can kill a slow or multi-chunk Telegram send, leaving the user with a partial message and no recovery/retry.

### 6. Telegram chunking can split MarkdownV2 escape sequences
- **Severity:** medium
- **File:**
  - `nowing_backend/app/gateway/telegram/formatting.py` (~L32-69)
  - `nowing_backend/app/automations/services/telegram_notifications.py` (~L359-360)
- **Evidence:**
  - `_split_at_boundary` hard-cuts at `max_units` UTF-16 code units and does not avoid splitting `\` + reserved-char pairs
  - `format_automation_run_message` escapes the whole text first (`escape_markdown_v2(output_text)` / `escape_markdown_v2(first_error)`), then calls `chunk_message(full_text)`
- **Why not handled:** A long run output without natural word/line boundaries (e.g. a base64 string or a long URL containing `=` or `*`) is escaped and then may be hard-cut between the backslash and the reserved character. The first chunk ends with a stray `\` and the next chunk starts with an unescaped reserved char, which triggers a Telegram `BadRequest` parse error and the client falls back to plain text, losing the clickable deep link and corrupting the output text.

### 7. Deep link is built without URL validation or escaping
- **Severity:** low
- **File:** `nowing_backend/app/automations/services/telegram_notifications.py` (~L74-78)
- **Evidence:**
  - `base_url = (config.NEXT_FRONTEND_URL or "").rstrip("/")`
  - `deep_link = f"{base_url}/dashboard/{automation.workspace_id}/automations/{automation.id}?run_id={run.id}"`
- **Why not handled:** If `NEXT_FRONTEND_URL` and `NOWING_PUBLIC_URL` are both unset, `base_url` is `""` and the link becomes relative (`/dashboard/...`), which is not a valid Telegram URL. Reserved chars in the URL (e.g. `=` in `?run_id=...`) may also trigger Telegram MarkdownV2 parse errors in some cases; the implementation relies on the client's fallback instead of escaping/validating the URL.

### 8. Frontend Telegram toggle has no in-flight guard
- **Severity:** low
- **File:** `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx` (~L184-203, ~L506-511)
- **Evidence:**
  - `async function toggleTelegramNotifications(enabled: boolean) { setTelegramNotificationsEnabled(enabled); ... }`
  - `<Switch ... disabled={isLoadingUserProfile} ... onCheckedChange={toggleTelegramNotifications} />`
- **Why not handled:** The switch is not disabled while the `authenticatedFetch` request is in flight. Rapid clicks or a slow request can cause overlapping toggles; the error path `setTelegramNotificationsEnabled(!enabled)` may revert to a stale value and leave the UI out of sync with the server.

### 9. Telegram binding resolution ignores suspended / revoked bindings
- **Severity:** low
- **File:** `nowing_backend/app/automations/services/telegram_notifications.py` (~L101-114)
- **Evidence:** `resolve_telegram_binding_for_run` filters only `ExternalChatBinding.state == BOUND` and `ExternalChatAccount.platform == TELEGRAM`
- **Why not handled:** It does not filter `ExternalChatBinding.suspended_at IS NULL` or `ExternalChatAccount.suspended_at IS NULL` / `revoked_at IS NULL`. A suspended or revoked binding can still be selected; the send is only stopped later after an API round-trip and a warning is logged.

### 10. `send_automation_run_telegram_notification` does not guard against non-terminal run statuses
- **Severity:** low
- **File:** `nowing_backend/app/automations/services/telegram_notifications.py` (~L117-148)
- **Evidence:**
  - `is_success = run.status == RunStatus.SUCCEEDED`
  - The in-app title and Telegram header always say "finished successfully" or "failed"
- **Why not handled:** `RunStatus` also includes `CANCELLED` and `TIMED_OUT`. If this function is ever called with one of those statuses (future code, manual invocation, or a test), it will misleadingly report "failed" and may have no error to display.

## Summary of changes reviewed

No source files were modified. This report is a read-only review of the diff in `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/code-review/diff-story-11.1.patch` against project root `/Users/luisphan/Documents/GitHub/nowing`.

Files touched by the diff that were traced:
- `nowing_backend/alembic/versions/187_add_user_notification_preferences.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/schemas/users.py`
- `nowing_backend/app/routes/users_routes.py`
- `nowing_backend/app/notifications/types.py`
- `nowing_backend/app/notifications/constants.py`
- `nowing_backend/app/automations/runtime/executor.py`
- `nowing_backend/app/automations/services/telegram_notifications.py`
- `nowing_backend/app/automations/tasks/notify_run_complete.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/app/gateway/telegram/formatting.py`
- `nowing_backend/app/gateway/telegram/client.py`
- `nowing_backend/tests/unit/automations/test_telegram_notification_formatter.py`
- `nowing_backend/tests/integration/automations/test_run_notification.py`
- `nowing_backend/tests/integration/routes/test_user_notification_preferences.py`
- `nowing_web/contracts/types/user.types.ts`
- `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx`
- `AGENTS.md`

Cross-referenced for boundary/edge analysis:
- `nowing_backend/app/notifications/persistence/models.py`
- `nowing_backend/app/notifications/service/facade.py`
- `nowing_backend/app/automations/persistence/models/run.py`
- `nowing_backend/app/automations/persistence/models/automation.py`
- `nowing_backend/app/automations/persistence/enums/run_status.py`
- `nowing_backend/app/automations/runtime/repository.py`
- `nowing_backend/app/gateway/telegram/adapter.py`
- `nowing_backend/app/gateway/telegram/client.py`
- `nowing_backend/app/gateway/accounts.py`
- `nowing_backend/app/users.py`
- `nowing_backend/app/tasks/celery_tasks/__init__.py`

## Notes / recommended actions

1. **Truncate the in-app title** (and possibly the Telegram message) before inserting the `Notification`. `notifications/constants.py` already defines `TITLE_MAX_LENGTH = 200` but it is not used in the new code.
2. **Defensively read `notification_preferences`**: check `isinstance(automation_run_complete, dict)` before the nested `.get("telegram")`.
3. **Disallow `null` for `notification_preferences` in `UserUpdate`** or explicitly treat it as an unset field in the manager update path.
4. **Consider atomicity** for the `/me/notification-preferences` merge (e.g. `SELECT FOR UPDATE` on the user row or an optimistic lock on `updated_at`).
5. **Review Celery `expires` / time limits**: either remove `expires=30` or align it with the task's `time_limit`; consider a larger `soft_time_limit` or a follow-up retry policy for multi-chunk sends.
6. **Make chunking escape-aware** or chunk *before* applying MarkdownV2 escaping so that escape sequences cannot be split across messages.
7. **Validate / escape the deep link** and ensure `NEXT_FRONTEND_URL` has a usable default or the link is omitted when the URL is unavailable.
8. **Add an `isSaving` / `isLoading` guard** to the React `Switch` while the preference PATCH is in flight.
9. **Filter out suspended/revoked bindings** in `resolve_telegram_binding_for_run`.
10. **Guard `send_automation_run_telegram_notification`** so it only runs for terminal run statuses, or maps `CANCELLED`/`TIMED_OUT` to separate messages.
