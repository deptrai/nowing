"""The walmart.reviews capability registers as a billed verb."""

from __future__ import annotations

import pytest

from app.capabilities import walmart  # noqa: F401
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.walmart.reviews.schemas import ReviewsInput, ReviewsOutput

pytestmark = pytest.mark.unit


def test_walmart_reviews_is_registered_and_billable():
    cap = get_capability("walmart.reviews")

    assert cap.name == "walmart.reviews"
    assert cap.input_schema is ReviewsInput
    assert cap.output_schema is ReviewsOutput
    assert cap.billing_unit is BillingUnit.WALMART_REVIEW
