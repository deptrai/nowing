# Edge Case Hunter — Story 11.3 Re-run

- **Callback handlers do not scope `run_id` / `automation_id` to `binding.workspace_id`.**
  `check_permission` only verifies the bound user has `AUTOMATIONS_READ` / `AUTOMATIONS_EXECUTE` in the binding workspace; it does not check that the requested resource belongs to that workspace.
  - Evidence: `callbacks.py:51-58` (`_fetch_run` loads by id only), `callbacks.py:230` (`_handle_rerun` loads `Automation` by id only), `app/utils/rbac.py:129-174` (`check_permission` checks membership, not resource workspace).

- **Group chat callback queries authorize any member as the bound user.**
  `_auth_for_binding` always derives permissions from `binding.user_id`, never from the Telegram user who pressed the button (`event.external_user_id`). In a bound Telegram group, any member can view runs or trigger automations as the bound Nowing user, and the bot may post the result to the group.
  - Evidence: `callbacks.py:39-48` (`_auth_for_binding`), `adapter.py:89-146` (`external_user_id` parsed but never checked), `inbox_processor.py:344-349` (callback_query bypasses the non-direct group rejection).

- **No rate limit or idempotency on `/run` and `rerun`.**
  `launch_run` is invoked directly with a brand-new in-memory `AutomationTrigger` each time. The only `acquire_token` usage is for unbound onboarding, so rapid invocations, button-mashing, or retries can enqueue duplicate `AutomationRun` rows.
  - Evidence: `commands.py:335-340` (`/run` calls `launch_run`), `callbacks.py:268-272` (`rerun` calls `launch_run`), `commands.py:99-105` (rate-limiting only for onboarding), `ratelimit.py:88-117` (`acquire_token` available but unused for commands/callbacks).

- **`/status` and `/run` command handlers do not catch `adapter.send_message` failures on reply paths.**
  Permission-denied, not-found, list, and launch-failure error messages are sent without a `try/except`. A transient Telegram/HTTP error will bubble up, mark the inbox event `FAILED`, and trigger a retry. Only the post-launch confirmation send is guarded.
  - Evidence: `commands.py:228-267` (`/status` sends are unguarded), `commands.py:270-368` (`/run` sends are unguarded except `358-367`).

- **`inbox_processor` can re-dispatch an event while it is already `PROCESSING`.**
  `process_inbound_event` only skips `PROCESSED` and `IGNORED` statuses. After the initial `PROCESSING` commit, a second worker or a retry can acquire the row and call `_dispatch_inbound_event` again, enabling double `/run`, `rerun`, or callback dispatch.
  - Evidence: `inbox_processor.py:81-103` (`process_inbound_event` status check and `PROCESSING` set).

- **Unbound or group/inline `callback_query` without a binding falls through to onboarding and never answers the callback.**
  When `binding is None`, `inbox_processor` calls `send_unbound_onboarding` and returns. For a `callback_query` this means the Telegram loading spinner is never cleared, and for an inline message the onboarding message is sent to an invalid `inline:` chat.
  - Evidence: `inbox_processor.py:366-394` (binding None → onboarding without `answer_callback_query`), `commands.py:91-113` (`send_unbound_onboarding` only calls `send_message`), `inbox_processor.py:398-444` (callback dispatch else-answer path not reached when a handler exists).

- **`/run` with a bot-mention-only argument returns a confusing "not found" error.**
  `_strip_bot_mention` on an argument like `"@BotName"` returns `''`, and `_find_active_automation_by_name` then queries `Automation.name == ''`, producing `Automation '' not found.` instead of the active-automation list.
  - Evidence: `commands.py:280-285` (argument parsing and `_strip_bot_mention`), `commands.py:319-327` (empty-name lookup).

- **`_active_automations_for_workspace` is unbounded and builds the full list before truncating.**
  The query has no `limit()` and `_build_automation_list_text` formats every active automation before truncating. A workspace with thousands of active automations wastes memory/CPU; a single oversized name can also produce an awkward mid-string-truncated entry.
  - Evidence: `commands.py:172-183` (no `limit()` on the query), `commands.py:204-225` (full list built then truncated; `222-225` fallback slices the first name).

- **Orphan-run branch in `_format_run_summary` is unreachable because `_latest_run_for_workspace` inner-joins `Automation`.**
  A run whose `Automation` row is missing is filtered out by the inner join, so the code can never reach the "automation record is missing" message. The `AutomationRun` FK is also `ON DELETE CASCADE`, making a missing-automation scenario impossible at the database level.
  - Evidence: `commands.py:153-169` (inner join with `Automation`), `commands.py:120-134` (orphan branch), `app/automations/persistence/models/run.py:23-26` (`ondelete="CASCADE"`).

- **`/status` and `/run` do not reject `SUSPENDED` bindings.**
  `_resolve_binding_for_event` matches both `BOUND` and `SUSPENDED`, but the command and callback handlers never inspect `binding.state` before executing permissions checks, querying runs, or launching automations.
  - Evidence: `inbox_processor.py:160-169` (binding resolution includes `SUSPENDED`), `commands.py:228-267` (`/status` no state check), `commands.py:270-368` (`/run` no state check), `callbacks.py:83-331` (callbacks no state check).

- **`_handle_view_run` fallback `send_message` for `edit_message` failures does not work for inline `external_peer_id`.**
  When `edit_message` fails, the handler falls back to `send_message(external_peer_id=event.external_peer_id or "", text=summary)`. For an inline message, `external_peer_id` is `"inline:<id>"`, which `TelegramClient.send_message` will reject because it expects a numeric `chat_id`, leaving the user with no summary after the spinner was cleared.
  - Evidence: `callbacks.py:154-170` (`edit_message` → `send_message` fallback), `adapter.py:148-163` (`send_message` forwards `chat_id` unchanged), `client.py:86-115` (`send_message` expects a `chat_id`).
