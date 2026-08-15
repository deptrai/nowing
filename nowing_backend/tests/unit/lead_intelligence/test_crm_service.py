"""Red-phase ATDD tests for Story 21.5 — CRM Integration & Write-Back.

Unit tests for ``CrmConnectionService`` and ``CrmSyncService``.
All DB/session interaction is mocked.
"""

from __future__ import annotations

import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.db import CrmConnection, Lead, Permission
from app.lead_intelligence.crm.service import CrmConnectionService, CrmSyncService

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.flushed = False
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, _obj: Any) -> None:
        pass


def _make_auth(workspace_id: int = 1, owner: bool = True) -> Any:
    user = types.SimpleNamespace(id=uuid4())
    return types.SimpleNamespace(
        user=user,
        is_gated=False,
    )


def _make_lead(
    lead_id: UUID, workspace_id: int = 1, domain: str | None = "acme.com"
) -> Lead:
    lead = Lead()
    lead.id = lead_id
    lead.workspace_id = workspace_id
    lead.domain = domain
    lead.company_name = "Acme"
    lead.industry = "SaaS"
    lead.company_size = "50-200"
    lead.location = "SF"
    return lead


def _make_connection(
    connection_id: UUID = uuid4(),
    workspace_id: int = 1,
    provider: str = "hubspot",
    status: str = "active",
    sync_config: dict | None = None,
    credentials_encrypted: str = "ENCRYPTED{}",
) -> CrmConnection:
    conn = CrmConnection()
    conn.id = connection_id
    conn.workspace_id = workspace_id
    conn.client_id = None
    conn.provider = provider
    conn.status = status
    conn.credentials_encrypted = credentials_encrypted
    conn.sync_config = sync_config or {}
    return conn


@pytest.mark.asyncio
async def test_create_pending_stores_crm_connection():
    session = _FakeSession()
    auth = _make_auth()
    service = CrmConnectionService(session)

    with patch(
        "app.lead_intelligence.crm.service.build_auth_url",
        return_value="https://auth.url",
    ), patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ) as mock_perm:
        url = await service.create_pending(
            auth, 1, "hubspot", None, {"dedup_enabled": True}
        )

    assert url == "https://auth.url"
    assert len(session.added) == 1
    conn = session.added[0]
    assert isinstance(conn, CrmConnection)
    assert conn.provider == "hubspot"
    assert conn.status == "pending"
    mock_perm.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_pending_rejects_unknown_provider():
    session = _FakeSession()
    auth = _make_auth()
    service = CrmConnectionService(session)

    with pytest.raises(Exception) as exc, patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ):
        await service.create_pending(auth, 1, "unknown", None)

    assert "Unsupported" in str(exc.value)


@pytest.mark.asyncio
async def test_list_connections_filters_by_workspace():
    conn = _make_connection()
    session = _FakeSession(rows=[conn])
    auth = _make_auth()
    service = CrmConnectionService(session)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ) as mock_perm:
        results = await service.list_connections(auth, 1)

    assert len(results) == 1
    assert results[0].provider == "hubspot"
    mock_perm.assert_awaited_once_with(session, auth, 1, Permission.CRM_READ)


@pytest.mark.asyncio
async def test_disconnect_marks_connection_disconnected():
    conn = _make_connection()
    session = _FakeSession(scalar=conn)
    auth = _make_auth()
    service = CrmConnectionService(session)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ) as mock_perm:
        await service.disconnect(auth, 1, conn.id)

    assert conn.status == "disconnected"
    assert session.committed
    assert mock_perm.await_count == 2
    mock_perm.assert_any_await(session, auth, 1, Permission.CRM_READ)
    mock_perm.assert_any_await(session, auth, 1, Permission.CRM_DISCONNECT)


@pytest.mark.asyncio
async def test_dedup_lead_returns_success_log():
    conn = _make_connection(
        sync_config={"dedup_enabled": True},
        credentials_encrypted="ENCRYPTED{}",
    )
    lead = _make_lead(uuid4())
    session = _FakeSession()
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ) as mock_perm, patch(
        "app.lead_intelligence.crm.service.decrypt_credentials",
        return_value={"access_token": "token"},
    ), patch(
        "app.lead_intelligence.crm.service._provider_client",
        return_value=MagicMock(
            search_contacts=AsyncMock(return_value=MagicMock(contacts=[]))
        ),
    ):
        result = await service.dedup_lead(auth, 1, conn.id, lead.id)

    assert result.degraded is False
    assert result.sync_log is not None
    assert result.sync_log.status == "success"
    assert result.sync_log.entity_type == "lead"
    mock_perm.assert_awaited_once_with(session, auth, 1, Permission.CRM_SYNC)


@pytest.mark.asyncio
async def test_push_lead_skips_when_writeback_disabled():
    conn = _make_connection(sync_config={"writeback_enabled": False})
    lead = _make_lead(uuid4())
    session = _FakeSession()
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ) as mock_perm:
        result = await service.push_lead(auth, 1, conn.id, lead.id)

    assert result.degraded is False
    assert result.sync_log is None
    mock_perm.assert_awaited_once_with(session, auth, 1, Permission.CRM_WRITE)


@pytest.mark.asyncio
async def test_push_lead_creates_sync_log_when_writeback_enabled():
    conn = _make_connection(sync_config={"writeback_enabled": True})
    lead = _make_lead(uuid4())
    session = _FakeSession()
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ) as mock_perm, patch(
        "app.lead_intelligence.crm.service.decrypt_credentials",
        return_value={"access_token": "token"},
    ), patch(
        "app.lead_intelligence.crm.service._provider_client",
        return_value=MagicMock(
            create_lead=AsyncMock(return_value={"id": "123"})
        ),
    ), patch(
        "app.lead_intelligence.crm.service.MemoryRepository",
    ) as mock_repo:
        instance = mock_repo.return_value
        instance.create_memory = AsyncMock()
        result = await service.push_lead(auth, 1, conn.id, lead.id)

    assert result.degraded is False
    assert result.sync_log is not None
    assert result.sync_log.status == "success"
    assert result.sync_log.direction == "nowing_to_crm"
    assert session.flushed is True
    mock_perm.assert_awaited_once_with(session, auth, 1, Permission.CRM_WRITE)
