"""``itviec.scrape`` capability registration (billed per job)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

ITVIEC_SCRAPE = Capability(
    name="itviec.scrape",
    description=(
        "Search ITviec job postings. Salary is often hidden for non-logged-in "
        "users; confidence may be lower."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.ITVIEC_JOB,
    docs_url="/docs/connectors/native/vn_jobs",
)

register_capability(ITVIEC_SCRAPE)
