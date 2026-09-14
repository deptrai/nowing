"""Unit tests for XActions social target scheduler & per-target ingest."""

from __future__ import annotations

import json
import operator as op_module
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import BindParameter

from app.proprietary.platforms.xactions.adapter_v2 import TargetUnsupportedError
from app.proprietary.platforms.xactions.mcp_client import XActionsMcpError
from app.proprietary.platforms.xactions.models import SocialPostData
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
    account_id: str | None = None,
    proxy_url: str | None = None,
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
        account_id=account_id,
        proxy_url=proxy_url,
    )


def _fake_binding(
    workspace_id: int = 7,
    platform: str = "facebook_group",
    account_id: str = "fb_acc_01",
    proxy_url: str = "socks5://proxy:1080",
    is_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        workspace_id=workspace_id,
        platform=platform,
        account_id=account_id,
        proxy_url=proxy_url,
        is_active=is_active,
    )


class _FakeResult:
    def __init__(self, target=None, binding=None, multi=None):
        self._target = target
        self._binding = binding
        self._multi = multi or []

    def scalars(self):
        return _FakeScalars(self._target, self._binding, self._multi)


class _FakeScalars:
    def __init__(self, target=None, binding=None, multi=None):
        self._target = target
        self._binding = binding
        self._multi = multi or []

    def all(self):
        return self._multi if self._multi else ([self._target] if self._target else [])

    def first(self):
        if isinstance(self._binding, list):
            return self._binding[0] if self._binding else None
        return self._binding


def _eval_whereclause(whereclause, obj: Any) -> bool:
    """Evaluate a SQLAlchemy where-clause against a plain object."""

    def _value(operand):
        # BindParameter has a generated `key`, but we want the literal `value`.
        if isinstance(operand, BindParameter):
            return operand.value
        if hasattr(operand, "key") and operand.key:
            return getattr(obj, operand.key, None)
        if hasattr(operand, "value"):
            return operand.value
        # SQLAlchemy True_/False_/Null_ singletons
        if str(operand).lower() == "true":
            return True
        if str(operand).lower() == "false":
            return False
        if str(operand).lower() == "null":
            return None
        return operand

    def _compare(clause) -> bool:
        # Unwrap Grouping (parentheses)
        if hasattr(clause, "element"):
            return _compare(clause.element)

        if hasattr(clause, "operator"):
            op = clause.operator

            if hasattr(clause, "clauses"):
                if op.__name__ == "or_":
                    return any(_compare(c) for c in clause.clauses)
                if op.__name__ == "and_":
                    return all(_compare(c) for c in clause.clauses)

            left = _value(clause.left)
            right = _value(clause.right)
            if op is op_module.eq or op.__name__ == "eq":
                return left == right
            if op.__name__ == "ne":
                return left != right
            if op.__name__ == "is_":
                if right is True:
                    return left is True
                if right is False:
                    return left is False
                return left is right
            if op.__name__ == "is_not":
                return left is not right
            if op.__name__ in ("lt", "__lt__"):
                return left < right
            if op.__name__ in ("le", "__le__"):
                return left <= right
            if op.__name__ in ("gt", "__gt__"):
                return left > right
            if op.__name__ in ("ge", "__ge__"):
                return left >= right
            raise NotImplementedError(f"operator {op}")

        raise NotImplementedError(f"cannot evaluate {type(clause)}")

    return _compare(whereclause)


class _FakeSession:
    """Minimal async SQLAlchemy session stub that respects where clauses."""

    def __init__(self, target=None, binding=None, multi=None):
        self._target = target
        self._binding = binding
        self._multi = multi or []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __call__(self):
        return self

    async def get(self, _model, _id):
        return self._target

    async def execute(self, query):
        whereclause = getattr(query, "whereclause", None)
        limit = getattr(query, "_limit_clause", None)
        # Single-row binding lookup (proxy binding query with .limit(1))
        if limit is not None and self._binding is not None:
            if whereclause is not None:
                candidates = [b for b in (self._binding if isinstance(self._binding, list) else [self._binding])
                              if _eval_whereclause(whereclause, b)]
                return _FakeResult(self._target, candidates, self._multi)
            return _FakeResult(
                self._target,
                self._binding if isinstance(self._binding, list) else [self._binding],
                self._multi,
            )
        if whereclause is not None and self._multi:
            filtered = [m for m in self._multi if _eval_whereclause(whereclause, m)]
            return _FakeResult(self._target, self._binding, filtered)
        return _FakeResult(self._target, self._binding, self._multi)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _fake_session_ctx(target=None, binding=None, multi=None):
    """Return a _FakeSession that is also a sessionmaker and async CM."""
    return _FakeSession(target, binding, multi)


