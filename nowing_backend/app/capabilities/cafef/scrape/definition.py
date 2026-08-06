"""Register the ``cafef.scrape`` capability."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

CAFEF_SCRAPE = Capability(
    name="cafef.scrape",
    description=(
        "Fetch CafeF stock quotes, financial statements, and market news "
        "for Vietnamese securities."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.CAFEF_DATA,
    docs_url="/docs/connectors/native/cafef",
)

register_capability(CAFEF_SCRAPE)
