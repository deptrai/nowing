"""Red-phase ATDD tests for the five signal capabilities (Story 21.1).

Covers capability registration, metadata, and executor wiring. All external
sources are mocked; no real DB is required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.capabilities.core.store import CapabilityRegistry, get_capability
from app.capabilities.core.types import Capability, CapabilityContext

pytestmark = pytest.mark.unit


class _FakeSession:
    """Lightweight stand-in for ``AsyncSession``."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> Any:
        return _FakeResult()

    async def commit(self) -> None:
        self.committed = True


class _FakeResult:
    def scalar_one_or_none(self) -> Any:
        return None

    def first(self) -> Any:
        return None

    def all(self) -> list[Any]:
        return []


def _make_context(session: _FakeSession | None = None, workspace_id: int = 1) -> Any:
    return CapabilityContext(
        session=session or _FakeSession(),
        workspace_id=workspace_id,
        run_id="run-cap-test",
    )


SIGNAL_CAPABILITY_NAMES = [
    "funding.signal",
    "hiring.signal",
    "tech_stack.signal",
    "executive_move.signal",
    "news.signal",
]


class TestSignalCapabilityRegistration:
    """AC-5: each signal source is registered with correct metadata."""

    def test_funding_signal_capability_is_registered(self):
        from app.capabilities.funding.signal.definition import FUNDING_SIGNAL

        assert FUNDING_SIGNAL.name == "funding.signal"
        assert FUNDING_SIGNAL.billing_unit is None
        assert FUNDING_SIGNAL.metadata == {
            "emits_signals": True,
            "signal_types": ["funding"],
        }

    def test_hiring_signal_capability_is_registered(self):
        from app.capabilities.hiring.signal.definition import HIRING_SIGNAL

        assert HIRING_SIGNAL.name == "hiring.signal"
        assert HIRING_SIGNAL.billing_unit is None
        assert HIRING_SIGNAL.metadata == {
            "emits_signals": True,
            "signal_types": ["hiring"],
        }

    def test_tech_stack_signal_capability_is_registered(self):
        from app.capabilities.tech_stack.signal.definition import TECH_STACK_SIGNAL

        assert TECH_STACK_SIGNAL.name == "tech_stack.signal"
        assert TECH_STACK_SIGNAL.billing_unit is None
        assert TECH_STACK_SIGNAL.metadata == {
            "emits_signals": True,
            "signal_types": ["tech_stack"],
        }

    def test_executive_move_signal_capability_is_registered(self):
        from app.capabilities.executive_move.signal.definition import (
            EXECUTIVE_MOVE_SIGNAL,
        )

        assert EXECUTIVE_MOVE_SIGNAL.name == "executive_move.signal"
        assert EXECUTIVE_MOVE_SIGNAL.billing_unit is None
        assert EXECUTIVE_MOVE_SIGNAL.metadata == {
            "emits_signals": True,
            "signal_types": ["executive_move"],
        }

    def test_news_signal_capability_is_registered(self):
        from app.capabilities.news.signal.definition import NEWS_SIGNAL

        assert NEWS_SIGNAL.name == "news.signal"
        assert NEWS_SIGNAL.billing_unit is None
        assert NEWS_SIGNAL.metadata == {
            "emits_signals": True,
            "signal_types": ["news"],
        }

    def test_registry_get_returns_funding_signal(self):
        cap = get_capability("funding.signal")
        assert cap.name == "funding.signal"

    def test_all_signal_capabilities_have_billing_unit_none(self):
        for name in SIGNAL_CAPABILITY_NAMES:
            cap = get_capability(name)
            assert cap.billing_unit is None

    def test_all_signal_capabilities_emits_signals_metadata(self):
        for name in SIGNAL_CAPABILITY_NAMES:
            cap = get_capability(name)
            assert cap.metadata.get("emits_signals") is True
            assert isinstance(cap.metadata.get("signal_types"), list)

    def test_query_metadata_emits_signals_returns_all_five(self):
        from app.capabilities import (
            executive_move,  # noqa: F401
            funding,  # noqa: F401
            hiring,  # noqa: F401
            news,  # noqa: F401
            tech_stack,  # noqa: F401
        )

        found = CapabilityRegistry.query_metadata("emits_signals")
        for name in SIGNAL_CAPABILITY_NAMES:
            assert name in found
            assert found[name] is True


