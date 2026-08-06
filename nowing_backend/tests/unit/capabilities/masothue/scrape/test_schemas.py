"""Unit tests for masothue.scrape schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.masothue.scrape.schemas import ScrapeInput

pytestmark = pytest.mark.unit


def test_scrape_input_clamps_max_items_and_pages() -> None:
    inp = ScrapeInput(query="vinamilk", max_items=200, max_pages=50)
    assert inp.max_items == 100
    assert inp.max_pages == 20
    assert inp.estimated_units == 100


def test_scrape_input_accepts_valid_search_type() -> None:
    inp = ScrapeInput(query="vinamilk", search_type="enterpriseTax")
    assert inp.search_type == "enterpriseTax"


def test_scrape_input_rejects_invalid_search_type() -> None:
    with pytest.raises(ValidationError):
        ScrapeInput(query="vinamilk", search_type="invalid")


def test_scrape_input_estimated_units() -> None:
    inp = ScrapeInput(query="vinamilk", max_items=25)
    assert inp.estimated_units == 25



@pytest.mark.asyncio
async def test_scrape_default_max_pages_is_five() -> None:
    """ScrapeInput / MasothueSearchInput defaults must match the spec."""
    from app.capabilities.masothue.scrape.schemas import ScrapeInput
    from app.proprietary.platforms.masothue.schemas import MasothueSearchInput

    public = ScrapeInput(query="vinamilk")
    proprietary = MasothueSearchInput(query="vinamilk")

    assert public.max_pages == 5
    assert public.max_items == 10
    assert public.resolve_detail is True
    assert proprietary.max_pages == 5
    assert proprietary.max_items == 10