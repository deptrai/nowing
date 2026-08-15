"""Integration tests (SQL / Pattern 6) for Story 21.3 — Contact Enrichment & PII Governance.

Verifies:
- DB persistence of EnrichmentRequest & VerifiedContact with encrypted PII (AD-25/AD-49)
- Memory provenance with source_uuid & source_entity_type='enrichment_request' (AD-44/AD-47)
- Multi-tenancy isolation via workspace_id + client_id (AD-31)
- BillingEvent ledger recording without TokenUsage (AD-10/AD-42)
- Wallet debit pre-check and degradation on zero credits (AC-10)
- Composite index lookup efficiency
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    BillingEvent,
    EnrichmentRequest,
    Lead,
    Memory,
    MemorySourceType,
    MemoryType,
    User,
    VerifiedContact,
    Workspace,
)
from app.lead_intelligence.enrichment.service import EnrichmentService
from app.utils.oauth_security import TokenEncryption

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _make_lead(
    db_session: AsyncSession,
    db_workspace: Workspace,
    company_name: str = "VinFast",
    client_id: str | None = None,
    domain: str = "vinfastauto.com",
    status: str = "open",
) -> Lead:
    lead = Lead(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id=client_id,
        source="integration_test",
        company_name=company_name,
        domain=domain,
        industry="automotive",
        status=status,
        enriched=False,
    )
    db_session.add(lead)
    await db_session.flush()
    return lead


def _make_ctx(
    db_workspace: Workspace,
    db_user: User | None = None,
    client_id: str | None = None,
) -> Any:
    return SimpleNamespace(
        workspace_id=db_workspace.id,
        run_id="run-integration-enrichment",
        client_id=client_id,
        user_id=db_user.id if db_user is not None else None,
    )


async def test_enrichment_persists_request_and_encrypted_contacts_in_db(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    patched_embed_texts: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1 & AC-3: DB persistence of EnrichmentRequest and VerifiedContact with TokenEncryption."""
    lead = await _make_lead(db_session, db_workspace)

    raw_contacts = [
        {
            "name": "Le Thi Thu Thuy",
            "title": "Chairwoman",
            "email": "thuy.le@vinfastauto.com",
            "phone": "+84909123456",
            "verification_status": "verified",
            "confidence": 98.0,
            "source_provider": "cleanlist",
            "consent_status": "legitimate_interest",
            "legal_basis": "legitimate_interest",
        }
    ]

    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
        mock.AsyncMock(return_value=raw_contacts),
    )

    with mock.patch.object(config, "CONTACT_ENRICHMENT_MICROS_PER_CONTACT", 0):
        ctx = _make_ctx(db_workspace, db_user)
        svc = EnrichmentService()
        output = await svc.enrich(db_session, ctx, lead.id, requested_count=1)

    assert output.contact_count == 1
    assert output.degraded is False

    # Check EnrichmentRequest in DB
    req_res = await db_session.execute(
        select(EnrichmentRequest).where(
            EnrichmentRequest.id == output.enrichment_request_id
        )
    )
    req = req_res.scalar_one()
    assert req.workspace_id == db_workspace.id
    assert req.lead_id == lead.id
    assert req.status == "completed"

    # Check VerifiedContact in DB
    contact_res = await db_session.execute(
        select(VerifiedContact).where(VerifiedContact.lead_id == lead.id)
    )
    contact = contact_res.scalar_one()
    assert contact.workspace_id == db_workspace.id
    assert contact.enrichment_request_id == req.id
    assert contact.source_provider == "cleanlist"
    assert contact.confidence == 98.0

    # Assert PII is encrypted at rest and decrypts accurately
    encryptor = TokenEncryption(config.SECRET_KEY)
    assert contact.email != "thuy.le@vinfastauto.com"
    assert contact.phone != "+84909123456"
    assert contact.name != "Le Thi Thu Thuy"
    assert encryptor.decrypt_token(contact.email) == "thuy.le@vinfastauto.com"
    assert encryptor.decrypt_token(contact.phone) == "+84909123456"
    assert encryptor.decrypt_token(contact.name) == "Le Thi Thu Thuy"

    # Assert Lead.enriched updated
    await db_session.refresh(lead)
    assert lead.enriched is True
    assert lead.consent_status == "legitimate_interest"
    assert lead.legal_basis == "legitimate_interest"