class TestSignalCapabilityRegistryValidation:
    """AC-5: registry validates signal capability metadata."""

    def test_registry_rejects_metadata_emits_signals_not_boolean(self):
        bad = Capability(
            name="bad.signal",
            description="Bad signal capability.",
            input_schema=dict,  # type: ignore[arg-type]
            output_schema=dict,  # type: ignore[arg-type]
            executor=AsyncMock(),
            billing_unit=None,
            metadata={"emits_signals": "yes", "signal_types": ["bad"]},
        )

        with pytest.raises(ValueError, match="emits_signals must be boolean"):
            CapabilityRegistry.register(bad)

    def test_registry_rejects_empty_signal_types(self):
        bad = Capability(
            name="empty.signal",
            description="Empty signal types.",
            input_schema=dict,  # type: ignore[arg-type]
            output_schema=dict,  # type: ignore[arg-type]
            executor=AsyncMock(),
            billing_unit=None,
            metadata={"emits_signals": True, "signal_types": []},
        )

        with pytest.raises(ValueError, match="signal_types must not be empty"):
            CapabilityRegistry.register(bad)

    def test_registry_accepts_multiple_signal_types(self):
        cap = Capability(
            name="multi.signal",
            description="Multi signal capability.",
            input_schema=dict,  # type: ignore[arg-type]
            output_schema=dict,  # type: ignore[arg-type]
            executor=AsyncMock(),
            billing_unit=None,
            metadata={"emits_signals": True, "signal_types": ["funding", "news"]},
        )

        CapabilityRegistry.register(cap)
        assert get_capability("multi.signal").metadata["signal_types"] == [
            "funding",
            "news",
        ]

    def test_registry_rejects_duplicate_capability(self):
        from app.capabilities.funding.signal.definition import FUNDING_SIGNAL

        with pytest.raises(
            ValueError, match=r"already registered|Action already registered"
        ):
            CapabilityRegistry.register(FUNDING_SIGNAL)


class TestSignalCapabilityExecutor:
    """AC-1/AC-5: executor routes to ``SignalDetectionService``."""

    @pytest.mark.asyncio
    async def test_funding_executor_calls_signal_detection_service(self, monkeypatch):
        from app.capabilities.funding.signal.executor import build_signal_executor
        from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

        ctx = _make_context()
        payload = SignalInput(company_name="FPT")

        captured: dict[str, Any] = {}

        async def _fake_detect(
            self: Any,
            session: Any,
            _ctx: Any,
            _company_name: str,
            signal_type: str,
            **kwargs: Any,
        ) -> SignalOutput:
            captured["session"] = session
            captured["signal_type"] = signal_type
            captured["kwargs"] = kwargs
            return SignalOutput(
                items=[],
                cost_micros=0,
                degraded=False,
            )

        monkeypatch.setattr(
            "app.lead_intelligence.signals.service.SignalDetectionService.detect",
            _fake_detect,
            raising=False,
        )

        execute = build_signal_executor("funding")
        output = await execute(payload, ctx)

        assert captured["signal_type"] == "funding"
        assert isinstance(output, SignalOutput)

    @pytest.mark.asyncio
    async def test_funding_executor_returns_degraded_output(self, monkeypatch):
        from app.capabilities.funding.signal.executor import build_signal_executor
        from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

        ctx = _make_context()
        payload = SignalInput(company_name="FPT")

        async def _fake_detect(*_args: Any, **_kwargs: Any) -> SignalOutput:
            return SignalOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reasons=["crunchbase.timeout"],
            )

        monkeypatch.setattr(
            "app.lead_intelligence.signals.service.SignalDetectionService.detect",
            _fake_detect,
            raising=False,
        )

        execute = build_signal_executor("funding")
        output = await execute(payload, ctx)

        assert output.degraded is True
        assert output.degradation_reasons == ["crunchbase.timeout"]

    @pytest.mark.asyncio
    async def test_hiring_executor_resolves_company_name(self, monkeypatch):
        from app.capabilities.hiring.signal.executor import build_signal_executor
        from app.lead_intelligence.signals.schemas import (
            SignalEventRead,
            SignalInput,
            SignalOutput,
        )

        ctx = _make_context()
        payload = SignalInput(company_name="FPT")

        async def _fake_detect(*_args: Any, **_kwargs: Any) -> SignalOutput:
            return SignalOutput(
                items=[
                    SignalEventRead(
                        id=uuid4(),
                        workspace_id=1,
                        client_id=None,
                        company_name="FPT",
                        signal_type="hiring",
                        source_url="https://example.com/jobs",
                        chunk_id=None,
                        confidence=70.0,
                        detected_at=datetime.now(UTC),
                        processed=False,
                    )
                ],
                cost_micros=1000,
                degraded=False,
            )

        monkeypatch.setattr(
            "app.lead_intelligence.signals.service.SignalDetectionService.detect",
            _fake_detect,
            raising=False,
        )

        execute = build_signal_executor("hiring")
        output = await execute(payload, ctx)

        assert output.items[0].company_name == "FPT"
        assert output.items[0].signal_type == "hiring"

    @pytest.mark.asyncio
    async def test_executor_rejects_unknown_signal_type(self):
        from app.capabilities.funding.signal.executor import build_signal_executor

        with pytest.raises(ValueError, match="unknown signal_type"):
            build_signal_executor("not_a_signal")


class TestSignalCapabilitySchemas:
    """AC-1/AC-5: each capability uses the shared signal schemas."""

    def test_funding_capability_uses_signal_input_and_output_schemas(self):
        from app.capabilities.funding.signal.definition import FUNDING_SIGNAL
        from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

        assert FUNDING_SIGNAL.input_schema is SignalInput
        assert FUNDING_SIGNAL.output_schema is SignalOutput

    def test_hiring_capability_uses_signal_input_and_output_schemas(self):
        from app.capabilities.hiring.signal.definition import HIRING_SIGNAL
        from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

        assert HIRING_SIGNAL.input_schema is SignalInput
        assert HIRING_SIGNAL.output_schema is SignalOutput
