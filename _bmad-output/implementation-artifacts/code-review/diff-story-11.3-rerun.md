diff --git a/nowing_backend/app/gateway/base/commands.py b/nowing_backend/app/gateway/base/commands.py
index ea5d09e20..c803c97b5 100644
--- a/nowing_backend/app/gateway/base/commands.py
+++ b/nowing_backend/app/gateway/base/commands.py
@@ -39,3 +39,23 @@ class BaseGatewayCommands:
         dashboard_url: str,
     ) -> None:
         return None
+
+    async def handle_status_command(
+        self,
+        *,
+        session,
+        adapter: BasePlatformAdapter,
+        event: ParsedInboundEvent,
+        binding,
+    ) -> bool:
+        return False
+
+    async def handle_run_command(
+        self,
+        *,
+        session,
+        adapter: BasePlatformAdapter,
+        event: ParsedInboundEvent,
+        binding,
+    ) -> bool:
+        return False
diff --git a/nowing_backend/app/gateway/inbox_processor.py b/nowing_backend/app/gateway/inbox_processor.py
index a7a45164f..f3b1e06ff 100644
--- a/nowing_backend/app/gateway/inbox_processor.py
+++ b/nowing_backend/app/gateway/inbox_processor.py
@@ -345,6 +345,7 @@ async def _dispatch_inbound_event(
             account.platform
             not in {ExternalChatPlatform.SLACK, ExternalChatPlatform.DISCORD}
             and parsed.external_peer_kind != ExternalChatPeerKind.DIRECT.value
+            and parsed.event_kind != "callback_query"
         ):
             if hasattr(adapter, "leave_chat"):
                 await adapter.leave_chat(external_peer_id=parsed.external_peer_id)
