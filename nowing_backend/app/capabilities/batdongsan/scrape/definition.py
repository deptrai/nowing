"""``batdongsan.scrape`` capability registration (billed per item)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.proprietary.platforms.batdongsan.fetch import fetch_web_listings

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

BATDONGSAN_SCRAPE = Capability(
    name="batdongsan.scrape",
    description=(
        "Scrape real-estate listings from batdongsan.com.vn. Use buy/rent "
        "listing_type, city code (HN, SG, HP, BD, KH, PT, LA, HY, QNG, TN, TG "
        "via mobile API; other provinces via web fallback when available), "
        "and optional district_id."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(web_fetch_fn=fetch_web_listings),
    billing_unit=BillingUnit.BATDONGSAN_ITEM,
    docs_url="/docs/connectors/native/batdongsan",
)

register_capability(BATDONGSAN_SCRAPE)
