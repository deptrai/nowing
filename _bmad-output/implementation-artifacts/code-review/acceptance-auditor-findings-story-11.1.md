# Acceptance Auditor Findings — Story 11.1: Telegram Notification Foundation

**Review target:** `diff-story-11.1.patch`  
**Spec:** `11-1-telegram-notification-foundation.md`  
**Status:** Does **not** fully satisfy the spec. The core notification pipeline (preference → in-app notification → Celery → Telegram) is wired correctly, but there are deviations in the deep-link URL, endpoint contract, UI toggle guard, and observability.

---

## What works

- Migration `187_add_user_notification_preferences` adds `notification_preferences` JSONB to the `user` table and model (both `AUTH_TYPE` branches).
- `automation_run_complete` is registered in `NotificationType` and `CATEGORY_TYPES["status"]`.
- `NotificationService.create_notification` is used correctly; in-app notification is always created even when Telegram is skipped.
- The executor (`executor.py`) enqueues `automation.notify_telegram_run_complete` after `session.commit()` for both success and failure paths, and the enqueue helper catches its own exceptions so the run cannot fail.
- The Celery task has `soft_time_limit=30` / `time_limit=60` and is registered in `celery_app.py`.
- `resolve_telegram_binding_for_run` correctly filters by user + workspace + `BOUND` + `TELEGRAM`.
- `TelegramClient._send_once` already handles `RetryAfter` retries, and all Telegram errors are caught/logged without propagating to the executor.
- Unit and integration tests are present and cover the formatter, preference endpoint, executor hook, and failure path.

---

## Findings

### 1. Deep link does not target a real run-detail route
- **One-line title:** Telegram message links to the automation page, not the specific run.
- **AC / Requirement:** AC-8 (deep link format: `/dashboard/{workspace_id}/automations/{automation_id}/runs/{run_id}`); Dev Note on deep link alignment.
- **Severity:** High
- **File + approximate line:**
  - `nowing_backend/app/automations/services/telegram_notifications.py:75-80`
  - `nowing_web/app/dashboard/[workspace_id]/automations/[automation_id]/page.tsx:1-18`
  - `nowing_web/app/dashboard/[workspace_id]/automations/[automation_id]/automation-detail-content.tsx:30-90`
- **Evidence:**
  ```python
  deep_link = (
      f"{base_url}/dashboard/{automation.workspace_id}"
      f"/automations/{automation.id}?run_id={run.id}"
  )
  ```
  The detail page and `AutomationRunsSection` never read `run_id` from the query string, and there is no `app/dashboard/[workspace_id]/automations/[automation_id]/runs/[run_id]/page.tsx` route.
- **Explanation:** AC-8 explicitly requires a deep link to the run (`.../runs/{run_id}`). The generated URL only opens the automation detail view and ignores `?run_id`. This also diverges from the existing `/workspaces/.../runs/{run_id}` links in `app/gateway/telegram/callbacks.py` and `commands.py`. Fix by either adding a dedicated run-detail route (or query-param handling in `AutomationDetailContent`) and making the backend link match.

### 2. UI toggle is visible for suspended as well as bound Telegram bindings
- **One-line title:** Telegram notification toggle shown for `suspended` connections.
- **AC / Requirement:** AC-1 (toggle visible only when a Telegram binding is `bound`).
- **Severity:** Low
- **File + approximate line:** `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx:302-304`
- **Evidence:**
  ```tsx
  const hasTelegramConnection = connections.some(
      (connection) => connection.platform === "telegram"
  );
  ```
  The `/api/v1/gateway/connections` endpoint returns bindings with `state in ('bound', 'suspended')`.
- **Explanation:** A user sees the toggle for a suspended binding, but `resolve_telegram_binding_for_run` only sends to `state == BOUND`. Filter the UI condition to `connection.platform === "telegram" && connection.state === "bound"` (or query only bound connections).

### 3. Preference endpoint path diverges from the spec
- **One-line title:** `PATCH` endpoint is under `/users`, not `/api/v1/users`.
- **AC / Requirement:** AC-9 (`PATCH /api/v1/users/me/notification-preferences`).
- **Severity:** Low
- **File + approximate line:**
  - `nowing_backend/app/routes/users_routes.py:54`
  - `nowing_backend/app/app.py:918`