@@ -394,6 +395,54 @@ async def _dispatch_inbound_event(
 
         event.external_chat_binding_id = binding.id
 
+        if parsed.event_kind == "callback_query":
+            handler = getattr(bundle.commands, "handle_callback_query", None)
+            if handler is not None:
+                callback_query_id = (parsed.metadata or {}).get("callback_query_id")
+                handler_failed = False
+                try:
+                    await handler(
+                        session=session,
+                        adapter=adapter,
+                        event=parsed,
+                        binding=binding,
+                    )
+                except Exception:
+                    handler_failed = True
+                    raise
+                finally:
+                    if (
+                        handler_failed
+                        and callback_query_id
+                        and hasattr(adapter, "answer_callback_query")
+                    ):
+                        try:
+                            await adapter.answer_callback_query(
+                                callback_query_id=callback_query_id
+                            )
+                        except Exception:
+                            logger.warning(
+                                "Failed to answer callback query %s",
+                                callback_query_id,
+                                exc_info=True,
+                            )
+            elif hasattr(adapter, "answer_callback_query"):
+                callback_query_id = (parsed.metadata or {}).get("callback_query_id")
+                if callback_query_id:
+                    try:
+                        await adapter.answer_callback_query(
+                            callback_query_id=callback_query_id
+                        )
+                    except Exception:
+                        logger.warning(
+                            "Failed to answer callback query %s",
+                            callback_query_id,
+                            exc_info=True,
+                        )
+            event.status = ExternalChatEventStatus.PROCESSED
+            await session.commit()
+            return
+
         if cmd == "/help":
             handled = await bundle.commands.handle_help_command(
                 adapter=adapter, event=parsed
@@ -415,6 +464,30 @@ async def _dispatch_inbound_event(
             await session.commit()
             return
 
+        if cmd == "/status":
+            handled = await bundle.commands.handle_status_command(
+                session=session,
+                adapter=adapter,
+                event=parsed,
+                binding=binding,
+            )
+            if handled:
+                event.status = ExternalChatEventStatus.PROCESSED
+                await session.commit()
+                return
+
+        if cmd == "/run":
+            handled = await bundle.commands.handle_run_command(
+                session=session,
+                adapter=adapter,
+                event=parsed,
+                binding=binding,
+            )
+            if handled:
+                event.status = ExternalChatEventStatus.PROCESSED
+                await session.commit()
+                return
+
         if not parsed.text:
             event.status = ExternalChatEventStatus.IGNORED
             event.last_error = "empty_message"
diff --git a/nowing_backend/app/gateway/telegram/callbacks.py b/nowing_backend/app/gateway/telegram/callbacks.py
new file mode 100644
index 000000000..155418f35
--- /dev/null
+++ b/nowing_backend/app/gateway/telegram/callbacks.py
@@ -0,0 +1,404 @@
+"""Telegram inline-keyboard callback query handlers."""
+
+from __future__ import annotations
+
+import logging
+from uuid import UUID
+
+from fastapi import HTTPException
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.auth.context import AuthContext
+from app.automations.dispatch.errors import DispatchError
+from app.automations.dispatch.launch import launch_run
+from app.automations.persistence.enums.automation_status import AutomationStatus
+from app.automations.persistence.enums.trigger_type import TriggerType
+from app.automations.persistence.models.automation import Automation
+from app.automations.persistence.models.run import AutomationRun
+from app.automations.persistence.models.trigger import AutomationTrigger
+from app.config import config
+from app.db import ExternalChatBinding, Permission, User
+from app.gateway.base.adapter import ParsedInboundEvent
+from app.gateway.telegram.adapter import TelegramAdapter
+from app.utils.rbac import check_permission
+
+logger = logging.getLogger(__name__)
+
+
+def _dashboard_run_url(workspace_id: int, automation_id: int, run_id: int) -> str:
+    base = (config.NEXT_FRONTEND_URL or "").rstrip("/")
+    return f"{base}/workspaces/{workspace_id}/automations/{automation_id}/runs/{run_id}"
+
+
+async def _load_user(session: AsyncSession, user_id: UUID | None) -> User | None:
+    if user_id is None:
+        return None
+    return await session.get(User, user_id)
+
+
+async def _auth_for_binding(
+    session: AsyncSession, binding: ExternalChatBinding
+) -> AuthContext:
+    user = await _load_user(session, binding.user_id)
+    if user is None:
+        raise HTTPException(
+            status_code=403,
+            detail="Access denied: user not found",
+        )
+    return AuthContext.session(user)
+
+
+async def _fetch_run(
+    session: AsyncSession, run_id: int
+) -> tuple[AutomationRun, Automation | None] | None:
+    run = await session.get(AutomationRun, run_id)
+    if run is None:
+        return None
+    automation = await session.get(Automation, run.automation_id)
+    return run, automation
+
+
+async def _format_run_summary(run: AutomationRun, automation: Automation | None) -> str:
+    status = run.status.value
+    finished_at = ""
+    if run.finished_at:
+        finished_at = f"\nFinished: {run.finished_at.isoformat()}"
+    if automation is None:
+        return (
+            f"A recent run exists, but the automation record is missing.\n"
+            f"Run status: {status}{finished_at}\n"
+            f"Run ID: {run.id}"
+        )
+    return (
+        f"Run: {automation.name}\n"
+        f"Status: {status}{finished_at}\n"
+        f"Link: {_dashboard_run_url(automation.workspace_id, automation.id, run.id)}"
+    )
+
+
+def _is_inline(event: ParsedInboundEvent) -> bool:
+    return (event.external_peer_id or "").startswith("inline:")
+
+
+async def _handle_view_run(
+    *,
+    session: AsyncSession,
+    adapter: TelegramAdapter,
+    event: ParsedInboundEvent,
+    binding: ExternalChatBinding,
+    run_id: int,
+    callback_query_id: str | None,
+) -> None:
+    try:
+        auth = await _auth_for_binding(session, binding)
+        await check_permission(
+            session,
+            auth,
+            binding.workspace_id,
+            Permission.AUTOMATIONS_READ.value,
+            "You don't have permission to read automations in this workspace",
+        )
+    except HTTPException:
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(
+                    callback_query_id=callback_query_id,
+                    text="Access denied: you can't view runs in this workspace.",
+                    show_alert=True,
+                )
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+        return
+
+    try:
+        pair = await _fetch_run(session, run_id)
+        if pair is None:
+            if callback_query_id:
+                try:
+                    await adapter.answer_callback_query(
+                        callback_query_id=callback_query_id, text="Run not found."
+                    )
+                except Exception:
+                    logger.warning(
+                        "Failed to answer callback query %s",
+                        callback_query_id,
+                        exc_info=True,
+                    )
+            if not _is_inline(event):
+                try:
+                    await adapter.send_message(
+                        external_peer_id=event.external_peer_id or "",
+                        text=f"Run {run_id} not found.",
+                    )
+                except Exception:
+                    logger.exception("Failed to send run-not-found message")
+            return
+
+        run, automation = pair
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(
+                    callback_query_id=callback_query_id, text=""
+                )
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+
+        summary = await _format_run_summary(run, automation)
+        if event.external_message_id:
+            try:
+                await adapter.edit_message(
+                    external_peer_id=event.external_peer_id or "",
+                    external_message_id=event.external_message_id,
+                    text=summary,
+                )
+            except Exception:
+                logger.exception("Failed to edit run summary")
+                try:
+                    await adapter.send_message(
+                        external_peer_id=event.external_peer_id or "",
+                        text=summary,
+                    )
+                except Exception:
+                    logger.exception("Failed to send run summary")
+        else:
+            try:
+                await adapter.send_message(
+                    external_peer_id=event.external_peer_id or "",
+                    text=summary,
+                )
+            except Exception:
+                logger.exception("Failed to send run summary")
+    except Exception:
+        logger.exception("Error handling view_run:%s", run_id)
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(
+                    callback_query_id=callback_query_id,
+                    text="Could not load run.",
+                )
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+
+
+async def _handle_rerun(
+    *,
+    session: AsyncSession,
+    adapter: TelegramAdapter,
+    event: ParsedInboundEvent,
+    binding: ExternalChatBinding,
+    automation_id: int,
+    callback_query_id: str | None,
+) -> None:
+    try:
+        auth = await _auth_for_binding(session, binding)
+        await check_permission(
+            session,
+            auth,
+            binding.workspace_id,
+            Permission.AUTOMATIONS_EXECUTE.value,
+            "You don't have permission to run automations in this workspace",
+        )
+    except HTTPException:
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(
+                    callback_query_id=callback_query_id,
+                    text="Access denied: you can't run automations in this workspace.",
+                    show_alert=True,
+                )
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+        return
+
+    try:
+        automation = await session.get(Automation, automation_id)
+        if automation is None:
+            if callback_query_id:
+                try:
+                    await adapter.answer_callback_query(
+                        callback_query_id=callback_query_id,
+                        text="Automation not found.",
+                    )
+                except Exception:
+                    logger.warning(
+                        "Failed to answer callback query %s",
+                        callback_query_id,
+                        exc_info=True,
+                    )
+            return
+
+        if automation.status != AutomationStatus.ACTIVE:
+            if callback_query_id:
+                try:
+                    await adapter.answer_callback_query(
+                        callback_query_id=callback_query_id,
+                        text=f"Automation is {automation.status.value}, not active.",
+                        show_alert=True,
+                    )
+                except Exception:
+                    logger.warning(
+                        "Failed to answer callback query %s",
+                        callback_query_id,
+                        exc_info=True,
+                    )
+            return
+
+        trigger = AutomationTrigger(
+            automation_id=automation.id,
+            type=TriggerType.MANUAL,
+            params={},
+            static_inputs={},
+        )
+        await launch_run(
+            session=session,
+            trigger=trigger,
+            runtime_inputs={"fired_by": "telegram_callback"},
+        )
+
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(
+                    callback_query_id=callback_query_id,
+                    text="Run started. You will be notified when it completes.",
+                )
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+
+        if _is_inline(event) and event.external_message_id:
+            try:
+                await adapter.edit_message(
+                    external_peer_id=event.external_peer_id or "",
+                    external_message_id=event.external_message_id,
+                    text=f"Started run for automation '{automation.name}'.",
+                )
+            except Exception:
+                logger.exception("Failed to edit rerun confirmation")
+        else:
+            try:
+                await adapter.send_message(
+                    external_peer_id=event.external_peer_id or "",
+                    text=f"Started run for automation '{automation.name}'.",
+                )
+            except Exception:
+                logger.exception("Failed to send rerun confirmation")
+    except DispatchError:
+        logger.exception("DispatchError rerunning automation %s", automation_id)
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(
+                    callback_query_id=callback_query_id,
+                    text="Could not start run. Please try again later.",
+                )
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+    except Exception:
+        logger.exception("Unexpected error rerunning automation %s", automation_id)
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(
+                    callback_query_id=callback_query_id,
+                    text="Could not start run. Please try again later.",
+                )
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+
+
+async def handle_callback_query(
+    *,
+    session: AsyncSession,
+    adapter: TelegramAdapter,
+    event: ParsedInboundEvent,
+    binding: ExternalChatBinding,
+) -> None:
+    """Dispatch a Telegram ``callback_query`` to ``view_run:`` or ``rerun:`` handlers."""
+    data = event.text or ""
+    callback_query_id = (event.metadata or {}).get("callback_query_id")
+
+    if not data:
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(callback_query_id=callback_query_id)
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+        return
+
+    if not event.external_peer_id:
+        if callback_query_id:
+            try:
+                await adapter.answer_callback_query(callback_query_id=callback_query_id)
+            except Exception:
+                logger.warning(
+                    "Failed to answer callback query %s",
+                    callback_query_id,
+                    exc_info=True,
+                )
+        return
+
+    parts = data.split(":", 1)
+    prefix = parts[0]
+    item_id: int | None = None
+    if len(parts) > 1 and parts[1].isdigit():
+        item_id = int(parts[1])
+
+    if prefix == "view_run" and item_id is not None:
+        await _handle_view_run(
+            session=session,
+            adapter=adapter,
+            event=event,
+            binding=binding,
+            run_id=item_id,
+            callback_query_id=callback_query_id,
+        )
+        return
+
+    if prefix == "rerun" and item_id is not None:
+        await _handle_rerun(
+            session=session,
+            adapter=adapter,
+            event=event,
+            binding=binding,
+            automation_id=item_id,
+            callback_query_id=callback_query_id,
+        )
+        return
+
+    # Unknown callback data: answer to clear the spinner and let the chat path handle it.
+    if callback_query_id:
+        try:
+            await adapter.answer_callback_query(callback_query_id=callback_query_id)
+        except Exception:
+            logger.warning(
+                "Failed to answer callback query %s", callback_query_id, exc_info=True
+            )
diff --git a/nowing_backend/app/gateway/telegram/commands.py b/nowing_backend/app/gateway/telegram/commands.py
index a3cfc9515..6495b251a 100644
--- a/nowing_backend/app/gateway/telegram/commands.py
+++ b/nowing_backend/app/gateway/telegram/commands.py
@@ -2,19 +2,44 @@
 
 from __future__ import annotations
 
+import logging
+import re
+from uuid import UUID
+
+from fastapi import HTTPException
+from sqlalchemy import select
+
+from app.auth.context import AuthContext
+from app.automations.dispatch.errors import DispatchError
+from app.automations.dispatch.launch import launch_run
+from app.automations.persistence.enums.automation_status import AutomationStatus
+from app.automations.persistence.enums.trigger_type import TriggerType
+from app.automations.persistence.models.automation import Automation
+from app.automations.persistence.models.run import AutomationRun
+from app.automations.persistence.models.trigger import AutomationTrigger
+from app.config import config
+from app.db import ExternalChatBinding, Permission, User
 from app.gateway.base.adapter import ParsedInboundEvent
 from app.gateway.base.commands import BaseGatewayCommands
 from app.gateway.pairing import redeem_pairing_code
 from app.gateway.ratelimit import acquire_token
 from app.gateway.telegram.adapter import TelegramAdapter
+from app.gateway.telegram.callbacks import handle_callback_query
+from app.utils.rbac import check_permission
+
+logger = logging.getLogger(__name__)
 
 HELP_TEXT = (
     "Nowing Telegram commands:\n"
     "/start <code> - pair this chat\n"
     "/new - start a fresh conversation\n"
+    "/status - latest automation run in this workspace\n"
+    "/run [name] - run an automation or list active automations\n"
     "/help - show this help"
 )
 
+TELEGRAM_MESSAGE_LIMIT = 4096
+
 
 async def handle_start_command(
     *,
@@ -87,6 +112,262 @@ async def send_unbound_onboarding(
     )
 
 
+def _dashboard_run_url(workspace_id: int, automation_id: int, run_id: int) -> str:
+    base = (config.NEXT_FRONTEND_URL or "").rstrip("/")
+    return f"{base}/workspaces/{workspace_id}/automations/{automation_id}/runs/{run_id}"
+
+
+def _format_run_summary(run: AutomationRun, automation: Automation | None) -> str:
+    finished_at = ""
+    if run.finished_at:
+        finished_at = f"\nFinished: {run.finished_at.isoformat()}"
+    if automation is None:
+        return (
+            f"A recent run exists, but the automation record is missing.\n"
+            f"Run status: {run.status.value}{finished_at}\n"
+            f"Run ID: {run.id}"
+        )
+    return (
+        f"Run: {automation.name}\n"
+        f"Status: {run.status.value}{finished_at}\n"
+        f"Link: {_dashboard_run_url(automation.workspace_id, automation.id, run.id)}"
+    )
+
+
+async def _load_user(session, user_id: UUID | None) -> User | None:
+    if user_id is None:
+        return None
+    return await session.get(User, user_id)
+
+
+async def _auth_for_binding(session, binding: ExternalChatBinding) -> AuthContext:
+    user = await _load_user(session, binding.user_id)
+    if user is None:
+        raise HTTPException(
+            status_code=403,
+            detail="Access denied: user not found",
+        )
+    return AuthContext.session(user)
+
+
+async def _latest_run_for_workspace(
+    session, workspace_id: int
+) -> tuple[AutomationRun, Automation | None] | None:
+    result = await session.execute(
+        select(AutomationRun)
+        .join(Automation)
+        .where(
+            Automation.workspace_id == workspace_id,
+        )
+        .order_by(AutomationRun.created_at.desc())
+        .limit(1)
+    )
+    run = result.scalars().first()
+    if run is None:
+        return None
+    automation = await session.get(Automation, run.automation_id)
+    return run, automation
+
+
+async def _active_automations_for_workspace(
+    session, workspace_id: int
+) -> list[Automation]:
+    result = await session.execute(
+        select(Automation)
+        .where(
+            Automation.workspace_id == workspace_id,
+            Automation.status == AutomationStatus.ACTIVE,
+        )
+        .order_by(Automation.name)
+    )
+    return list(result.scalars().all())
+
+
+async def _find_active_automation_by_name(
+    session, workspace_id: int, name: str
+) -> Automation | None:
+    result = await session.execute(
+        select(Automation).where(
+            Automation.workspace_id == workspace_id,
+            Automation.name == name,
+            Automation.status == AutomationStatus.ACTIVE,
+        )
+    )
+    return result.scalars().first()
+
+
+def _strip_bot_mention(text: str) -> str:
+    """Strip a leading '@BotName' (and any following whitespace) from an argument."""
+    return re.sub(r"^@\S+\s*", "", text)
+
+
+def _build_automation_list_text(automations: list[Automation]) -> str:
+    """Build a '/run' list reply, truncating if it would exceed Telegram's message limit."""
+    header = "Active automations:\n"
+    footer = "\n\nSend /run <name> to start one."
+    note = "\n\n... list truncated, send /run <name> for a specific automation."
+    names = [f"- {a.name}" for a in automations]
+    full = header + "\n".join(names) + footer
+    if len(full) <= TELEGRAM_MESSAGE_LIMIT:
+        return full
+
+    max_body = TELEGRAM_MESSAGE_LIMIT - len(header) - len(note) - len(footer)
+    included: list[str] = []
+    for name in names:
+        body = "\n".join([*included, name])
+        if len(body) <= max_body:
+            included.append(name)
+        else:
+            break
+    if not included:
+        first = names[0]
+        included.append(first[:max_body])
+    return header + "\n".join(included) + note + footer
+
+
+async def _handle_status_command(
+    *,
+    session,
+    adapter: TelegramAdapter,
+    event: ParsedInboundEvent,
+    binding: ExternalChatBinding,
+) -> bool:
+    if not event.external_peer_id:
+        return True
+
+    try:
+        auth = await _auth_for_binding(session, binding)
+        await check_permission(
+            session,
+            auth,
+            binding.workspace_id,
+            Permission.AUTOMATIONS_READ.value,
+            "You don't have permission to read automations in this workspace",
+        )
+    except HTTPException:
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text="Access denied: you can't view runs in this workspace.",
+        )
+        return True
+
+    pair = await _latest_run_for_workspace(session, binding.workspace_id)
+    if pair is None:
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text="No recent runs in this workspace.",
+        )
+        return True
+
+    run, automation = pair
+    await adapter.send_message(
+        external_peer_id=event.external_peer_id,
+        text=_format_run_summary(run, automation),
+    )
+    return True
+
+
+async def _handle_run_command(
+    *,
+    session,
+    adapter: TelegramAdapter,
+    event: ParsedInboundEvent,
+    binding: ExternalChatBinding,
+) -> bool:
+    if not event.external_peer_id:
+        return True
+
+    text = event.text or ""
+    parts = text.split(maxsplit=1)
+    is_list = len(parts) == 1
+    name = ""
+    if not is_list:
+        name = _strip_bot_mention(parts[1].strip())
+
+    try:
+        auth = await _auth_for_binding(session, binding)
+        await check_permission(
+            session,
+            auth,
+            binding.workspace_id,
+            Permission.AUTOMATIONS_EXECUTE.value,
+            "You don't have permission to run automations in this workspace",
+        )
+    except HTTPException:
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text="Access denied: you can't run automations in this workspace.",
+        )
+        return True
+
+    if is_list:
+        automations = await _active_automations_for_workspace(
+            session, binding.workspace_id
+        )
+        if not automations:
+            await adapter.send_message(
+                external_peer_id=event.external_peer_id,
+                text="No active automations in this workspace.",
+            )
+            return True
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text=_build_automation_list_text(automations),
+        )
+        return True
+
+    automation = await _find_active_automation_by_name(
+        session, binding.workspace_id, name
+    )
+    if automation is None:
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text=f"Automation '{name}' not found.",
+        )
+        return True
+
+    trigger = AutomationTrigger(
+        automation_id=automation.id,
+        type=TriggerType.MANUAL,
+        params={},
+        static_inputs={},
+    )
+    try:
+        await launch_run(
+            session=session,
+            trigger=trigger,
+            runtime_inputs={"fired_by": "telegram"},
+        )
+    except DispatchError:
+        logger.exception("DispatchError starting run for automation %s", automation.id)
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text="Could not start run. Please try again later.",
+        )
+        return True
+    except Exception:
+        logger.exception(
+            "Unexpected error starting run for automation %s", automation.id
+        )
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text="Could not start run. Please try again later.",
+        )
+        return True
+
+    try:
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text="Run started. You will be notified when it completes.",
+        )
+    except Exception:
+        logger.exception(
+            "Failed to send confirmation after starting run for automation %s",
+            automation.id,
+        )
+    return True
+
+
 class TelegramGatewayCommands(BaseGatewayCommands):
     async def handle_start_command(
         self,
@@ -117,3 +398,42 @@ class TelegramGatewayCommands(BaseGatewayCommands):
             event=event,
             dashboard_url=dashboard_url,
         )
