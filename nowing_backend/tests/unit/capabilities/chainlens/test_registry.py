from __future__ import annotations

import pytest

from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability

pytestmark = pytest.mark.unit


def test_chainlens_research_is_registered_and_metered():
    capability = get_capability("chainlens.research")

    assert capability.input_schema is ResearchInput
    assert capability.output_schema is ResearchOutput
    assert capability.billing_unit is BillingUnit.CHAINLENS_QUERY
