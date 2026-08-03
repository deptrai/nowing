# Edge Case Hunter Findings — Story 11.3

- **Missing user on binding skips all permission checks (fail-open)** — `nowing_backend/app/gateway/telegram/commands.py:126-132`; callers in `_handle_status_command` (`commands.py:193-208`), `_handle_run_command` (`commands.py:267-282`), and the callback handlers (`callbacks.py:90-98`, `callbacks.py:138-146`) only call `check_permission` when `auth` is not `None`. If `session.get(User, binding.user_id)` ever returns `None`, the command/callback proceeds without authorization.

- **`/run` can enumerate and probe automations before permission enforcement** — `nowing_backend/app/gateway/telegram/commands.py:239-282`. The no-argument branch lists all active automations with no permission check, and the named branch returns "Automation '<name>' not found" before `check_permission`, allowing a user without `AUTOMATIONS_EXECUTE` to infer which automations exist.

- **Callback permission errors are not caught, breaking the "answer every callback" contract** — `nowing_backend/app/gateway/telegram/callbacks.py:92-98` and `callbacks.py:140-146`. `check_permission` is called outside any `try/except`; a 403/404 propagates uncaught, `answer_callback_query` is never called, and the Telegram spinner stays.

- **Callback `view_run`/`rerun` do not scope to the binding workspace** — `nowing_backend/app/gateway/telegram/callbacks.py:92-98` and `callbacks.py:140-167`. Permission is checked against the target automation/run's workspace, not `binding.workspace_id`, so a tampered `rerun:<automation_id>` can act across workspaces where the binding user has permission.

- **Group/inline callback queries can fall through to onboarding without answering** — `nowing_backend/app/gateway/inbox_processor.py:344-415`. The new `parsed.event_kind != "callback_query"` guard lets non-direct callbacks through; if no binding exists, the processor reaches `send_unbound_onboarding` and returns without ever calling `answer_callback_query`, leaving the spinner and potentially messaging a group or an `inline:` peer.

- **Callback handler exceptions leave the spinner and inbox unprocessed** — `nowing_backend/app/gateway/inbox_processor.py:398-415` and `telegram/commands.py:365-378`. There is no `try/finally` around `bundle.commands.handle_callback_query`, so any exception bypasses the `answer_callback_query` fallback.

- **`_handle_rerun` does not catch `launch_run` exceptions; `_handle_run_command` leaks raw errors to the user** — `nowing_backend/app/gateway/telegram/callbacks.py:163-167` and `telegram/commands.py:296-301`. The rerun path has no exception handling for `launch_run`, while the command path catches `Exception` but replies with `f"Could not start run: {exc}"`, exposing internal details.

- **No idempotency / duplicate-run prevention for rapid `/run` or `rerun` invocations** — `nowing_backend/app/gateway/telegram/commands.py:290-295` and `telegram/callbacks.py:163-167`. Each click/command calls `launch_run` with no deduplication token or rate limit, so rapid double-clicks/resubmissions create multiple runs.

- **`/run` active-automation list can exceed Telegram's message-length limit** — `nowing_backend/app/gateway/telegram/commands.py:156-167` and `commands.py:249-253`. There is no pagination or length guard; a workspace with many active automations can hit Telegram's 4096-character `BadRequest` with no fallback.

- **Confirmation `send_message` after a successful `launch_run` is unguarded** — `nowing_backend/app/gateway/telegram/commands.py:303-307`. If the final "Run started" message fails, the run has already been committed/enqueued, the inbox event is marked `FAILED`, and the user may retry, causing duplicate runs.

- **Orphaned latest run with missing automation is reported as "No recent runs"** — `nowing_backend/app/gateway/telegram/commands.py:147-153`, `commands.py:210-216`. `_latest_run_for_workspace` returns `None` if the run's linked `Automation` row cannot be loaded, even though a run exists, producing a misleading reply.

- **Missing `external_peer_id` silently marks the event `PROCESSED`** — `nowing_backend/app/gateway/telegram/commands.py:190-191` and `commands.py:233-234`. Both `_handle_status_command` and `_handle_run_command` return `True` immediately when `event.external_peer_id` is missing, so the inbox row is marked `PROCESSED` with no reply attempted.

- **Unit tests mask the permission and error paths** — `nowing_backend/tests/unit/gateway/test_telegram_commands.py:88-214`. They mock `check_permission` and `launch_run` and never exercise `_auth_for_binding` returning `None`, callback permission denial, group/inline callbacks, `send_message`/`launch_run` failure, or long automation lists.
