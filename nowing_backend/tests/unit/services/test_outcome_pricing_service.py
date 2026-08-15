"""Unit tests for Outcome-Based Pricing Service (Story 21.7 / AD-42 / AD-48 / FR-69).

Validates first-touch attribution, outcome event recording, $0 chat invariants,
and credit wallet debits for qualified meetings and enriched leads.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.db import (
    BillingEvent,
    Lead,
    OutcomeEvent,
    PricingPlan,
    User,
)
from app.services.etl_credit_service import InsufficientCreditsError
from app.services.outcome_pricing_service import (
    DEFAULT_MEETING_BOOKED_MICROS,
    OutcomePricingService,
)

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

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(
        self,
        *,
        scalar: Any = None,
        scalars: list[Any] | None = None,
        rows: list[Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self._scalar = scalar
        self._scalars = list(scalars) if scalars else None
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        if self._scalars is not None and self._scalars:
            val = self._scalars.pop(0)
            return _FakeResult(val, self._rows)
        return _FakeResult(self._scalar, self._rows)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        pass


@pytest.fixture
def mock_user() -> User:
    user = User()
    user.id = uuid4()
    user.credit_micros_balance = 10_000_000  # $10.00
    user.credit_micros_reserved = 0
    return user


@pytest.fixture
def mock_lead() -> Lead:
    lead = Lead()
    lead.id = uuid4()
    lead.workspace_id = 1
    lead.company_name = "Acme Corp"
    lead.source = "batdongsan"
    lead.source_url = "https://batdongsan.com.vn/item-1"
    return lead


@pytest.mark.asyncio
async def test_resolve_first_touch_attribution_sequence(mock_lead: Lead) -> None:
    """When a lead has an enrolled sequence, attribution points to first sequence."""
    seq_id = uuid4()
    session = _FakeSession()
    service = OutcomePricingService(session)

    with patch.object(
        service,
        "_find_earliest_sequence_enrollment",
        new=AsyncMock(return_value=seq_id),
    ):
        attr = await service.resolve_first_touch_attribution(mock_lead.id)
        assert attr == f"sequence:{seq_id}"


@pytest.mark.asyncio
async def test_resolve_first_touch_attribution_scraper_fallback(
    mock_lead: Lead,
) -> None:
    """When no sequence exists, attribution falls back to lead source."""
    session = _FakeSession(scalar=mock_lead)
    service = OutcomePricingService(session)

    with patch.object(
        service,
        "_find_earliest_sequence_enrollment",
        new=AsyncMock(return_value=None),
    ):
        attr = await service.resolve_first_touch_attribution(mock_lead.id)
        assert attr == "source:batdongsan"


@pytest.mark.asyncio
async def test_record_meeting_outcome_success(mock_user: User, mock_lead: Lead) -> None:
    """Meeting outcome debits 50 credits (2,000,000 micros), creates OutcomeEvent and BillingEvent."""
    session = _FakeSession(scalars=[mock_lead, None])
    service = OutcomePricingService(session)

    with (
        patch("app.services.wallet_credit.check_balance", new=AsyncMock()),
        patch(
            "app.services.wallet_credit.apply_debit",
            new=AsyncMock(return_value=8_000_000),
        ),
        patch.object(
            service,
            "get_workspace_rate",
            new=AsyncMock(return_value=DEFAULT_MEETING_BOOKED_MICROS),
        ),
    ):
        result = await service.record_meeting_booked(
            workspace_id=1,
            lead_id=mock_lead.id,
            user_id=mock_user.id,
            attribution=f"source:{mock_lead.source}",
            metadata={"meeting_title": "Demo Call", "calendar_provider": "google"},
        )

        assert result.cost_micros == DEFAULT_MEETING_BOOKED_MICROS
        assert result.event_type == "outcome_meeting_booked"
        assert result.workspace_id == 1
        assert session.committed is True

        # Assert OutcomeEvent was added
        outcome_events = [obj for obj in session.added if isinstance(obj, OutcomeEvent)]
        assert len(outcome_events) == 1
        assert outcome_events[0].cost_micros == DEFAULT_MEETING_BOOKED_MICROS

        # Assert BillingEvent was added with AD-42 / AD-48 matrix
        billing_events = [obj for obj in session.added if isinstance(obj, BillingEvent)]
        assert len(billing_events) == 1
        assert billing_events[0].event_entity_type == "outcome_event"
        assert billing_events[0].event_type == "outcome_meeting_booked"
        assert billing_events[0].event_id == outcome_events[0].id
        assert billing_events[0].cost_basis == "actual"


@pytest.mark.asyncio
async def test_record_meeting_outcome_insufficient_credits(
    mock_user: User, mock_lead: Lead
) -> None:
    """When wallet balance is insufficient, raises InsufficientCreditsError and rolls back."""
    session = _FakeSession(scalars=[mock_lead, None])
    service = OutcomePricingService(session)

    with (
        patch(
            "app.services.wallet_credit.check_balance",
            new=AsyncMock(side_effect=InsufficientCreditsError("Balance too low")),
        ),
        patch.object(
            service,
            "get_workspace_rate",
            new=AsyncMock(return_value=DEFAULT_MEETING_BOOKED_MICROS),
        ),
    ):
        with pytest.raises(InsufficientCreditsError):
            await service.record_meeting_booked(
                workspace_id=1,
                lead_id=mock_lead.id,
                user_id=mock_user.id,
                attribution="direct_chat",
            )

        assert session.committed is False


@pytest.mark.asyncio
async def test_custom_pricing_plan_rates() -> None:
    """Workspace custom PricingPlan overrides standard default rates."""
    plan = PricingPlan()
    plan.workspace_id = 42
    plan.plan_type = "hybrid"
    plan.outcome_rates_json = {
        "meeting_booked": 3_000_000,  # $3.00 custom
        "phone_unlock": 50_000,
    }
    session = _FakeSession(scalar=plan)
    service = OutcomePricingService(session)

    rate = await service.get_workspace_rate(
        workspace_id=42, event_type="meeting_booked"
    )
    assert rate == 3_000_000


@pytest.mark.asyncio
async def test_zero_cost_chat_invariants() -> None:
    """$0 Chat policy guarantees customer debit is 0 for standard chat turns."""
    session = _FakeSession()
    service = OutcomePricingService(session)

    is_zero_cost = service.is_zero_cost_action("standard_chat_turn")
    assert is_zero_cost is True

    is_zero_cost_table = service.is_zero_cost_action("table_transform")
    assert is_zero_cost_table is True

    is_zero_cost_export = service.is_zero_cost_action("csv_export")
    assert is_zero_cost_export is True

    is_billable = service.is_zero_cost_action("outcome_meeting_booked")
    assert is_billable is False
