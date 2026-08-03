# Blind Hunter Findings — Story 11.3

- **Permission checks are skipped when the binding's user cannot be loaded (fail-open).** `_auth_for_binding` returns `None` when `session.get(User, ...)` returns `None`, and both `/status` and `/run` then bypass `check_permission`. A chat whose user row is missing can still view runs and trigger automations. Evidence: `nowing_backend/app/gateway/telegram/commands.py:193-208` (`/status`), `:267-282` (`/run`); `_auth_for_binding` at `:126-132`.

- **`/run` with no argument lists active automations without any permission check.** The list path enumerates automations before any `check_permission` call, so any bound chat can read all active automation names. Evidence: `nowing_backend/app/gateway/telegram/commands.py:239-254`.

- **Automation lookup in `/run <name>` happens before permission check, leaking name existence.** `_find_active_automation_by_name` runs before `check_permission`. A user without `AUTOMATIONS_EXECUTE` gets "not found" for a missing name but "access denied" for an existing one, revealing whether an automation with that name exists. Evidence: `nowing_backend/app/gateway/telegram/commands.py:256-282`.

- **Dashboard "Link" is a relative path, not a clickable URL in Telegram.** `_dashboard_run_url` returns `/workspaces/{...}`; Telegram only auto-detects `http(s)://` URLs, so the link in the bot message is plain text. Evidence: `nowing_backend/app/gateway/telegram/commands.py:105-117` (new code); same helper also in `nowing_backend/app/gateway/telegram/callbacks.py:20-21` and `:57-59`.

- **Group bot mention is not stripped from the `/run` automation name.** `command_name` removes `@botname` from the command token, but `_handle_run_command` takes the raw remainder of `event.text` as the automation name. A message like `/run @NowingBot Foo` will search for an automation named `@NowingBot Foo` and fail. Evidence: `nowing_backend/app/gateway/base/commands.py:8-11`, `nowing_backend/app/gateway/telegram/commands.py:236-239` and `:256-265`.

- **`launch_run` failures expose raw exception text to users.** `_handle_run_command` catches `Exception as exc` and sends `f"Could not start run: {exc}"`, which can leak internal error details. Evidence: `nowing_backend/app/gateway/telegram/commands.py:290-301`.

- **Failed `/run` still marks the inbound event as `PROCESSED`.** After catching a `launch_run` exception and sending an error reply, the handler returns `True`, so `inbox_processor` sets `event.status = PROCESSED` rather than a failure state. Evidence: `nowing_backend/app/gateway/telegram/commands.py:290-301`, `nowing_backend/app/gateway/inbox_processor.py:450-460`.

- **Wrong `user_id` type hint in `_load_user`.** `ExternalChatBinding.user_id` is a UUID, but `_load_user` declares `user_id: int | None`. Evidence: `nowing_backend/app/gateway/telegram/commands.py:120`, `nowing_backend/app/db.py:981-982`.

- **Callback query dispatch does not guarantee `answer_callback_query` on handler exceptions.** The `inbox_processor` callback block only answers when no handler is present. If `handle_callback_query` raises (e.g. `launch_run` fails inside `_handle_rerun`), the Telegram loading spinner is never cleared. Evidence: `nowing_backend/app/gateway/inbox_processor.py:398-415`, `nowing_backend/app/gateway/telegram/callbacks.py:163-167` (unwrapped `launch_run`).

- **Unit tests mask the fail-open auth path and do not exercise real permission checks.** `test_status_command_no_recent_runs` sets `session.get.return_value = None`, causing `_auth_for_binding` to return `None` and skip `check_permission`, yet expects a normal response. Other tests patch `check_permission` directly. Evidence: `nowing_backend/tests/unit/gateway/test_telegram_commands.py:88-99`, `:175-196`.
