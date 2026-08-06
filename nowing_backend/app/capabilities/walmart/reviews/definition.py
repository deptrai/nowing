"""``walmart.reviews`` capability registration (billed per review)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_reviews_executor
from .schemas import ReviewsInput, ReviewsOutput

WALMART_REVIEWS = Capability(
    name="walmart.reviews",
    description=(
        "Fetch paginated customer reviews for a Walmart product. "
        "Returns review text, rating, date, and verified status. "
        "May degrade if anti-bot protection blocks access."
    ),
    input_schema=ReviewsInput,
    output_schema=ReviewsOutput,
    executor=build_reviews_executor(),
    billing_unit=BillingUnit.WALMART_REVIEW,
    docs_url="/docs/connectors/native/walmart",
)

register_capability(WALMART_REVIEWS)
