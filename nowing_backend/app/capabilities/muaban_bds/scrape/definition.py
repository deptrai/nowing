"""Muaban BĐS ``scrape`` capability registration."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.core.types import BillingUnit

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

MUABAN_BDS_SCRAPE = Capability(
    name="muaban_bds.scrape",
    description="Scrape real-estate listings from Muaban.net (buy/rent, city, district).",
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.MUABAN_BDS_ITEM,
)

register_capability(MUABAN_BDS_SCRAPE)
