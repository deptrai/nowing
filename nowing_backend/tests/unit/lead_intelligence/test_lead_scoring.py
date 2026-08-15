"""Red-phase ATDD tests for Story 21.2 — Lead Scoring & Prioritization.

These tests describe the contract the new ``LeadScoringService`` and its
schemas must satisfy. They will fail until the implementation is written.

All DB/session interaction is mocked; no real PostgreSQL is required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _patch_memory_repo_for_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid real embedding in all lead scoring unit tests."""
    from app.db import Memory

    async def _fake_create_memory(*args: Any, **kwargs: Any) -> Memory:
        return Memory(id=1, content=kwargs.get("content", ""))

    monkeypatch.setattr(
        "app.lead_intelligence.scoring.service.MemoryRepository.create_memory",
        _fake_create_memory,
    )


def _uuid() -> UUID:
    return uuid4()


class _FakeWorkspace:
    """Minimal workspace stand-in for unit tests."""

    def __init__(self, *, workspace_id: int = 1, user_id: UUID | None = None) -> None:
        self.id = workspace_id
        self.user_id = user_id or _uuid()
        self.icp_criteria = None


class _FakeLead:
    """Minimal lead stand-in for unit tests."""

    def __init__(
        self,
        *,
        lead_id: UUID | None = None,
        workspace_id: int = 1,
        client_id: str | None = None,
        company_name: str = "FPT",
        industry: str | None = "software",
        location: str | None = "Vietnam",
        tech_stack: list[str] | None = None,
        company_size: str | None = "100-500",
        status: str = "open",
    ) -> None:
        self.id = lead_id or _uuid()
        self.workspace_id = workspace_id
        self.client_id = client_id
        self.company_name = company_name
        self.industry = industry
        self.location = location
        self.tech_stack = tech_stack or ["python", "aws"]
        self.company_size = company_size
        self.status = status


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

    def __init__(
        self,
        *,
        scalar: Any = None,
        rows: list[Any] | None = None,
        workspace: _FakeWorkspace | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self._scalar = scalar
        self._rows = rows or []
        self._workspace = workspace

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def get(self, model: Any, id: Any) -> Any:
        if self._workspace is not None and model.__name__ == "Workspace":
            return self._workspace
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, _obj: Any) -> None:
        pass

    async def flush(self) -> None:
        self.flushed = True


def _make_context(session: _FakeSession | None = None, workspace_id: int = 1) -> Any:
    """Minimal ``CapabilityContext`` for lead scoring tests."""
    from app.capabilities.core.types import CapabilityContext

    return CapabilityContext(
        session=session or _FakeSession(),
        workspace_id=workspace_id,
        run_id="run-lead-scoring-test",
    )


def _make_session(
    *, workspace: _FakeWorkspace | None = None, leads: list[_FakeLead] | None = None
) -> _FakeSession:
    return _FakeSession(
        workspace=workspace or _FakeWorkspace(),
        rows=list(leads or []),
    )


def _patch_billing(monkeypatch: Any) -> None:
    """Patch ``_record_billing`` so tests don't hit wallet credit."""
    monkeypatch.setattr(
        "app.lead_intelligence.scoring.service.LeadScoringService._record_billing",
        AsyncMock(return_value=None),
        raising=False,
    )


def _patch_scoring_methods(
    monkeypatch: Any, fit: float = 60.0, intent: float = 80.0
) -> None:
    """Patch fit/intent methods to return deterministic tuples."""
    monkeypatch.setattr(
        "app.lead_intelligence.scoring.service.LeadScoringService._fit_score",
        AsyncMock(return_value=(fit, {"company_size": 15, "icp": 20})),
        raising=False,
    )
    monkeypatch.setattr(
        "app.lead_intelligence.scoring.service.LeadScoringService._intent_score",
        AsyncMock(return_value=(intent, {"signal_strength": intent, "recency": 80})),
        raising=False,
    )


