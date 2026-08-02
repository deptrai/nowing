"""Offline tests for the Batdongsan ``p_sync`` fetcher and decode pipeline.

No network. Uses a captured fixture plus hand-built edge cases to exercise the
``gzip → base64 → nibble-swap → Latin-1 JSON`` pipeline.
"""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

import pytest

from app.proprietary.platforms.batdongsan.fetch import (
    BatdongsanAccessBlockedError,
    BatdongsanDecodeError,
    BatdongsanRateLimitedError,
    decode_response,
    fetch_listings,
)

pytestmark = pytest.mark.unit

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_sample() -> dict:
    return json.loads((_FIXTURE_DIR / "sample_p_sync.json").read_text(encoding="utf-8"))


def _nibble_swap(data: bytes) -> bytes:
    return bytes(((b & 0x0F) << 4) | (b >> 4) for b in data)


def _encode_fixture(decoded: dict) -> bytes:
    """Reverse the decoder pipeline to produce the raw response bytes."""
    json_bytes = json.dumps(decoded, ensure_ascii=True).encode("latin-1")
    swapped = _nibble_swap(json_bytes)
    b64_bytes = base64.b64encode(swapped)
    return gzip.compress(b64_bytes)


def test_nibble_swap_is_self_inverse():
    assert _nibble_swap(_nibble_swap(b"hello")) == b"hello"


def test_decode_response_extracts_data_and_meta():
    decoded = _load_sample()
    raw = _encode_fixture(decoded)

    result = decode_response(raw)

    assert result == decoded


def test_decode_response_handles_plain_base64_without_gzip():
    decoded = _load_sample()
    json_bytes = json.dumps(decoded, ensure_ascii=True).encode("latin-1")
    raw = base64.b64encode(_nibble_swap(json_bytes))

    result = decode_response(raw)

    assert result == decoded


def test_decode_response_returns_empty_for_empty_data():
    raw = _encode_fixture({"data": [], "m": None})

    result = decode_response(raw)

    assert result["data"] == []


def test_decode_response_raises_decode_error_for_invalid_bytes():
    with pytest.raises(ValueError):
        decode_response(b"not-valid-data")


def test_decode_response_raises_decode_error_for_gzip_bomb(mocker):
    mocker.patch("app.proprietary.platforms.batdongsan.fetch._MAX_DECODED_BYTES", 1024)
    bomb = gzip.compress(b"\x00" * 8192)
    with pytest.raises(BatdongsanDecodeError, match="size cap"):
        decode_response(bomb)


@pytest.mark.asyncio
async def test_fetch_listings_returns_data(mocker):
    decoded = _load_sample()
    raw = _encode_fixture(decoded)

    mock_page = mocker.MagicMock()
    mock_page.status = 200
    mock_page.content = raw
    mock_post = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
        new_callable=mocker.AsyncMock,
    )
    mock_post.return_value = mock_page

    payload = {"ptype": 38, "city": "HN", "page": 1}
    result = await fetch_listings(payload)

    assert isinstance(result, dict)
    assert "data" in result
    assert len(result["data"]) == 2
    mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_listings_raises_decode_error_without_retrying(mocker):
    mock_page = mocker.MagicMock()
    mock_page.status = 200
    mock_page.content = b"not-valid-data"
    mock_post = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
        new_callable=mocker.AsyncMock,
    )
    mock_post.return_value = mock_page

    with pytest.raises(BatdongsanDecodeError):
        await fetch_listings({"ptype": 38, "city": "HN"})

    mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_listings_404_raises_blocked(mocker):
    mock_page = mocker.MagicMock()
    mock_page.status = 404
    mock_page.content = b""
    mock_post = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
        new_callable=mocker.AsyncMock,
    )
    mock_post.return_value = mock_page
    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")

    with pytest.raises(BatdongsanAccessBlockedError):
        await fetch_listings({"ptype": 38, "city": "HN"})


@pytest.mark.asyncio
async def test_fetch_listings_429_raises_rate_limited(mocker):
    mock_page = mocker.MagicMock()
    mock_page.status = 429
    mock_page.content = b""
    mock_post = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
        new_callable=mocker.AsyncMock,
    )
    mock_post.return_value = mock_page
    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")

    with pytest.raises(BatdongsanRateLimitedError):
        await fetch_listings({"ptype": 38, "city": "HN"})


@pytest.mark.asyncio
async def test_fetch_listings_rotates_on_403_then_succeeds(mocker):
    decoded = _load_sample()
    raw = _encode_fixture(decoded)

    blocked_page = mocker.MagicMock()
    blocked_page.status = 403
    blocked_page.content = b""

    ok_page = mocker.MagicMock()
    ok_page.status = 200
    ok_page.content = raw

    mock_post = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
        new_callable=mocker.AsyncMock,
    )
    mock_post.side_effect = [blocked_page, ok_page]
    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")

    result = await fetch_listings({"ptype": 38, "city": "HN"})

    assert isinstance(result, dict)
    assert mock_post.await_count == 2
