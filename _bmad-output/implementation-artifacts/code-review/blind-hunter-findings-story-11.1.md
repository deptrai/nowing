# Blind Hunter Findings — Story 11.1: Telegram Notification Foundation

Reviewed diff: `diff-story-11.1.patch`

The implementation adds a `notification_preferences` JSONB column, a deep-merge endpoint, a Celery-based Telegram delivery task for automation runs, and a frontend toggle. The overall design is sound, but several production-impacting issues were found.

---

## 1. In-app notification title can exceed `Notification.title` `VARCHAR(200)`

- **Severity:** high
- **File:** `nowing_backend/app/automations/services/telegram_notifications.py` ~L149
- **Evidence from diff/project:**
  - `title = f"Automation '{automation.name}' {status_label}"`
  - `Automation.name` is `String(200)` (`app/automations/persistence/models/automation.py` L41)
  - `Notification.title` is `String(200)` (`app/notifications/persistence/models.py` L57)
- **Risk:** For an automation name at its 200-character limit, the generated title is 220–235 characters. `NotificationService.create_notification()` calls `session.commit()`, so PostgreSQL raises a `DataError` for the oversize `title`. The exception is caught and logged in the Celery task, but **neither the in-app nor the Telegram notification is created**, and the failure is silent to the user.

---

## 2. Frontend toggle does not recover from `authenticatedFetch` rejections

- **Severity:** medium
- **File:** `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx` ~L184–203
- **Evidence from diff/project:**
  ```tsx
  async function toggleTelegramNotifications(enabled: boolean) {
      setTelegramNotificationsEnabled(enabled);
      const res = await authenticatedFetch(buildBackendUrl("/users/me/notification-preferences"), {
          ...
      });
      if (!res.ok) {
          setTelegramNotificationsEnabled(!enabled);
          toast.error("Failed to update Telegram notification preference");
          return;
      }
      ...
  }
  ```
- **Risk:** If `authenticatedFetch` throws (network/DNS/CORS error) rather than returning a non-OK `Response`, the `await` rejects and the function exits without entering the `!res.ok` branch. The switch stays in the wrong state, the user sees no error toast, and the preference may not match the displayed toggle.

---

## 3. Telegram sends are attempted without checking account/binding suspension

- **Severity:** medium
- **File:** `nowing_backend/app/automations/services/telegram_notifications.py` ~L374–L469
- **Evidence from diff/project:**
  - `resolve_telegram_binding_for_run()` only checks `ExternalChatBinding.state == ExternalChatBindingState.BOUND` and `ExternalChatAccount.platform == TELEGRAM`.
  - Both `ExternalChatAccount` and `ExternalChatBinding` have `suspended_at` columns (`app/db.py` L870, L1022) and `ExternalChatAccount` has a `health_status` enum.
- **Risk:** A BOUND binding whose account has been suspended or marked `FAILING` is still selected and the API call is attempted. It will fail and be caught/logged, but the in-app notification has already been committed, so the user is told a notification was created while the Telegram message never arrives. Wasted API calls and confusing UX.

---

## 4. Notification preference check treats any truthy value as enabled

- **Severity:** low
- **File:** `nowing_backend/app/automations/services/telegram_notifications.py` ~L167
- **Evidence from diff:**
  ```python
  if not preferences.get("automation_run_complete", {}).get("telegram"):
      return
  ```
- **Risk:** `UserNotificationPreferencesUpdate.notification_preferences: dict[str, Any]` and `UserUpdate.notification_preferences: dict[str, Any] | None` do not constrain the `telegram` leaf to a boolean. A client could set `"telegram": "false"`, which is truthy in Python and would enable notifications despite the user intending to disable them.

---

## 5. `UserUpdate` allows `None` for a non-nullable DB column

- **Severity:** low
- **File:** `nowing_backend/app/schemas/users.py` ~L112, `nowing_backend/app/db.py` ~L2736 / L2888
- **Evidence from diff/project:**
  - `notification_preferences: dict[str, Any] | None = None` in `UserUpdate`
  - `JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")` on the `User` model
- **Risk:** A `PATCH /users/me` request with `"notification_preferences": null` passes schema validation but will raise an `IntegrityError` when `UserManager` tries to commit the null to a `NOT NULL` column.

---

## 6. Preference "deep merge" is only two levels deep

- **Severity:** low
- **File:** `nowing_backend/app/routes/users_routes.py` ~L20–L31
- **Evidence from diff:**
  ```python
  if isinstance(value, dict) and isinstance(merged.get(key), dict):
      merged[key] = {**merged[key], **value}
  ```
- **Risk:** The docstring claims "deep-merge" but the implementation only merges the top level and one nested level. Deeper structures are overwritten rather than merged, which can silently wipe nested preferences when the schema expands beyond `automation_run_complete.telegram`.

---

## 7. Notification Celery task expires after only 30 seconds

- **Severity:** low
- **File:** `nowing_backend/app/automations/runtime/executor.py` ~L31
- **Evidence from diff:**
  ```python
  notify_telegram_run_complete.apply_async(args=(run_id,), expires=30)
  ```
- **Risk:** If workers are backlogged or restarting, the notification task may expire before it is picked up and be silently dropped. Since the run itself has already completed, this is a silent loss of user-facing delivery with no retry.

---

## Notes

- Tests in the diff passed (`pytest tests/unit/automations/test_telegram_notification_formatter.py tests/integration/automations/test_run_notification.py tests/integration/routes/test_user_notification_preferences.py -q` → 10 passed). This does **not** cover the long-automation-name title overflow or the frontend fetch-rejection path.
- The new `unescape_markdown_v2` helper in `app/gateway/telegram/formatting.py` and the `executor.py` lazy import of the notification task are correct and avoid circular dependencies.
- The migration `187_add_user_notification_preferences.py` correctly adds a non-null `JSONB` column with a server default and is chained off the current Alembic head.