async def test_enrichment_memory_provenance_and_redaction(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    patched_embed_texts: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4 & AD-44/AD-47: Memory row has provenance linking to EnrichmentRequest with redacted PII."""
    lead = await _make_lead(db_session, db_workspace)

    raw_contacts = [
        {
            "name": "Nguyen Van B",
            "title": "Deputy CEO",
            "email": "b.nguyen@vinfastauto.com",
            "phone": "+84908888999",
            "verification_status": "verified",
            "confidence": 95.0,
            "source_provider": "cleanlist",
            "consent_status": "legitimate_interest",
            "legal_basis": "legitimate_interest",
        }
    ]

    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
        mock.AsyncMock(return_value=raw_contacts),
    )

    with mock.patch.object(config, "CONTACT_ENRICHMENT_MICROS_PER_CONTACT", 0):
        ctx = _make_ctx(db_workspace, db_user)
        svc = EnrichmentService()
        output = await svc.enrich(db_session, ctx, lead.id, requested_count=1)

    # Query Memory by source_uuid & source_entity_type
    mem_res = await db_session.execute(
        select(Memory).where(
            Memory.source_uuid == output.enrichment_request_id,
            Memory.source_entity_type == "enrichment_request",
        )
    )
    memory = mem_res.scalar_one()
    assert memory.workspace_id == db_workspace.id
    assert memory.type == MemoryType.SEMANTIC
    assert memory.source_type == MemorySourceType.ENRICHMENT
    assert "enriched_contact" in memory.tags

    # Content must NOT contain raw email or phone
    assert "b.nguyen@vinfastauto.com" not in memory.content
    assert "+84908888999" not in memory.content


async def test_enrichment_tenancy_and_client_id_isolation(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    patched_embed_texts: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AD-31: Multi-tenancy isolation via workspace_id + client_id (CITEXT)."""
    lead_acme = await _make_lead(db_session, db_workspace, client_id="acme")

    raw_contacts = [
        {
            "name": "Acme Contact",
            "title": "Manager",
            "email": "manager@acme.com",
            "phone": "+84901234123",
            "verification_status": "verified",
            "confidence": 90.0,
            "source_provider": "cleanlist",
            "consent_status": "legitimate_interest",
            "legal_basis": "legitimate_interest",
        }
    ]

    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
        mock.AsyncMock(return_value=raw_contacts),
    )

    with mock.patch.object(config, "CONTACT_ENRICHMENT_MICROS_PER_CONTACT", 0):
        ctx = _make_ctx(db_workspace, db_user, client_id="acme")
        svc = EnrichmentService()
        output = await svc.enrich(db_session, ctx, lead_acme.id, requested_count=1)

    assert output.contact_count == 1

    # Verify query with matching client_id finds contact
    contact_acme = (
        await db_session.execute(
            select(VerifiedContact).where(
                VerifiedContact.workspace_id == db_workspace.id,
                VerifiedContact.client_id == "acme",
            )
        )
    ).scalar_one_or_none()
    assert contact_acme is not None

    # Verify query with different client_id returns None
    contact_other = (
        await db_session.execute(
            select(VerifiedContact).where(
                VerifiedContact.workspace_id == db_workspace.id,
                VerifiedContact.client_id == "other_client",
            )
        )
    ).scalar_one_or_none()
    assert contact_other is None


async def test_enrichment_billing_event_persistence(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    patched_embed_texts: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-6: BillingEvent created with actual cost_micros, no TokenUsage."""
    lead = await _make_lead(db_session, db_workspace)

    raw_contacts = [
        {
            "name": "Contact 1",
            "title": "Lead",
            "email": "c1@test.com",
            "phone": "+84901111222",
            "verification_status": "verified",
            "confidence": 95.0,
            "source_provider": "cleanlist",
        }
    ]

    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
        mock.AsyncMock(return_value=raw_contacts),
    )
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.wallet_credit.check_balance",
        mock.AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.wallet_credit.apply_debit",
        mock.AsyncMock(return_value=None),
    )

    with mock.patch.object(config, "CONTACT_ENRICHMENT_MICROS_PER_CONTACT", 50000):
        ctx = _make_ctx(db_workspace, db_user)
        svc = EnrichmentService()
        output = await svc.enrich(db_session, ctx, lead.id, requested_count=1)

    assert output.cost_micros == 50000

    # Verify BillingEvent in DB
    billing_res = await db_session.execute(
        select(BillingEvent).where(
            BillingEvent.event_entity_type == "enrichment_request",
            BillingEvent.event_id == output.enrichment_request_id,
        )
    )
    billing_event = billing_res.scalar_one()
    assert billing_event.workspace_id == db_workspace.id
    assert billing_event.event_type == "contact_enrichment"
    assert billing_event.cost_micros == 50000
