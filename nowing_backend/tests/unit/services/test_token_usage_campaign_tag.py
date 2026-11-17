"""Unit tests Epic 44.4 — contextvar ``current_campaign_run_id`` tag.

``record_token_usage`` tự tag ``call_details['campaign_run_id']`` khi chạy
trong run context (set bởi ``execute_and_persist``); ngoài context → không
tag. Signature giữ nguyên.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import token_tracking_service
from app.services.token_tracking_service import (
    current_campaign_run_id,
    record_token_usage,
)

# Import adapters.base TRƯỚC orchestrator — phá vòng import
# orchestrator → adapters/__init__ → batdongsan → capabilities → executor →
# orchestrator (same pattern tests/unit/lead_intelligence/test_campaign_binding.py).
import app.lead_intelligence.adapters.base  # noqa: F401,E402

pytestmark = pytest.mark.unit


def _session() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_tags_call_details_inside_run_context() -> None:
    run_id = str(uuid.uuid4())
    session = _session()
    token = current_campaign_run_id.set(run_id)
    try:
        with patch.object(
            token_tracking_service, "set_request_tenant_context", new=AsyncMock()
        ):
            record = await record_token_usage(
                session,
                usage_type="lead_gen",
                workspace_id=1,
                cost_micros=100,
                call_details={"model": "gpt-4o"},
            )
    finally:
        current_campaign_run_id.reset(token)

    assert record is not None
    assert record.call_details["campaign_run_id"] == run_id
    assert record.call_details["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_no_tag_outside_run_context() -> None:
    session = _session()
    with patch.object(
        token_tracking_service, "set_request_tenant_context", new=AsyncMock()
    ):
        record = await record_token_usage(
            session,
            usage_type="lead_gen",
            workspace_id=1,
            cost_micros=100,
            call_details={"model": "gpt-4o"},
        )
    assert record is not None
    assert "campaign_run_id" not in record.call_details


@pytest.mark.asyncio
async def test_no_tag_when_contextvar_default_none() -> None:
    """call_details=None ngoài context → vẫn None, không tạo dict rác."""
    session = _session()
    with patch.object(
        token_tracking_service, "set_request_tenant_context", new=AsyncMock()
    ):
        record = await record_token_usage(
            session,
            usage_type="lead_gen",
            workspace_id=1,
        )
    assert record is not None
    assert record.call_details is None


@pytest.mark.asyncio
async def test_tag_does_not_overwrite_explicit_value() -> None:
    """Caller truyền campaign_run_id tường minh → không bị contextvar đè."""
    session = _session()
    token = current_campaign_run_id.set(str(uuid.uuid4()))
    try:
        with patch.object(
            token_tracking_service, "set_request_tenant_context", new=AsyncMock()
        ):
            explicit = str(uuid.uuid4())
            record = await record_token_usage(
                session,
                usage_type="lead_gen",
                workspace_id=1,
                call_details={"campaign_run_id": explicit},
            )
    finally:
        current_campaign_run_id.reset(token)

    assert record is not None
    assert record.call_details["campaign_run_id"] == explicit


@pytest.mark.asyncio
async def test_caller_dict_not_mutated() -> None:
    """Merge tạo dict mới — dict của caller không bị thay đổi."""
    session = _session()
    caller_details: dict = {"model": "gpt-4o"}
    token = current_campaign_run_id.set(str(uuid.uuid4()))
    try:
        with patch.object(
            token_tracking_service, "set_request_tenant_context", new=AsyncMock()
        ):
            await record_token_usage(
                session,
                usage_type="lead_gen",
                workspace_id=1,
                call_details=caller_details,
            )
    finally:
        current_campaign_run_id.reset(token)

    assert caller_details == {"model": "gpt-4o"}


@pytest.mark.asyncio
async def test_orchestrator_sets_and_resets_contextvar() -> None:
    """``execute_and_persist`` set contextvar khi ``campaign_run_id`` có
    mặt và reset trong finally (không leak)."""
    from app.lead_intelligence.services.lead_gen_orchestrator import (
        LeadGenOrchestrator,
    )

    orch = LeadGenOrchestrator.__new__(LeadGenOrchestrator)
    run_id = uuid.uuid4()
    seen: dict = {}

    async def _impl(_self, **kwargs):
        seen["campaign_run_id"] = current_campaign_run_id.get()
        return MagicMock()

    with patch.object(LeadGenOrchestrator, "_execute_and_persist_impl", _impl):
        await orch.execute_and_persist(
            AsyncMock(), workspace_id=1, campaign_run_id=run_id
        )

    assert seen["campaign_run_id"] == str(run_id)
    # reset sau khi return
    assert current_campaign_run_id.get() is None


@pytest.mark.asyncio
async def test_orchestrator_no_context_without_run_id() -> None:
    from app.lead_intelligence.services.lead_gen_orchestrator import (
        LeadGenOrchestrator,
    )

    orch = LeadGenOrchestrator.__new__(LeadGenOrchestrator)
    seen: dict = {}

    async def _impl(_self, **kwargs):
        seen["tag"] = current_campaign_run_id.get()
        return MagicMock()

    with patch.object(LeadGenOrchestrator, "_execute_and_persist_impl", _impl):
        await orch.execute_and_persist(AsyncMock(), workspace_id=1)

    assert seen["tag"] is None


@pytest.mark.asyncio
async def test_orchestrator_resets_on_impl_failure() -> None:
    """Impl raise → finally vẫn reset contextvar."""
    from app.lead_intelligence.services.lead_gen_orchestrator import (
        LeadGenOrchestrator,
    )

    orch = LeadGenOrchestrator.__new__(LeadGenOrchestrator)

    async def _impl(_self, **kwargs):
        raise RuntimeError("boom")

    with patch.object(LeadGenOrchestrator, "_execute_and_persist_impl", _impl):
        with pytest.raises(RuntimeError):
            await orch.execute_and_persist(
                AsyncMock(), workspace_id=1, campaign_run_id=uuid.uuid4()
            )

    assert current_campaign_run_id.get() is None
