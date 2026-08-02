"""``batdongsan.scrape`` capability registration (billed per item)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

BATDONGSAN_SCRAPE = Capability(
    name="batdongsan.scrape",
    description=(
        "Scrape real-estate listings from batdongsan.com.vn. Use buy/rent "
        "listing_type, city code (HN, SG, HP, CT), and optional district_id."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.BATDONGSAN_ITEM,
    docs_url="/docs/connectors/native/batdongsan",
)

register_capability(BATDONGSAN_SCRAPE)
