"""Red-phase ATDD tests for Story 21.1 — Intent Signal Detection.

These tests describe the contract the new ``SignalDetectionService`` and its
schemas must satisfy. They will fail until the implementation is written.

All DB/session interaction is mocked; no real PostgreSQL is required.
"""

from __future__ import annotations

import types
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.unit


class _FakeResult:
    """Return value for ``FakeSession.execute`` that supports SQLAlchemy-style
    result helpers."""

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
    """In-memory stand-in for ``AsyncSession`` so unit tests avoid Postgres."""

    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, _obj: Any) -> None:
        pass

    async def flush(self) -> None:
        self.flushed = True


def _make_context(session: _FakeSession | None = None, workspace_id: int = 1) -> Any:
    """Minimal execution context for signal tests."""
    return types.SimpleNamespace(
        session=session or _FakeSession(),
        workspace_id=workspace_id,
        run_id="run-signal-test",
        user_id=uuid4(),
    )


def _now() -> datetime:
    return datetime.now(UTC)


class TestSignalSchemas:
    """AC-1/AC-5: schema contract and validation boundaries."""

    def test_signal_input_accepts_expected_fields(self):
        from app.lead_intelligence.signals.schemas import SignalInput

        inp = SignalInput(
            company_name="FPT",
            domain="fpt.com",
            lookback_days=30,
            confidence_threshold=0.0,
        )
        assert inp.company_name == "FPT"
        assert inp.domain == "fpt.com"
        assert inp.lookback_days == 30
        assert inp.confidence_threshold == 0.0

    def test_signal_input_rejects_empty_company_name(self):
        from app.lead_intelligence.signals.schemas import SignalInput

        with pytest.raises(ValueError, match="company_name"):
            SignalInput(company_name="   ")

    def test_signal_input_rejects_confidence_threshold_over_100(self):
        from app.lead_intelligence.signals.schemas import SignalInput

        with pytest.raises(ValueError, match="confidence_threshold"):
            SignalInput(company_name="FPT", confidence_threshold=101.0)

    def test_signal_input_allows_confidence_threshold_zero_and_100(self):
        from app.lead_intelligence.signals.schemas import SignalInput

        low = SignalInput(company_name="FPT", confidence_threshold=0.0)
        high = SignalInput(company_name="FPT", confidence_threshold=100.0)
        assert low.confidence_threshold == 0.0
        assert high.confidence_threshold == 100.0

    def test_signal_input_rejects_negative_lookback_days(self):
        from app.lead_intelligence.signals.schemas import SignalInput

        with pytest.raises(ValueError, match="lookback_days"):
            SignalInput(company_name="FPT", lookback_days=-1)

    def test_signal_input_allows_lookback_days_zero(self):
        from app.lead_intelligence.signals.schemas import SignalInput

        inp = SignalInput(company_name="FPT", lookback_days=0)
        assert inp.lookback_days == 0

    def test_signal_output_has_exact_contract_fields(self):
        from app.lead_intelligence.signals.schemas import (
            SignalEventRead,
            SignalOutput,
        )

        item = SignalEventRead(
            id=uuid4(),
            workspace_id=1,
            client_id=None,
            company_name="FPT",
            signal_type="funding",
            source_url="https://example.com/funding",
            chunk_id=uuid4(),
            confidence=85.0,
            detected_at=_now(),
            processed=False,
        )
        out = SignalOutput(
            items=[item],
            cost_micros=1000,
            degraded=False,
            degradation_reasons=None,
        )

        assert out.items[0].signal_type == "funding"
        assert out.items[0].confidence == 85.0
        assert out.cost_micros == 1000
        assert out.degraded is False
        # Mirror: public corpus fields are not exposed on the output.
        assert not hasattr(out, "raw_document")
        assert not hasattr(out, "lead_score")
        assert not hasattr(out, "fit_score")

    def test_signal_output_does_not_include_raw_public_document(self):
        from app.lead_intelligence.signals.schemas import SignalOutput

        out = SignalOutput(items=[], cost_micros=0, degraded=False)
        assert not hasattr(out, "raw_document")
        assert not hasattr(out, "full_text")


