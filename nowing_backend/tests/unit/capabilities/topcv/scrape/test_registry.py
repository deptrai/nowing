"""The topcv namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    topcv,  # noqa: F401
)
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.topcv.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_topcv_scrape_is_registered_and_billable():
    cap = get_capability("topcv.scrape")

    assert cap.name == "topcv.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.TOPCV_JOB
