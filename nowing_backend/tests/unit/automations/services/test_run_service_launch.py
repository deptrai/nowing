"""Unit tests for ``RunService.launch`` (manual run, no DB).

Isolates the thin-wrapper behaviour: permission gate, transient MANUAL
trigger, ``launch_run`` delegation, and ``DispatchError`` → HTTP mapping.
Pattern 6 (real SQL) is covered by the integration tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.automations.dispatch.errors import DispatchError
from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.services.run import RunService
from app.db import Permission

pytestmark = pytest.mark.unit


class _FakeSession:
    def __init__(self, automation: Any | None) -> None:
        self._automation = automation

    async def get(self, _model: Any, pk: int) -> Any:
        return self._automation


class _FakeAuth:
    pass


def _automation(status: str = "active") -> SimpleNamespace:
    return SimpleNamespace(id=7, workspace_id=1, status=status)


def _service(automation: Any | None) -> RunService:
    return RunService(session=_FakeSession(automation), auth=_FakeAuth())


async def _launch(monkeypatch: Any, *, automation: Any | None, error: Exception | None = None) -> Any:
    """Run ``service.launch`` with ``check_permission`` / ``launch_run`` patched out."""
    captured: dict[str, Any] = {}
    seen_permissions: list[str] = []

    async def _check(_session: Any, _auth: Any, _workspace_id: int, permission: str, _message: str) -> None:
        seen_permissions.append(permission)

    async def _launch_run(**kwargs: Any) -> Any:
        captured["trigger_type"] = kwargs["trigger"].type
        captured["inputs"] = kwargs["runtime_inputs"]
        if error is not None:
            raise error
        return SimpleNamespace(id=99, status=RunStatus.PENDING, automation_id=7)

    import app.automations.services.run as run_mod

    monkeypatch.setattr(run_mod, "check_permission", _check)
    monkeypatch.setattr(run_mod, "launch_run", _launch_run)

    service = _service(automation)
    try:
        result = await service.launch(automation_id=7)
        captured["result"] = result
    except HTTPException as exc:
        captured["http_exc"] = exc

    captured["seen_permissions"] = seen_permissions
    return captured


async def test_launch_checks_execute_permission(monkeypatch):
    """launch requires automations:execute before dispatching."""
    captured = await _launch(monkeypatch, automation=_automation())
    assert captured["seen_permissions"] == [Permission.AUTOMATIONS_EXECUTE.value]
    assert captured["trigger_type"] == TriggerType.MANUAL
    assert captured["inputs"] == {"fired_by": "mcp"}


async def test_launch_returns_pending_run(monkeypatch):
    """The returned run carries the PENDING status from launch_run."""
    captured = await _launch(monkeypatch, automation=_automation())
    assert captured["result"].status == RunStatus.PENDING
    assert captured["result"].id == 99


async def test_launch_not_active_raises_400(monkeypatch):
    """A paused/archived automation maps to HTTP 400 with a readable message."""
    captured = await _launch(
        monkeypatch,
        automation=_automation(status="paused"),
        error=DispatchError("automation 7 is paused, not active"),
    )
    assert captured["http_exc"].status_code == 400
    assert "not active" in captured["http_exc"].detail


async def test_launch_missing_automation_raises_404(monkeypatch):
    """A missing automation (no row) maps to HTTP 404 from authorization."""
    captured = await _launch(monkeypatch, automation=None)
    assert captured["http_exc"].status_code == 404
    assert "not found" in captured["http_exc"].detail


async def test_launch_dispatch_not_found_raises_404(monkeypatch):
    """A dispatch 'not found' failure maps to HTTP 404."""
    captured = await _launch(
        monkeypatch,
        automation=_automation(),
        error=DispatchError("automation 7 not found for trigger None"),
    )
    assert captured["http_exc"].status_code == 404
    assert "not found" in captured["http_exc"].detail


async def test_launch_invalid_definition_raises_400(monkeypatch):
    """An invalid automation definition maps to HTTP 400 (not 500)."""
    captured = await _launch(
        monkeypatch,
        automation=_automation(),
        error=DispatchError("invalid automation definition: boom"),
    )
    assert captured["http_exc"].status_code == 400
    assert "definition" in captured["http_exc"].detail


async def test_launch_run_celery_apply_async_failure_sets_failed_status(monkeypatch):
    """Verify launch_run sets status=FAILED and raises DispatchError if Celery enqueue fails."""
    from unittest.mock import AsyncMock, MagicMock
    from app.automations.dispatch.launch import launch_run
    from app.automations.persistence.enums.run_status import RunStatus
    from app.automations.persistence.models.trigger import AutomationTrigger
    from app.automations.persistence.models.automation import Automation
    from app.automations.persistence.enums.automation_status import AutomationStatus

    session = AsyncMock()
    trigger = AutomationTrigger(id=1, automation_id=10, type="schedule", params={"cron": "0 0 * * *"})
    automation = Automation(
        id=10,
        workspace_id=1,
        status=AutomationStatus.ACTIVE,
        definition={"name": "Test", "plan": [{"step_id": "s1", "action": "continue_research", "params": {"research_thread_id": 1}}]},
    )

    monkeypatch.setattr("app.automations.dispatch.launch.resolve_active_automation", AsyncMock(return_value=automation))
    monkeypatch.setattr("app.automations.dispatch.launch.resolve_research_thread_id", AsyncMock(return_value=None))

    mock_task = MagicMock()
    mock_task.apply_async.side_effect = RuntimeError("Broker connection refused")
    monkeypatch.setattr("app.automations.dispatch.launch.automation_run_execute", mock_task)

    with pytest.raises(DispatchError, match="failed to enqueue execution"):
        await launch_run(session=session, trigger=trigger)

    assert session.commit.await_count >= 2
    # Verify the added run object was marked FAILED
    added_run = session.add.call_args.args[0]
    assert added_run.status == RunStatus.FAILED
