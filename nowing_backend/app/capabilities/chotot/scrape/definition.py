"""``chotot_bds.scrape`` capability registration (billed per item)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

CHOTOT_BDS_SCRAPE = Capability(
    name="chotot_bds.scrape",
    description=(
        "Scrape real-estate listings from Chợ Tốt Nhà (nha.chotot.com). "
        "Use buy/rent listing_type, property_type (apartment/house/land/office/all), "
        "city (e.g. 'hanoi', 'ho chi minh', 'da nang'), and optional district/area_v2."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.CHOTOT_BDS_ITEM,
    docs_url="/docs/connectors/native/chotot_bds",
)

register_capability(CHOTOT_BDS_SCRAPE)
