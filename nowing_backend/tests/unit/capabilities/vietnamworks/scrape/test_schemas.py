"""Unit tests for ``vietnamworks.scrape`` schemas (Story 12.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.vietnamworks.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


class TestScrapeInputValidation:
    """Schema validation and caps."""

    def test_keyword_required(self):
        with pytest.raises(ValidationError):
            ScrapeInput()

    def test_max_items_defaults_to_50(self):
        inp = ScrapeInput(keyword="data engineer")
        assert inp.max_items == 50

    def test_max_items_clamped_to_100(self):
        inp = ScrapeInput(keyword="data engineer", max_items=200)
        assert inp.max_items == 100

    def test_max_items_rejects_negative(self):
        with pytest.raises(ValidationError):
            ScrapeInput(keyword="data engineer", max_items=-1)

    def test_max_items_zero_allowed(self):
        inp = ScrapeInput(keyword="data engineer", max_items=0)
        assert inp.max_items == 0

    def test_max_pages_clamped_to_config_max(self):
        from app.config import config

        ceiling = getattr(config, "VIETNAMWORKS_MAX_PAGES", 5)
        inp = ScrapeInput(keyword="data engineer", max_pages=ceiling + 10)
        assert inp.max_pages == ceiling

    def test_max_pages_rejects_negative(self):
        with pytest.raises(ValidationError):
            ScrapeInput(keyword="data engineer", max_pages=-1)

    def test_max_pages_zero_allowed(self):
        inp = ScrapeInput(keyword="data engineer", max_pages=0)
        assert inp.max_pages == 0

    def test_salary_min_max_optional(self):
        inp = ScrapeInput(keyword="data engineer", salary_min=10_000_000)
        assert inp.salary_min == 10_000_000
        assert inp.salary_max is None

    def test_employment_type_enum(self):
        with pytest.raises(ValidationError):
            ScrapeInput(keyword="data engineer", employment_type="freelance")

        inp = ScrapeInput(keyword="data engineer", employment_type="full_time")
        assert inp.employment_type == "full_time"

    def test_estimated_units_equals_max_items(self):
        assert ScrapeInput(keyword="data engineer").estimated_units == 50
        assert ScrapeInput(keyword="data engineer", max_items=7).estimated_units == 7


class TestScrapeOutputShape:
    """ScrapeOutput billable behavior."""

    def test_default_output_values(self):
        out = ScrapeOutput()
        assert out.items == []
        assert out.cost_micros == 0
        assert out.degraded is False
        assert out.degradation_reason is None

    def test_total_items_computed_from_items(self):
        out = ScrapeOutput(items=[{"id": "1"}, {"id": "2"}])
        assert out.total_items == 2

    def test_total_items_serialized_in_model_dump(self):
        out = ScrapeOutput(items=[{"id": "1"}, {"id": "2"}])
        assert "total_items" in out.model_dump()

    def test_billable_units_is_len_items(self):
        out = ScrapeOutput(items=[{"id": "1"}, {"id": "2"}])
        assert out.billable_units == 2

    def test_degraded_output_values(self):
        out = ScrapeOutput(degraded=True, degradation_reason="rate_limited")
        assert out.degraded is True
        assert out.degradation_reason == "rate_limited"

    def test_rejects_empty_keyword(self):
        with pytest.raises(ValidationError):
            ScrapeInput(keyword="")

    def test_rejects_whitespace_only_keyword(self):
        with pytest.raises(ValidationError):
            ScrapeInput(keyword="   ")

    def test_rejects_negative_salary_min(self):
        with pytest.raises(ValidationError):
            ScrapeInput(keyword="data", salary_min=-1)

    def test_rejects_salary_max_below_salary_min(self):
        with pytest.raises(ValidationError):
            ScrapeInput(keyword="data", salary_min=10_000_000, salary_max=5_000_000)

    def test_max_pages_defaults_to_five(self):
        inp = ScrapeInput(keyword="data")
        assert inp.max_pages == 5
