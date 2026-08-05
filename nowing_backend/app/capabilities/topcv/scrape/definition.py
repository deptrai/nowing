"""``topcv.scrape`` capability registration (billed per job)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_scrape_executor
from .schemas import ScrapeInput, ScrapeOutput

TOPCV_SCRAPE = Capability(
    name="topcv.scrape",
    description=(
        "Search TopCV job postings. May degrade if anti-bot protection blocks "
        "access. Salary data may be partial."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.TOPCV_JOB,
    docs_url="/docs/connectors/native/vn_jobs",
)

register_capability(TOPCV_SCRAPE)
