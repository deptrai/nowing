"""``chainlens.contents`` capability registration."""

from __future__ import annotations

from app.capabilities.chainlens.contents.executor import build_contents_executor
from app.capabilities.chainlens.contents.schemas import (
    ContentsInput,
    ContentsOutput,
)
from app.capabilities.core import BillingUnit, Capability, register_capability

CHAINLENS_CONTENTS = Capability(
    name="chainlens.contents",
    description=(
        "Clean page extraction. Use when user gives explicit URL(s) — "
        "\"read this page\", \"what does this doc say\", \"summarize https://…\". "
        "NOT for discovering pages (use chainlens_search to find, then contents "
        "to read)."
    ),
    input_schema=ContentsInput,
    output_schema=ContentsOutput,
    executor=build_contents_executor(),
    billing_unit=BillingUnit.CHAINLENS_QUERY,
    docs_url="/docs/connectors/native/chainlens-contents",
    context_aware=True,
)

register_capability(CHAINLENS_CONTENTS)
