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
index a7a45164f..ce35db5ec 100644
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
@@ -394,6 +395,25 @@ async def _dispatch_inbound_event(
 
         event.external_chat_binding_id = binding.id
 
+        if parsed.event_kind == "callback_query":
+            handler = getattr(bundle.commands, "handle_callback_query", None)
+            if handler is not None:
+                await handler(
+                    session=session,
+                    adapter=adapter,
+                    event=parsed,
+                    binding=binding,
+                )
+            elif hasattr(adapter, "answer_callback_query"):
+                callback_query_id = (parsed.metadata or {}).get("callback_query_id")
+                if callback_query_id:
+                    await adapter.answer_callback_query(
+                        callback_query_id=callback_query_id
+                    )
+            event.status = ExternalChatEventStatus.PROCESSED
+            await session.commit()
+            return
+
         if cmd == "/help":
             handled = await bundle.commands.handle_help_command(
                 adapter=adapter, event=parsed
@@ -415,6 +435,30 @@ async def _dispatch_inbound_event(
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
diff --git a/nowing_backend/app/gateway/telegram/commands.py b/nowing_backend/app/gateway/telegram/commands.py
index a3cfc9515..f42176cd9 100644
--- a/nowing_backend/app/gateway/telegram/commands.py
+++ b/nowing_backend/app/gateway/telegram/commands.py
@@ -2,16 +2,31 @@
 
 from __future__ import annotations
 
+from fastapi import HTTPException
+from sqlalchemy import select
+
+from app.auth.context import AuthContext
+from app.automations.dispatch.launch import launch_run
+from app.automations.persistence.enums.automation_status import AutomationStatus
+from app.automations.persistence.enums.trigger_type import TriggerType
+from app.automations.persistence.models.automation import Automation
+from app.automations.persistence.models.run import AutomationRun
+from app.automations.persistence.models.trigger import AutomationTrigger
+from app.db import ExternalChatBinding, Permission, User
 from app.gateway.base.adapter import ParsedInboundEvent
 from app.gateway.base.commands import BaseGatewayCommands
 from app.gateway.pairing import redeem_pairing_code
 from app.gateway.ratelimit import acquire_token
 from app.gateway.telegram.adapter import TelegramAdapter
+from app.gateway.telegram.callbacks import handle_callback_query
+from app.utils.rbac import check_permission
 
 HELP_TEXT = (
     "Nowing Telegram commands:\n"
     "/start <code> - pair this chat\n"
     "/new - start a fresh conversation\n"
+    "/status - latest automation run in this workspace\n"
+    "/run [name] - run an automation or list active automations\n"
     "/help - show this help"
 )
 
@@ -87,6 +102,211 @@ async def send_unbound_onboarding(
     )
 
 
+def _dashboard_run_url(workspace_id: int, automation_id: int, run_id: int) -> str:
+    return f"/workspaces/{workspace_id}/automations/{automation_id}/runs/{run_id}"
+
+
+def _format_run_summary(run: AutomationRun, automation: Automation) -> str:
+    finished_at = ""
+    if run.finished_at:
+        finished_at = f"\nFinished: {run.finished_at.isoformat()}"
+    return (
+        f"Run: {automation.name}\n"
+        f"Status: {run.status.value}{finished_at}\n"
+        f"Link: {_dashboard_run_url(automation.workspace_id, automation.id, run.id)}"
+    )
+
+
+async def _load_user(session, user_id: int | None) -> User | None:
+    if user_id is None:
+        return None
+    return await session.get(User, user_id)
+
+
+async def _auth_for_binding(
+    session, binding: ExternalChatBinding
+) -> AuthContext | None:
+    user = await _load_user(session, binding.user_id)
+    if user is None:
+        return None
+    return AuthContext.session(user)
+
+
+async def _latest_run_for_workspace(
+    session, workspace_id: int
+) -> tuple[AutomationRun, Automation] | None:
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
+    if automation is None:
+        return None
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
+    auth = await _auth_for_binding(session, binding)
+    if auth is not None:
+        try:
+            await check_permission(
+                session,
+                auth,
+                binding.workspace_id,
+                Permission.AUTOMATIONS_READ.value,
+                "You don't have permission to read automations in this workspace",
+            )
+        except HTTPException:
+            await adapter.send_message(
+                external_peer_id=event.external_peer_id,
+                text="Access denied: you can't view runs in this workspace.",
+            )
+            return True
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
+
+    if len(parts) == 1:
+        automations = await _active_automations_for_workspace(
+            session, binding.workspace_id
+        )
+        if not automations:
+            await adapter.send_message(
+                external_peer_id=event.external_peer_id,
+                text="No active automations in this workspace.",
+            )
+            return True
+        names = "\n".join(f"- {a.name}" for a in automations)
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text=f"Active automations:\n{names}\n\nSend /run <name> to start one.",
+        )
+        return True
+
+    name = parts[1].strip()
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
+    auth = await _auth_for_binding(session, binding)
+    if auth is not None:
+        try:
+            await check_permission(
+                session,
+                auth,
+                binding.workspace_id,
+                Permission.AUTOMATIONS_EXECUTE.value,
+                "You don't have permission to run automations in this workspace",
+            )
+        except HTTPException:
+            await adapter.send_message(
+                external_peer_id=event.external_peer_id,
+                text="Access denied: you can't run automations in this workspace.",
+            )
+            return True
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
+    except Exception as exc:
+        await adapter.send_message(
+            external_peer_id=event.external_peer_id,
+            text=f"Could not start run: {exc}",
+        )
+        return True
+
+    await adapter.send_message(
+        external_peer_id=event.external_peer_id,
+        text="Run started. You will be notified when it completes.",
+    )
+    return True
+
+
 class TelegramGatewayCommands(BaseGatewayCommands):
     async def handle_start_command(
         self,
@@ -117,3 +337,42 @@ class TelegramGatewayCommands(BaseGatewayCommands):
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
diff --git a/nowing_backend/tests/unit/gateway/test_telegram_commands.py b/nowing_backend/tests/unit/gateway/test_telegram_commands.py
new file mode 100644
index 000000000..3dfc6a973
--- /dev/null
+++ b/nowing_backend/tests/unit/gateway/test_telegram_commands.py
@@ -0,0 +1,214 @@
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
+        user_id=100,
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
+    session.get.return_value = None
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
+async def test_status_command_shows_latest_run(
+    session, adapter, binding, commands, mocker
+):
+    run = _run_mock()
+    automation = _automation_mock()
+    user = MagicMock()
+    session.get.side_effect = [user, automation]
+    _set_execute_first(session, run)
+    mocker.patch("app.gateway.telegram.commands.check_permission", new=AsyncMock())
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
+    automation.status = AutomationStatus.ACTIVE
+    _set_execute_first(session, automation)
+    mocker.patch("app.gateway.telegram.commands.check_permission", new=AsyncMock())
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
