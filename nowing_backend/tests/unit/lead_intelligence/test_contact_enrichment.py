"""Unit tests for contact enrichment service (Story 21.3, Task 3)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

pytestmark = pytest.mark.unit


def _uuid() -> UUID:
    return uuid4()


class _FakeWorkspace:
    def __init__(self, *, workspace_id: int = 1, user_id: UUID | None = None) -> None:
        self.id = workspace_id
        self.user_id = user_id or _uuid()


class _FakeLead:
    def __init__(
        self,
        *,
        lead_id: UUID | None = None,
        workspace_id: int = 1,
        client_id: str | None = None,
        company_name: str = "FPT",
        domain: str | None = "fpt.com",
        source_url: str | None = None,
        consent_status: str | None = None,
        legal_basis: str | None = None,
        enriched: bool = False,
    ) -> None:
        self.id = lead_id or _uuid()
        self.workspace_id = workspace_id
        self.client_id = client_id
        self.company_name = company_name
        self.domain = domain
        self.source_url = source_url
        self.consent_status = consent_status
        self.legal_basis = legal_basis
        self.enriched = enriched


class _FakeEnrichmentRequest:
    def __init__(
        self,
        *,
        request_id: UUID | None = None,
        workspace_id: int = 1,
        client_id: str | None = None,
        lead_id: UUID | None = None,
        status: str = "pending",
        requested_count: int = 5,
    ) -> None:
        self.id = request_id or _uuid()
        self.workspace_id = workspace_id
        self.client_id = client_id
        self.lead_id = lead_id or _uuid()
        self.status = status
        self.requested_count = requested_count
        self.provider_results: dict[str, Any] = {}
        self.cost_micros = 0
        self.contact_count = 0


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        if self._value is not None:
            return self._value
        return self._rows[0] if self._rows else None

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """In-memory stand-in for ``AsyncSession`` so unit tests avoid Postgres."""

    def __init__(self, *, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self._rows = rows or []
        self.registry: dict[tuple[str, UUID | int], Any] = {}

    def register(self, model_name: str, obj: Any) -> None:
        self.registry[(model_name, obj.id)] = obj

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any, _params: dict[str, Any] | None = None) -> _FakeResult:
        self.last_stmt = _stmt
        return _FakeResult(None, self._rows)

    async def get(self, model: Any, id: Any) -> Any:
        return self.registry.get((model.__name__, id))

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, _obj: Any) -> None:
        pass

    async def flush(self) -> None:
        self.flushed = True


def _make_context(session: _FakeSession | None = None, workspace_id: int = 1) -> Any:
    return SimpleNamespace(
        session=session or _FakeSession(),
        workspace_id=workspace_id,
        run_id="run-enrichment-test",
        client_id=None,
        user_id=_uuid(),
    )


@pytest.fixture(autouse=True)
def _patch_async_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate provider/billing/memory/redaction/cache/wallet side effects.

    Cosmic-ray runs tests from a temporary copy without the repo's
    ``.env.local``. Provide a deterministic Fernet key so
    ``VerifiedContactEncryption`` does not fail to initialize.
    """
    from app.config import config as app_config

    secret = Fernet.generate_key().decode()
    monkeypatch.setattr(app_config, "SECRET_KEY", secret)

    async def _noop_create_memory(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(id=1)

    async def _noop_check_balance(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.MemoryRepository.create_memory",
        _noop_create_memory,
    )
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.redact_pii",
        lambda text, **kw: SimpleNamespace(text="redacted"),
    )
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.cache.get_cached_contact_ids",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.cache.set_cached_contact_ids",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.wallet_credit.check_balance",
        _noop_check_balance,
    )
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.config.CONTACT_ENRICHMENT_MICROS_PER_CONTACT",
        1000,
    )


