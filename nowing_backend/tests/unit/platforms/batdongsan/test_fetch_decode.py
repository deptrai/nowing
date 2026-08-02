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

from app.proprietary.platforms.batdongsan.fetch import decode_response, fetch_listings

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
