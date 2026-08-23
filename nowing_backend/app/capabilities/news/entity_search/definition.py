"""``news.entity_search`` capability registration."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.news.entity_search.executor import build_entity_search_executor
from app.capabilities.news.entity_search.schemas import (
    EntitySearchInput,
    EntitySearchOutput,
)

NEWS_ENTITY_SEARCH = Capability(
    name="news.entity_search",
    description=(
        "Search news articles mentioning a specific named entity (person, organization, "
        "location) across indexed news portals."
    ),
    input_schema=EntitySearchInput,
    output_schema=EntitySearchOutput,
    executor=build_entity_search_executor(),
    billing_unit=BillingUnit.CHAINLENS_QUERY,
    docs_url="/docs/capabilities/news/entity-search",
    context_aware=True,
)

register_capability(NEWS_ENTITY_SEARCH)
