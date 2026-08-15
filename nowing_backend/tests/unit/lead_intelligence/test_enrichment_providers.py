"""Unit tests for enrichment providers (Story 21.3, Task 4)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


def _lead(**overrides: Any) -> Any:
    from types import SimpleNamespace

    base = {
        "id": uuid4(),
        "company_name": "FPT",
        "domain": "fpt.com",
        "source_url": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestParseContacts:
    def test_parse_list_payload(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import _parse_contacts

        payload = [
            {"email": "a@fpt.com", "name": "A", "phone": "+841", "confidence": 0.9},
        ]
        contacts = _parse_contacts(payload, provider="cleanlist")
        assert len(contacts) == 1
        assert contacts[0]["email"] == "a@fpt.com"
        assert contacts[0]["name"] == "A"
        assert contacts[0]["source_provider"] == "cleanlist"
        assert contacts[0]["verification_status"] == "verified"

    def test_parse_dict_payload(self) -> None:
        from app.lead_intelligence.enrichment.providers import _parse_contacts

        payload = {
            "contacts": [
                {"email": "b@fpt.com", "full_name": "B", "job_title": "CEO"},
            ]
        }
        contacts = _parse_contacts(payload, provider="bettercontact")
        assert len(contacts) == 1
        assert contacts[0]["email"] == "b@fpt.com"
        assert contacts[0]["name"] == "B"
        assert contacts[0]["title"] == "CEO"

    def test_skips_items_without_email(self) -> None:
        from app.lead_intelligence.enrichment.providers import _parse_contacts

        payload = [{"name": "No Email"}, {"email": "ok@fpt.com"}]
        contacts = _parse_contacts(payload, provider="cleanlist")
        assert len(contacts) == 1
        assert contacts[0]["email"] == "ok@fpt.com"


class TestResolveWaterfall:
    def test_default_primary_is_cleanlist(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import resolve_waterfall

        primary, secondary = resolve_waterfall()
        assert primary.name == "cleanlist"
        assert secondary.name == "bettercontact"

    def test_explicit_primary_bettercontact(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import resolve_waterfall

        primary, secondary = resolve_waterfall(primary="bettercontact")
        assert primary.name == "bettercontact"
        assert secondary.name == "cleanlist"

    def test_unknown_primary_falls_back_to_cleanlist(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import resolve_waterfall

        primary, secondary = resolve_waterfall(primary="not-a-provider")
        assert primary.name == "cleanlist"
        assert secondary.name == "bettercontact"


class TestCleanlistClient:
    async def test_skips_when_no_api_key(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import CleanlistClient

        client = CleanlistClient(api_key="")
        contacts = await client.find_contacts(_lead(), 5)
        assert contacts == []

    async def test_returns_parsed_contacts(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import CleanlistClient

        class _FakeResponse:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> Any:
                return {
                    "contacts": [
                        {"email": "c@fpt.com", "name": "C", "confidence": 0.8},
                    ]
                }

        class _FakeClient:
            async def __aenter__(self) -> _FakeClient:
                return self

            async def __aexit__(self, *args: Any) -> None:
                pass

            async def get(self, *args: Any, **kwargs: Any) -> _FakeResponse:
                return _FakeResponse()

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.providers.httpx.AsyncClient",
            lambda **kw: _FakeClient(),
        )
        client = CleanlistClient(api_key="test-key")
        contacts = await client.find_contacts(_lead(), 5)
        assert len(contacts) == 1
        assert contacts[0]["email"] == "c@fpt.com"
        assert contacts[0]["source_provider"] == "cleanlist"


class TestBetterContactClient:
    async def test_skips_when_no_api_key(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import BetterContactClient

        client = BetterContactClient(api_key="")
        contacts = await client.find_contacts(_lead(), 5)
        assert contacts == []

    async def test_returns_parsed_contacts(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import BetterContactClient

        class _FakeResponse:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> Any:
                return {
                    "data": [
                        {"email": "d@fpt.com", "phone": "+842", "confidence": 0.7},
                    ]
                }

        class _FakeClient:
            async def __aenter__(self) -> _FakeClient:
                return self

            async def __aexit__(self, *args: Any) -> None:
                pass

            async def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
                return _FakeResponse()

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.providers.httpx.AsyncClient",
            lambda **kw: _FakeClient(),
        )
        client = BetterContactClient(api_key="test-key")
        contacts = await client.find_contacts(_lead(), 5)
        assert len(contacts) == 1
        assert contacts[0]["email"] == "d@fpt.com"
        assert contacts[0]["source_provider"] == "bettercontact"


class TestRunWaterfall:
    async def test_primary_hit_returns_its_contacts(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import run_waterfall

        primary_hit = {
            "email": "p@fpt.com",
            "confidence": 0.9,
            "source_provider": "cleanlist",
        }

        async def _primary_find(_lead: Any, _count: int) -> list[dict]:
            return [primary_hit]

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.providers.resolve_waterfall",
            lambda: (
                _FakeProvider("cleanlist", _primary_find),
                _FakeProvider("bettercontact", _never_called),
            ),
        )
        contacts, provider = await run_waterfall(_lead(), 5)
        assert provider == "cleanlist"
        assert contacts == [primary_hit]

    async def test_both_empty_returns_none_provider(self, monkeypatch) -> None:
        from app.lead_intelligence.enrichment.providers import run_waterfall

        async def _empty(_lead: Any, _count: int) -> list[dict]:
            return []

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.providers.resolve_waterfall",
            lambda: (
                _FakeProvider("cleanlist", _empty),
                _FakeProvider("bettercontact", _empty),
            ),
        )
        contacts, provider = await run_waterfall(_lead(), 5, retry_attempts=1)
        assert contacts == []
        assert provider == "none"

    async def test_primary_failure_falls_through_to_secondary(
        self, monkeypatch
    ) -> None:
        from app.lead_intelligence.enrichment.providers import run_waterfall

        async def _boom(_lead: Any, _count: int) -> list[dict]:
            raise ValueError("provider exploded")

        secondary_hit = {
            "email": "s@fpt.com",
            "confidence": 0.6,
            "source_provider": "bettercontact",
        }

        async def _secondary_find(_lead: Any, _count: int) -> list[dict]:
            return [secondary_hit]

        monkeypatch.setattr(
            "app.lead_intelligence.enrichment.providers.resolve_waterfall",
            lambda: (
                _FakeProvider("cleanlist", _boom),
                _FakeProvider("bettercontact", _secondary_find),
            ),
        )
        contacts, provider = await run_waterfall(_lead(), 5, retry_attempts=1)
        assert provider == "bettercontact"
        assert contacts == [secondary_hit]


async def _never_called(_lead: Any, _count: int) -> list[dict]:
    raise AssertionError("secondary provider should not be called")


class _FakeProvider:
    name: str

    def __init__(self, name: str, find: Any) -> None:
        self.name = name
        self._find = find

    async def find_contacts(self, lead: Any, count: int) -> list[dict]:
        return await self._find(lead, count)