def _fake_redis_client(acquired: bool = True, exists: int = 0) -> AsyncMock:
    client = AsyncMock()
    client.set.return_value = acquired
    client.exists.return_value = exists
    client.delete.return_value = 1
    client.aclose.return_value = None
    return client


class _FakeAdapterCtx:
    """Context manager stub for XActionsSocialAdapterV2."""

    def __init__(self, adapter):
        self._adapter = adapter

    async def __aenter__(self):
        return self._adapter

    async def __aexit__(self, exc_type, exc, tb):
        return False


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

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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
async def test_check_social_targets_filters_status(
    monkeypatch,
):
    """Scheduler only selects active or paused targets, skipping error."""
    active = _fake_target(target_id=1, status="active", last_scraped_at=datetime.now(UTC) - timedelta(minutes=30))
    paused = _fake_target(target_id=2, status="paused", last_scraped_at=datetime.now(UTC) - timedelta(minutes=30))
    error = _fake_target(target_id=3, status="error")
    multi = [active, paused, error]

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: _fake_session_ctx(multi=multi),
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
    assert triggered == 2  # active + paused, error skipped
    called_ids = {call.args[0] for call in delay_mock.call_args_list}
    assert called_ids == {1, 2}


@pytest.mark.asyncio
async def test_check_social_targets_resumes_paused_when_due(
    monkeypatch,
):
    """Scheduler triggers paused target when cooldown has expired."""
    target = _fake_target(
        target_id=2,
        status="paused",
        last_scraped_at=datetime.now(UTC) - timedelta(minutes=30),
    )
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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


