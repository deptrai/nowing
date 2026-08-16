"""Unit tests for ManualCreditAdjustmentService pure logic.

These tests do not require a database. Database-backed assertions live in
``tests/integration/services/test_manual_credits.py``.
"""

from __future__ import annotations

import pytest

from app.services.manual_credit_service import (
    CREDIT_TO_MICROS,
    DAILY_CREDIT_QUOTA,
    ManualCreditAdjustmentService,
    ManualCreditValidationError,
)

pytestmark = [pytest.mark.unit]


class _FakeSession:
    """Placeholder session for unit tests that only exercise validation."""


def test_credit_micros_conversion() -> None:
    """1 credit = 10_000 micro-USD (i.e. $0.01)."""
    svc = ManualCreditAdjustmentService(_FakeSession())
    assert svc._micros_from_credits(500) == 500 * CREDIT_TO_MICROS
    assert svc._credits_from_micros(5_000_000) == 500


def test_daily_credit_quota_constant() -> None:
    """The guardrail is $10 / 1,000 credits per day."""
    assert DAILY_CREDIT_QUOTA == 1_000


def test_validate_payload_accepted() -> None:
    """AC-1: A valid CREDIT payload passes validation."""
    svc = ManualCreditAdjustmentService(_FakeSession())
    svc._validate_payload(
        amount_credits=500,
        direction="CREDIT",
        reason="Promotional partner top-up",
        ticket_ref="https://zendesk.example.com/tickets/12345",
    )


def test_validate_payload_rejects_invalid_values() -> None:
    """AC-1: Invalid amount, direction, reason, or ticket_ref are rejected."""
    svc = ManualCreditAdjustmentService(_FakeSession())

    with pytest.raises(ManualCreditValidationError):
        svc._validate_payload(
            amount_credits=-10,
            direction="CREDIT",
            reason="Valid reason here",
            ticket_ref="TICKET-1",
        )

    with pytest.raises(ManualCreditValidationError):
        svc._validate_payload(
            amount_credits=100,
            direction="HOLD",
            reason="Valid reason here",
            ticket_ref="TICKET-1",
        )

    with pytest.raises(ManualCreditValidationError):
        svc._validate_payload(
            amount_credits=100,
            direction="DEBIT",
            reason="short",
            ticket_ref="TICKET-1",
        )

    with pytest.raises(ManualCreditValidationError):
        svc._validate_payload(
            amount_credits=100,
            direction="CREDIT",
            reason="Valid reason here",
            ticket_ref="",
        )