class TestEnrich:
    """Task 3.1: enrich() entrypoint behavior."""

    async def test_enrich_degraded_when_lead_missing(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        session = _FakeSession()
        workspace = _FakeWorkspace()
        session.register("Workspace", workspace)
        ctx = _make_context(session)

        svc = EnrichmentService()
        output = await svc.enrich(session, ctx, lead_id=_uuid())

        assert output.degraded is True
        assert output.degradation_reasons == ["lead_not_found"]
        assert output.enrichment_request_id is None

    async def test_enrich_degraded_when_wallet_insufficient(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService
        from app.services.etl_credit_service import InsufficientCreditsError

        session = _FakeSession(rows=[_FakeLead()])
        workspace = _FakeWorkspace()
        session.register("Workspace", workspace)
        ctx = _make_context(session)

        async def _short_balance(*args: Any, **kwargs: Any) -> None:
            raise InsufficientCreditsError(
                message="short",
                balance_micros=0,
                required_micros=100,
            )

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.wallet_credit.check_balance",
            _short_balance,
        )

        svc = EnrichmentService()
        output = await svc.enrich(session, ctx, lead_id=session._rows[0].id)

        assert output.degraded is True
        assert output.degradation_reasons == ["insufficient_wallet"]
        assert output.enrichment_request_id is None
        assert session.added == []  # no EnrichmentRequest created

    async def test_enrich_creates_pending_request_and_enqueues(
        self, monkeypatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(rows=[lead])
        workspace = _FakeWorkspace()
        session.register("Workspace", workspace)
        ctx = _make_context(session)

        enqueue = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._enqueue",
            enqueue,
        )

        svc = EnrichmentService()
        output = await svc.enrich(session, ctx, lead_id=lead.id, requested_count=3)

        assert output.degraded is False
        assert output.enrichment_request_id is not None
        assert len(session.added) == 1
        request = session.added[0]
        assert request.status == "pending"
        assert request.lead_id == lead.id
        assert request.requested_count == 3
        assert enqueue.awaited_once is True
        assert enqueue.last_args == (request.id, 1, None)

    async def test_enrich_uses_cache_and_skips_enqueue(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        contact_id = _uuid()
        session = _FakeSession(rows=[SimpleNamespace(id=contact_id)])
        workspace = _FakeWorkspace()
        session.register("Workspace", workspace)
        ctx = _make_context(session)

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.cache.get_cached_contact_ids",
            lambda *a, **kw: [contact_id],
        )
        enqueue = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._enqueue",
            enqueue,
        )

        svc = EnrichmentService()
        output = await svc.enrich(session, ctx, lead_id=lead.id)

        assert output.degraded is False
        assert output.verified_contact_ids == [contact_id]
        assert output.contact_count == 1
        assert output.cost_micros == 0
        assert session.added == []  # no request, no billing
        assert enqueue.awaited_once is False

    async def test_enrich_falls_back_inline_when_celery_unavailable(
        self, monkeypatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(rows=[lead])
        workspace = _FakeWorkspace()
        session.register("Workspace", workspace)
        ctx = _make_context(session)

        async def _raise_enqueue(_request_id: UUID) -> None:
            raise RuntimeError("no broker")

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._enqueue",
            _raise_enqueue,
        )
        waterfall = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._run_waterfall",
            waterfall,
        )

        svc = EnrichmentService()
        output = await svc.enrich(session, ctx, lead_id=lead.id)

        assert output.degraded is True
        assert output.degradation_reasons == ["celery_unavailable"]
        assert waterfall.awaited_once is True

    async def test_enrich_uses_default_requested_count(self) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        session = _FakeSession(rows=[lead])
        workspace = _FakeWorkspace()
        session.register("Workspace", workspace)
        ctx = _make_context(session)

        svc = EnrichmentService()
        output = await svc.enrich(session, ctx, lead_id=lead.id)

        assert output.degraded is False
        request = session.added[0]
        assert request.requested_count == 5

    async def test_enrich_passes_client_id_to_tenant_and_fetch(
        self, monkeypatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead(client_id="acme")
        session = _FakeSession(rows=[lead])
        workspace = _FakeWorkspace()
        session.register("Workspace", workspace)
        ctx = _make_context(session)
        ctx.client_id = "acme"

        tenant_spy = _AsyncMockResult(None)
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.set_request_tenant_context",
            tenant_spy,
        )
        fetch_spy = _AsyncMockResult(lead)
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.EnrichmentService._fetch_lead",
            fetch_spy,
        )

        svc = EnrichmentService()
        await svc.enrich(session, ctx, lead_id=lead.id)

        assert tenant_spy.awaited_once is True
        assert tenant_spy.last_kwargs["client_id"] == "acme"
        assert fetch_spy.awaited_once is True
        assert fetch_spy.last_args[2] == "acme"


