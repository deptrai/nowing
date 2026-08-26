"""Unit tests for AdminAuditLogService (Story 25.6).

These tests mock the database session so they run without a live Postgres instance.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


def _load_service():
    """Lazy import to allow test collection before service is implemented."""
    try:
        from app.services.admin_audit_log_service import AdminAuditLogService

        return AdminAuditLogService
    except ImportError as exc:
        pytest.fail(f"AdminAuditLogService not implemented yet: {exc}")


class _Row:
    """Mock row container for SQLAlchemy result rows."""

    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _MockResult:
    """Minimal async result mock."""

    def __init__(self, rows: list[_Row] | None = None, scalar_value: Any = None):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def all(self) -> list[_Row]:
        return self._rows

    def scalar(self) -> Any:
        return self._scalar_value

    def scalar_one(self) -> Any:
        return self._scalar_value


@pytest.fixture
def service():
    service_cls = _load_service()
    session = AsyncMock()
    return service_cls(session)


@pytest.mark.asyncio
async def test_get_audit_events_default_pagination(service) -> None:
    """AC-1: Default limit is 50, max limit is 200, returns items and total."""
    event_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    now = datetime.now(UTC)

    mock_event = _Row(
        id=event_id,
        actor_id=actor_id,
        subject_id=subject_id,
        action="user.impersonate_start",
        ip_address="127.0.0.1",
        user_agent="Mozilla/5.0",
        diff_payload={
            "reason": "Support debugging",
            "endpoint": "/api/v1/admin/impersonate",
        },
        created_at=now,
        actor_email="admin@nowing.net",
        subject_email="target@nowing.net",
    )

    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult(scalar_value=1),  # count query
            _MockResult(rows=[mock_event]),  # items query
        ]
    )

    result = await service.list_audit_events(limit=50, offset=0)
    assert result["total"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["id"] == event_id
    assert item["actor_email"] == "admin@nowing.net"
    assert item["subject_email"] == "target@nowing.net"
    assert item["action"] == "user.impersonate_start"
    assert item["diff_payload"]["endpoint"] == "/api/v1/admin/impersonate"


@pytest.mark.asyncio
async def test_get_audit_events_clamps_max_limit(service) -> None:
    """AC-1: limit > 200 is clamped to 200; limit < 1 is clamped to 1."""
    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult(scalar_value=0),
            _MockResult(rows=[]),
        ]
    )

    result = await service.list_audit_events(limit=500, offset=0)
    assert result["limit"] == 200

    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult(scalar_value=0),
            _MockResult(rows=[]),
        ]
    )
    result_low = await service.list_audit_events(limit=-10, offset=0)
    assert result_low["limit"] == 1


@pytest.mark.asyncio
async def test_get_audit_events_filters_by_action_and_ticket_ref(service) -> None:
    """AC-1: Filtering by action string and ticket_ref inside diff_payload."""
    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult(scalar_value=1),
            _MockResult(rows=[]),
        ]
    )

    result = await service.list_audit_events(
        action="global_dnc.add",
        ticket_ref="TICKET-1234",
        limit=50,
        offset=0,
    )
    assert result["total"] == 1
    assert result["items"] == []


@pytest.mark.asyncio
async def test_get_audit_events_filters_by_date_range(service) -> None:
    """AC-1: Filtering by start_date and end_date ISO timestamps."""
    start = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 8, 26, 23, 59, tzinfo=UTC)

    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult(scalar_value=5),
            _MockResult(rows=[]),
        ]
    )

    result = await service.list_audit_events(
        start_date=start,
        end_date=end,
        limit=50,
        offset=0,
    )
    assert result["total"] == 5


@pytest.mark.asyncio
async def test_get_audit_events_handles_null_subject_id_for_non_user_entities(
    service,
) -> None:
    """AC-1: For DNC/broadcast actions, subject_id is None and subject_email resolves to None."""
    event_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    now = datetime.now(UTC)

    mock_event = _Row(
        id=event_id,
        actor_id=actor_id,
        subject_id=None,
        action="global_dnc.add",
        ip_address="10.0.0.1",
        user_agent="AdminClient/1.0",
        diff_payload={
            "record_type": "phone",
            "masked_value": "0908 *** 456",
            "value_hmac": "abcdef123456",
            "reason": "Opt-out requested",
            "endpoint": "/api/v1/admin/dnc/global",
        },
        created_at=now,
        actor_email="superadmin@nowing.net",
        subject_email=None,
    )

    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult(scalar_value=1),
            _MockResult(rows=[mock_event]),
        ]
    )

    result = await service.list_audit_events(limit=50, offset=0)
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["subject_id"] is None
    assert item["subject_email"] is None
    assert item["diff_payload"]["record_type"] == "phone"
    assert item["diff_payload"]["masked_value"] == "0908 *** 456"
