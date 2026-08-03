# Story 11.3 Acceptance Auditor Findings

The following acceptance criteria or architecture/dev-note constraints are not fully satisfied. AC-1 through AC-4 are satisfied by the existing `client.py`, `adapter.py`, and `inbox_processor.py` code.

- **Callback handlers do not catch `check_permission` or `launch_run` failures and may leave the callback spinner unanswered**
  - **AC/Constraint:** AC-5, AC-6, AC-9, AD-4, Error-Handling dev note
  - **Evidence:** `app/gateway/telegram/callbacks.py:90-98` calls `check_permission(..., Permission.AUTOMATIONS_READ)` for `view_run:` without `try/except`; `callbacks.py:138-146` calls `check_permission(..., Permission.AUTOMATIONS_EXECUTE)` for `rerun:` without `try/except`; `callbacks.py:157-173` calls `launch_run` before the `answer_callback_query` at `:169-173`. Any `HTTPException` or `DispatchError` raised in those calls will fail the event without answering the callback.

- **`/run` command permits automation enumeration and name probing before checking execute permission**
  - **AC/Constraint:** AC-8, AD-4
  - **Evidence:** `app/gateway/telegram/commands.py:239-254` lists all active automations and `:256-265` looks up the named automation before `check_permission(..., Permission.AUTOMATIONS_EXECUTE)` at `:267-282`. A user lacking `AUTOMATIONS_EXECUTE` still receives the automation list or an "Automation '<name>' not found" reply instead of an access-denied reply.

- **Callback handlers perform resource lookup before permission check, exposing existence of runs/automations and risking the same unhandled exception**
  - **AC/Constraint:** AC-5, AC-6
  - **Evidence:** `callbacks.py:76-98` fetches the run via `_fetch_run` at `:76` before `check_permission(..., AUTOMATIONS_READ)` at `:90-98`; `callbacks.py:128-146` fetches the automation at `:128` before `check_permission(..., AUTOMATIONS_EXECUTE)` at `:139-146`. "Run not found" / "Automation not found" can be answered before permission is validated.

- **`/status` and `/run` command handlers silently bypass permission when the bound user cannot be loaded**
  - **AC/Constraint:** AC-7, AC-8, AD-4
  - **Evidence:** `commands.py:193-208` and `:267-282` only call `check_permission` inside `if auth is not None:`. `_auth_for_binding` (`commands.py:126-132`) returns `None` when `session.get(User, binding.user_id)` returns `None`, and the command then proceeds to fetch and return run/automation data without authorization.

- **Required integration tests and callback-permission coverage are missing**
  - **AC/Constraint:** AC-10
  - **Evidence:** The diff only adds `tests/unit/gateway/test_telegram_commands.py` (7 unit tests). No `tests/integration/gateway/` tests exercise callback dispatch, `/status`/`/run` permission, or unbound onboarding end-to-end, and `tests/unit/gateway/test_telegram_callbacks.py` was not expanded to cover permission-denied paths or `launch_run` failures.

**Overall verdict:** NOT ACCEPTED.
