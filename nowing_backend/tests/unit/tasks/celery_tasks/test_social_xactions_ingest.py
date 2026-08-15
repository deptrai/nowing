"""Unit tests for XActions social target scheduler & per-target ingest."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.proprietary.platforms.xactions.adapter import SocialPostData
from app.tasks.celery_tasks import social_xactions_ingest

pytestmark = pytest.mark.unit


def _fake_target(
    target_id: int = 1,
    workspace_id: int = 7,
    platform: str = "facebook_group",
    external_target_id: str = "bds_hanoi_group",
    interval_minutes: int = 15,
    last_scraped_at: datetime | None = None,
    is_active: bool = True,
    status: str = "active",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=target_id,
        workspace_id=workspace_id,
        platform=platform,
        target_id=external_target_id,
        target_name="Test Target",
        scrape_interval_minutes=interval_minutes,
        last_scraped_at=last_scraped_at,
        is_active=is_active,
        status=status,
    )


class _FakeResult:
    def __init__(self, target):
        self._target = target

    def scalars(self):
        return _FakeScalars(self._target)


class _FakeScalars:
    def __init__(self, target):
        self._target = target

    def all(self):
        return [self._target]


class _FakeSession:
    """Minimal async SQLAlchemy session stub."""

    def __init__(self, target):
        self._target = target
        self.commits = 0
        self.rollbacks = 0

    async def get(self, _model, _id):
        return self._target

    async def execute(self, _query):
        return _FakeResult(self._target)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@asynccontextmanager
async def _fake_session_ctx():
    yield _FakeSession(_fake_target())


def _fake_redis_client(acquired: bool = True) -> AsyncMock:
    client = AsyncMock()
    client.set.return_value = acquired
    client.exists.return_value = 0
    client.delete.return_value = 1
    client.aclose.return_value = None
    return client


@pytest.fixture
def fake_redis():
    return _fake_redis_client()


@pytest.mark.asyncio
async def test_check_social_targets_triggers_due_target(
    monkeypatch,
):
    """Scheduler spawns ingest_social_target for a due active target."""
    target = _fake_target(last_scraped_at=datetime.now(UTC) - timedelta(minutes=30))
    session = _FakeSession(target)

    @asynccontextmanager
    async def _session_ctx():
        yield session

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: _session_ctx,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    delay_mock = MagicMock()
    monkeypatch.setattr(
        social_xactions_ingest.ingest_social_target_task,
        "delay",
        delay_mock,
    )

    triggered = await social_xactions_ingest._check_and_trigger_social_targets()

    assert triggered == 1
    delay_mock.assert_called_once_with(target.id)
    client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_check_social_targets_skips_not_due(
    monkeypatch,
):
    """Scheduler does not trigger a target scraped within its interval."""
    target = _fake_target(last_scraped_at=datetime.now(UTC) - timedelta(minutes=5))
    session = _FakeSession(target)

    @asynccontextmanager
    async def _session_ctx():
        yield session

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: _session_ctx,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    delay_mock = MagicMock()
    monkeypatch.setattr(
        social_xactions_ingest.ingest_social_target_task,
        "delay",
        delay_mock,
    )

    triggered = await social_xactions_ingest._check_and_trigger_social_targets()

    assert triggered == 0
    delay_mock.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_social_target_facebook_group(
    monkeypatch,
):
    """Per-target task fetches Facebook posts and pushes them to Redis stream."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    @asynccontextmanager
    async def _session_ctx():
        yield session

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: _session_ctx,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    post = SocialPostData(
        platform="facebook",
        external_post_id="fb_001",
        content="Bán nhà 0912345678",
    )
    mock_adapter = MagicMock()
    mock_adapter.fetch_facebook_group_posts = AsyncMock(return_value=[post])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="123-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapter",
        lambda: mock_adapter,
    )

    ingested = await social_xactions_ingest._ingest_social_target(target.id)

    assert ingested == 1
    assert post.target_id == target.id
    assert post.workspace_id == target.workspace_id
    mock_adapter.fetch_facebook_group_posts.assert_called_once_with(
        group_id=target.target_id,
        limit=20,
        account_id=f"fb:{target.id}",
        auth_cookie=None,
    )
    mock_adapter.ingest_raw_post_to_stream.assert_called_once_with(
        post,
        redis_client=client,
    )
    assert session.commits == 1
    assert target.last_scraped_at is not None


@pytest.mark.asyncio
async def test_ingest_social_target_twitter_keyword(
    monkeypatch,
):
    """Per-target task fetches Twitter keyword posts and pushes them."""
    target = _fake_target(
        platform="twitter_keyword",
        external_target_id="batdongsan",
    )
    session = _FakeSession(target)

    @asynccontextmanager
    async def _session_ctx():
        yield session

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: _session_ctx,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    post = SocialPostData(
        platform="twitter",
        external_post_id="tw_001",
        content="Tuyển dụng bds 0912345678",
    )
    mock_adapter = MagicMock()
    mock_adapter.search_tweets = AsyncMock(return_value=[post])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="456-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapter",
        lambda: mock_adapter,
    )

    ingested = await social_xactions_ingest._ingest_social_target(target.id)

    assert ingested == 1
    assert post.target_id == target.id
    mock_adapter.search_tweets.assert_called_once_with(
        query=target.target_id,
        limit=20,
        account_id=f"tw:{target.id}",
    )


@pytest.mark.asyncio
async def test_ingest_social_target_already_locked(
    monkeypatch,
):
    """Task bails out if another worker already holds the target lock."""
    target = _fake_target()
    session = _FakeSession(target)

    @asynccontextmanager
    async def _session_ctx():
        yield session

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: _session_ctx,
    )

    client = _fake_redis_client(acquired=False)
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    ingested = await social_xactions_ingest._ingest_social_target(target.id)

    assert ingested == 0
    assert session.commits == 0