- **Evidence:**
  ```python
  @router.patch("/me/notification-preferences", response_model=UserRead)
  ```
  `users_router` is included in `app.py` with `app.include_router(users_router)`, producing the path `/users/me/notification-preferences`. The frontend and tests both call this path.
- **Explanation:** The implemented path is internally consistent with other `/users/me` routes and with the frontend (`buildBackendUrl("/users/me/notification-preferences")`), but it does not match the spec’s `/api/v1` prefix. Either remount the router under `/api/v1` or update the spec/contract.

### 4. No usage/metric tracking for Telegram delivery
- **One-line title:** Telegram notification send is not instrumented for metrics or `TokenUsage`.
- **AC / Requirement:** AC-7 ("log lỗi, metric"); Dev Notes AD-8 / AD-15 (tracking via `TokenUsage` with `usage_type = "telegram_message"`).
- **Severity:** Medium
- **File + approximate line:**
  - `nowing_backend/app/automations/tasks/notify_run_complete.py:36-45`
  - `nowing_backend/app/automations/services/telegram_notifications.py:190-204`
  - `nowing_backend/app/tasks/celery_tasks/__init__.py:115-158`
- **Evidence:** Exceptions are caught and `logger.exception(...)` is called, but no `ot_metrics`, `record_token_usage`, or `TokenUsage` row is written. The task uses the generic `run_async_celery_task` from `__init__.py`, which does not record connector outcomes (unlike the version in `connector_tasks.py`).
- **Explanation:** AC-7 and the Dev Notes require observable delivery failures and retry metrics. Add `record_token_usage(usage_type="telegram_message", ...)` or emit an OpenTelemetry counter for sent/failed messages.

### 5. MarkdownV2 text can be split inside an escaped character sequence
- **One-line title:** `chunk_message` may break MarkdownV2 escape sequences across chunk boundaries.
- **AC / Requirement:** AC-6 (chunk ≤ 4096 UTF-16 units); AC-8 (preserves formatting).
- **Severity:** Low
- **File + approximate line:**
  - `nowing_backend/app/automations/services/telegram_notifications.py:59-92`
  - `nowing_backend/app/gateway/telegram/formatting.py:54-70`
- **Evidence:**
  ```python
  output_text = _format_output_text(run.output)
  if output_text:
      parts.append(escape_markdown_v2(output_text))
  ...
  full_text = "\n\n".join(parts)
  return chunk_message(full_text)
  ```
  `chunk_message` searches for `\n\n`, `. `, or `\n` boundaries but has no awareness of backslash escapes.
- **Explanation:** If a chunk boundary falls between a backslash and a reserved character (e.g., `\*` becomes `\` at the end of one chunk and `*` at the start of the next), the remaining chunks contain invalid MarkdownV2. Telegram will then drop `parse_mode` and fall back to plain text. Chunk the plain text first and escape each chunk individually, or ensure chunk boundaries respect escape runs.

### 6. Formatter unit tests do not verify the deep-link route
- **One-line title:** Unit tests only assert the literal deep-link string, not whether it resolves.
- **AC / Requirement:** AC-10 (test coverage) and AC-8 (deep link).
- **Severity:** Low
- **File + approximate line:** `nowing_backend/tests/unit/automations/test_telegram_notification_formatter.py:47-49`
- **Evidence:**
  ```python
  assert (
      "[Open run](https://app.nowing.net/dashboard/42/automations/123?run_id=7)"
      in chunks[0]
  )
  ```
- **Explanation:** This allowed the non-functional `?run_id` link to pass. Add an integration/E2E test that follows the generated URL and asserts the dashboard opens/highlight the specific run, or update the formatter test to assert the canonical run-detail path exists in the app.

---

## Recommendation

The highest-priority fix is the **deep link**: choose a single, working URL scheme (`/dashboard/{workspace_id}/automations/{automation_id}/runs/{run_id}` or `?run_id=` with query-param handling), align the backend formatter and existing `commands.py`/`callbacks.py`, and update the unit test. After that, tighten the UI toggle guard and add usage/metric instrumentation.