@pytest.mark.asyncio
async def test_check_social_targets_skips_unsupported_platform(
    monkeypatch,
):
    """Scheduler skips platforms not in SUPPORTED_PLATFORMS."""
    target = _fake_target(platform="unknown_platform", last_scraped_at=datetime.now(UTC) - timedelta(minutes=30))
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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
async def test_check_social_targets_skips_locked_target(
    monkeypatch,
):
    """Scheduler skips targets that already hold a Redis lock."""
    target = _fake_target(last_scraped_at=datetime.now(UTC) - timedelta(minutes=30))
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client(exists=1)
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
    """Per-target task fetches posts via V2 adapter and pushes them to Redis stream."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[post])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="123-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    task.retry = MagicMock(side_effect=lambda **kw: RuntimeError("retry"))
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 1
    assert post.target_id == target.id
    assert post.workspace_id == target.workspace_id
    mock_adapter.fetch_posts_for_target.assert_called_once_with(target)
    mock_adapter.ingest_raw_post_to_stream.assert_called_once_with(
        post,
        redis_client=client,
    )
    assert session.commits == 1
    assert target.last_scraped_at is not None


@pytest.mark.asyncio
async def test_ingest_social_target_resolves_proxy_binding(
    monkeypatch,
):
    """Per-target task resolves XActionsProxyBinding when account_id/proxy_url missing."""
    target = _fake_target(account_id=None, proxy_url=None)
    binding = _fake_binding()
    _FakeSession(target, binding)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        _fake_session_ctx(target, binding),
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    post = SocialPostData(platform="facebook", external_post_id="fb_001", content="x")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[post])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="1-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 1
    assert target.account_id == binding.account_id
    assert target.proxy_url == binding.proxy_url


@pytest.mark.asyncio
async def test_ingest_social_target_retries_on_rate_limit(
    monkeypatch,
):
    """XACT_4291 triggers task.retry with retry_after countdown."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("rate limited", code="XACT_4291", retry_after=45)
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    retry_exc = RuntimeError("retry-scheduled")
    task.retry = MagicMock(side_effect=retry_exc)

    with pytest.raises(RuntimeError):
        await social_xactions_ingest._ingest_social_target(task, target.id)

    task.retry.assert_called_once_with(countdown=45, max_retries=5)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ingest_social_target_rate_limit_exhausted_retries_halts(
    monkeypatch,
):
    """XACT_4291 when retries >= 5 halts target and does not write DLQ."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("rate limited", code="XACT_4291", retry_after=45)
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    task.request = SimpleNamespace(retries=5)

    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "error"
    assert target.is_active is False
    client.xadd.assert_not_called()
    task.retry.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_social_target_pauses_on_hibernation(
    monkeypatch,
):
    """ACCOUNT_HIBERNATION pauses target, pushes last_scraped_at to future, and returns 0."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("account hibernated", code="ACCOUNT_HIBERNATION", retry_after=600)
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    before = datetime.now(UTC)
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "paused"
    assert target.last_scraped_at is not None
    assert target.last_scraped_at >= before + timedelta(seconds=590)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ingest_social_target_pauses_on_proxy_exhausted(monkeypatch):
    """PROXY_EXHAUSTED pauses target and pushes last_scraped_at to future."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("proxy exhausted", code="PROXY_EXHAUSTED", retry_after=120)
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    before = datetime.now(UTC)
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "paused"
    assert target.last_scraped_at >= before + timedelta(seconds=115)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ingest_social_target_pauses_on_5030_temporary_unavailable(monkeypatch):
    """XACT_5030 pauses target and pushes last_scraped_at to future."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("temporary unavailable", code="XACT_5030", retry_after=300)
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    before = datetime.now(UTC)
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "paused"
    assert target.last_scraped_at >= before + timedelta(seconds=295)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ingest_social_target_halts_on_auth_failure(
    monkeypatch,
):
    """XACT_4010 halts target and marks it inactive."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("auth failed", code="XACT_4010")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "error"
    assert target.is_active is False


@pytest.mark.asyncio
async def test_ingest_social_target_signer_crash_retries(
    monkeypatch,
):
    """XACT_5000 triggers retry with countdown=60, max_retries=3."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("signer crash", code="XACT_5000")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    retry_exc = RuntimeError("retry-scheduled")
    task.retry = MagicMock(side_effect=retry_exc)

    with pytest.raises(RuntimeError):
        await social_xactions_ingest._ingest_social_target(task, target.id)

    task.retry.assert_called_once_with(countdown=60, max_retries=3)


@pytest.mark.asyncio
async def test_ingest_social_target_signer_crash_exhausted_retries_writes_dlq_and_halts(
    monkeypatch,
):
    """XACT_5000 when retries >= 3 writes DLQ and halts target."""
    target = _fake_target(target_id=42, workspace_id=10, account_id="acc_1", platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("signer crash", code="XACT_5000")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    task.request = SimpleNamespace(retries=3)

    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "error"
    assert target.is_active is False
    task.retry.assert_not_called()

    client.xadd.assert_called_once()
    stream_name, entry_data = client.xadd.call_args[0]
    assert stream_name == "stream:social:failed"
    assert entry_data["original_id"] == "42"
    assert entry_data["error"] == str(err)
    assert entry_data["code"] == "XACT_5000"
    assert entry_data["retries"] == "3"
    assert "failed_at" in entry_data
    # failed_at must be a parseable ISO timestamp
    datetime.fromisoformat(entry_data["failed_at"])

    payload = json.loads(entry_data["payload"])
    assert payload["target_id"] == 42
    assert payload["platform"] == "facebook_group"
    assert payload["workspace_id"] == 10
    assert payload["account_id"] == "acc_1"
    assert payload["code"] == "XACT_5000"
    assert payload["retries"] == 3


@pytest.mark.asyncio
async def test_ingest_social_target_signer_crash_dlq_fail_still_halts(
    monkeypatch,
):
    """When DLQ xadd raises an exception, the target is still halted safely."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    client.xadd.side_effect = RuntimeError("redis is down")
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("signer crash", code="XACT_5000")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    task.request = SimpleNamespace(retries=3)

    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "error"
    assert target.is_active is False
    task.retry.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_social_target_bad_request_4001_pauses_and_logs_suggested_action(
    monkeypatch,
    caplog,
):
    """XACT_4001 pauses target, sets future last_scraped_at, and logs suggested action."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError(
        "invalid filter parameter",
        code="XACT_4001",
        retry_after=180,
        suggested_action="check keyword syntax",
    )
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    before = datetime.now(UTC)
    with caplog.at_level("WARNING"):
        ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "paused"
    assert target.last_scraped_at >= before + timedelta(seconds=175)
    assert "check keyword syntax" in caplog.text
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ingest_social_target_already_locked(
    monkeypatch,
):
    """Task bails out if another worker already holds the target lock."""
    target = _fake_target()
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client(acquired=False)
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert session.commits == 0