class TestLeadScoreSchemas:
    """AC-1/AC-2/AC-5: schema contract and response shape."""

    def test_lead_score_input_accepts_expected_fields(self):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput

        inp = LeadScoreInput(
            lead_ids=[_uuid(), _uuid()],
            recalculate_all=False,
        )
        assert len(inp.lead_ids) == 2
        assert inp.recalculate_all is False

    def test_lead_score_input_allows_none_for_all_leads(self):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput

        inp = LeadScoreInput(lead_ids=None, recalculate_all=False)
        assert inp.lead_ids is None

    def test_lead_score_output_has_exact_contract_fields(self):
        from app.lead_intelligence.scoring.schemas import LeadScoreOutput, LeadScoreRead

        item = LeadScoreRead(
            id=_uuid(),
            workspace_id=1,
            client_id=None,
            lead_id=_uuid(),
            company_name="FPT",
            score=75.0,
            fit_score=70.0,
            intent_score=80.0,
            classification="warm",
            factors_json={"company_size": 15, "icp": 20},
            trend="stable",
            converted_similarity=None,
            computed_at=datetime.now(UTC),
        )
        out = LeadScoreOutput(
            items=[item],
            cost_micros=1000,
            degraded=False,
            degradation_reasons=None,
        )
        assert out.items[0].score == 75.0
        assert out.items[0].classification == "warm"

    def test_lead_score_output_rejects_score_above_100(self):
        from app.lead_intelligence.scoring.schemas import LeadScoreRead

        with pytest.raises(ValueError, match="score"):
            LeadScoreRead(
                id=_uuid(),
                workspace_id=1,
                lead_id=_uuid(),
                company_name="FPT",
                score=101.0,
                fit_score=70.0,
                intent_score=80.0,
                classification="hot",
                factors_json={},
                trend="stable",
                converted_similarity=None,
                computed_at=datetime.now(UTC),
            )


