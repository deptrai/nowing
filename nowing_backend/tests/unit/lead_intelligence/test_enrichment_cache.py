"""Unit tests for the enrichment Redis cache (Story 21.3, Task 3.1, AC-5)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


class _FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.sets: list[tuple[str, str, dict]] = []

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.sets.append((key, value, {"ex": ex}))
        self.store[key] = value


def test_cache_key_uses_client_id(monkeypatch) -> None:
    from app.lead_intelligence.enrichment.cache import cache_key

    lead_id = uuid4()
    assert cache_key(1, "client-a", lead_id) == (
        f"enrichment:v1:1:client:client-a:{lead_id}"
    )
    assert cache_key(1, None, lead_id) == f"enrichment:v1:1:global:{lead_id}"


def test_get_enrichment_cache_client_creates_once_with_decode_responses(
    monkeypatch,
) -> None:
    from app.lead_intelligence.enrichment import cache

    created: list[tuple[str, dict]] = []

    def fake_from_url(url: str, **kwargs: object) -> _FakeRedisClient:
        created.append((url, kwargs))
        return _FakeRedisClient()

    monkeypatch.setattr(cache.redis, "from_url", fake_from_url)
    monkeypatch.setattr(cache, "_redis_client", None)

    first = cache.get_enrichment_cache_client()
    second = cache.get_enrichment_cache_client()

    assert first is second
    assert created == [
        (cache.config.REDIS_APP_URL, {"decode_responses": True}),
    ]


def test_set_then_get_roundtrip(monkeypatch) -> None:
    from app.lead_intelligence.enrichment import cache

    fake = _FakeRedisClient()
    monkeypatch.setattr(cache, "get_enrichment_cache_client", lambda: fake)

    lead_id = uuid4()
    contact_ids = [uuid4(), uuid4()]
    cache.set_cached_contact_ids(1, None, lead_id, contact_ids)
    assert cache.get_cached_contact_ids(1, None, lead_id) == contact_ids


def test_miss_returns_none(monkeypatch) -> None:
    from app.lead_intelligence.enrichment import cache

    fake = _FakeRedisClient()
    monkeypatch.setattr(cache, "get_enrichment_cache_client", lambda: fake)

    assert cache.get_cached_contact_ids(1, None, uuid4()) is None


def test_uses_config_ttl_when_not_given(monkeypatch) -> None:
    from app.config import config
    from app.lead_intelligence.enrichment import cache

    monkeypatch.setattr(config, "CONTACT_ENRICHMENT_CACHE_TTL_SECONDS", 1234)
    fake = _FakeRedisClient()
    monkeypatch.setattr(cache, "get_enrichment_cache_client", lambda: fake)

    lead_id = uuid4()
    cache.set_cached_contact_ids(1, None, lead_id, [uuid4()])
    assert fake.sets[0][2] == {"ex": 1234}


def test_redis_error_on_read_treated_as_miss(monkeypatch) -> None:
    from app.lead_intelligence.enrichment import cache

    broken = MagicMock()
    broken.get.side_effect = RuntimeError("redis down")
    monkeypatch.setattr(cache, "get_enrichment_cache_client", lambda: broken)

    assert cache.get_cached_contact_ids(1, None, uuid4()) is None


def test_redis_error_on_write_swallowed(monkeypatch) -> None:
    from app.lead_intelligence.enrichment import cache

    broken = MagicMock()
    broken.set.side_effect = RuntimeError("redis down")
    monkeypatch.setattr(cache, "get_enrichment_cache_client", lambda: broken)

    cache.set_cached_contact_ids(1, None, uuid4(), [uuid4()])


def test_malformed_cache_value_returns_none(monkeypatch) -> None:
    from app.lead_intelligence.enrichment import cache

    fake = _FakeRedisClient()
    fake.store[cache.cache_key(1, None, uuid4())] = "not-json"
    monkeypatch.setattr(cache, "get_enrichment_cache_client", lambda: fake)

    assert cache.get_cached_contact_ids(1, None, uuid4()) is None
