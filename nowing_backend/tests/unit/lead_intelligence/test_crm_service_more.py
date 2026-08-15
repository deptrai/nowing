"""Additional unit tests to kill remaining P1 mutants for Story 21.5."""

from __future__ import annotations

import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db import CrmConnection, Lead
from app.lead_intelligence.crm.providers.base import CrmContact
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
    status: str = "active",
    sync_config: dict | None = None,
    credentials_encrypted: str = "ENCRYPTED{}",
) -> CrmConnection:
    conn = CrmConnection()
    conn.id = uuid4()
    conn.workspace_id = 1
    conn.client_id = None
    conn.provider = "hubspot"
    conn.status = status
    conn.credentials_encrypted = credentials_encrypted
    conn.sync_config = sync_config or {}
    return conn


def _make_lead() -> Lead:
    lead = Lead()
    lead.id = uuid4()
    lead.workspace_id = 1
    lead.domain = "acme.com"
    lead.company_name = "Acme"
    lead.industry = "SaaS"
    lead.company_size = "50-200"
    lead.location = "SF"
    return lead


@pytest.mark.asyncio
async def test_create_pending_rejects_unknown_provider_with_status_400():
    """Kills NumberReplacer on status_code=400."""
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmConnectionService(session)

    with (
        pytest.raises(Exception) as exc,
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.create_pending(auth, 1, "zoho", None)

    assert exc.value.status_code == 400
    assert "Unsupported" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_dedup_detects_duplicate_by_domain():
    """Kills ReplaceOrWithAnd on duplicate check (domain match, no email)."""
    conn = _make_connection(
        status="active",
        sync_config={"dedup_enabled": True},
    )
    lead = _make_lead()
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    matching_contact = CrmContact(
        crm_record_id="123",
        email=None,
        domain="acme.com",
        company_name="Acme",
        first_name=None,
        last_name=None,
        title=None,
        phone=None,
        owner_id=None,
    )

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
                search_contacts=AsyncMock(
                    return_value=MagicMock(contacts=[matching_contact], has_more=False)
                )
            ),
        ),
    ):
        result = await service.dedup_lead(auth, 1, conn.id, lead.id)

    assert result.degraded is False
    assert result.sync_log is not None
    assert result.sync_log.error_message == "duplicate_detected"


@pytest.mark.asyncio
async def test_dedup_connection_not_found_raises_404():
    """Kills NumberReplacer on _get_connection status_code=404."""
    session = _QueueSession([_FakeResult()])  # _get_connection returns None
    auth = _make_auth()
    service = CrmSyncService(session)

    with (
        pytest.raises(Exception) as exc,
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.dedup_lead(auth, 1, uuid4(), uuid4())

    assert exc.value.status_code == 404
    assert "CRM connection not found or not active" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_dedup_lead_not_found_raises_404():
    """Kills NumberReplacer on _get_lead status_code=404."""
    conn = _make_connection(status="active")
    session = _QueueSession([_FakeResult(value=conn), _FakeResult()])  # conn, then None
    auth = _make_auth()
    service = CrmSyncService(session)

    with (
        pytest.raises(Exception) as exc,
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.dedup_lead(auth, 1, conn.id, uuid4())

    assert exc.value.status_code == 404
    assert "Lead not found" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_push_lead_connection_not_found_raises_404():
    """Kills NumberReplacer on _get_connection status_code=404."""
    session = _QueueSession([_FakeResult()])
    auth = _make_auth()
    service = CrmSyncService(session)

    with (
        pytest.raises(Exception) as exc,
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.push_lead(auth, 1, uuid4(), uuid4())

    assert exc.value.status_code == 404
    assert "CRM connection not found or not active" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_push_lead_lead_not_found_raises_404():
    """Kills NumberReplacer on _get_lead status_code=404."""
    conn = _make_connection(
        status="active",
        sync_config={"writeback_enabled": True},
    )
    session = _QueueSession([_FakeResult(value=conn), _FakeResult()])
    auth = _make_auth()
    service = CrmSyncService(session)

    with (
        pytest.raises(Exception) as exc,
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.push_lead(auth, 1, conn.id, uuid4())

    assert exc.value.status_code == 404
    assert "Lead not found" in str(exc.value.detail)
