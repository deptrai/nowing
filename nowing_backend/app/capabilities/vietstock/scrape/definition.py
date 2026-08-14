"""Register the ``vietstock.scrape`` capability."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

VIETSTOCK_SCRAPE = Capability(
    name="vietstock.scrape",
    description=(
        "Fetch Vietstock stock quotes and financial statements "
        "for Vietnamese securities."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.VIETSTOCK_DATA,
    docs_url="/docs/connectors/native/vietstock",
)

register_capability(VIETSTOCK_SCRAPE)