@pytest.mark.asyncio
async def test_ingest_social_target_inactive(
    monkeypatch,
):
    """Task skips inactive or error targets."""
    target = _fake_target(is_active=False)
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert session.commits == 0


@pytest.mark.asyncio
async def test_ingest_social_target_not_found(
    monkeypatch,
):
    """Task returns 0 when target does not exist."""
    session = _FakeSession(target=None)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        _fake_session_ctx(target=None),
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, 999)

    assert ingested == 0
    assert session.commits == 0


@pytest.mark.asyncio
async def test_ingest_social_target_lock_ttl(
    monkeypatch,
):
    """Lock TTL uses max(interval * 60, SOCIAL_TARGET_LOCK_MIN_TTL_SECONDS)."""
    target = _fake_target(interval_minutes=5)

    ttl = social_xactions_ingest._lock_ttl_for_target(target)
    assert ttl == 960

    target_long = _fake_target(interval_minutes=30)
    ttl_long = social_xactions_ingest._lock_ttl_for_target(target_long)
    assert ttl_long == 1800


@pytest.mark.asyncio


@pytest.mark.asyncio
async def test_acquire_target_lock_uses_nx():
    """Redis lock is acquired with nx=True to avoid overwriting."""
    client = _fake_redis_client()
    acquired = await social_xactions_ingest._acquire_target_lock(client, 1, 120)
    assert acquired is True
    client.set.assert_called_once_with(
        "xactions:social_target_lock:1",
        "1",
        nx=True,
        ex=120,
    )


@pytest.mark.asyncio
async def test_pause_target_with_retry_after_sets_future():
    """_pause_target sets last_scraped_at into the future when retry_after given."""
    target = _fake_target()
    session = _FakeSession(target)
    await social_xactions_ingest._pause_target(session, target, "hibernated", retry_after_seconds=600)
    assert target.status == "paused"
    assert target.last_scraped_at is not None
    assert target.last_scraped_at > datetime.now(UTC)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_pause_target_without_retry_after_sets_future_default():
    """_pause_target sets last_scraped_at into future with default cooldown when no retry_after."""
    target = _fake_target()
    before = datetime.now(UTC)
    session = _FakeSession(target)
    await social_xactions_ingest._pause_target(session, target, "transient")
    assert target.status == "paused"
    assert target.last_scraped_at is not None
    assert target.last_scraped_at >= before + timedelta(seconds=590)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ingest_social_target_status_error_skips(monkeypatch):
    """Target with status='error' is skipped before any binding/lock logic."""
    target = _fake_target(status="error")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert session.commits == 0
    client.set.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_social_target_status_paused_continues(monkeypatch):
    """Target with status='paused' is not confused with 'error'."""
    target = _fake_target(status="paused")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ingest_social_target_proxy_binding_uses_workspace_filter(monkeypatch):
    """Proxy binding query filters by workspace_id, platform, is_active."""
    target = _fake_target(account_id=None, proxy_url=None)
    wrong_binding = _fake_binding(workspace_id=99, platform="twitter_user")
    right_binding = _fake_binding()
    # _FakeSession should filter to the correct binding
    session = _FakeSession(target, binding=[wrong_binding, right_binding])

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    post = SocialPostData(platform="facebook", external_post_id="fb_001", content="x")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[post])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="1-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 1
    assert target.account_id == right_binding.account_id
    assert target.proxy_url == right_binding.proxy_url


