"""Mutation-focused tests to raise CRM service mutation score."""

from __future__ import annotations

import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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
    sync_config: Any = None,
    provider: str = "hubspot",
    credentials_encrypted: str = "ENCRYPTED{}",
) -> CrmConnection:
    conn = CrmConnection()
    conn.id = uuid4()
    conn.workspace_id = 1
    conn.client_id = None
    conn.provider = provider
    conn.status = status
    conn.credentials_encrypted = credentials_encrypted
    conn.sync_config = sync_config
    return conn


def _make_lead() -> Lead:
    lead = Lead()
    lead.id = uuid4()
    lead.workspace_id = 1
    lead.domain = "acme.com"
    lead.company_name = "Acme"
    return lead


@pytest.mark.asyncio
async def test_create_pending_preserves_sync_config():
    """Kills sync_config or/and mutation."""
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmConnectionService(session)

    with (
        patch(
            "app.lead_intelligence.crm.service.build_auth_url",
            return_value="https://auth.url",
        ),
        patch(
            "app.lead_intelligence.crm.service.check_permission",
            new=AsyncMock(),
        ),
    ):
        await service.create_pending(auth, 1, "hubspot", None, {"dedup_enabled": True})

    assert len(session.added) == 1
    conn = session.added[0]
    assert conn.sync_config == {"dedup_enabled": True}


@pytest.mark.asyncio
async def test_dedup_skips_when_writeback_default_is_false():
    """Kills ReplaceFalseWithTrue on writeback_enabled default."""
    conn = _make_connection(sync_config={})
    lead = _make_lead()
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    with patch(
        "app.lead_intelligence.crm.service.check_permission",
        new=AsyncMock(),
    ):
        result = await service.push_lead(auth, 1, conn.id, lead.id)

    assert result.degraded is False
    assert result.sync_log is None
    service._get_lead.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_lead_score_skips_when_writeback_default_is_false():
    """Kills ReplaceFalseWithTrue on writeback_enabled default."""
    conn = _make_connection(sync_config={})
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
async def test_load_sync_config_parses_json_string():
    """Kills AddNot on isinstance(sync_config, str)."""
    service = CrmSyncService(_QueueSession([]))
    loaded = service._load_sync_config('{"dedup_enabled": true}')
    assert loaded == {"dedup_enabled": True}


@pytest.mark.asyncio
async def test_push_lead_writes_context_memory_with_commit_false():
    """Kills ReplaceFalseWithTrue on commit=True."""
    conn = _make_connection(
        sync_config={"writeback_enabled": True},
        credentials_encrypted="ENCRYPTED{}",
    )
    lead = _make_lead()
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
            return_value=MagicMock(create_lead=AsyncMock()),
        ),
        patch(
            "app.lead_intelligence.crm.service.MemoryRepository",
        ) as mock_repo,
    ):
        instance = mock_repo.return_value
        instance.create_memory = AsyncMock()
        await service.push_lead(auth, 1, conn.id, lead.id)

    call_kwargs = instance.create_memory.await_args.kwargs
    assert call_kwargs["commit"] is False


@pytest.mark.asyncio
async def test_dedup_salesforce_provider():
    """Kills _provider_client comparison mutants for salesforce."""
    conn = _make_connection(
        provider="salesforce",
        sync_config={"dedup_enabled": True},
    )
    lead = _make_lead()
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    captured: list[Any] = []

    def capture_client(provider: str, credentials: Any):
        captured.append(provider)
        return MagicMock(search_contacts=AsyncMock(return_value=MagicMock(contacts=[])))

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
            side_effect=capture_client,
        ),
    ):
        await service.dedup_lead(auth, 1, conn.id, lead.id)

    assert captured == ["salesforce"]


@pytest.mark.asyncio
async def test_dedup_pipedrive_provider():
    """Kills _provider_client comparison mutants for pipedrive."""
    conn = _make_connection(
        provider="pipedrive",
        sync_config={"dedup_enabled": True},
    )
    lead = _make_lead()
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    captured: list[Any] = []

    def capture_client(provider: str, credentials: Any):
        captured.append(provider)
        return MagicMock(search_contacts=AsyncMock(return_value=MagicMock(contacts=[])))

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
            side_effect=capture_client,
        ),
    ):
        await service.dedup_lead(auth, 1, conn.id, lead.id)

    assert captured == ["pipedrive"]


@pytest.mark.asyncio
async def test_dedup_hubspot_provider():
    """Kills _provider_client comparison mutants for hubspot."""
    conn = _make_connection(
        provider="hubspot",
        sync_config={"dedup_enabled": True},
    )
    lead = _make_lead()
    session = _QueueSession([])
    auth = _make_auth()
    service = CrmSyncService(session)

    service._get_connection = AsyncMock(return_value=conn)
    service._get_lead = AsyncMock(return_value=lead)

    captured: list[Any] = []

    def capture_client(provider: str, credentials: Any):
        captured.append(provider)
        return MagicMock(search_contacts=AsyncMock(return_value=MagicMock(contacts=[])))

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
            side_effect=capture_client,
        ),
    ):
        await service.dedup_lead(auth, 1, conn.id, lead.id)

    assert captured == ["hubspot"]
