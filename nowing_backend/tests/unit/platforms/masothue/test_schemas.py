"""Unit tests for masothue proprietary schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.proprietary.platforms.masothue.schemas import (
    MasothueCompany,
    MasothueScrapeOutput,
    MasothueSearchInput,
)

pytestmark = pytest.mark.unit


def test_search_input_defaults() -> None:
    inp = MasothueSearchInput(query="vinamilk")

    assert inp.search_type == "auto"
    assert inp.tax_code is None
    assert inp.max_pages == 5
    assert inp.max_items == 10
    assert inp.resolve_detail is True
    assert inp.include_phone is False
    assert inp.estimated_units == 10


def test_search_input_rejects_negative_max_pages() -> None:
    with pytest.raises(ValidationError):
        MasothueSearchInput(query="vinamilk", max_pages=-1)


def test_search_input_rejects_negative_max_items() -> None:
    with pytest.raises(ValidationError):
        MasothueSearchInput(query="vinamilk", max_items=-1)


def test_company_to_output_keeps_none_fields() -> None:
    company = MasothueCompany(name="Vinamilk", tax_code=None)
    output = company.to_output()

    assert output["name"] == "Vinamilk"
    assert "tax_code" in output
    assert output["tax_code"] is None


def test_scrape_output_defaults_and_billable_units() -> None:
    out = MasothueScrapeOutput()

    assert out.items == []
    assert out.total_items == 0
    assert out.degraded is False
    assert out.degradation_reason is None
    assert out.billable_units == 0