class TestRunWaterfall:
    """Task 3.1: the async provider waterfall."""

    def _make_session_with_entities(
        self,
        *,
        lead: _FakeLead | None = None,
        request: _FakeEnrichmentRequest | None = None,
        workspace: _FakeWorkspace | None = None,
    ) -> _FakeSession:
        lead = lead or _FakeLead()
        session = _FakeSession(rows=[lead])
        session.register("Workspace", workspace or _FakeWorkspace())
        session.register("Lead", lead)
        session.register(
            "EnrichmentRequest",
            request or _FakeEnrichmentRequest(lead_id=lead.id),
        )
        return session

    async def test_waterfall_completes_and_encrypts_pii(self, monkeypatch) -> None:
        from app.db import VerifiedContact
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead(consent_status="granted", legal_basis="legitimate_interest")
        request = _FakeEnrichmentRequest(lead_id=lead.id, requested_count=5)
        session = self._make_session_with_entities(lead=lead, request=request)

        contacts = [
            {
                "name": "Alice Nguyen",
                "title": "CTO",
                "email": "alice@fpt.com",
                "phone": "+84123456789",
                "verification_status": "verified",
                "confidence": 0.95,
                "source_provider": "cleanlist",
            }
        ]
        run_waterfall = _AsyncMockResult((contacts, "cleanlist"))
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.run_waterfall",
            run_waterfall,
        )
        billing = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            billing,
        )
        cache_set = _SyncSpy()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.cache.set_cached_contact_ids",
            cache_set,
        )

        svc = EnrichmentService()
        output = await svc._run_waterfall(session, request.id)

        assert output.degraded is False
        assert output.contact_count == 1
        assert len(output.verified_contact_ids) == 1
        assert output.cost_micros > 0

        assert request.status == "completed"
        assert request.contact_count == 1
        assert request.provider_results["provider"] == "cleanlist"
        assert lead.enriched is True
        assert lead.consent_status == "granted"
        assert lead.legal_basis == "legitimate_interest"

        stored = [o for o in session.added if isinstance(o, VerifiedContact)]
        assert len(stored) == 1
        # AD-42: PII is encrypted at rest.
        assert stored[0].email != "alice@fpt.com"
        assert stored[0].phone != "+84123456789"
        assert stored[0].name != "Alice Nguyen"
        assert stored[0].source_provider == "cleanlist"
        assert stored[0].consent_status == "granted"
        assert stored[0].legal_basis == "legitimate_interest"
        assert stored[0].consent is False

        assert billing.awaited_once is True
        assert billing.last_kwargs["cost_micros"] == output.cost_micros
        assert billing.last_kwargs["enrichment_request_id"] == request.id
        assert cache_set.called_once is True

    async def test_waterfall_degraded_when_all_providers_fail(
        self, monkeypatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        request = _FakeEnrichmentRequest(lead_id=lead.id)
        session = self._make_session_with_entities(lead=lead, request=request)

        run_waterfall = _AsyncMockResult(([], "none"))
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.run_waterfall",
            run_waterfall,
        )
        fallback = _AsyncMockResult([])
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.FallbackVerifier.find_contacts",
            fallback,
        )
        billing = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            billing,
        )

        svc = EnrichmentService()
        output = await svc._run_waterfall(session, request.id)

        assert output.degraded is True
        assert "provider_unavailable" in output.degradation_reasons
        assert output.contact_count == 0
        assert request.status == "completed"
        assert request.contact_count == 0
        assert request.provider_results["degraded"] is True
        assert session.added == []
        assert billing.awaited_once is False

    async def test_waterfall_falls_back_to_verifier(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        request = _FakeEnrichmentRequest(lead_id=lead.id)
        session = self._make_session_with_entities(lead=lead, request=request)

        run_waterfall = _AsyncMockResult(([], "none"))
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.run_waterfall",
            run_waterfall,
        )
        fallback_contacts = [
            {
                "name": None,
                "title": None,
                "email": "info@fpt.com",
                "phone": None,
                "verification_status": "low_confidence",
                "confidence": 0.4,
                "source_provider": "fallback",
            }
        ]
        fallback = _AsyncMockResult(fallback_contacts)
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.FallbackVerifier.find_contacts",
            fallback,
        )
        billing = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            billing,
        )

        svc = EnrichmentService()
        output = await svc._run_waterfall(session, request.id)

        assert output.degraded is False
        assert output.contact_count == 1
        assert request.status == "completed"
        assert request.provider_results["provider"] == "fallback"
        assert billing.awaited_once is True
        assert billing.last_kwargs["cost_micros"] == output.cost_micros

    async def test_waterfall_sets_consent_true_when_explicit(
        self, monkeypatch
    ) -> None:
        from app.db import VerifiedContact
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead(consent_status="granted", legal_basis="legitimate_interest")
        request = _FakeEnrichmentRequest(lead_id=lead.id, requested_count=1)
        session = self._make_session_with_entities(lead=lead, request=request)

        # Build a runtime string so `is` vs `==` comparison mutants are killed.
        consent_status = "explic"
        consent_status += "it"
        contacts = [
            {
                "name": "A",
                "title": "T",
                "email": "a@fpt.com",
                "phone": "+84000000000",
                "verification_status": "verified",
                "confidence": 0.9,
                "source_provider": "cleanlist",
                "consent_status": consent_status,
            }
        ]
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.run_waterfall",
            _AsyncMockResult((contacts, "cleanlist")),
        )
        billing = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            billing,
        )

        svc = EnrichmentService()
        await svc._run_waterfall(session, request.id)

        stored = [o for o in session.added if isinstance(o, VerifiedContact)]
        assert len(stored) == 1
        assert stored[0].consent is True
        assert stored[0].consent_status == consent_status

    async def test_waterfall_keeps_lead_consent_when_present(
        self, monkeypatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead(consent_status="granted", legal_basis="legitimate_interest")
        request = _FakeEnrichmentRequest(lead_id=lead.id, requested_count=1)
        session = self._make_session_with_entities(lead=lead, request=request)

        contacts = [
            {
                "name": "A",
                "title": "T",
                "email": "a@fpt.com",
                "phone": "+84000000000",
                "verification_status": "verified",
                "confidence": 0.9,
                "source_provider": "cleanlist",
                "consent_status": "explicit",
                "legal_basis": "consent",
            }
        ]
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.run_waterfall",
            _AsyncMockResult((contacts, "cleanlist")),
        )
        billing = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            billing,
        )

        svc = EnrichmentService()
        await svc._run_waterfall(session, request.id)

        assert lead.consent_status == "granted"
        assert lead.legal_basis == "legitimate_interest"

    async def test_waterfall_propagates_contact_consent_when_lead_missing(
        self, monkeypatch
    ) -> None:
        from app.db import VerifiedContact
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead(consent_status=None, legal_basis=None)
        request = _FakeEnrichmentRequest(lead_id=lead.id, requested_count=1)
        session = self._make_session_with_entities(lead=lead, request=request)

        # Build a runtime string so `is` vs `==` comparison mutants are killed.
        consent_status = "explic"
        consent_status += "it"
        contacts = [
            {
                "name": "A",
                "title": "T",
                "email": "a@fpt.com",
                "phone": "+84000000000",
                "verification_status": "verified",
                "confidence": 0.9,
                "source_provider": "cleanlist",
                "consent_status": consent_status,
                "legal_basis": "consent",
            }
        ]
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.run_waterfall",
            _AsyncMockResult((contacts, "cleanlist")),
        )
        billing = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            billing,
        )

        svc = EnrichmentService()
        await svc._run_waterfall(session, request.id)

        stored = [o for o in session.added if isinstance(o, VerifiedContact)]
        assert stored[0].consent is True
        assert lead.consent_status == consent_status
        assert lead.legal_basis == "consent"

    async def test_waterfall_uses_zero_confidence_default(
        self, monkeypatch
    ) -> None:
        from app.db import VerifiedContact
        from app.lead_intelligence.enrichment.service import EnrichmentService

        lead = _FakeLead()
        request = _FakeEnrichmentRequest(lead_id=lead.id, requested_count=1)
        session = self._make_session_with_entities(lead=lead, request=request)

        contacts = [
            {
                "name": "A",
                "title": "T",
                "email": "a@fpt.com",
                "phone": "+84000000000",
                "verification_status": "verified",
                "source_provider": "cleanlist",
                # confidence intentionally omitted
            }
        ]
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.run_waterfall",
            _AsyncMockResult((contacts, "cleanlist")),
        )
        billing = _AsyncMockResult()
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.BillingEventService.record_contact_enrichment",
            billing,
        )

        svc = EnrichmentService()
        await svc._run_waterfall(session, request.id)

        stored = [o for o in session.added if isinstance(o, VerifiedContact)]
        assert stored[0].confidence == 0.0

    async def test_waterfall_degraded_when_lead_not_found(self) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        request = _FakeEnrichmentRequest(lead_id=_uuid(), requested_count=1)
        session = _FakeSession(rows=[])
        session.register("Workspace", _FakeWorkspace())
        session.register("EnrichmentRequest", request)

        svc = EnrichmentService()
        output = await svc._run_waterfall(session, request.id)

        assert output.degraded is True
        assert output.degradation_reasons == ["lead_not_found"]
        assert request.provider_results["degraded"] is True
        assert request.provider_results["reasons"] == ["lead_not_found"]


