"""Unit tests Epic 44.2 — ``launch_campaign_run`` celery task.

Cover matrix rows TASK_PATH (task load campaign+run, gọi execute_and_persist
với đúng binding) và TENANT_RLS (task ``set_request_tenant_context`` trên
session riêng). Mock ``run_async_celery_task`` chỉ để chạy coroutine — phần
còn lại (spec parse, session riêng, finalize) chạy thật.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models.campaigns import CampaignRun, LeadCampaign
from app.tasks.campaign_tasks import launch_campaign_run

pytestmark = pytest.mark.unit


class _TaskSession:
    """Fake AsyncSession cho task — get/rollback/commit."""

    def __init__(self, campaign: Any = None, run: Any = None) -> None:
        self._campaign = campaign
        self._run = run
        self.committed = False
        self.rolled_back = False

    async def get(self, model: type, obj_id: Any) -> Any:
        if model is LeadCampaign:
            return self._campaign
        if model is CampaignRun:
            return self._run
        return None

    async def rollback(self) -> None:
        self.rolled_back = True

    async def commit(self) -> None:
        self.committed = True


class _SessionCM:
    """Async context manager trả fake session (mock async_session_maker)."""

    def __init__(self, session: _TaskSession) -> None:
        self._session = session

    async def __aenter__(self) -> _TaskSession:
        return self._session

    async def __aexit__(self, *exc: Any) -> bool:
        return False


# Cùng shape FE payload như routes test — parse thật qua
# ``CampaignSpec.from_payload`` bên trong task.
_INPUT_PAYLOAD = {
    "name": "ICP Demand Campaign",
    "description": None,
    "workspace_id": 10,
    "direction": "demand",
    "icp_config": {
        "template": "custom",
        "target_industries": ["B2B SaaS"],
        "locations": ["Hà Nội"],
        "company_size_range": None,
        "tech_stack": [],
        "intents": ["BÁN"],
        "negative_keywords": [],
        "reverse_icp_url": None,
        "custom_instructions": None,
        "location_profile": None,
    },
    "source_budget_config": {
        "sources": ["muasamcong", "enterprise"],
        "expected_leads_target": 100,
        "max_daily_spend_vnd": 500000,
        "min_fit_score": 60,
        "min_intent_score": 50,
        "max_contacts_per_lead": 3,
        "exclude_dnc": True,
        "auto_unlock_verified_phones": False,
    },
    "launch_config": {
        "schedule_type": "once",
        "cron_expression": None,
        "start_time": None,
        "auto_start": True,
        "export_destination": "workspace",
        "notification_webhook": None,
    },
}


def _campaign() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=10,
        name="ICP Demand Campaign",
        status="running",
        input_payload=dict(_INPUT_PAYLOAD),
    )


def _run_coro(factory: Any) -> Any:
    """Thay run_async_celery_task — chỉ chạy coroutine, bỏ engine-dispose."""
    return asyncio.run(factory())


def test_launch_campaign_run_happy_path():
    """TASK_PATH + TENANT_RLS: task set tenant ctx rồi gọi
    execute_and_persist với campaign + campaign_run_id đúng."""
    campaign = _campaign()
    run = SimpleNamespace(id=uuid4(), status="running")
    session = _TaskSession(campaign=campaign, run=run)
    tenant_ctx = AsyncMock()
    exec_persist = AsyncMock(return_value=SimpleNamespace(status="succeeded"))

    with patch(
        "app.tasks.campaign_tasks.async_session_maker",
        return_value=_SessionCM(session),
    ), patch(
        "app.tasks.campaign_tasks.set_request_tenant_context", tenant_ctx
    ), patch(
        "app.tasks.campaign_tasks.run_async_celery_task", _run_coro
    ), patch(
        "app.tasks.campaign_tasks.LeadGenOrchestrator"
    ) as orch_cls:
        orch_cls.return_value.execute_and_persist = exec_persist
        res = launch_campaign_run.run(str(campaign.id), str(run.id), 10)

    assert res == {
        "campaign_id": str(campaign.id),
        "run_id": str(run.id),
        "status": "succeeded",
    }
    # TENANT_RLS: GUC set trên session riêng của task, đúng workspace.
    tenant_ctx.assert_awaited_once_with(session, workspace_id=10)
    exec_persist.assert_awaited_once()
    _pos, kwargs = exec_persist.call_args
    assert kwargs["session"] is session
    assert kwargs["campaign"] is campaign
    assert kwargs["campaign_run_id"] == run.id


def test_launch_campaign_run_failure_finalizes_failed():
    """execute_and_persist raise → rollback + finalize 'failed' + commit,
    exception propagate (worker retry). Run không kẹt 'running'."""
    campaign = _campaign()
    run = SimpleNamespace(id=uuid4(), status="running")
    session = _TaskSession(campaign=campaign, run=run)
    tenant_ctx = AsyncMock()
    finalize = AsyncMock()

    with patch(
        "app.tasks.campaign_tasks.async_session_maker",
        return_value=_SessionCM(session),
    ), patch(
        "app.tasks.campaign_tasks.set_request_tenant_context", tenant_ctx
    ), patch(
        "app.tasks.campaign_tasks.run_async_celery_task", _run_coro
    ), patch(
        "app.tasks.campaign_tasks.LeadGenOrchestrator"
    ) as orch_cls, patch(
        "app.tasks.campaign_tasks.campaign_service.finalize_campaign_run",
        finalize,
    ):
        orch_cls.return_value.execute_and_persist = AsyncMock(
            side_effect=RuntimeError("adapter boom")
        )
        with pytest.raises(RuntimeError, match="adapter boom"):
            launch_campaign_run.run(str(campaign.id), str(run.id), 10)

    # Rollback trước finalize — session aborted từ exception phải reset,
    # nếu không finalize bị PendingRollbackError (run kẹt 'running').
    assert session.rolled_back
    finalize.assert_awaited_once()
    _pos, kwargs = finalize.call_args
    assert kwargs["status"] == "failed"
    assert "adapter boom" in kwargs["error"]
    assert session.committed


def test_launch_campaign_run_missing_campaign_lookup_error():
    """Campaign không tồn tại → LookupError → finalize 'failed' + propagate."""
    run = SimpleNamespace(id=uuid4(), status="running")
    session = _TaskSession(campaign=None, run=run)
    finalize = AsyncMock()

    with patch(
        "app.tasks.campaign_tasks.async_session_maker",
        return_value=_SessionCM(session),
    ), patch(
        "app.tasks.campaign_tasks.set_request_tenant_context", AsyncMock()
    ), patch(
        "app.tasks.campaign_tasks.run_async_celery_task", _run_coro
    ), patch(
        "app.tasks.campaign_tasks.campaign_service.finalize_campaign_run",
        finalize,
    ):
        with pytest.raises(LookupError):
            launch_campaign_run.run(str(uuid4()), str(run.id), 10)

    finalize.assert_awaited_once()
    assert session.committed
