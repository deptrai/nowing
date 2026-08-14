"""Chợ Tốt scraper capability registration (billed per item)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

CHOTOT_SCRAPE = Capability(
    name="chotot.scrape",
    description=(
        "Scrape listings from Chợ Tốt (chotot.com, nhatot.com, xe.chotot.com, "
        "vieclamtot.com) across categories: bds, cars, motorbikes, electronics, "
        "jobs, pets, fashion, home_goods, home_appliances, kitchen, services, "
        "home_services, or a raw numeric gateway category code (cg). "
        "Use listing_type sell/rent/want_to_buy and property_type for BĐS."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.CHOTOT_ITEM,
    docs_url="/docs/connectors/native/chotot",
)

# Deprecated alias; kept for backward compatibility.
CHOTOT_BDS_SCRAPE = Capability(
    name="chotot_bds.scrape",
    description=(
        "Deprecated alias for chotot.scrape with category=\"bds\". "
        "Use chotot.scrape instead."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(
        rate_attr="CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM",
        locked_category="bds",
    ),
    billing_unit=BillingUnit.CHOTOT_BDS_ITEM,
    docs_url="/docs/connectors/native/chotot",
)

register_capability(CHOTOT_SCRAPE)
register_capability(CHOTOT_BDS_SCRAPE)
