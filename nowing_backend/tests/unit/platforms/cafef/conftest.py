"""Mock HTTP transport for CafeF fetch tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlparse

import pytest

from app.proprietary.platforms.cafef import fetch as fetch_module

_HTTP_RESPONSES: dict[tuple[str, frozenset[tuple[str, str]]], tuple[int, Any]] = {}


def _split_url(url: str) -> tuple[str, dict[str, str]]:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    query = dict(parse_qsl(parsed.query))
    return base, query


def _key(base: str, params: Mapping[str, Any]) -> tuple[str, frozenset[tuple[str, str]]]:
    return (base, frozenset((k, str(v)) for k, v in params.items()))


class FakeResponse:
    def __init__(self, status_code: int, data: Any):
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data


class FakeClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> FakeResponse:
        base, query = _split_url(url)
        merged = {**query, **dict(params or {})}
        request_key = _key(base, merged)
        for (base_url, required), payload in _HTTP_RESPONSES.items():
            if base == base_url and required.issubset(request_key[1]):
                return FakeResponse(*payload)
        raise AssertionError(
            f"Unexpected fake HTTP request: {url} params={dict(params or {})}"
        )


@pytest.fixture
def http_mock(monkeypatch):
    """Install a fake httpx.AsyncClient and return a mapping setter."""
    _HTTP_RESPONSES.clear()
    monkeypatch.setattr(fetch_module.httpx, "AsyncClient", FakeClient)

    def _set(
        mapping: dict[tuple[str, tuple[tuple[str, Any], ...]], tuple[int, Any]],
    ) -> None:
        _HTTP_RESPONSES.clear()
        for (url, params), payload in mapping.items():
            _HTTP_RESPONSES[_key(url, dict(params))] = payload

    return _set