class TestGetContacts:
    """AC-6: contacts are decrypted only for authorized reads."""

    async def test_get_contacts_returns_decrypted_pii(self, monkeypatch) -> None:
        from app.db import VerifiedContact
        from app.lead_intelligence.enrichment.service import EnrichmentService
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )

        cipher = VerifiedContactEncryption()
        contact_id = _uuid()
        lead_id = _uuid()
        encrypted = cipher.encrypt_contact(
            {
                "name": "Bob Tran",
                "title": "CEO",
                "email": "bob@fpt.com",
                "phone": "+84987654321",
            }
        )
        row = VerifiedContact(
            id=contact_id,
            workspace_id=1,
            client_id=None,
            lead_id=lead_id,
            enrichment_request_id=_uuid(),
            name=encrypted.get("name"),
            title=encrypted.get("title"),
            email=encrypted.get("email"),
            phone=encrypted.get("phone"),
            verification_status="verified",
            confidence=0.9,
            source_provider="cleanlist",
        )
        session = _FakeSession(rows=[row])

        svc = EnrichmentService()
        contacts = await svc.get_contacts(
            session,
            workspace_id=1,
            client_id=None,
            lead_id=lead_id,
            user_id=_uuid(),
        )

        assert len(contacts) == 1
        assert contacts[0].email == "bob@fpt.com"
        assert contacts[0].phone == "+84987654321"
        assert contacts[0].name == "Bob Tran"


