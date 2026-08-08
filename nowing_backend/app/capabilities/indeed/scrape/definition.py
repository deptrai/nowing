"""``indeed.scrape`` capability registration (billed per job)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

INDEED_SCRAPE = Capability(
    name="indeed.scrape",
    description=(
        "Search Indeed job postings. May degrade if anti-bot protection blocks "
        "access. Salary and benefits data may be partial."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.INDEED_JOB,
    docs_url="/docs/connectors/native/indeed",
)

register_capability(INDEED_SCRAPE)
