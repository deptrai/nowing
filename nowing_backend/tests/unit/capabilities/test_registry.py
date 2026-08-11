"""The registry exposes each verb as one Capability entry the doors/agent read from."""

from __future__ import annotations

import pytest

from app.capabilities import (
    web,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core.store import (
    CapabilityRegistry,
    get_capability,
    register_capability,
)
from app.capabilities.core.types import BillingUnit, Capability
from app.capabilities.web.crawl.schemas import CrawlInput, CrawlOutput

pytestmark = pytest.mark.unit


def test_web_crawl_is_registered_with_its_schemas_and_billing_unit():
    cap = get_capability("web.crawl")

    assert cap.name == "web.crawl"
    assert cap.input_schema is CrawlInput
    assert cap.output_schema is CrawlOutput
    assert cap.billing_unit is BillingUnit.WEB_CRAWL


def test_capability_metadata_and_registry_query():
    cap = Capability(
        name="test.signal",
        description="Test signal capability",
        input_schema=CrawlInput,
        output_schema=CrawlOutput,
        executor=None,  # type: ignore[arg-type]
        billing_unit=None,
        metadata={"emits_signals": True, "signal_types": ["funding"]},
    )
    register_capability(cap)

    assert get_capability("test.signal").metadata["emits_signals"] is True
    assert CapabilityRegistry.query_metadata_for("test.signal", "emits_signals") is True
    assert CapabilityRegistry.query_metadata("emits_signals") == {"test.signal": True}
    assert "test.signal" in CapabilityRegistry.query_metadata("signal_types")
