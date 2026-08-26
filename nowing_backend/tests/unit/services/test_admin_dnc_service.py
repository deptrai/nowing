"""Unit tests for AdminDncService (Story 25.6).

These tests mock the database and Redis session to run isolated without external services.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _load_service():
    try:
        from app.services.admin_dnc_service import AdminDncService

        return AdminDncService
    except ImportError as exc:
        pytest.fail(f"AdminDncService not implemented yet: {exc}")


@pytest.fixture
def service():
    service_cls = _load_service()
    session = AsyncMock()
    return service_cls(session)


@pytest.mark.asyncio
async def test_canonicalize_and_hash_phone(service) -> None:
    """AC-2: Phone numbers are normalized to E.164 and hashed via HMAC-SHA256."""
    raw_phone = " 0908 123 456 "
    canonical, hmac_hash, masked = service.canonicalize_and_hash(
        record_type="phone", value=raw_phone
    )
    assert canonical == "+84908123456"
    assert len(hmac_hash) == 64
    assert masked == "0908 *** 456" or "***" in masked


@pytest.mark.asyncio
async def test_canonicalize_and_hash_domain_and_email(service) -> None:
    """AC-2: Domain and Email are lowercased, stripped, and hashed deterministically."""
    raw_email = " TEST.User@Example.COM "
    canonical, hmac_hash, masked = service.canonicalize_and_hash(
        record_type="email", value=raw_email
    )
    assert canonical == "test.user@example.com"
    assert len(hmac_hash) == 64
    assert "@" in masked

    raw_domain = " WWW.SPAM-SITE.VN "
    canonical_d, hmac_hash_d, _ = service.canonicalize_and_hash(
        record_type="domain", value=raw_domain
    )
    assert canonical_d == "www.spam-site.vn"
    assert len(hmac_hash_d) == 64


@pytest.mark.asyncio
async def test_add_dnc_entry_writes_audit(service) -> None:
    """AC-2: Adding a new DNC entry writes a global_dnc.add AuditEvent."""
    # Simulate no existing record
    service.session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(first=AsyncMock(return_value=None))
            )
        )
    )
    service.session.add = MagicMock()
    service.session.flush = AsyncMock()

    admin_id = uuid.uuid4()
    entry = await service.add_global_dnc_record(
        record_type="phone",
        value="0912345678",
        reason="Customer opt-out request",
        source="admin_manual",
        actor_id=admin_id,
        ip_address="127.0.0.1",
        user_agent="AdminBrowser/1.0",
        endpoint="/api/v1/admin/dnc/global",
    )

    assert entry is not None
    assert service.session.add.call_count >= 2  # GlobalDncRecord + AuditEvent


@pytest.mark.asyncio
async def test_add_dnc_entry_updates_existing_writes_update_audit(service) -> None:
    """AC-2: Re-adding an existing DNC entry updates metadata and logs global_dnc.update."""
    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing.record_type = "phone"
    existing.value = "masked"
    existing.value_hmac = "existing_hmac"
    existing.reason = "Old reason"
    existing.source = "old_source"

    service.session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(first=AsyncMock(return_value=existing))
            )
        )
    )
    service.session.add = MagicMock()
    service.session.flush = AsyncMock()

    admin_id = uuid.uuid4()
    entry = await service.add_global_dnc_record(
        record_type="phone",
        value="0912345678",
        reason="Customer opt-out request",
        source="admin_manual",
        actor_id=admin_id,
        ip_address="127.0.0.1",
        user_agent="AdminBrowser/1.0",
        endpoint="/api/v1/admin/dnc/global",
    )

    assert entry is existing
    assert entry.reason == "Customer opt-out request"
    assert service.session.add.call_count >= 1  # AuditEvent only


@pytest.mark.asyncio
async def test_import_csv_parses_rows_and_returns_summary(service) -> None:
    """AC-2: Bulk CSV import parses, hashes, deduplicates, and returns import summary."""
    csv_content = (
        "record_type,value,reason\n"
        "phone,0901112233,DNC National Registry\n"
        "domain,bad-leads.com,Spam domain\n"
        "email,bot@spammer.net,Automated bot\n"
        "phone,invalid-phone,Bad format\n"
    )

    # Mock the bulk insert returning 3 inserted rows
    mock_result = MagicMock()
    mock_result.rowcount = 3
    service.session.execute = AsyncMock(return_value=mock_result)
    service.session.add = MagicMock()
    service.session.flush = AsyncMock()

    admin_id = uuid.uuid4()
    summary = await service.import_dnc_csv(
        csv_content=csv_content,
        actor_id=admin_id,
        ip_address="127.0.0.1",
        user_agent="AdminBrowser/1.0",
        endpoint="/api/v1/admin/dnc/global/import-csv",
    )

    assert summary["imported_count"] == 3
    assert summary["failed_count"] == 1
    assert len(summary["errors"]) == 1


@pytest.mark.asyncio
async def test_delete_dnc_entry_audits(service) -> None:
    """AC-2: Deleting DNC entry removes row and records an audit event."""
    record_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    # Mock DB find
    mock_record = MagicMock()
    mock_record.id = record_id
    mock_record.record_type = "phone"
    mock_record.value_hmac = "hash123"
    service.session.get = AsyncMock(return_value=mock_record)
    service.session.delete = AsyncMock()
    service.session.add = MagicMock()
    service.session.flush = AsyncMock()

    deleted = await service.delete_global_dnc_record(
        record_id=record_id,
        actor_id=admin_id,
        ip_address="127.0.0.1",
        user_agent="AdminBrowser/1.0",
        endpoint=f"/api/v1/admin/dnc/global/{record_id}",
    )

    assert deleted is True
    service.session.delete.assert_awaited_once_with(mock_record)
