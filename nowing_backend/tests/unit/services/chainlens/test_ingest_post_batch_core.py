"""Unit tests for ``_post_batch_core`` status code mapping."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.connectors.exceptions import (
    ConnectorAPIError,
    ConnectorAuthError,
    ConnectorRateLimitError,
    ConnectorTimeoutError,
)
from app.services.chainlens import ingest as ingest_mod
from app.services.chainlens.ingest import _post_batch_core

pytestmark = pytest.mark.unit


def _fake_config(**overrides: Any) -> Any:
    defaults = {
        "CHAINLENS_API_URL": "https://chainlens.test",
        "CHAINLENS_SERVICE_TOKEN": "tok1,tok2",
        "CHAINLENS_REQUEST_TIMEOUT_SECONDS": 5,
        "CHAINLENS_QUERY_MICROS_PER_CALL": 60000,
        "CHAINLENS_INGEST_MAX_BATCH_SIZE": 1000,
        "CHAINLENS_INGEST_TIMEOUT_SECONDS": 5,
        "CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS": 3,
        "CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS": 0.0,
    }
    defaults.update(overrides)
    return type("Config", (), defaults)()


def _make_client_class(responses: list[Any]):
    """Return a fake httpx.AsyncClient class replaying ``responses``.

    Each item is either (status_code, json_data) or an exception to raise.
    """

    class _FakeResponse:
        def __init__(self, status_code: int, json_data: dict[str, Any] | None = None):
            self.status_code = status_code
            self._json = json_data or {}
            self.content = b"" if json_data is None else b"{}"
            self.text = ""

        def json(self) -> dict[str, Any]:
            return self._json

    class _FakeClient:
        def __init__(self, **kwargs: Any):
            self._client_kwargs = kwargs

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *exc: Any) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            if not responses:
                return _FakeResponse(500)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return _FakeResponse(*item)

    return _FakeClient


@pytest.mark.asyncio
async def test_post_batch_core_returns_body_on_200():
    """200 returns the parsed JSON body."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(200, {"ingestJobId": "job-200"})])):
        result = await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert result == {"ingestJobId": "job-200"}


@pytest.mark.asyncio
async def test_post_batch_core_returns_body_on_202():
    """202 is also a success."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(202, {"ingestJobId": "job-202"})])):
        result = await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert result == {"ingestJobId": "job-202"}


@pytest.mark.asyncio
async def test_post_batch_core_rotates_and_retries_on_401():
    """On 401, rotate token once and retry the request."""
    config_obj = _fake_config()
    calls: list[dict[str, Any]] = []

    class _TrackingClient(_make_client_class([(401, None), (200, {"ingestJobId": "job-rotated"})])):
        async def post(self, url: str, **kwargs: Any):
            calls.append(kwargs)
            return await super().post(url, **kwargs)

    with patch.object(ingest_mod.httpx, "AsyncClient", _TrackingClient):
        result = await _post_batch_core("batdongsan", 1, [], config_obj)

    assert result == {"ingestJobId": "job-rotated"}
    assert len(calls) == 2
    assert calls[0]["headers"]["Authorization"] != calls[1]["headers"]["Authorization"]


@pytest.mark.asyncio
async def test_post_batch_core_raises_auth_error_when_401_and_rotation_fails():
    """If only one token is available, 401 cannot be recovered."""
    with patch.object(
        ingest_mod.httpx,
        "AsyncClient",
        _make_client_class([(401, None)]),
    ):
        with pytest.raises(ConnectorAuthError) as exc:
            await _post_batch_core("batdongsan", 1, [], _fake_config(CHAINLENS_SERVICE_TOKEN="single"))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_post_batch_core_raises_auth_error_on_403():
    """403 is a non-retryable auth failure."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(403, {"error": "forbidden"})])):
        with pytest.raises(ConnectorAuthError) as exc:
            await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_post_batch_core_raises_api_error_on_400():
    """400 is a client error."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(400, {"error": "bad request"})])):
        with pytest.raises(ConnectorAPIError) as exc:
            await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_post_batch_core_raises_api_error_on_422():
    """422 is a client error."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(422, {"error": "validation"})])):
        with pytest.raises(ConnectorAPIError) as exc:
            await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_post_batch_core_raises_conflict_on_409():
    """409 is mapped to a non-retryable ConnectorAPIError."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(409, {"ingestJobId": "job-409"})])):
        with pytest.raises(ConnectorAPIError) as exc:
            await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_post_batch_core_raises_rate_limit_on_429():
    """429 is a retryable rate limit."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(429, {"error": "rate limited"})])):
        with pytest.raises(ConnectorRateLimitError) as exc:
            await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_post_batch_core_raises_server_error_on_500():
    """5xx is a server error."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(500, {"error": "boom"})])):
        with pytest.raises(ConnectorAPIError) as exc:
            await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_post_batch_core_raises_timeout_on_504():
    """504 is a gateway timeout."""
    with patch.object(ingest_mod.httpx, "AsyncClient", _make_client_class([(504, {"error": "timeout"})])):
        with pytest.raises(ConnectorTimeoutError) as exc:
            await _post_batch_core("batdongsan", 1, [], _fake_config())
    assert exc.value.status_code == 504