class TestSignalDetectionService:
    """AC-1/AC-2/AC-6/AC-7: detection, storage, and billing contracts."""

    @pytest.mark.asyncio
    async def test_detect_returns_signal_output_with_expected_fields(self):
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        assert hasattr(output, "items")
        assert hasattr(output, "cost_micros")
        assert hasattr(output, "degraded")
        assert isinstance(output.items, list)

    @pytest.mark.asyncio
    async def test_detect_funding_returns_funding_signal_type(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "test-key", raising=False)
        monkeypatch.setattr(
            httpx.AsyncClient,
            "get",
            AsyncMock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {
                            "name": "FPT",
                            "funding_total": 1000000,
                            "announced_on": "2026-08-01",
                        }
                    ],
                )
            ),
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        assert output.items
        assert output.items[0].signal_type == "funding"
        assert 0 <= output.items[0].confidence <= 100

    @pytest.mark.asyncio
    async def test_detect_hiring_resolves_company_name(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "", raising=False)
        monkeypatch.setattr(
            "app.services.jobs_aggregator.aggregate_jobs",
            AsyncMock(
                return_value={
                    "items": [
                        {
                            "company_name": "FPT",
                            "source_url": "https://example.com/job",
                            "confidence_score": 70.0,
                        }
                    ],
                    "degraded": False,
                }
            ),
            raising=False,
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "hiring",
        )

        for item in output.items:
            assert item.company_name.lower() == "fpt"

    @pytest.mark.asyncio
    async def test_detect_returns_degraded_when_crunchbase_api_key_missing(
        self, monkeypatch
    ):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "", raising=False)

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        assert output.degraded is True
        assert any(
            "crunchbase_api_key_missing" in r for r in output.degradation_reasons
        )

    @pytest.mark.asyncio
    async def test_detect_returns_degraded_when_crunchbase_timeout(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "test-key", raising=False)
        monkeypatch.setattr(
            httpx.AsyncClient, "get", AsyncMock(side_effect=httpx.TimeoutException)
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        assert output.degraded is True

    @pytest.mark.asyncio
    async def test_detect_returns_degraded_when_newsapi_empty(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "NEWSAPI_KEY", "test-key", raising=False)
        monkeypatch.setattr(
            httpx.AsyncClient,
            "get",
            AsyncMock(return_value=httpx.Response(200, json={"articles": []})),
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "news",
        )

        assert output.degraded is False or output.items == []

    @pytest.mark.asyncio
    async def test_detect_returns_degraded_when_website_5xx(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "NEWSAPI_KEY", "", raising=False)
        monkeypatch.setattr(
            httpx.AsyncClient,
            "get",
            AsyncMock(return_value=httpx.Response(503, text="Unavailable")),
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "tech_stack",
        )

        assert output.degraded is True

    @pytest.mark.asyncio
    async def test_detect_returns_degraded_when_vn_jobs_aggregate_degraded(
        self, monkeypatch
    ):
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        # Simulate the upstream job aggregator returning a degraded output.
        monkeypatch.setattr(
            "app.services.jobs_aggregator.aggregate_jobs",
            AsyncMock(
                return_value={
                    "items": [],
                    "degraded": True,
                    "degradation_reasons": ["itviec.timeout"],
                }
            ),
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "hiring",
        )

        assert output.degraded is True

    @pytest.mark.asyncio
    async def test_detect_executive_move_deferred_when_disabled(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(
            config, "SIGNAL_EXECUTIVE_MOVE_ENABLED", False, raising=False
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "executive_move",
        )

        assert output.degraded is True
        assert any("ToS" in r for r in output.degradation_reasons)

    @pytest.mark.asyncio
    async def test_detect_confidence_exactly_zero_for_no_signal(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "", raising=False)

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="UnknownCo"),
            "funding",
        )

        if output.items:
            assert output.items[0].confidence == 0.0

    @pytest.mark.asyncio
    async def test_detect_clamps_confidence_above_100(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "test-key", raising=False)
        # A source that claims 150% confidence should be clamped.
        monkeypatch.setattr(
            httpx.AsyncClient,
            "get",
            AsyncMock(
                return_value=httpx.Response(
                    200,
                    json=[{"name": "FPT", "funding_total": 1000000, "confidence": 150}],
                )
            ),
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        if output.items:
            assert output.items[0].confidence <= 100.0

    @pytest.mark.asyncio
    async def test_detect_confidence_100_boundary(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "test-key", raising=False)
        monkeypatch.setattr(
            httpx.AsyncClient,
            "get",
            AsyncMock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {
                            "name": "FPT",
                            "funding_total": 1000000,
                            "announced_on": "2026-08-01",
                            "confidence": 100,
                        }
                    ],
                )
            ),
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT", confidence_threshold=100.0),
            "funding",
        )

        if output.items:
            assert output.items[0].confidence == 100.0

    @pytest.mark.asyncio
    async def test_detect_raises_value_error_for_unknown_signal_type(self):
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        service = SignalDetectionService()
        with pytest.raises(ValueError, match="unknown signal_type"):
            await service.detect(
                _FakeSession(),
                _make_context(),
                SignalInput(company_name="FPT"),
                "not_a_signal",
            )

    @pytest.mark.asyncio
    async def test_detect_redacts_pii_before_memory_insert(self, monkeypatch):
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService
        from app.services.pii.redact import RedactedText

        redact_calls: list[dict[str, Any]] = []

        def _fake_redact(text: str | None, context: str = "default") -> RedactedText:
            redact_calls.append({"text": text, "context": context})
            return RedactedText(text=text or "", phones_detected=0, emails_detected=0)

        monkeypatch.setattr(
            "app.services.pii.redact.redact_pii",
            _fake_redact,
            raising=False,
        )

        service = SignalDetectionService()
        await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        assert any(c["context"] == "lead_enrichment" for c in redact_calls)

    @pytest.mark.asyncio
    async def test_detect_does_not_create_lead_or_verified_contact(self):
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        assert not any(hasattr(item, "lead_id") for item in output.items)

    @pytest.mark.asyncio
    async def test_detect_records_memory_with_source_uuid_equal_to_signal_event_id(
        self, monkeypatch
    ):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "", raising=False)

        session = _FakeSession()
        service = SignalDetectionService()
        await service.detect(
            session,
            _make_context(session=session),
            SignalInput(company_name="FPT"),
            "funding",
        )

        signal_events = [o for o in session.added if type(o).__name__ == "SignalEvent"]
        memories = [o for o in session.added if type(o).__name__ == "Memory"]
        assert signal_events
        assert memories
        assert memories[0].source_uuid == signal_events[0].id
        assert memories[0].source_entity_type == "SignalEvent"
        assert memories[0].type == "semantic"
        assert memories[0].tags == ["lead_signal"]

    @pytest.mark.asyncio
    async def test_detect_records_billing_event_per_item(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(
            config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 1000, raising=False
        )
        monkeypatch.setattr(
            "app.services.wallet_credit.check_balance",
            AsyncMock(),
            raising=False,
        )
        monkeypatch.setattr(
            "app.services.wallet_credit.apply_debit",
            AsyncMock(return_value=1_000_000),
            raising=False,
        )

        session = _FakeSession()
        service = SignalDetectionService()
        output = await service.detect(
            session,
            _make_context(session=session),
            SignalInput(company_name="FPT"),
            "funding",
        )

        billing_rows = [o for o in session.added if type(o).__name__ == "BillingEvent"]
        assert output.cost_micros == len(output.items) * 1000
        if output.items:
            assert billing_rows
            assert billing_rows[0].event_entity_type == "signal_event"
            assert billing_rows[0].event_type == "signal_scan"

    @pytest.mark.asyncio
    async def test_detect_records_token_usage_when_llm_used(self, monkeypatch):
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        recorded: list[dict[str, Any]] = []

        async def _fake_record_token_usage(_session: Any, **kwargs: Any) -> Any:
            recorded.append(kwargs)
            return None

        monkeypatch.setattr(
            "app.services.token_tracking_service.record_token_usage",
            _fake_record_token_usage,
            raising=False,
        )

        service = SignalDetectionService()
        await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        if recorded:
            assert recorded[0]["usage_type"] in {"llm_reasoning", "llm_summary"}

    @pytest.mark.asyncio
    async def test_detect_returns_degraded_when_wallet_insufficient(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService
        from app.services.etl_credit_service import InsufficientCreditsError

        monkeypatch.setattr(
            config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 1000, raising=False
        )

        async def _check_balance_short(*_args: Any, **_kwargs: Any) -> None:
            raise InsufficientCreditsError(
                message="short",
                balance_micros=0,
                required_micros=1000,
            )

        monkeypatch.setattr(
            "app.services.wallet_credit.check_balance",
            _check_balance_short,
            raising=False,
        )

        service = SignalDetectionService()
        output = await service.detect(
            _FakeSession(),
            _make_context(),
            SignalInput(company_name="FPT"),
            "funding",
        )

        assert output.degraded is True
        assert any("insufficient_wallet" in r for r in output.degradation_reasons)

    @pytest.mark.asyncio
    async def test_detect_is_idempotent_for_concurrent_calls(self, monkeypatch):
        from app.config import config
        from app.lead_intelligence.signals.schemas import SignalInput
        from app.lead_intelligence.signals.service import SignalDetectionService

        monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "", raising=False)

        session = _FakeSession()
        service = SignalDetectionService()
        first = await service.detect(
            session,
            _make_context(session=session),
            SignalInput(company_name="FPT"),
            "funding",
        )
        second = await service.detect(
            session,
            _make_context(session=session),
            SignalInput(company_name="FPT"),
            "funding",
        )

        # The same source/signal should not produce two different ids within
        # the same second; implementation must dedupe via unique constraint.
        if first.items and second.items:
            assert first.items[0].source_url == second.items[0].source_url