class _AsyncMockResult:
    """Tiny helper recording awaited calls on a function-like attribute."""

    def __init__(self, value: Any = None) -> None:
        self._value = value
        self.awaited_once = False
        self.last_args: tuple = ()
        self.last_kwargs: dict[str, Any] = {}

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.awaited_once = True
        self.last_args = args
        self.last_kwargs = kwargs
        return self._value


class _SyncSpy:
    """Tiny helper recording synchronous calls."""

    def __init__(self) -> None:
        self.called_once = False
        self.last_args: tuple = ()
        self.last_kwargs: dict[str, Any] = {}

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.called_once = True
        self.last_args = args
        self.last_kwargs = kwargs
        return None


class TestEstimatedCost:
    """Kill arithmetic/number-replacer mutants in _estimated_cost."""

    def test_estimated_cost_multiplies_by_capped_count(self) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        svc = EnrichmentService()
        assert svc._estimated_cost(0) == 0
        assert svc._estimated_cost(1) == 1000
        assert svc._estimated_cost(3) == 3000

    def test_estimated_cost_caps_at_max_contacts(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.config.CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD",
            2,
        )
        svc = EnrichmentService()
        assert svc._estimated_cost(5) == 2000

    def test_estimated_cost_defaults_to_zero_when_config_unset(
        self, monkeypatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.config.CONTACT_ENRICHMENT_MICROS_PER_CONTACT",
            0,
        )
        svc = EnrichmentService()
        assert svc._estimated_cost(5) == 0


