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

    # Boundaries: 0, negative raises ValidationError, exactly 100, exactly 20
    inp_zero = ScrapeInput(query="vinamilk", max_items=0, max_pages=0)
    assert inp_zero.max_items == 0
    assert inp_zero.max_pages == 0
    assert inp_zero.estimated_units == 0

    with pytest.raises(ValidationError):
        ScrapeInput(query="vinamilk", max_items=-5)

    with pytest.raises(ValidationError):
        ScrapeInput(query="vinamilk", max_pages=-2)

    inp_exact = ScrapeInput(query="vinamilk", max_items=100, max_pages=20)
    assert inp_exact.max_items == 100
    assert inp_exact.max_pages == 20

    inp_99 = ScrapeInput(query="vinamilk", max_items=99, max_pages=19)
    assert inp_99.max_items == 99
    assert inp_99.max_pages == 19


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


def test_masothue_scrape_context_aware() -> None:
    """The registered masothue.scrape capability must be context-aware."""
    from app.capabilities.masothue.scrape.definition import MASOTHUE_SCRAPE

    assert MASOTHUE_SCRAPE.context_aware is True