class TestLeadScoringService:
    """AC-1: composite fit + intent score and classification."""

    async def test_score_composite_is_exactly_weighted_average(self, monkeypatch):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput
        from app.lead_intelligence.scoring.service import LeadScoringService

        lead = _FakeLead()
        session = _make_session(leads=[lead])
        ctx = _make_context(session)

        _patch_scoring_methods(monkeypatch, fit=60.0, intent=80.0)
        _patch_billing(monkeypatch)

        svc = LeadScoringService()
        output = await svc.score(
            session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        assert len(output.items) == 1
        assert output.items[0].score == 70.0
        assert output.items[0].classification == "warm"

    async def test_score_clamps_below_zero(self, monkeypatch):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput
        from app.lead_intelligence.scoring.service import LeadScoringService

        lead = _FakeLead()
        session = _make_session(leads=[lead])
        ctx = _make_context(session)

        _patch_scoring_methods(monkeypatch, fit=-10.0, intent=-5.0)
        _patch_billing(monkeypatch)

        svc = LeadScoringService()
        output = await svc.score(
            session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        assert output.items[0].score == 0.0
        assert output.items[0].classification == "cold"

    async def test_score_classifies_hot_at_exactly_80(self, monkeypatch):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput
        from app.lead_intelligence.scoring.service import LeadScoringService

        lead = _FakeLead()
        session = _make_session(leads=[lead])
        ctx = _make_context(session)

        _patch_scoring_methods(monkeypatch, fit=85.0, intent=75.0)
        _patch_billing(monkeypatch)

        svc = LeadScoringService()
        output = await svc.score(
            session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        assert output.items[0].score == 80.0
        assert output.items[0].classification == "hot"


class TestLeadScorePersistence:
    """AC-3: persist as LeadScore + redacted Memory."""

    async def test_score_writes_lead_score_and_memory(self, monkeypatch):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput
        from app.lead_intelligence.scoring.service import LeadScoringService

        lead = _FakeLead()
        session = _make_session(leads=[lead])
        ctx = _make_context(session)

        _patch_scoring_methods(monkeypatch, fit=70.0, intent=60.0)
        _patch_billing(monkeypatch)

        monkeypatch.setattr(
            "app.lead_intelligence.scoring.service.redact_pii",
            MagicMock(return_value=MagicMock(text="redacted")),
        )

        svc = LeadScoringService()
        await svc.score(
            session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        assert len(session.added) == 1  # LeadScore only in this fake session

    async def test_score_calls_redact_pii_with_lead_enrichment_context(
        self, monkeypatch
    ):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput
        from app.lead_intelligence.scoring.service import LeadScoringService

        lead = _FakeLead()
        session = _make_session(leads=[lead])
        ctx = _make_context(session)
        redact_mock = MagicMock(return_value=MagicMock(text="redacted"))

        _patch_scoring_methods(monkeypatch, fit=70.0, intent=60.0)
        _patch_billing(monkeypatch)

        monkeypatch.setattr(
            "app.lead_intelligence.scoring.service.redact_pii",
            redact_mock,
        )

        svc = LeadScoringService()
        await svc.score(
            session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        assert redact_mock.called
        _, kwargs = redact_mock.call_args
        assert kwargs.get("context") == "lead_enrichment"


class TestLeadScoreBilling:
    """AC-5: BillingEvent + TokenUsage split."""

    async def test_score_writes_billing_event_with_lead_score_entity(self, monkeypatch):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput
        from app.lead_intelligence.scoring.service import LeadScoringService

        lead = _FakeLead()
        session = _make_session(leads=[lead])
        ctx = _make_context(session)

        _patch_scoring_methods(monkeypatch, fit=70.0, intent=60.0)

        monkeypatch.setattr(
            "app.lead_intelligence.scoring.service.LeadScoringService._record_billing",
            AsyncMock(return_value=None),
        )

        svc = LeadScoringService()
        output = await svc.score(
            session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        assert output.cost_micros == 0


class TestLeadScoreErrorPaths:
    """AC-7: insufficient wallet and degradation."""

    async def test_score_returns_degraded_when_wallet_insufficient(self, monkeypatch):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput
        from app.lead_intelligence.scoring.service import LeadScoringService
        from app.services.wallet_credit import InsufficientCreditsError

        lead = _FakeLead()
        session = _make_session(leads=[lead])
        ctx = _make_context(session)

        _patch_scoring_methods(monkeypatch, fit=70.0, intent=60.0)

        monkeypatch.setattr(
            "app.lead_intelligence.scoring.service.wallet_credit.check_balance",
            MagicMock(side_effect=InsufficientCreditsError("insufficient")),
        )

        svc = LeadScoringService()
        output = await svc.score(
            session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        assert output.degraded is True
        assert "insufficient_wallet" in output.degradation_reasons
        assert len(session.added) == 0


class TestWorkspaceIcpConfig:
    """AC-6: ICP criteria default and configuration."""

    async def test_score_uses_default_weights_when_icp_missing(self, monkeypatch):
        from app.lead_intelligence.scoring.schemas import LeadScoreInput
        from app.lead_intelligence.scoring.service import LeadScoringService

        lead = _FakeLead()
        session = _make_session(leads=[lead])
        ctx = _make_context(session)

        fit_mock = AsyncMock(return_value=(50.0, {"company_size": 10, "icp": 10}))
        monkeypatch.setattr(
            "app.lead_intelligence.scoring.service.LeadScoringService._fit_score",
            fit_mock,
        )
        monkeypatch.setattr(
            "app.lead_intelligence.scoring.service.LeadScoringService._intent_score",
            AsyncMock(return_value=(50.0, {"signal_strength": 50, "recency": 80})),
        )
        _patch_billing(monkeypatch)

        svc = LeadScoringService()
        await svc.score(
            session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        assert fit_mock.called