@pytest.mark.asyncio
async def test_ingest_social_target_proxy_missing_only_account_id(monkeypatch):
    """Binding is resolved when only account_id is missing."""
    target = _fake_target(account_id=None, proxy_url="socks5://existing:1080")
    binding = _fake_binding()
    session = _FakeSession(target, binding)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    post = SocialPostData(platform="facebook", external_post_id="fb_001", content="x")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[post])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="1-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    await social_xactions_ingest._ingest_social_target(task, target.id)
    assert target.account_id == binding.account_id
    assert target.proxy_url == "socks5://existing:1080"


@pytest.mark.asyncio
async def test_ingest_social_target_proxy_missing_only_proxy_url(monkeypatch):
    """Binding is resolved when only proxy_url is missing."""
    target = _fake_target(account_id="existing_acc", proxy_url=None)
    binding = _fake_binding()
    session = _FakeSession(target, binding)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    post = SocialPostData(platform="facebook", external_post_id="fb_001", content="x")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[post])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="1-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    await social_xactions_ingest._ingest_social_target(task, target.id)
    assert target.account_id == "existing_acc"
    assert target.proxy_url == binding.proxy_url


@pytest.mark.asyncio
async def test_ingest_social_target_no_proxy_binding_needed(monkeypatch):
    """No query is made when both account_id and proxy_url are present."""
    target = _fake_target(account_id="acc", proxy_url="http://proxy:1080")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    post = SocialPostData(platform="facebook", external_post_id="fb_001", content="x")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[post])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="1-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    await social_xactions_ingest._ingest_social_target(task, target.id)
    assert session.commits == 1
    assert target.account_id == "acc"
    assert target.proxy_url == "http://proxy:1080"


