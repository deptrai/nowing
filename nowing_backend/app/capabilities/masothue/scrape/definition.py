"""Register the ``masothue.scrape`` capability."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

MASOTHUE_SCRAPE = Capability(
    name="masothue.scrape",
    description=(
        "Scrape Vietnamese company profiles from masothue.com by company name, "
        "tax code, or representative. Returns company name, tax code, address, "
        "status, company type, main industry and other directory fields."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.MASOTHUE_COMPANY,
    context_aware=True,
    docs_url="/docs/connectors/native/masothue",
)

register_capability(MASOTHUE_SCRAPE)
