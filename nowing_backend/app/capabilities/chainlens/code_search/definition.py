"""``chainlens.code_search`` capability registration."""

from __future__ import annotations

from app.capabilities.chainlens.code_search.executor import (
    build_code_search_executor,
)
from app.capabilities.chainlens.code_search.schemas import (
    CodeSearchInput,
    CodeSearchOutput,
)
from app.capabilities.core import BillingUnit, Capability, register_capability

CHAINLENS_CODE_SEARCH = Capability(
    name="chainlens.code_search",
    description=(
        "Code snippets + API docs (GitHub/SO/packages). "
        "Use ONLY for programming questions — never for prose."
    ),
    input_schema=CodeSearchInput,
    output_schema=CodeSearchOutput,
    executor=build_code_search_executor(),
    billing_unit=BillingUnit.CHAINLENS_QUERY,
    docs_url="/docs/connectors/native/chainlens-code-search",
    context_aware=True,
)

register_capability(CHAINLENS_CODE_SEARCH)