@pytest.mark.asyncio
async def test_ingest_social_target_unmapped_code_defaults_to_pause(monkeypatch):
    """An unrecognized XActions error code defaults to PAUSE and sets last_scraped_at to future."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("unknown", code="XACT_9999", retry_after=120)
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    before = datetime.now(UTC)
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "paused"
    assert target.last_scraped_at >= before + timedelta(seconds=115)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ingest_social_target_none_code_defaults_to_pause(monkeypatch):
    """A None error code defaults to PAUSE and sets last_scraped_at to future."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("error with no code", code=None)
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    before = datetime.now(UTC)
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "paused"
    assert target.last_scraped_at >= before + timedelta(seconds=590)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_rate_limit_default_retry_after(monkeypatch):
    """XACT_4291 without retry_after falls back to 30 seconds and max_retries=5."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("rate limited", code="XACT_4291")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    retry_exc = RuntimeError("retry-scheduled")
    task.retry = MagicMock(side_effect=retry_exc)

    with pytest.raises(RuntimeError):
        await social_xactions_ingest._ingest_social_target(task, target.id)

    task.retry.assert_called_once_with(countdown=30, max_retries=5)


@pytest.mark.asyncio
async def test_check_social_targets_exactly_due_threshold(monkeypatch):
    """A target is due when last_scraped_at is exactly at the interval boundary."""
    now = datetime.now(UTC)
    target = _fake_target(
        last_scraped_at=now - timedelta(minutes=15),
        interval_minutes=15,
    )
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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


@pytest.mark.asyncio
async def test_check_social_targets_just_not_due(monkeypatch):
    """A target scraped 14m59s ago with a 15m interval is not due."""
    now = datetime.now(UTC)
    target = _fake_target(
        last_scraped_at=now - timedelta(minutes=14, seconds=59),
        interval_minutes=15,
    )
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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
async def test_check_social_targets_paused_due_when_cooldown_expired(monkeypatch):
    """A paused target becomes due as soon as last_scraped_at <= now (cooldown
    expired), without also requiring scrape_interval to elapse."""
    now = datetime.now(UTC)
    # _pause_target sets last_scraped_at = now + cooldown. After the cooldown
    # lapses, last_scraped_at is in the past — the target should be due even
    # though scrape_interval (default 15m) has not fully elapsed since then.
    target = _fake_target(
        target_id=7,
        status="paused",
        last_scraped_at=now - timedelta(seconds=30),  # cooldown expired 30s ago
        interval_minutes=15,
    )
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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
    delay_mock.assert_called_once_with(7)


@pytest.mark.asyncio
async def test_check_social_targets_paused_not_due_during_cooldown(monkeypatch):
    """A paused target with last_scraped_at still in the future is not due."""
    now = datetime.now(UTC)
    target = _fake_target(
        target_id=8,
        status="paused",
        last_scraped_at=now + timedelta(minutes=10),  # cooldown active
        interval_minutes=15,
    )
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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
async def test_ingest_social_target_resumes_paused_to_active_on_success(monkeypatch):
    """When a paused target fetches successfully, its status resets to active."""
    target = _fake_target(
        status="paused",
        last_scraped_at=datetime.now(UTC) - timedelta(seconds=5),
    )
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "active"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_check_social_targets_continue_past_unsupported(monkeypatch):
    """Continue past an unsupported platform to schedule the next due target."""
    now = datetime.now(UTC)
    bad = _fake_target(target_id=1, platform="unknown", last_scraped_at=now - timedelta(minutes=30))
    good = _fake_target(target_id=2, platform="facebook_group", last_scraped_at=now - timedelta(minutes=30))

    session = _FakeSession(multi=[bad, good])

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
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
    delay_mock.assert_called_once_with(good.id)


@pytest.mark.asyncio
async def test_check_social_targets_continue_past_locked(monkeypatch):
    """Continue past a locked target to schedule the next due target."""
    now = datetime.now(UTC)
    locked = _fake_target(target_id=1, last_scraped_at=now - timedelta(minutes=30))
    free = _fake_target(target_id=2, last_scraped_at=now - timedelta(minutes=30))

    session = _FakeSession(multi=[locked, free])

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client(exists=1)
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    # First call to exists returns 1, second returns 0
    client.exists.side_effect = [1, 0]

    delay_mock = MagicMock()
    monkeypatch.setattr(
        social_xactions_ingest.ingest_social_target_task,
        "delay",
        delay_mock,
    )

    triggered = await social_xactions_ingest._check_and_trigger_social_targets()
    assert triggered == 1
    delay_mock.assert_called_once_with(free.id)


@pytest.mark.asyncio
async def test_check_social_targets_exception_in_delay_continues(monkeypatch):
    """An exception when calling delay is logged and the loop continues."""
    now = datetime.now(UTC)
    bad = _fake_target(target_id=1, last_scraped_at=now - timedelta(minutes=30))
    good = _fake_target(target_id=2, last_scraped_at=now - timedelta(minutes=30))

    session = _FakeSession(multi=[bad, good])

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    def _delay(target_id):
        if target_id == bad.id:
            raise RuntimeError("queue down")
        return None

    delay_mock = MagicMock(side_effect=_delay)
    monkeypatch.setattr(
        social_xactions_ingest.ingest_social_target_task,
        "delay",
        delay_mock,
    )

    with patch.object(social_xactions_ingest.logger, "exception") as log_exc:
        triggered = await social_xactions_ingest._check_and_trigger_social_targets()

    assert triggered == 1
    log_exc.assert_called_once()
    delay_mock.assert_called_with(good.id)


async def test_ingest_social_target_unexpected_exception_rolls_back(
    monkeypatch,
):
    """Unexpected exception rolls back and re-raises."""
    target = _fake_target()
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=RuntimeError("boom"))
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    with pytest.raises(RuntimeError, match="boom"):
        await social_xactions_ingest._ingest_social_target(task, target.id)

    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_ingest_social_target_marks_unsupported_on_target_unsupported_error(
    monkeypatch,
):
    """TargetUnsupportedError sets status='unsupported', is_active=False, commits and does not retry."""
    target = _fake_target(platform="shopee_keyword")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(
        side_effect=TargetUnsupportedError("Target lacks valid HTTP(S) URL for x_crawl_post fallback")
    )
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )

    task = MagicMock()
    with patch.object(social_xactions_ingest.logger, "warning") as log_warn:
        ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert target.status == "unsupported"
    assert target.is_active is False
    assert session.commits >= 1
    task.retry.assert_not_called()
    log_warn.assert_called()


@pytest.mark.asyncio
async def test_ingest_social_target_status_unsupported_skips(monkeypatch):
    """Target with status='unsupported' is skipped before any binding/lock logic."""
    target = _fake_target(status="unsupported")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    assert session.commits == 0
    client.set.assert_not_called()


def test_get_task_retries_various_shapes():
    """_get_task_retries safely handles various task and request shapes."""
    assert social_xactions_ingest._get_task_retries(None) == 0
    assert social_xactions_ingest._get_task_retries(object()) == 0
    assert social_xactions_ingest._get_task_retries(SimpleNamespace(request=None)) == 0
    assert social_xactions_ingest._get_task_retries(SimpleNamespace(request=SimpleNamespace(retries=3))) == 3
    assert social_xactions_ingest._get_task_retries(SimpleNamespace(request=SimpleNamespace(retries="5"))) == 5
    assert social_xactions_ingest._get_task_retries(SimpleNamespace(request=SimpleNamespace(retries="bad"))) == 0
    assert social_xactions_ingest._get_task_retries(SimpleNamespace(request=SimpleNamespace(retries=True))) == 0
    assert social_xactions_ingest._get_task_retries(SimpleNamespace(request=SimpleNamespace(retries=False))) == 0
    assert social_xactions_ingest._get_task_retries(SimpleNamespace(request=SimpleNamespace(retries=-2))) == 0


@pytest.mark.asyncio
async def test_ingest_social_target_unhandled_behavior_raises(monkeypatch):
    """An unhandled behavior like RAISE re-raises the underlying exception."""
    from app.proprietary.platforms.xactions.error_map import (
        BehaviorDecision,
        TaskBehavior,
    )

    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    err = XActionsMcpError("fatal crash", code="XACT_FATAL")
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )
    monkeypatch.setattr(
        social_xactions_ingest,
        "resolve_task_behavior",
        lambda _exc: BehaviorDecision(behavior=TaskBehavior.RAISE, reason="fatal crash"),
    )

    task = MagicMock()
    with pytest.raises(XActionsMcpError):
        await social_xactions_ingest._ingest_social_target(task, target.id)


# Story 36.4: Single-Writer Stream tests


def test_single_writer_config_default_and_parsing(monkeypatch):
    """XACTIONS_STREAM_SINGLE_WRITER_ENABLED defaults to False and parses env var."""
    import importlib

    import app.config.entities as entities_mod
    from app.config import config

    try:
        # Default in app.config is False
        assert config.XACTIONS_STREAM_SINGLE_WRITER_ENABLED is False

        # Verify env var parsing logic: true, 1, yes, on
        for truthy in ("true", "True ", "1", "yes", "on", "ON"):
            monkeypatch.setenv("XACTIONS_STREAM_SINGLE_WRITER_ENABLED", truthy)
            importlib.reload(entities_mod)
            assert entities_mod.XACTIONS_STREAM_SINGLE_WRITER_ENABLED is True

        for falsy in ("false", "0", "no", "off", "invalid", ""):
            monkeypatch.setenv("XACTIONS_STREAM_SINGLE_WRITER_ENABLED", falsy)
            importlib.reload(entities_mod)
            assert entities_mod.XACTIONS_STREAM_SINGLE_WRITER_ENABLED is False

        monkeypatch.delenv("XACTIONS_STREAM_SINGLE_WRITER_ENABLED", raising=False)
        importlib.reload(entities_mod)
        assert entities_mod.XACTIONS_STREAM_SINGLE_WRITER_ENABLED is False
    finally:
        monkeypatch.delenv("XACTIONS_STREAM_SINGLE_WRITER_ENABLED", raising=False)
        importlib.reload(entities_mod)


@pytest.mark.asyncio
async def test_ingest_social_target_single_writer_disabled_calls_xadd(monkeypatch):
    """When single_writer is False, adapter.ingest_raw_post_to_stream is called for every post."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    posts = [
        SocialPostData(
            platform="facebook",
            external_post_id=f"fb_{i}",
            content=f"Post content {i}",
        )
        for i in range(5)
    ]
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=posts)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock(return_value="123-0")

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )
    monkeypatch.setattr(
        social_xactions_ingest.config,
        "XACTIONS_STREAM_SINGLE_WRITER_ENABLED",
        False,
    )

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 5
    assert mock_adapter.ingest_raw_post_to_stream.call_count == 5
    for p in posts:
        assert p.target_id == target.id
        assert p.workspace_id == target.workspace_id
    assert session.commits == 1
    assert target.last_scraped_at is not None


