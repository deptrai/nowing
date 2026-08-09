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
    open_escalation_after_retry,
    resolve_escalation,
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
        escalation_metadata={"storage_key": "anti_bot_screenshots/1/test.png"},
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
    session.add = MagicMock()
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


@pytest.mark.unit
def test_screenshot_key_includes_screenshot_id(workspace_id: int, run_id: UUID) -> None:
    assert (
        _screenshot_key(workspace_id, run_id, screenshot_id="abc123")
        == f"anti_bot_screenshots/{workspace_id}/{run_id}/abc123.png"
    )


@pytest.mark.unit
async def test_create_or_update_escalation_validates_input_length(
    workspace_id: int, run_id: UUID
) -> None:
    """Overly long capability or domain should be rejected early."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    with pytest.raises(ValueError, match="capability exceeds"):
        await create_or_update_escalation(
            session,
            run_id=run_id,
            workspace_id=workspace_id,
            capability="x" * 101,
            domain="walmart.com",
            block_type="cloudflare",
        )

    with pytest.raises(ValueError, match="domain exceeds"):
        await create_or_update_escalation(
            session,
            run_id=run_id,
            workspace_id=workspace_id,
            capability="walmart_search",
            domain="x" * 501,
            block_type="cloudflare",
        )


@pytest.mark.unit
async def test_resolve_escalation_marks_resolved_and_audits(
    workspace_id: int, run_id: UUID, base_escalation: AntiBotEscalation
) -> None:
    """Resolve flips status, records resolved_by and deletes the screenshot key."""
    session = AsyncMock()
    session.get.return_value = base_escalation

    user_id = uuid4()
    with patch(
        "app.services.anti_bot_escalation.get_storage_backend"
    ) as mock_backend:
        mock_backend.return_value.delete = AsyncMock()
        resolved = await resolve_escalation(session, base_escalation.id, user_id)

    assert resolved is base_escalation
    assert resolved.status == "resolved"
    assert resolved.escalation_metadata["resolved_by"] == str(user_id)
    mock_backend.return_value.delete.assert_called_once()


@pytest.mark.unit
async def test_open_escalation_after_retry(
    workspace_id: int, run_id: UUID, base_escalation: AntiBotEscalation
) -> None:
    """A retry run completion re-opens a retry-status escalation."""
    base_escalation.status = "retry"
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = base_escalation
    session.execute.return_value = result_mock

    updated = await open_escalation_after_retry(session, run_id)
    assert updated is base_escalation
    assert updated.status == "open"
    assert "retry_completed_at" in updated.escalation_metadata