class TestListEnrichmentRequests:
    """Kill NumberReplacer mutants for offset/limit defaults."""

    async def test_list_enrichment_requests_default_offset_is_zero(self) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        svc = EnrichmentService()
        kwdefaults = svc.list_enrichment_requests.__kwdefaults__
        assert kwdefaults is not None
        assert kwdefaults["offset"] == 0
        assert kwdefaults["limit"] == 50

    async def test_list_enrichment_requests_filters_by_workspace_lead_and_client(
        self, monkeypatch
    ) -> None:
        from sqlalchemy.dialects import postgresql

        from app.lead_intelligence.enrichment.service import EnrichmentService

        session = _FakeSession(rows=[])
        svc = EnrichmentService()
        lead_id = _uuid()
        await svc.list_enrichment_requests(
            session, workspace_id=1, client_id="acme", lead_id=lead_id
        )

        compiled = str(
            session.last_stmt.compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "workspace_id = 1" in compiled
        assert f"lead_id = '{lead_id}'" in compiled
        assert "client_id = 'acme'" in compiled


class TestDegraded:
    """Kill NumberReplacer mutants in _degraded."""

    def test_degraded_returns_zero_cost_and_count(self) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        output = EnrichmentService._degraded(["insufficient_wallet"])
        assert output.degraded is True
        assert output.degradation_reasons == ["insufficient_wallet"]
        assert output.contact_count == 0
        assert output.cost_micros == 0
        assert output.enrichment_request_id is None


class TestWriteMemory:
    """Kill mutants in _write_memory confidence/provider arithmetic."""

    async def test_write_memory_averages_confidence_and_uses_first_provider(
        self, monkeypatch
    ) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        spy = _AsyncMockResult(SimpleNamespace(id=1))
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.MemoryRepository.create_memory",
            spy,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.redact_pii",
            lambda text, **kw: SimpleNamespace(text=text),
        )

        request = _FakeEnrichmentRequest()
        contacts = [
            {
                "name": "A",
                "title": "TA",
                "email": "a@fpt.com",
                "phone": "+84111111111",
                "verification_status": "verified",
                "confidence": 0.12345,
                "source_provider": "cleanlist 越南",
            },
            {
                "name": "B",
                "title": "TB",
                "email": "b@fpt.com",
                "phone": "+84222222222",
                "verification_status": "verified",
                "confidence": 0.12344,
                "source_provider": "bettercontact",
            }
        ]

        svc = EnrichmentService()
        await svc._write_memory(None, request, contacts, _uuid())

        assert spy.awaited_once is True
        kwargs = spy.last_kwargs
        assert kwargs["source_uuid"] == request.id
        assert kwargs["source_entity_type"] == "enrichment_request"
        assert kwargs["confidence"] == 0.9

        # Average confidence of the two contacts, rounded to 4 decimals.
        assert "0.1234" in kwargs["content"]
        # Provider must be the *first* contact's provider, using a non-ASCII
        # name so json.dumps(ensure_ascii=False) is asserted.
        assert '"provider": "cleanlist 越南"' in kwargs["content"]
        assert "bettercontact" not in kwargs["content"]
        assert kwargs["tags"] == ["enriched_contact"]

    async def test_write_memory_handles_empty_contacts(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.service import EnrichmentService

        spy = _AsyncMockResult(SimpleNamespace(id=1))
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.MemoryRepository.create_memory",
            spy,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.service.redact_pii",
            lambda text, **kw: SimpleNamespace(text=text),
        )

        request = _FakeEnrichmentRequest()
        svc = EnrichmentService()
        await svc._write_memory(None, request, [], _uuid())

        assert spy.awaited_once is True
        kwargs = spy.last_kwargs
        assert '"provider": "none"' in kwargs["content"]
        assert '"contact_count": 0' in kwargs["content"]
        assert '"confidence": 0.0' in kwargs["content"]
