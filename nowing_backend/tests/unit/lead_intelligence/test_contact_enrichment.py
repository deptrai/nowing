"""Red-phase ATDD acceptance tests for Story 21.3 — Contact Enrichment & PII Governance.

These tests specify and verify the contracts for:
- AC-1: EnrichmentRequest creation (status=pending, 202 Accepted, Celery dispatch)
- AC-2: Waterfall verification (Cleanlist -> BetterContact -> FallbackVerifier MX/regex)
- AC-3: VerifiedContact persistence with PII encryption via TokenEncryption, Lead.enriched=True
- AC-4: Redaction of raw PII via redact_pii(..., context="lead_enrichment") and Memory provenance
- AC-5: 30-day Redis cache key (enrichment:v1:{workspace_id}:{client_id}:{lead_id})
- AC-6: BillingEvent recording (no TokenUsage, billing_unit=None, pre-check wallet debit)
- AC-7: Consent & legal basis fields preservation (no fabricated defaults)
- AC-8: REST endpoints (POST /enrich, POST /bulk, GET /enrichments, GET /contacts, GET /cost)
- AC-10: Degradation handling (insufficient_wallet, provider_unavailable, lead_not_found)

All DB/session interaction is mocked in unit tests; no real PostgreSQL/Redis required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def _uuid() -> UUID:
    return uuid4()


class _FakeWorkspace:
    """Minimal workspace stand-in for unit tests."""

    def __init__(self, *, workspace_id: int = 1, user_id: UUID | None = None) -> None:
        self.id = workspace_id
        self.user_id = user_id or _uuid()


class _FakeLead:
    """Minimal lead stand-in for unit tests."""

    def __init__(
        self,
        *,
        lead_id: UUID | None = None,
        workspace_id: int = 1,
        client_id: str | None = None,
        company_name: str = "VinGroup",
        domain: str = "vingroup.net",
        industry: str | None = "conglomerate",
        status: str = "open",
        enriched: bool = False,
        consent_status: str | None = None,
        legal_basis: str | None = None,
    ) -> None:
        self.id = lead_id or _uuid()
        self.workspace_id = workspace_id
        self.client_id = client_id
        self.company_name = company_name
        self.domain = domain
        self.industry = industry
        self.status = status
        self.enriched = enriched
        self.consent_status = consent_status
        self.legal_basis = legal_basis


class _FakeResult:
    """Return value for FakeSession.execute supporting SQLAlchemy-style result helpers."""

    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        if self._value is not None:
            return self._value
        if self._rows:
            return self._rows[0]
        raise ValueError("No rows found")

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """In-memory stand-in for AsyncSession so unit tests avoid Postgres."""

    def __init__(
        self,
        *,
        scalar: Any = None,
        rows: list[Any] | None = None,
        workspace: _FakeWorkspace | None = None,
        lead: _FakeLead | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self._scalar = scalar
        self._rows = rows or []
        self._workspace = workspace
        self._lead = lead

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def get(self, model: Any, id: Any) -> Any:
        if (
            self._workspace is not None
            and getattr(model, "__name__", "") == "Workspace"
        ):
            return self._workspace
        if self._lead is not None and getattr(model, "__name__", "") == "Lead":
            return self._lead
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, _obj: Any) -> None:
        pass

    async def flush(self) -> None:
        self.flushed = True


def _make_context(
    session: _FakeSession | None = None,
    workspace_id: int = 1,
    client_id: str | None = None,
    user_id: UUID | None = None,
) -> Any:
    """Minimal CapabilityContext for contact enrichment tests."""
    from app.capabilities.core.types import CapabilityContext

    return CapabilityContext(
        session=session or _FakeSession(),
        workspace_id=workspace_id,
        run_id="run-contact-enrichment-test",
        client_id=client_id,
        user_id=user_id or _uuid(),
    )


# ============================================================================
# Schemas Contract Tests (AC-1, AC-3, AC-8, AC-9, AC-10)
# ============================================================================


class TestEnrichmentSchemas:
    """Validate Pydantic schema contracts for Story 21.3."""

    def test_enrichment_input_single_and_bulk_fields(self) -> None:
        from app.lead_intelligence.enrichment.schemas import EnrichmentInput

        single = EnrichmentInput(lead_id=_uuid(), requested_count=3)
        assert single.requested_count == 3
        assert single.lead_ids is None

        bulk = EnrichmentInput(lead_ids=[_uuid(), _uuid()], requested_count=5)
        assert bulk.lead_id is None
        assert len(bulk.lead_ids) == 2

    def test_enrichment_output_exact_contract_fields(self) -> None:
        from app.lead_intelligence.enrichment.schemas import EnrichmentOutput

        req_id = _uuid()
        lead_id = _uuid()
        contact_id = _uuid()

        out = EnrichmentOutput(
            enrichment_request_id=req_id,
            lead_id=lead_id,
            contact_count=1,
            cost_micros=50000,
            verified_contact_ids=[contact_id],
            degraded=False,
            degradation_reasons=None,
        )
        assert out.enrichment_request_id == req_id
        assert out.contact_count == 1
        assert out.cost_micros == 50000
        assert out.degraded is False

    def test_verified_contact_read_schema_attributes(self) -> None:
        from app.lead_intelligence.enrichment.schemas import VerifiedContactRead

        cid = _uuid()
        now = datetime.now(UTC)
        contact = VerifiedContactRead(
            id=cid,
            name="Pham Nhat Vuong",
            title="Chairman",
            email="vuong@vingroup.net",
            phone="+84901234567",
            verification_status="verified",
            confidence=95.5,
            source_provider="cleanlist",
            consent_status="legitimate_interest",
            legal_basis="legitimate_interest",
            created_at=now,
        )
        assert contact.id == cid
        assert contact.email == "vuong@vingroup.net"
        assert contact.confidence == 95.5
        assert contact.source_provider == "cleanlist"

    def test_enrichment_request_read_schema_attributes(self) -> None:
        from app.lead_intelligence.enrichment.schemas import EnrichmentRequestRead

        rid = _uuid()
        lid = _uuid()
        now = datetime.now(UTC)
        req = EnrichmentRequestRead(
            id=rid,
            lead_id=lid,
            status="pending",
            contact_count=0,
            cost_micros=0,
            created_at=now,
        )
        assert req.id == rid
        assert req.status == "pending"

    def test_enrichment_cost_output_schema(self) -> None:
        from app.lead_intelligence.enrichment.schemas import EnrichmentCostOutput

        cost_out = EnrichmentCostOutput(
            cost_per_contact_micros=50000,
            estimated_cost_micros=250000,
            lead_count=5,
        )
        assert cost_out.cost_per_contact_micros == 50000
        assert cost_out.estimated_cost_micros == 250000
        assert cost_out.lead_count == 5


# ============================================================================
# AC-1 & AC-3: Service Core, Persistence, Encryption, Lead.enriched
# ============================================================================


class TestEnrichmentServiceCore:
    """AC-1 & AC-3: Request enrichment, persist verified contacts, encrypt PII."""

    async def test_request_enrichment_creates_pending_request_and_enqueues_celery(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.schemas import EnrichmentInput
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        ctx = _make_context(session, workspace_id=lead.workspace_id)

        task_mock = MagicMock()
        task_mock.delay = MagicMock()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.enrich_lead_task",
            task_mock,
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.check_balance",
            AsyncMock(return_value=None),
            raising=False,
        )

        svc = EnrichmentService()
        output = await svc.request_enrichment(
            session=session,
            ctx=ctx,
            inp=EnrichmentInput(lead_id=lead.id, requested_count=3),
        )

        assert output.status == "pending"
        assert output.lead_id == lead.id
        task_mock.delay.assert_called_once()

    async def test_enrich_persists_verified_contacts_with_pii_encryption(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import config
        from app.lead_intelligence.enrichment.service import EnrichmentService
        from app.utils.oauth_security import TokenEncryption

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        ctx = _make_context(session)

        raw_contacts = [
            {
                "name": "Nguyen Van A",
                "title": "CTO",
                "email": "a.nguyen@vingroup.net",
                "phone": "+84912345678",
                "verification_status": "verified",
                "confidence": 98.0,
                "source_provider": "cleanlist",
                "consent_status": "legitimate_interest",
                "legal_basis": "legitimate_interest",
            }
        ]

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            AsyncMock(return_value=raw_contacts),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            AsyncMock(return_value=None),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.apply_debit",
            AsyncMock(return_value=None),
            raising=False,
        )

        svc = EnrichmentService()
        output = await svc.enrich(
            session=session, ctx=ctx, lead_id=lead.id, requested_count=1
        )

        assert output.contact_count == 1
        assert len(output.verified_contact_ids) == 1

        # Check persisted VerifiedContact has encrypted PII
        encryptor = TokenEncryption(config.SECRET_KEY)
        added_contact = next(
            (
                o
                for o in session.added
                if getattr(o, "__tablename__", "") == "verified_contacts"
            ),
            None,
        )
        assert added_contact is not None
        assert added_contact.email != "a.nguyen@vingroup.net"  # Must be encrypted
        assert encryptor.decrypt_token(added_contact.email) == "a.nguyen@vingroup.net"
        assert encryptor.decrypt_token(added_contact.name) == "Nguyen Van A"
        assert encryptor.decrypt_token(added_contact.phone) == "+84912345678"

    async def test_enrich_updates_lead_enriched_flag_and_caches_consent_legal_basis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        assert lead.enriched is False
        session = _FakeSession(lead=lead)
        ctx = _make_context(session)

        raw_contacts = [
            {
                "name": "Le Thi B",
                "title": "Head of Procurement",
                "email": "b.le@vingroup.net",
                "phone": "+84987654321",
                "verification_status": "verified",
                "confidence": 90.0,
                "source_provider": "bettercontact",
                "consent_status": "explicit",
                "legal_basis": "consent",
            }
        ]

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            AsyncMock(return_value=raw_contacts),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            AsyncMock(return_value=None),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.apply_debit",
            AsyncMock(return_value=None),
            raising=False,
        )

        svc = EnrichmentService()
        await svc.enrich(session=session, ctx=ctx, lead_id=lead.id, requested_count=1)

        assert lead.enriched is True
        assert lead.consent_status == "explicit"
        assert lead.legal_basis == "consent"


# ============================================================================
# AC-2: Waterfall Verification (Cleanlist -> BetterContact -> FallbackVerifier)
# ============================================================================


class TestWaterfallVerification:
    """AC-2: Waterfall verification across cleanlist, bettercontact, and fallback."""

    async def test_waterfall_uses_primary_cleanlist_when_successful(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.providers import (
            CleanlistClient,
            WaterfallCoordinator,
        )

        lead = _FakeLead()
        cleanlist_contacts = [
            {
                "name": "Tran C",
                "title": "Director",
                "email": "c.tran@vingroup.net",
                "phone": "+84900000001",
                "verification_status": "verified",
                "confidence": 95.0,
                "source_provider": "cleanlist",
                "consent_status": "legitimate_interest",
                "legal_basis": "legitimate_interest",
            }
        ]

        cleanlist_mock = MagicMock(spec=CleanlistClient)
        cleanlist_mock.find_contacts = AsyncMock(return_value=cleanlist_contacts)

        bettercontact_mock = MagicMock()
        bettercontact_mock.find_contacts = AsyncMock()

        coordinator = WaterfallCoordinator(
            primary_provider=cleanlist_mock,
            secondary_provider=bettercontact_mock,
        )
        results = await coordinator.verify_lead(lead, requested_count=1)

        assert len(results) == 1
        assert results[0]["source_provider"] == "cleanlist"
        cleanlist_mock.find_contacts.assert_awaited_once()
        bettercontact_mock.find_contacts.assert_not_awaited()

    async def test_waterfall_falls_back_to_secondary_on_primary_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.providers import WaterfallCoordinator

        lead = _FakeLead()
        bettercontact_contacts = [
            {
                "name": "Pham D",
                "title": "VP Engineering",
                "email": "d.pham@vingroup.net",
                "phone": "+84900000002",
                "verification_status": "verified",
                "confidence": 92.0,
                "source_provider": "bettercontact",
                "consent_status": "legitimate_interest",
                "legal_basis": "legitimate_interest",
            }
        ]

        primary_mock = MagicMock()
        primary_mock.find_contacts = AsyncMock(
            side_effect=RuntimeError("500 Server Error")
        )

        secondary_mock = MagicMock()
        secondary_mock.find_contacts = AsyncMock(return_value=bettercontact_contacts)

        coordinator = WaterfallCoordinator(
            primary_provider=primary_mock,
            secondary_provider=secondary_mock,
        )
        results = await coordinator.verify_lead(lead, requested_count=1)

        assert len(results) == 1
        assert results[0]["source_provider"] == "bettercontact"
        secondary_mock.find_contacts.assert_awaited_once()

    async def test_waterfall_falls_back_to_mx_and_regex_verifier_when_all_external_fail(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.fallback import FallbackVerifier
        from app.lead_intelligence.enrichment.providers import WaterfallCoordinator

        lead = _FakeLead(domain="vingroup.net")

        primary_mock = MagicMock()
        primary_mock.find_contacts = AsyncMock(return_value=[])

        secondary_mock = MagicMock()
        secondary_mock.find_contacts = AsyncMock(side_effect=TimeoutError("Timeout"))

        fallback_verifier = FallbackVerifier()
        monkeypatch.setattr(
            fallback_verifier,
            "verify_domain_mx",
            AsyncMock(return_value=True),
        )

        coordinator = WaterfallCoordinator(
            primary_provider=primary_mock,
            secondary_provider=secondary_mock,
            fallback_verifier=fallback_verifier,
        )
        results = await coordinator.verify_lead(lead, requested_count=1)

        assert len(results) >= 1
        assert results[0]["source_provider"] == "fallback"
        assert results[0]["verification_status"] == "low_confidence"

    def test_fallback_verifier_email_and_phone_validation(self) -> None:
        from app.lead_intelligence.enrichment.fallback import FallbackVerifier

        verifier = FallbackVerifier()
        assert verifier.validate_email_syntax("user@domain.com") is True
        assert verifier.validate_email_syntax("invalid-email") is False
        assert verifier.validate_phone_format("+84912345678") is True
        assert verifier.validate_phone_format("not-a-phone") is False


# ============================================================================
# AC-4: Redaction for Memory & Provenance (AD-44/AD-47)
# ============================================================================


class TestEnrichmentMemoryProvenance:
    """AC-4: Redaction of raw PII and Memory row with provenance."""

    async def test_memory_created_with_redacted_pii_and_correct_provenance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.db import MemorySourceType, MemoryType
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        ctx = _make_context(session)

        raw_contacts = [
            {
                "name": "Hoang Van E",
                "title": "Chief Architect",
                "email": "e.hoang@vingroup.net",
                "phone": "+84903333444",
                "verification_status": "verified",
                "confidence": 99.0,
                "source_provider": "cleanlist",
                "consent_status": "legitimate_interest",
                "legal_basis": "legitimate_interest",
            }
        ]

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            AsyncMock(return_value=raw_contacts),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            AsyncMock(return_value=None),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.apply_debit",
            AsyncMock(return_value=None),
            raising=False,
        )

        created_memory_kwargs: dict[str, Any] = {}

        async def _fake_create_memory(repo_session: Any, **kwargs: Any) -> Any:
            created_memory_kwargs.update(kwargs)
            return SimpleNamespace(id=1, **kwargs)

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.MemoryRepository.create_memory",
            _fake_create_memory,
            raising=False,
        )

        svc = EnrichmentService()
        output = await svc.enrich(
            session=session, ctx=ctx, lead_id=lead.id, requested_count=1
        )

        assert output.enrichment_request_id is not None
        assert created_memory_kwargs.get("type") in {MemoryType.SEMANTIC, "semantic"}
        assert (
            created_memory_kwargs.get("source_type") == MemorySourceType.ENRICHMENT
            or str(created_memory_kwargs.get("source_type")) == "enrichment"
        )
        assert created_memory_kwargs.get("source_uuid") == output.enrichment_request_id
        assert created_memory_kwargs.get("source_entity_type") == "enrichment_request"
        assert "enriched_contact" in created_memory_kwargs.get("tags", [])

        # Content must be redacted JSON (not raw email/phone/name)
        content_str = str(created_memory_kwargs.get("content", ""))
        assert "e.hoang@vingroup.net" not in content_str
        assert "+84903333444" not in content_str
        assert (
            "<EMAIL>" in content_str
            or "<PHONE>" in content_str
            or "<NAME>" in content_str
        )


# ============================================================================
# AC-5: 30-Day Redis Cache (enrichment:v1:{workspace_id}:{client_id}:{lead_id})
# ============================================================================


class TestEnrichmentCache:
    """AC-5: 30-day cache in Redis skips API and billing."""

    async def test_cache_hit_returns_existing_contacts_without_api_or_billing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        ctx = _make_context(session, workspace_id=lead.workspace_id, client_id="acme")

        cached_contact_ids = [_uuid(), _uuid()]

        fake_redis = MagicMock()
        fake_redis.get = AsyncMock(
            return_value=",".join(str(cid) for cid in cached_contact_ids).encode()
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.get_redis_client",
            AsyncMock(return_value=fake_redis),
            raising=False,
        )

        waterfall_mock = AsyncMock()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            waterfall_mock,
            raising=False,
        )
        billing_mock = AsyncMock()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            billing_mock,
            raising=False,
        )

        svc = EnrichmentService()
        output = await svc.enrich(session=session, ctx=ctx, lead_id=lead.id)

        assert output.contact_count == 2
        assert output.cost_micros == 0  # Cache hit is free
        assert output.verified_contact_ids == cached_contact_ids
        waterfall_mock.assert_not_awaited()
        billing_mock.assert_not_awaited()

    async def test_cache_miss_writes_redis_with_30_day_ttl(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        ctx = _make_context(session, workspace_id=1, client_id="default")

        fake_redis = MagicMock()
        fake_redis.get = AsyncMock(return_value=None)
        fake_redis.set = AsyncMock()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.get_redis_client",
            AsyncMock(return_value=fake_redis),
            raising=False,
        )

        raw_contacts = [
            {
                "name": "Vu F",
                "title": "VP",
                "email": "f.vu@vingroup.net",
                "phone": "+84904444555",
                "verification_status": "verified",
                "confidence": 95.0,
                "source_provider": "cleanlist",
                "consent_status": "legitimate_interest",
                "legal_basis": "legitimate_interest",
            }
        ]
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            AsyncMock(return_value=raw_contacts),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            AsyncMock(return_value=None),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.apply_debit",
            AsyncMock(return_value=None),
            raising=False,
        )

        svc = EnrichmentService()
        output = await svc.enrich(session=session, ctx=ctx, lead_id=lead.id)

        assert output.contact_count == 1
        fake_redis.set.assert_awaited_once()
        args, kwargs = fake_redis.set.call_args
        assert f"enrichment:v1:{lead.workspace_id}:default:{lead.id}" in args[0]
        # 30 days = 2592000 seconds
        assert kwargs.get("ex") == 2592000 or args[2] == 2592000


# ============================================================================
# AC-6: Billing via BillingEvent (No TokenUsage, Pre-check debit)
# ============================================================================


class TestEnrichmentBilling:
    """AC-6: Billing via BillingEventService with cost_micros, no TokenUsage."""

    async def test_billing_event_recorded_with_exact_attributes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService
        from app.services.billing_event_service import BillingEventService

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        user_id = _uuid()
        ctx = _make_context(session, user_id=user_id)

        raw_contacts = [
            {
                "name": "Contact 1",
                "title": "Lead",
                "email": "c1@vingroup.net",
                "phone": "+84901111111",
                "verification_status": "verified",
                "confidence": 95.0,
                "source_provider": "cleanlist",
            },
            {
                "name": "Contact 2",
                "title": "Lead",
                "email": "c2@vingroup.net",
                "phone": "+84902222222",
                "verification_status": "verified",
                "confidence": 95.0,
                "source_provider": "cleanlist",
            },
        ]
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            AsyncMock(return_value=raw_contacts),
            raising=False,
        )

        record_billing_mock = AsyncMock()
        monkeypatch.setattr(
            BillingEventService,
            "record_contact_enrichment",
            record_billing_mock,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.check_balance",
            AsyncMock(return_value=None),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.apply_debit",
            AsyncMock(return_value=None),
            raising=False,
        )

        with patch("app.config.config.CONTACT_ENRICHMENT_MICROS_PER_CONTACT", 50000):
            svc = EnrichmentService()
            output = await svc.enrich(
                session=session, ctx=ctx, lead_id=lead.id, requested_count=2
            )

        assert output.cost_micros == 100000  # 2 contacts * 50,000
        record_billing_mock.assert_awaited_once()
        _, kwargs = record_billing_mock.call_args
        assert kwargs["cost_micros"] == 100000
        assert kwargs["workspace_id"] == lead.workspace_id
        assert kwargs["enrichment_request_id"] == output.enrichment_request_id

    async def test_wallet_balance_prechecked_before_external_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService
        from app.services.wallet_credit import InsufficientCreditsError

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        ctx = _make_context(session)

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.check_balance",
            AsyncMock(side_effect=InsufficientCreditsError("Wallet empty")),
            raising=False,
        )
        waterfall_mock = AsyncMock()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            waterfall_mock,
            raising=False,
        )

        with patch("app.config.config.CONTACT_ENRICHMENT_MICROS_PER_CONTACT", 50000):
            svc = EnrichmentService()
            output = await svc.enrich(
                session=session, ctx=ctx, lead_id=lead.id, requested_count=5
            )

        assert output.degraded is True
        assert output.degradation_reasons == ["insufficient_wallet"]
        waterfall_mock.assert_not_awaited()


# ============================================================================
# AC-7: Consent & Legal Basis Preservation (No Fabricated Defaults)
# ============================================================================


class TestConsentAndLegalBasis:
    """AC-7: Consent & legal basis gates and preservation."""

    async def test_missing_consent_or_legal_basis_not_defaulted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        ctx = _make_context(session)

        raw_contacts = [
            {
                "name": "Do G",
                "title": "Engineer",
                "email": "g.do@vingroup.net",
                "phone": "+84905555666",
                "verification_status": "verified",
                "confidence": 85.0,
                "source_provider": "cleanlist",
                "consent_status": None,  # Provider did not provide consent
                "legal_basis": None,
            }
        ]

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            AsyncMock(return_value=raw_contacts),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            AsyncMock(return_value=None),
            raising=False,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.apply_debit",
            AsyncMock(return_value=None),
            raising=False,
        )

        svc = EnrichmentService()
        await svc.enrich(session=session, ctx=ctx, lead_id=lead.id, requested_count=1)

        added_contact = next(
            (
                o
                for o in session.added
                if getattr(o, "__tablename__", "") == "verified_contacts"
            ),
            None,
        )
        assert added_contact is not None
        assert added_contact.consent_status is None
        assert added_contact.legal_basis is None


# ============================================================================
# AC-8: REST API Endpoints End-to-End Routing
# ============================================================================


class TestEnrichmentRoutes:
    """AC-8: REST endpoint behaviors, status codes, and query contracts."""

    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        import app.routes.enrichment_routes as enrichment_routes
        from app.auth.context import AuthContext
        from app.db import get_async_session
        from app.routes.enrichment_routes import router
        from app.users import get_auth_context

        async def _fake_require_workspace_member(*_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(id=1, user_id=_uuid(), role="owner")

        monkeypatch.setattr(
            enrichment_routes,
            "require_workspace_member",
            _fake_require_workspace_member,
            raising=False,
        )

        fake_session = _FakeSession()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_async_session] = lambda: fake_session
        app.dependency_overrides[get_auth_context] = lambda: AuthContext.session(
            SimpleNamespace(id=_uuid(), is_active=True)
        )

        return TestClient(app)

    def test_post_enrich_lead_returns_202_accepted(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lid = _uuid()
        req_id = _uuid()
        fake_req_read = {
            "id": str(req_id),
            "lead_id": str(lid),
            "status": "pending",
            "contact_count": 0,
            "cost_micros": 0,
            "created_at": datetime.now(UTC).isoformat(),
        }

        async def _fake_request_enrichment(*_args: Any, **_kwargs: Any) -> Any:
            return fake_req_read

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService.request_enrichment",
            _fake_request_enrichment,
            raising=False,
        )

        response = client.post(
            f"/workspaces/1/leads/{lid}/enrich",
            json={"requested_count": 3},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["id"] == str(req_id)
        assert body["status"] == "pending"

    def test_post_bulk_enrich_returns_list_of_requests(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lid1 = _uuid()
        lid2 = _uuid()

        async def _fake_bulk_enrich(
            *_args: Any, **_kwargs: Any
        ) -> list[dict[str, Any]]:
            return [
                {
                    "id": str(_uuid()),
                    "lead_id": str(lid1),
                    "status": "pending",
                    "contact_count": 0,
                    "cost_micros": 0,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                {
                    "id": str(_uuid()),
                    "lead_id": str(lid2),
                    "status": "pending",
                    "contact_count": 0,
                    "cost_micros": 0,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            ]

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService.bulk_request_enrichment",
            _fake_bulk_enrich,
            raising=False,
        )

        response = client.post(
            "/workspaces/1/leads/enrich",
            json={"lead_ids": [str(lid1), str(lid2)], "requested_count": 2},
        )
        assert response.status_code == 202
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 2

    def test_get_lead_enrichments_with_pagination(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lid = _uuid()

        async def _fake_list_enrichments(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "items": [],
                "total": 0,
                "limit": 20,
                "offset": 0,
            }

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService.list_enrichment_requests",
            _fake_list_enrichments,
            raising=False,
        )

        response = client.get(
            f"/workspaces/1/leads/{lid}/enrichments?limit=20&offset=0"
        )
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body

    def test_get_lead_contacts_with_pagination(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lid = _uuid()

        async def _fake_list_contacts(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "items": [],
                "total": 0,
                "limit": 20,
                "offset": 0,
            }

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService.list_verified_contacts",
            _fake_list_contacts,
            raising=False,
        )

        response = client.get(f"/workspaces/1/leads/{lid}/contacts?limit=20&offset=0")
        assert response.status_code == 200
        body = response.json()
        assert "items" in body

    def test_get_enrich_cost_projection(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_cost_projection(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "cost_per_contact_micros": 50000,
                "estimated_cost_micros": 250000,
                "lead_count": 5,
            }

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService.estimate_cost",
            _fake_cost_projection,
            raising=False,
        )

        response = client.get("/workspaces/1/leads/enrich/cost?lead_count=5")
        assert response.status_code == 200
        body = response.json()
        assert body["cost_per_contact_micros"] == 50000
        assert body["estimated_cost_micros"] == 250000


# ============================================================================
# AC-10: Degradation and Error Handling
# ============================================================================


class TestEnrichmentDegradation:
    """AC-10: Degradation on wallet exhaustion, missing lead, or provider failures."""

    async def test_enrich_returns_degraded_when_lead_not_found(self) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        session = _FakeSession(lead=None)
        ctx = _make_context(session)

        svc = EnrichmentService()
        output = await svc.enrich(session=session, ctx=ctx, lead_id=_uuid())

        assert output.degraded is True
        assert "lead_not_found" in output.degradation_reasons
        assert len(output.verified_contact_ids) == 0

    async def test_enrich_returns_degraded_when_all_providers_unavailable_and_no_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(lead=lead)
        ctx = _make_context(session)

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall_providers",
            AsyncMock(return_value=[]),  # No contacts found
            raising=False,
        )

        svc = EnrichmentService()
        output = await svc.enrich(session=session, ctx=ctx, lead_id=lead.id)

        assert output.contact_count == 0
        assert (
            len(session.added) == 1
        )  # EnrichmentRequest created with completed / 0 contacts


# ============================================================================
# PII Encryption Service Helper Tests
# ============================================================================


class TestVerifiedContactEncryption:
    """Validate encryption and decryption wrapper for VerifiedContact fields."""

    def test_encrypt_and_decrypt_contact_dictionary(self) -> None:
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )

        encryptor = VerifiedContactEncryption(
            secret_key="test-secret-key-at-least-32-chars-long"
        )

        contact = {
            "name": "Ngo Bao Chau",
            "title": "Professor",
            "email": "chau@math.uchicago.edu",
            "phone": "+13125550199",
            "verification_status": "verified",
        }

        encrypted = encryptor.encrypt_contact(contact)
        assert encrypted["name"] != "Ngo Bao Chau"
        assert encrypted["email"] != "chau@math.uchicago.edu"

        decrypted = encryptor.decrypt_contact(encrypted)
        assert decrypted["name"] == "Ngo Bao Chau"
        assert decrypted["title"] == "Professor"
        assert decrypted["email"] == "chau@math.uchicago.edu"
        assert decrypted["phone"] == "+13125550199"

    def test_encrypt_none_returns_none(self) -> None:
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )

        encryptor = VerifiedContactEncryption(
            secret_key="test-secret-key-at-least-32-chars-long"
        )
        assert encryptor.encrypt(None) is None
        assert encryptor.decrypt(None) is None
