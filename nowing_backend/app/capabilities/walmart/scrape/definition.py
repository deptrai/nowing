"""``walmart.scrape`` capability registration (billed per product)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

WALMART_SCRAPE = Capability(
    name="walmart.scrape",
    description=(
        "Search Walmart product listings or fetch a product detail page. "
        "Returns title, price, rating, seller, availability, and a review summary. "
        "May degrade if anti-bot protection blocks access."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.WALMART_PRODUCT,
    docs_url="/docs/connectors/native/walmart",
)

register_capability(WALMART_SCRAPE)
