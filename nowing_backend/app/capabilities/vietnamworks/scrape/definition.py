"""``vietnamworks.scrape`` capability registration (billed per job)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

VIETNAMWORKS_SCRAPE = Capability(
    name="vietnamworks.scrape",
    description=(
        "Search public VietnamWorks job postings by keyword, location, salary, "
        "and employment type. Returns typed job listings. Does not apply or "
        "submit CVs."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.VIETNAMWORKS_JOB,
    docs_url="/docs/connectors/native/vn_jobs",
)

register_capability(VIETNAMWORKS_SCRAPE)