@pytest.mark.asyncio
async def test_ingest_social_target_single_writer_enabled_bypasses_xadd(monkeypatch, caplog):
    """When single_writer is True, adapter.ingest_raw_post_to_stream is NOT called, target is updated."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    posts = [
        SocialPostData(
            platform="facebook",
            external_post_id=f"fb_{i}",
            content=f"Post content {i}",
        )
        for i in range(5)
    ]
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=posts)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )
    monkeypatch.setattr(
        social_xactions_ingest.config,
        "XACTIONS_STREAM_SINGLE_WRITER_ENABLED",
        True,
    )

    task = MagicMock()
    with caplog.at_level("INFO"):
        ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 5
    mock_adapter.ingest_raw_post_to_stream.assert_not_called()
    assert session.commits == 1
    assert target.last_scraped_at is not None
    assert "Single-writer mode enabled; bypassed raw-posts stream publish" in caplog.text


@pytest.mark.asyncio
async def test_ingest_social_target_single_writer_enabled_resumes_paused_target(monkeypatch):
    """When single_writer is True and target is paused, target.status is restored to active."""
    target = _fake_target(
        platform="facebook_group",
        status="paused",
        last_scraped_at=datetime.now(UTC) - timedelta(seconds=10),
    )
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    posts = [
        SocialPostData(
            platform="facebook",
            external_post_id="fb_resume_01",
            content="Resume test",
        )
    ]
    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=posts)
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )
    monkeypatch.setattr(
        social_xactions_ingest.config,
        "XACTIONS_STREAM_SINGLE_WRITER_ENABLED",
        True,
    )

    task = MagicMock()
    ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 1
    mock_adapter.ingest_raw_post_to_stream.assert_not_called()
    assert target.status == "active"
    assert session.commits == 1
    assert target.last_scraped_at is not None


@pytest.mark.asyncio
async def test_ingest_social_target_single_writer_enabled_empty_posts(monkeypatch, caplog):
    """When single_writer is True and adapter returns 0 posts, returns 0 and updates target."""
    target = _fake_target(platform="facebook_group")
    session = _FakeSession(target)

    monkeypatch.setattr(
        social_xactions_ingest,
        "get_celery_session_maker",
        lambda: session,
    )

    client = _fake_redis_client()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = client
    monkeypatch.setattr(social_xactions_ingest, "aioredis", fake_aioredis)

    mock_adapter = MagicMock()
    mock_adapter.fetch_posts_for_target = AsyncMock(return_value=[])
    mock_adapter.ingest_raw_post_to_stream = AsyncMock()

    monkeypatch.setattr(
        social_xactions_ingest,
        "XActionsSocialAdapterV2",
        lambda: _FakeAdapterCtx(mock_adapter),
    )
    monkeypatch.setattr(
        social_xactions_ingest.config,
        "XACTIONS_STREAM_SINGLE_WRITER_ENABLED",
        True,
    )

    task = MagicMock()
    with caplog.at_level("INFO"):
        ingested = await social_xactions_ingest._ingest_social_target(task, target.id)

    assert ingested == 0
    mock_adapter.ingest_raw_post_to_stream.assert_not_called()
    assert session.commits == 1
    assert target.last_scraped_at is not None
    assert "Single-writer mode enabled; bypassed raw-posts stream publish" in caplog.text
