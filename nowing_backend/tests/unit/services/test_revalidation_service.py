"""Unit tests for RevalidationService (Story 9.6c)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.db import MemorySourceType
from app.services.memory.revalidation_service import (
    RevalidationError,
    RevalidationResult,
    RevalidationService,
)

pytestmark = [pytest.mark.unit]


class _FakeInput(BaseModel):
    query: str


class _FakeCapability:
    def __init__(self, billing_unit=None, answer=""):
        self.name = "reddit.scrape"
        self.input_schema = _FakeInput
        self.billing_unit = billing_unit
        self.executor = AsyncMock(return_value=_FakeOutput(answer=answer))


class _FakeOutput(BaseModel):
    answer: str | None = None


def _make_memory(**overrides) -> MagicMock:
    """Build a Memory mock with sensible defaults."""
    memory = MagicMock()
    memory.id = 1
    memory.workspace_id = 7
    memory.client_id = None
    memory.content = "Widget costs 19.99 USD"
    memory.confidence = 0.9
    memory.source_type = MemorySourceType.SCRAPER_RUN
    memory.source_capability = "reddit.scrape"
    memory.source_input = {"query": "pricing"}
    memory.source_run_id = None
    memory.versions = []
    memory.updated_at = datetime.now(UTC)
    for key, value in overrides.items():
        setattr(memory, key, value)
    return memory


def _make_session(memory=None) -> MagicMock:
    """Mock AsyncSession that returns the given memory on select."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=memory)
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_revalidate_not_revalidatable_when_source_capability_is_none():
    memory = _make_memory(source_capability=None, source_input=None)
    session = _make_session(memory)
    service = RevalidationService(session)

    with pytest.raises(RevalidationError) as exc_info:
        await service.revalidate(1, workspace_id=7)

    assert exc_info.value.code == "not_revalidatable"


@pytest.mark.asyncio
async def test_revalidate_not_revalidatable_when_source_type_is_not_scraper_run():
    memory = _make_memory(source_type=MemorySourceType.MANUAL)
    session = _make_session(memory)
    service = RevalidationService(session)

    with pytest.raises(RevalidationError) as exc_info:
        await service.revalidate(1, workspace_id=7)

    assert exc_info.value.code == "not_revalidatable"


@pytest.mark.asyncio
async def test_revalidate_capability_not_found():
    memory = _make_memory()
    session = _make_session(memory)
    service = RevalidationService(session)

    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            side_effect=KeyError("missing"),
        ),
        pytest.raises(RevalidationError) as exc_info,
    ):
        await service.revalidate(1, workspace_id=7)

    assert exc_info.value.code == "capability_not_found"


@pytest.mark.asyncio
async def test_revalidate_invalid_recipe():
    memory = _make_memory(source_input={"invalid": "schema"})
    session = _make_session(memory)
    service = RevalidationService(session)

    capability = _FakeCapability()
    capability.input_schema = (
        _FakeInput  # still permissive, force strict via validation
    )

    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=capability,
        ),
        pytest.raises(RevalidationError) as exc_info,
    ):
        await service.revalidate(1, workspace_id=7)

    assert exc_info.value.code == "invalid_recipe"


@pytest.mark.asyncio
async def test_revalidate_gate_failed():
    memory = _make_memory()
    session = _make_session(memory)
    service = RevalidationService(session)

    capability = _FakeCapability()
    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=capability,
        ),
        patch(
            "app.services.memory.revalidation_service.gate_capability",
            new=AsyncMock(side_effect=RuntimeError("no credits")),
        ),
        pytest.raises(RevalidationError) as exc_info,
    ):
        await service.revalidate(1, workspace_id=7)

    assert exc_info.value.code == "gate_failed"


@pytest.mark.asyncio
async def test_revalidate_match_bumps_confidence():
    memory = _make_memory(content="Widget costs 19.99 USD")
    session = _make_session(memory)
    service = RevalidationService(session)

    capability = _FakeCapability(answer="Widget costs 19.99 USD")
    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=capability,
        ),
        patch(
            "app.services.memory.revalidation_service.gate_capability",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.memory.revalidation_service.execute_with_context",
            new=AsyncMock(return_value=_FakeOutput(answer="Widget costs 19.99 USD")),
        ),
        patch(
            "app.services.memory.revalidation_service.charge_capability",
            new=AsyncMock(return_value=3500),
        ),
        patch(
            "app.services.memory.revalidation_service.record_run",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await service.revalidate(1, workspace_id=7)

    assert isinstance(result, RevalidationResult)
    assert result.status == "verified"
    assert result.memory.confidence > 0.9
    assert result.cost_micros == 3500


@pytest.mark.asyncio
async def test_revalidate_mismatch_creates_version():
    memory = _make_memory(content="Widget costs 19.99 USD")
    session = _make_session(memory)
    repo = AsyncMock()
    repo.update_memory = AsyncMock(return_value=memory)

    service = RevalidationService(session)

    capability = _FakeCapability(answer="Widget costs 29.99 USD")
    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=capability,
        ),
        patch(
            "app.services.memory.revalidation_service.gate_capability",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.memory.revalidation_service.execute_with_context",
            new=AsyncMock(return_value=_FakeOutput(answer="Widget costs 29.99 USD")),
        ),
        patch(
            "app.services.memory.revalidation_service.charge_capability",
            new=AsyncMock(return_value=3500),
        ),
        patch(
            "app.services.memory.revalidation_service.record_run",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.memory.revalidation_service.MemoryRepository",
            return_value=repo,
        ),
    ):
        result = await service.revalidate(1, workspace_id=7)

    assert result.status == "mismatch"
    repo.update_memory.assert_awaited_once()
    assert result.cost_micros == 3500


@pytest.mark.asyncio
async def test_revalidate_failed_when_executor_raises():
    memory = _make_memory()
    session = _make_session(memory)
    service = RevalidationService(session)

    capability = _FakeCapability()
    capability.executor = AsyncMock(side_effect=RuntimeError("upstream"))

    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=capability,
        ),
        patch(
            "app.services.memory.revalidation_service.gate_capability",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await service.revalidate(1, workspace_id=7)

    assert result.status == "failed"
    assert result.cost_micros is None
    assert "upstream" in result.reason


@pytest.mark.asyncio
async def test_revalidate_charge_failed():
    memory = _make_memory()
    session = _make_session(memory)
    service = RevalidationService(session)

    capability = _FakeCapability(answer="Widget costs 19.99 USD")
    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=capability,
        ),
        patch(
            "app.services.memory.revalidation_service.gate_capability",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.memory.revalidation_service.execute_with_context",
            new=AsyncMock(return_value=_FakeOutput(answer="Widget costs 19.99 USD")),
        ),
        patch(
            "app.services.memory.revalidation_service.charge_capability",
            new=AsyncMock(side_effect=RuntimeError("billing down")),
        ),
        pytest.raises(RevalidationError) as exc_info,
    ):
        await service.revalidate(1, workspace_id=7)

    assert exc_info.value.code == "charge_failed"
