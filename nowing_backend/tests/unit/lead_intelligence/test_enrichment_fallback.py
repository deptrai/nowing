"""Unit tests for the enrichment fallback verifier (Story 21.3, Task 4.2)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


def _lead(**overrides) -> SimpleNamespace:
    base = {
        "id": uuid4(),
        "company_name": "FPT",
        "domain": "fpt.com",
        "source_url": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestFallbackVerifier:
    async def test_no_domain_and_no_source_url_returns_empty(self) -> None:
        from app.lead_intelligence.enrichment.fallback import FallbackVerifier

        verifier = FallbackVerifier()
        contacts = await verifier.find_contacts(_lead(domain=None, source_url=None))
        assert contacts == []

    async def test_domain_without_source_url_returns_empty(self) -> None:
        from app.lead_intelligence.enrichment.fallback import FallbackVerifier

        verifier = FallbackVerifier()
        contacts = await verifier.find_contacts(_lead(domain="fpt.com"))
        assert contacts == []

    async def test_source_url_yields_info_email(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.fallback import FallbackVerifier

        verifier = FallbackVerifier()
        monkeypatch.setattr(
            verifier,
            "verify_email",
            _AsyncLambda(True),
        )
        contacts = await verifier.find_contacts(
            _lead(domain="fpt.com", source_url="https://fpt.com/about")
        )
        assert len(contacts) == 1
        assert contacts[0]["email"] == "info@fpt.com"
        assert contacts[0]["verification_status"] == "low_confidence"
        assert contacts[0]["confidence"] == 0.4
        assert contacts[0]["source_provider"] == "fallback"

    async def test_mx_lookup_failure_still_accepts_format(self, monkeypatch) -> None:
        import sys
        from types import ModuleType

        from app.lead_intelligence.enrichment.fallback import FallbackVerifier

        fake_dns = ModuleType("dns")
        fake_resolver = ModuleType("dns.resolver")

        def _raise(*_args, **_kwargs):
            raise Exception("no dns")

        fake_resolver.resolve = _raise
        fake_dns.resolver = fake_resolver
        monkeypatch.setitem(sys.modules, "dns", fake_dns)
        monkeypatch.setitem(sys.modules, "dns.resolver", fake_resolver)

        verifier = FallbackVerifier()
        assert await verifier.verify_email("info@fpt.com") is True

    async def test_invalid_email_rejected(self) -> None:
        from app.lead_intelligence.enrichment.fallback import FallbackVerifier

        verifier = FallbackVerifier()
        assert await verifier.verify_email("not-an-email") is False

    async def test_phone_e164_check(self) -> None:
        from app.lead_intelligence.enrichment.fallback import FallbackVerifier

        verifier = FallbackVerifier()
        assert await verifier.verify_phone("+841234567890") is True
        assert await verifier.verify_phone("abc") is False
        assert await verifier.verify_phone(None) is False

    async def test_domain_from_url(self) -> None:
        from app.lead_intelligence.enrichment.fallback import _domain_from_url

        assert _domain_from_url("https://x.example.com/a") == "example.com"
        assert _domain_from_url("https://fpt.com") == "fpt.com"
        assert _domain_from_url("not a url") is None
        assert _domain_from_url(None) is None


class _AsyncLambda:
    def __init__(self, result: bool) -> None:
        self._result = result

    async def __call__(self, *args, **kwargs) -> bool:
        return self._result
