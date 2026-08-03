"""Unit tests for the Muaban BĐS fetcher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.proprietary.platforms.muaban_bds.fetch import (
    MuabanBdsDecodeError,
    MuabanBdsRateLimitedError,
    extract_next_data,
    fetch_page,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"


def _html(name: str) -> str:
    return (FIXTURES / name).with_suffix(".html").read_text(encoding="utf-8")


def test_extract_next_data_from_html():
    data = extract_next_data(_html("hcm_city"))
    assert "props" in data


def test_extract_next_data_missing_payload():
    with pytest.raises(MuabanBdsDecodeError):
        extract_next_data("<html><body>nothing</body></html>")


def test_extract_next_data_malformed_json():
    html = '<script id="__NEXT_DATA__">{not valid</script>'
    with pytest.raises(MuabanBdsDecodeError):
        extract_next_data(html)


@pytest.mark.asyncio
async def test_fetch_page_with_mock_session():
    html = _html("hcm_city")
    response = MagicMock()
    response.status = 200
    response.body = html.encode("utf-8")

    session = MagicMock()
    session.fetch = AsyncMock(return_value=response)

    data = await fetch_page("https://muaban.net/test", session=session)
    assert "props" in data
    session.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_page_rate_limited():
    response = MagicMock()
    response.status = 429

    session = MagicMock()
    session.fetch = AsyncMock(return_value=response)

    with pytest.raises(MuabanBdsRateLimitedError):
        await fetch_page("https://muaban.net/test", session=session)


@pytest.mark.asyncio
async def test_fetch_page_not_found():
    response = MagicMock()
    response.status = 404

    session = MagicMock()
    session.fetch = AsyncMock(return_value=response)

    data = await fetch_page("https://muaban.net/test", session=session)
    assert data.get("notFound") is True
