"""The vietnamworks namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    vietnamworks,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.vietnamworks.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_vietnamworks_scrape_is_registered_and_billable():
    cap = get_capability("vietnamworks.scrape")

    assert cap.name == "vietnamworks.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.VIETNAMWORKS_JOB


def test_vietnamworks_scrape_appears_on_rest_router():
    """The registered verb appears as a generated POST route."""
    import app.capabilities.vietnamworks  # noqa: F401  (registers vietnamworks.*)
    from app.capabilities.core.access import rest

    router = rest.build_capabilities_router()
    paths = {route.path for route in router.routes}
    assert "/workspaces/{workspace_id}/scrapers/vietnamworks/scrape" in paths