+
+    async def handle_status_command(
+        self,
+        *,
+        session,
+        adapter: TelegramAdapter,
+        event: ParsedInboundEvent,
+        binding: ExternalChatBinding,
+    ) -> bool:
+        return await _handle_status_command(
+            session=session, adapter=adapter, event=event, binding=binding
+        )
+
+    async def handle_run_command(
+        self,
+        *,
+        session,
+        adapter: TelegramAdapter,
+        event: ParsedInboundEvent,
+        binding: ExternalChatBinding,
+    ) -> bool:
+        return await _handle_run_command(
+            session=session, adapter=adapter, event=event, binding=binding
+        )
+
+    async def handle_callback_query(
+        self,
+        *,
+        session,
+        adapter: TelegramAdapter,
+        event: ParsedInboundEvent,
+        binding: ExternalChatBinding,
+    ) -> None:
+        await handle_callback_query(
+            session=session,
+            adapter=adapter,
+            event=event,
+            binding=binding,
+        )
diff --git a/nowing_backend/tests/unit/gateway/test_telegram_callbacks.py b/nowing_backend/tests/unit/gateway/test_telegram_callbacks.py
new file mode 100644
index 000000000..377ee089b
--- /dev/null
+++ b/nowing_backend/tests/unit/gateway/test_telegram_callbacks.py
@@ -0,0 +1,278 @@
+"""Tests for Telegram callback query dispatch."""
+
+from __future__ import annotations
+
+from datetime import UTC, datetime
+from unittest.mock import AsyncMock, MagicMock
+
+import pytest
+from fastapi import HTTPException
+
+from app.automations.dispatch.errors import DispatchError
+from app.automations.persistence.enums.automation_status import AutomationStatus
+from app.automations.persistence.enums.run_status import RunStatus
+from app.automations.persistence.enums.trigger_type import TriggerType
+from app.db import ExternalChatBinding
+from app.gateway.base.adapter import ParsedInboundEvent
+from app.gateway.telegram.callbacks import handle_callback_query
+
+
+@pytest.fixture
+def session(mocker) -> MagicMock:
+    return mocker.AsyncMock()
+
+
+@pytest.fixture
+def binding() -> ExternalChatBinding:
+    # user_id=None avoids loading a User in these unit tests.
+    return ExternalChatBinding(
+        id=1,
+        account_id=1,
+        user_id=None,
+        workspace_id=42,
+        external_peer_id="12345",
+        external_peer_kind="direct",
+    )
+
+
+def _event(text: str = "view_run:123") -> ParsedInboundEvent:
+    return ParsedInboundEvent(
+        platform="telegram",
+        event_kind="callback_query",
+        external_peer_id="12345",
+        external_peer_kind="direct",
+        external_message_id="99",
+        external_user_id="111",
+        text=text,
+        metadata={"callback_query_id": "cqid"},
+        raw_payload={},
+    )
+
+
+@pytest.fixture
+def event() -> ParsedInboundEvent:
+    return _event()
+
+
+@pytest.fixture
+def adapter(mocker) -> MagicMock:
+    mock = MagicMock()
+    mock.send_message = AsyncMock()
+    mock.edit_message = AsyncMock()
+    mock.answer_callback_query = AsyncMock()
+    return mock
+
+
+@pytest.fixture(autouse=True)
+def mock_auth(mocker):
+    mocker.patch(
+        "app.gateway.telegram.callbacks._load_user",
+        new=AsyncMock(return_value=MagicMock()),
+    )
+    return mocker.patch(
+        "app.gateway.telegram.callbacks.check_permission", new=AsyncMock()
+    )
+
+
+@pytest.mark.asyncio
+async def test_view_run_edits_message(session, adapter, binding, event):
+    run = MagicMock()
+    run.id = 123
+    run.status = RunStatus.SUCCEEDED
+    run.finished_at = datetime.now(UTC)
+    run.automation_id = 5
+
+    automation = MagicMock()
+    automation.id = 5
+    automation.name = "Test Automation"
+    automation.workspace_id = 42
+
+    session.get.side_effect = [run, automation]
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once()
+    adapter.edit_message.assert_awaited_once()
+    call = adapter.edit_message.call_args.kwargs
+    assert "Test Automation" in call["text"]
+    assert call["external_peer_id"] == "12345"
+    assert call["external_message_id"] == "99"
+
+
+@pytest.mark.asyncio
+async def test_view_run_not_found(session, adapter, binding):
+    session.get.return_value = None
+    event = _event("view_run:999")
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once()
+    adapter.send_message.assert_awaited_once()
+    assert "not found" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_view_run_permission_denied(session, adapter, binding, mocker):
+    event = _event("view_run:123")
+    mocker.patch(
+        "app.gateway.telegram.callbacks.check_permission",
+        new=AsyncMock(side_effect=HTTPException(status_code=403)),
+    )
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once()
+    assert "Access denied" in adapter.answer_callback_query.call_args.kwargs["text"]
+    session.get.assert_not_called()
+    adapter.edit_message.assert_not_awaited()
+    adapter.send_message.assert_not_awaited()
+
+
+@pytest.mark.asyncio
+async def test_view_run_user_not_found(session, adapter, binding, mocker):
+    event = _event("view_run:123")
+    mocker.patch(
+        "app.gateway.telegram.callbacks._load_user",
+        new=AsyncMock(return_value=None),
+    )
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once()
+    assert "Access denied" in adapter.answer_callback_query.call_args.kwargs["text"]
+    session.get.assert_not_called()
+    adapter.edit_message.assert_not_awaited()
+    adapter.send_message.assert_not_awaited()
+
+
+@pytest.mark.asyncio
+async def test_rerun_triggers_automation(session, adapter, binding, mocker):
+    event = _event("rerun:5")
+    automation = MagicMock()
+    automation.id = 5
+    automation.name = "Test Automation"
+    automation.workspace_id = 42
+    automation.status = AutomationStatus.ACTIVE
+
+    session.get.return_value = automation
+    launch = mocker.patch("app.gateway.telegram.callbacks.launch_run", new=AsyncMock())
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    launch.assert_awaited_once()
+    launch_call = launch.call_args.kwargs
+    assert launch_call["trigger"].automation_id == 5
+    assert launch_call["trigger"].type == TriggerType.MANUAL
+    adapter.answer_callback_query.assert_awaited_once()
+    adapter.send_message.assert_awaited_once()
+    assert "Started run" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_rerun_not_active(session, adapter, binding):
+    event = _event("rerun:5")
+    automation = MagicMock()
+    automation.id = 5
+    automation.status = AutomationStatus.PAUSED
+
+    session.get.return_value = automation
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once()
+    assert "paused" in adapter.answer_callback_query.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_rerun_permission_denied(session, adapter, binding, mocker):
+    event = _event("rerun:5")
+    mocker.patch(
+        "app.gateway.telegram.callbacks.check_permission",
+        new=AsyncMock(side_effect=HTTPException(status_code=403)),
+    )
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once()
+    assert "Access denied" in adapter.answer_callback_query.call_args.kwargs["text"]
+    session.get.assert_not_called()
+    adapter.send_message.assert_not_awaited()
+
+
+@pytest.mark.asyncio
+async def test_rerun_launch_run_dispatch_error(session, adapter, binding, mocker):
+    event = _event("rerun:5")
+    automation = MagicMock()
+    automation.id = 5
+    automation.name = "Test Automation"
+    automation.workspace_id = 42
+    automation.status = AutomationStatus.ACTIVE
+
+    session.get.return_value = automation
+    mocker.patch(
+        "app.gateway.telegram.callbacks.launch_run",
+        new=AsyncMock(side_effect=DispatchError("bad inputs")),
+    )
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once()
+    text = adapter.answer_callback_query.call_args.kwargs["text"]
+    assert "Could not start run" in text
+    assert "bad inputs" not in text
+    adapter.send_message.assert_not_awaited()
+
+
+@pytest.mark.asyncio
+async def test_rerun_launch_run_unexpected_error(session, adapter, binding, mocker):
+    event = _event("rerun:5")
+    automation = MagicMock()
+    automation.id = 5
+    automation.name = "Test Automation"
+    automation.workspace_id = 42
+    automation.status = AutomationStatus.ACTIVE
+
+    session.get.return_value = automation
+    mocker.patch(
+        "app.gateway.telegram.callbacks.launch_run",
+        new=AsyncMock(side_effect=RuntimeError("explosion")),
+    )
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once()
+    text = adapter.answer_callback_query.call_args.kwargs["text"]
+    assert "Could not start run" in text
+    assert "explosion" not in text
+    adapter.send_message.assert_not_awaited()
+
+
+@pytest.mark.asyncio
+async def test_unknown_callback_data_answers_only(session, adapter, binding):
+    event = _event("unknown:stuff")
+
+    await handle_callback_query(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.answer_callback_query.assert_awaited_once_with(callback_query_id="cqid")
+    adapter.send_message.assert_not_awaited()
+    adapter.edit_message.assert_not_awaited()
diff --git a/nowing_backend/tests/unit/gateway/test_telegram_commands.py b/nowing_backend/tests/unit/gateway/test_telegram_commands.py
new file mode 100644
index 000000000..b7bc2153f
--- /dev/null
+++ b/nowing_backend/tests/unit/gateway/test_telegram_commands.py
@@ -0,0 +1,421 @@
+"""Tests for Telegram bot /status and /run commands."""
+
+from __future__ import annotations
+
+from datetime import UTC, datetime
+from unittest.mock import AsyncMock, MagicMock
+
+import pytest
+from fastapi import HTTPException
+
+from app.automations.dispatch.errors import DispatchError
+from app.automations.persistence.enums.automation_status import AutomationStatus
+from app.automations.persistence.enums.run_status import RunStatus
+from app.automations.persistence.enums.trigger_type import TriggerType
+from app.db import ExternalChatBinding
+from app.gateway.base.adapter import ParsedInboundEvent
+from app.gateway.telegram.commands import TelegramGatewayCommands
+
+
+@pytest.fixture
+def session(mocker) -> MagicMock:
+    mock = mocker.AsyncMock()
+    mock.execute.return_value = MagicMock()
+    return mock
+
+
+@pytest.fixture
+def binding() -> ExternalChatBinding:
+    return ExternalChatBinding(
+        id=1,
+        account_id=1,
+        user_id=None,
+        workspace_id=42,
+        external_peer_id="12345",
+        external_peer_kind="direct",
+    )
+
+
+@pytest.fixture
+def adapter(mocker) -> MagicMock:
+    mock = MagicMock()
+    mock.send_message = AsyncMock()
+    return mock
+
+
+@pytest.fixture
+def commands() -> TelegramGatewayCommands:
+    return TelegramGatewayCommands()
+
+
+@pytest.fixture(autouse=True)
+def mock_auth(mocker):
+    mocker.patch(
+        "app.gateway.telegram.commands._load_user",
+        new=AsyncMock(return_value=MagicMock()),
+    )
+    return mocker.patch(
+        "app.gateway.telegram.commands.check_permission", new=AsyncMock()
+    )
+
+
+def _event(text: str) -> ParsedInboundEvent:
+    return ParsedInboundEvent(
+        platform="telegram",
+        event_kind="message",
+        external_peer_id="12345",
+        external_peer_kind="direct",
+        external_message_id=None,
+        external_user_id="111",
+        text=text,
+        raw_payload={},
+    )
+
+
+def _run_mock(automation_id: int = 5) -> MagicMock:
+    run = MagicMock()
+    run.id = 123
+    run.automation_id = automation_id
+    run.status = RunStatus.SUCCEEDED
+    run.finished_at = datetime.now(UTC)
+    return run
+
+
+def _automation_mock(name: str = "Test Automation") -> MagicMock:
+    automation = MagicMock()
+    automation.id = 5
+    automation.name = name
+    automation.workspace_id = 42
+    automation.status = AutomationStatus.ACTIVE
+    return automation
+
+
+def _set_execute_first(session: MagicMock, value) -> None:
+    session.execute.return_value.scalars.return_value.first.return_value = value
+
+
+def _set_execute_all(session: MagicMock, values) -> None:
+    session.execute.return_value.scalars.return_value.all.return_value = values
+
+
+@pytest.mark.asyncio
+async def test_status_command_no_recent_runs(session, adapter, binding, commands):
+    _set_execute_first(session, None)
+    event = _event("/status")
+
+    await commands.handle_status_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    assert "No recent runs" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_status_command_shows_latest_run(session, adapter, binding, commands):
+    run = _run_mock()
+    automation = _automation_mock()
+    _set_execute_first(session, run)
+    session.get.return_value = automation
+    event = _event("/status")
+
+    await commands.handle_status_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    text = adapter.send_message.call_args.kwargs["text"]
+    assert "Test Automation" in text
+    assert "succeeded" in text
+
+
+@pytest.mark.asyncio
+async def test_status_command_orphan_run(session, adapter, binding, commands):
+    run = _run_mock()
+    _set_execute_first(session, run)
+    session.get.return_value = None
+    event = _event("/status")
+
+    await commands.handle_status_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    text = adapter.send_message.call_args.kwargs["text"]
+    assert "automation record is missing" in text
+    assert "No recent runs" not in text
+
+
+@pytest.mark.asyncio
+async def test_status_command_permission_denied(
+    session, adapter, binding, commands, mocker
+):
+    mocker.patch(
+        "app.gateway.telegram.commands.check_permission",
+        new=AsyncMock(side_effect=HTTPException(status_code=403)),
+    )
+    event = _event("/status")
+
+    await commands.handle_status_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_status_command_user_not_found(
+    session, adapter, binding, commands, mocker
+):
+    mocker.patch(
+        "app.gateway.telegram.commands._load_user",
+        new=AsyncMock(return_value=None),
+    )
+    event = _event("/status")
+
+    await commands.handle_status_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_run_command_lists_active_automations(
+    session, adapter, binding, commands
+):
+    event = _event("/run")
+    auto_a = _automation_mock("Automation A")
+    auto_b = _automation_mock("Automation B")
+    _set_execute_all(session, [auto_a, auto_b])
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    text = adapter.send_message.call_args.kwargs["text"]
+    assert "Automation A" in text
+    assert "Automation B" in text
+    assert "/run <name>" in text
+
+
+@pytest.mark.asyncio
+async def test_run_command_not_found(session, adapter, binding, commands):
+    event = _event("/run Missing")
+    _set_execute_first(session, None)
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    assert "Missing' not found" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_run_command_triggers_automation(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run Test Automation")
+    automation = _automation_mock("Test Automation")
+    _set_execute_first(session, automation)
+    launch = mocker.patch("app.gateway.telegram.commands.launch_run", new=AsyncMock())
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    launch.assert_awaited_once()
+    trigger = launch.call_args.kwargs["trigger"]
+    assert trigger.automation_id == 5
+    assert trigger.type == TriggerType.MANUAL
+    assert launch.call_args.kwargs["runtime_inputs"] == {"fired_by": "telegram"}
+    adapter.send_message.assert_awaited_once()
+    assert "Run started" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_run_command_permission_denied(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run Test Automation")
+    mocker.patch(
+        "app.gateway.telegram.commands.check_permission",
+        new=AsyncMock(side_effect=HTTPException(status_code=403)),
+    )
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_run_command_user_not_found(session, adapter, binding, commands, mocker):
+    mocker.patch(
+        "app.gateway.telegram.commands._load_user",
+        new=AsyncMock(return_value=None),
+    )
+    event = _event("/run Test Automation")
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_run_command_list_permission_before_query(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run")
+    list_mock = mocker.patch(
+        "app.gateway.telegram.commands._active_automations_for_workspace",
+        new=AsyncMock(),
+    )
+    mocker.patch(
+        "app.gateway.telegram.commands.check_permission",
+        new=AsyncMock(side_effect=HTTPException(status_code=403)),
+    )
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    list_mock.assert_not_awaited()
+    adapter.send_message.assert_awaited_once()
+    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_run_command_named_permission_before_lookup(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run Test Automation")
+    find_mock = mocker.patch(
+        "app.gateway.telegram.commands._find_active_automation_by_name",
+        new=AsyncMock(),
+    )
+    mocker.patch(
+        "app.gateway.telegram.commands.check_permission",
+        new=AsyncMock(side_effect=HTTPException(status_code=403)),
+    )
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    find_mock.assert_not_awaited()
+    adapter.send_message.assert_awaited_once()
+    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]
+
+
+@pytest.mark.asyncio
+async def test_run_command_long_automation_list(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run")
+    long_names = [MagicMock(name=f"auto_{i}") for i in range(300)]
+    for i, auto in enumerate(long_names):
+        auto.name = f"Automation {i} {'x' * 50}"
+    mocker.patch(
+        "app.gateway.telegram.commands._active_automations_for_workspace",
+        new=AsyncMock(return_value=long_names),
+    )
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    text = adapter.send_message.call_args.kwargs["text"]
+    assert len(text) <= 4096
+    assert "truncated" in text
+
+
+@pytest.mark.asyncio
+async def test_run_command_bot_mention_strip(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run @NowingBot   Automation Name")
+    automation = _automation_mock("Automation Name")
+    find_mock = mocker.patch(
+        "app.gateway.telegram.commands._find_active_automation_by_name",
+        new=AsyncMock(return_value=automation),
+    )
+    mocker.patch("app.gateway.telegram.commands.launch_run", new=AsyncMock())
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    find_mock.assert_awaited_once_with(session, 42, "Automation Name")
+
+
+@pytest.mark.asyncio
+async def test_run_command_launch_run_dispatch_error(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run Test Automation")
+    automation = _automation_mock("Test Automation")
+    _set_execute_first(session, automation)
+    mocker.patch(
+        "app.gateway.telegram.commands.launch_run",
+        new=AsyncMock(side_effect=DispatchError("bad inputs")),
+    )
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    text = adapter.send_message.call_args.kwargs["text"]
+    assert "Could not start run" in text
+    assert "bad inputs" not in text
+
+
+@pytest.mark.asyncio
+async def test_run_command_launch_run_unexpected_error(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run Test Automation")
+    automation = _automation_mock("Test Automation")
+    _set_execute_first(session, automation)
+    mocker.patch(
+        "app.gateway.telegram.commands.launch_run",
+        new=AsyncMock(side_effect=RuntimeError("explosion")),
+    )
+
+    await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    adapter.send_message.assert_awaited_once()
+    text = adapter.send_message.call_args.kwargs["text"]
+    assert "Could not start run" in text
+    assert "explosion" not in text
+
+
+@pytest.mark.asyncio
+async def test_run_command_confirmation_send_failure(
+    session, adapter, binding, commands, mocker
+):
+    event = _event("/run Test Automation")
+    automation = _automation_mock("Test Automation")
+    _set_execute_first(session, automation)
+    mocker.patch("app.gateway.telegram.commands.launch_run", new=AsyncMock())
+    adapter.send_message.side_effect = RuntimeError("send failed")
+
+    result = await commands.handle_run_command(
+        session=session, adapter=adapter, event=event, binding=binding
+    )
+
+    assert result is True
+    adapter.send_message.assert_awaited_once()
