"""Verify generated SQL operators for CrmSyncService.

SQLAlchemy ``==`` / ``!=`` comparison mutants cannot be killed by
mocked-result tests because the fake session ignores the query.
These tests compile each statement and assert the operator is correct.
"""

from __future__ import annotations

import types
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db import CrmConnection, Lead
from app.lead_intelligence.crm.service import CrmConnectionService, CrmSyncService

pytestmark = pytest.mark.unit


def _make_auth() -> Any:
    return types.SimpleNamespace(
        user=types.SimpleNamespace(id=uuid4()),
        is_gated=False,
    )


def _make_connection() -> CrmConnection:
    conn = CrmConnection()
    conn.id = uuid4()
    conn.workspace_id = 1
    conn.provider = "hubspot"
    conn.status = "active"
    return conn


def _make_lead() -> Lead:
    lead = Lead()
    lead.id = uuid4()
    lead.workspace_id = 1
    return lead


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalars(self):
        return self

    def first(self) -> Any:
        return self._value

    def all(self) -> list[Any]:
        return self._rows


class _RecordingSession:
    """AsyncSession that records compiled SQL strings."""

    def __init__(self, queue: list[Any] | None = None) -> None:
        self.statements: list[str] = []
        self._queue = queue or []

    def add(self, _obj: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        from sqlalchemy.dialects import postgresql

        compiled = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        self.statements.append(compiled)
        if self._queue:
            return self._queue.pop(0)
        return _FakeResult(rows=[])

    async def commit(self) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def refresh(self, _obj: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_handle_callback_query_uses_equality():
    """Kills comparison operator mutants in handle_callback SQL."""
    session = _RecordingSession()
    service = CrmConnectionService(session)

    with (
        pytest.raises(HTTPException),
        patch(
            "app.lead_intelligence.crm.service.exchange_code",
            new=AsyncMock(return_value=("ENCRYPTED{}", "token")),
        ),
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.handle_callback("hubspot", "code", "state")

    assert len(session.statements) == 1
    sql = session.statements[0]
    assert "provider = 'hubspot'" in sql
    assert "status = 'pending'" in sql


@pytest.mark.asyncio
async def test_list_connections_query_uses_equality_and_inequality():
    """Kills comparison operator mutants in list_connections SQL."""
    session = _RecordingSession(queue=[_FakeResult(rows=[])])
    auth = _make_auth()
    service = CrmConnectionService(session)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ):
        await service.list_connections(auth, 1)

    assert len(session.statements) == 1
    sql = session.statements[0]
    assert "workspace_id = 1" in sql
    assert "status != 'disconnected'" in sql


@pytest.mark.asyncio
async def test_get_connection_query_uses_equality():
    """Kills comparison operator mutants in get_connection SQL."""
    session = _RecordingSession()
    auth = _make_auth()
    service = CrmConnectionService(session)
    conn_id = uuid4()

    with (
        pytest.raises(HTTPException),
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.get_connection(auth, 1, conn_id)

    assert len(session.statements) == 1
    sql = session.statements[0]
    assert f"id = '{conn_id}'" in sql
    assert "workspace_id = 1" in sql


@pytest.mark.asyncio
async def test_sync_get_connection_query_uses_equality():
    """Kills comparison operator mutants in _get_connection SQL."""
    conn = _make_connection()
    conn.id = uuid4()
    session = _RecordingSession()
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_lead = AsyncMock(return_value=_make_lead())

    with (
        pytest.raises(HTTPException),
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.dedup_lead(auth, 1, conn.id, uuid4())

    # _get_connection is the first execute; _get_lead is mocked.
    assert len(session.statements) >= 1
    sql = session.statements[0]
    assert f"id = '{conn.id}'" in sql
    assert "workspace_id = 1" in sql
    assert "status = 'active'" in sql


@pytest.mark.asyncio
async def test_get_lead_query_uses_equality():
    """Kills comparison operator mutants in _get_lead SQL."""
    conn = _make_connection()
    lead_id = uuid4()
    session = _RecordingSession()
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)

    with (
        pytest.raises(HTTPException),
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.dedup_lead(auth, 1, conn.id, lead_id)

    # _get_connection is mocked; _get_lead is the first real execute.
    assert len(session.statements) == 1
    sql = session.statements[0]
    assert f"id = '{lead_id}'" in sql
    assert "workspace_id = 1" in sql
