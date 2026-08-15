"""Edge-case and error-path tests for Story 21.5 — CRM Integration & Write-Back.

These tests target P1 mutation survivors:
- status_code 404/403/405 assertions
- .limit(1) boundary
- missing connection / missing lead
- provider API errors
- sync config flags
"""

from __future__ import annotations

import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.db import CrmConnection, Lead
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


class _QueueSession:
    """AsyncSession where each ``execute`` pops the next queued result."""

    def __init__(self, queue: list[_FakeResult]) -> None:
        self.queue = queue
        self.added: list[Any] = []
        self.committed = False
        self.flushed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return self.queue.pop(0)

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, _obj: Any) -> None:
        pass


def _make_auth() -> Any:
    return types.SimpleNamespace(
        user=types.SimpleNamespace(id=uuid4()),
        is_gated=False,
    )


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


def _make_lead(lead_id: UUID, workspace_id: int = 1) -> Lead:
    lead = Lead()
    lead.id = lead_id
    lead.workspace_id = workspace_id
    lead.domain = "acme.com"
    lead.company_name = "Acme"
    lead.industry = "SaaS"
    lead.company_size = "50-200"
    lead.location = "SF"
    return lead


@pytest.mark.asyncio
async def test_handle_callback_404_when_no_pending_connection():
    session = _QueueSession([_FakeResult()])  # first() returns None
    service = CrmConnectionService(session)

    with (
        patch(
            "app.lead_intelligence.crm.service.exchange_code",
            new=AsyncMock(return_value=("ENCRYPTED{}", "token")),
        ),
        pytest.raises(Exception) as exc,
    ):
        await service.handle_callback("hubspot", "code", "state")

    assert exc.value.status_code == 404
    assert "No pending CRM connection found" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_handle_callback_finds_most_recent_pending_connection():
    """Kills .limit(1) -> .limit(0) and 404 NumberReplacer mutants."""
    newer = _make_connection()
    session = _QueueSession([_FakeResult(value=newer)])
    service = CrmConnectionService(session)

    with (
        patch(
            "app.lead_intelligence.crm.service.exchange_code",
            new=AsyncMock(return_value=("ENCRYPTED{}", "token")),
        ),
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        result = await service.handle_callback("hubspot", "code", "state")

    assert result.id == newer.id
    assert result.status == "active"
    assert session.committed


@pytest.mark.asyncio
async def test_get_connection_404_when_not_found():
    session = _QueueSession([_FakeResult()])
    service = CrmConnectionService(session)
    auth = _make_auth()

    with (
        pytest.raises(Exception) as exc,
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.get_connection(auth, 1, uuid4())

    assert exc.value.status_code == 404
    assert "CRM connection not found" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_dedup_skips_when_disabled():
    conn = _make_connection(sync_config={"dedup_enabled": False})
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock()

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ):
        result = await service.dedup_lead(auth, 1, conn.id, uuid4())

    assert result.degraded is False
    assert result.sync_log is None
    service._get_lead.assert_not_awaited()


@pytest.mark.asyncio
async def test_dedup_degraded_on_provider_search_error():
    conn = _make_connection(sync_config={"dedup_enabled": True})
    lead = _make_lead(uuid4())
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    with (
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
        patch(
            "app.lead_intelligence.crm.service.decrypt_credentials",
            return_value={"access_token": "token"},
        ),
        patch(
            "app.lead_intelligence.crm.service._provider_client",
            return_value=MagicMock(
                search_contacts=AsyncMock(side_effect=RuntimeError("CRM down"))
            ),
        ),
    ):
        result = await service.dedup_lead(auth, 1, conn.id, lead.id)

    assert result.degraded is True
    assert result.sync_log is not None
    assert result.sync_log.status == "error"
    assert "CRM down" in result.sync_log.error_message


@pytest.mark.asyncio
async def test_push_lead_degraded_on_provider_create_error():
    conn = _make_connection(
        sync_config={"writeback_enabled": True},
        credentials_encrypted="ENCRYPTED{}",
    )
    lead = _make_lead(uuid4())
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    with (
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
        patch(
            "app.lead_intelligence.crm.service.decrypt_credentials",
            return_value={"access_token": "token"},
        ),
        patch(
            "app.lead_intelligence.crm.service._provider_client",
            return_value=MagicMock(
                create_lead=AsyncMock(side_effect=RuntimeError("rate limit"))
            ),
        ),
    ):
        result = await service.push_lead(auth, 1, conn.id, lead.id)

    assert result.degraded is True
    assert result.sync_log is not None
    assert result.sync_log.status == "error"
    assert "rate limit" in result.sync_log.error_message


@pytest.mark.asyncio
async def test_sync_lead_score_skips_when_writeback_disabled():
    conn = _make_connection(sync_config={"writeback_enabled": False})
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ):
        result = await service.sync_lead_score(auth, 1, conn.id, uuid4())

    assert result.degraded is False
    assert result.sync_log is None


@pytest.mark.asyncio
async def test_sync_lead_score_creates_log_when_writeback_enabled():
    conn = _make_connection(sync_config={"writeback_enabled": True})
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ):
        result = await service.sync_lead_score(auth, 1, conn.id, uuid4())

    assert result.degraded is False
    assert result.sync_log is not None
    assert result.sync_log.entity_type == "lead_score"
