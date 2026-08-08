"""Unit tests for anti-bot escalation service.

Uses in-memory SQLAlchemy models and mocked AsyncSession for the grouping path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.db import AntiBotEscalation
from app.services.anti_bot_escalation import (
    _screenshot_key,
    _updated_metadata,
    create_or_update_escalation,
)


@pytest.fixture
def workspace_id() -> int:
    return 1


@pytest.fixture
def run_id() -> UUID:
    return uuid4()


@pytest.fixture
def base_escalation(workspace_id: int, run_id: UUID) -> AntiBotEscalation:
    return AntiBotEscalation(
        run_id=run_id,
        workspace_id=workspace_id,
        capability="walmart_search",
        domain="walmart.com",
        block_type="cloudflare",
        status="open",
        detection_count=1,
        last_seen_at=datetime.now(UTC),
    )


@pytest.mark.unit
async def test_create_or_update_escalation_groups_open_rows(
    workspace_id: int, run_id: UUID, base_escalation: AntiBotEscalation
) -> None:
    """Repeated blocks for the same (workspace, domain, capability) bump detection_count."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = base_escalation
    session.execute.return_value = result_mock

    with patch("app.services.anti_bot_escalation.metrics.record_anti_bot_detection"):
        updated = await create_or_update_escalation(
            session,
            run_id=run_id,
            workspace_id=workspace_id,
            capability="walmart_search",
            domain="walmart.com",
            block_type="cloudflare",
            screenshot_url="https://example.com/s.png",
        )

    assert updated is base_escalation
    assert updated.detection_count == 2
    assert updated.status == "open"
    assert updated.screenshot_url == "https://example.com/s.png"
    assert updated.last_seen_at >= base_escalation.last_seen_at


@pytest.mark.unit
async def test_create_or_update_escalation_creates_new_when_none(
    workspace_id: int, run_id: UUID
) -> None:
    """A fresh block with no open row creates a new escalation."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    with patch("app.services.anti_bot_escalation.metrics.record_anti_bot_detection"):
        created = await create_or_update_escalation(
            session,
            run_id=run_id,
            workspace_id=workspace_id,
            capability="walmart_search",
            domain="walmart.com",
            block_type="cloudflare",
            screenshot_url=None,
        )

    assert created.detection_count == 1
    assert created.status == "open"
    assert created.workspace_id == workspace_id
    assert created.capability == "walmart_search"
    session.add.assert_called_once_with(created)


@pytest.mark.unit
def test_screenshot_key_uses_workspace_and_run(workspace_id: int, run_id: UUID) -> None:
    assert (
        _screenshot_key(workspace_id, run_id)
        == f"anti_bot_screenshots/{workspace_id}/{run_id}.png"
    )


@pytest.mark.unit
def test_updated_metadata_keeps_storage_key(workspace_id: int, run_id: UUID) -> None:
    updated = _updated_metadata(None, workspace_id, run_id, {"foo": "bar"})
    assert updated["storage_key"] == _screenshot_key(workspace_id, run_id)
    assert updated["foo"] == "bar"
