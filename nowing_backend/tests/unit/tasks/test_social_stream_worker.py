"""Unit tests for social stream worker alert matching and lead creation."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
from redis.exceptions import ResponseError

from app.alerts.persistence.models.alert_rule import AlertRule
from app.db import User
from app.proprietary.platforms.xactions.constants import (
    STREAM_SOCIAL_DEAD_LETTER,
    STREAM_SOCIAL_RAW_POSTS,
)
from app.tasks.social_stream_worker import (
    _LAG_STATE,
    CONSUMER_GROUP_NAME,
    DLQ_REASON_INVALID_SCHEMA_VERSION,
    DLQ_REASON_MISSING_CONTENT,
    DLQ_REASON_MISSING_TARGET_ID,
    DLQ_REASON_MISSING_WORKSPACE_ID,
    DLQ_REASON_RUNTIME_FAILURE,
    DLQ_REASON_SCHEMA_VALIDATION_ERROR,
    DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSION_MAX,
    SocialPostEvent,
    ValidationResult,
    _check_stream_lag,
    _create_lead_from_social_post,
    _evaluate_alerts_for_social_post,
    _route_to_dlq,
    _safe_serialize_payload,
    _validate_event_schema,
    process_social_post_event,
    run_social_stream_consumer,
)


@pytest.fixture(autouse=True)
def _reset_lag_state():
    _LAG_STATE["last_check"] = float("-inf")
    yield
    _LAG_STATE["last_check"] = float("-inf")


@pytest.fixture
def fake_event():
    return SocialPostEvent(
        platform="facebook",
        external_post_id="fb_001",
        content="Cần bán nhà Quận 1 giá 5 tỷ, LH 0912345678",
        author_id="usr_1",
        author_name="Test Author",
        post_url="https://facebook.com/posts/fb_001",
        target_id=1,
        workspace_id=1,
    )


@pytest.fixture
def fake_extracted():
    return {
        "phones": ["0912345678"],
        "emails": [],
        "prices": [],
        "locations": ["Quận 1"],
        "intent": "sell",
    }


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, rows=None, target=None, workspace=None, existing_lead_id=None):
        self._rows = rows or []
        self._target = target
        self._workspace = workspace
        self._existing_lead_id = existing_lead_id
        self.added = []
        self.committed = 0

    async def get(self, model, _id):
        if model.__name__ == "SocialMonitoredTarget":
            return self._target
        if model.__name__ == "Workspace":
            return self._workspace
        if model.__name__ == "Lead":
            return None
        if model.__name__ == "User":
            return User(
                id=uuid4(),
                email="test@nowing.net",
                hashed_password="hashed",
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
        return None

    async def scalar(self, _stmt):
        return self._existing_lead_id

    async def execute(self, _stmt):
        return _FakeResult(self._rows)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        pass


@pytest.mark.asyncio
async def test_evaluate_alerts_for_social_post_triggers_alert_rule(
    fake_event,
    fake_extracted,
):
    """When content matches a rule, the worker executes the alert rule."""
    rule = AlertRule(
        id=uuid4(),
        workspace_id=1,
        client_id=None,
        name="Bán nhà Quận 1",
        capability_id="social.search_leads",
        query={"keyword": "Quận 1"},
        schedule="none",
        timezone="UTC",
        cron="",
        next_fire_at=None,
        last_fired_at=None,
        diff_strategy="new_items",
        threshold=None,
        notification_channels=["in_app"],
        enabled=True,
    )
    session = _FakeSession(rows=[rule])

    with mock.patch(
        "app.tasks.social_stream_worker.execute_alert_rule", new=mock.AsyncMock()
    ) as mock_execute:
        await _evaluate_alerts_for_social_post(
            session=session,
            event=fake_event,
            raw_entities=fake_extracted,
            fit_score=0.75,
        )

    assert mock_execute.await_count == 1
    assert mock_execute.await_args.kwargs["alert_rule"] is rule


@pytest.mark.asyncio
async def test_create_lead_from_social_post_skips_existing_lead(
    fake_event,
    fake_extracted,
):
    """Duplicate lead by source_url is not re-created."""
    session = _FakeSession(
        existing_lead_id=uuid4(),
        target=SimpleNamespace(workspace_id=1, target_name="Hanoi BDS"),
    )

    lead = await _create_lead_from_social_post(
        session=session,
        event=fake_event,
        raw_entities=fake_extracted,
        fit_score=0.75,
    )

    assert lead is None
    assert session.added == []



def test_social_post_event_alias_and_version():
    # 1. Alias content_snippet alone
    e1 = SocialPostEvent.model_validate({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Snippet only",
        "workspace_id": 1,
    })
    assert e1.content == "Snippet only"
    assert e1.schema_version == 1

    # 2. Both content and content_snippet: content wins when non-empty
    e2 = SocialPostEvent.model_validate({
        "platform": "facebook",
        "external_post_id": "p2",
        "content": "Original content",
        "content_snippet": "Snippet content",
        "workspace_id": 1,
        "schema_version": 1,
    })
    assert e2.content == "Original content"
    assert e2.schema_version == 1

    # P1 cases: coalesce prefers non-empty values
    # content="" + content_snippet="real" -> event.content == "real"
    e_empty = SocialPostEvent.model_validate({
        "platform": "facebook",
        "external_post_id": "p_empty",
        "content": "",
        "content_snippet": "real",
        "workspace_id": 1,
    })
    assert e_empty.content == "real"

    # content=None + content_snippet="real" -> event.content == "real"
    e_none = SocialPostEvent.model_validate({
        "platform": "facebook",
        "external_post_id": "p_none",
        "content": None,
        "content_snippet": "real",
        "workspace_id": 1,
    })
    assert e_none.content == "real"

    # content="real" + content_snippet="other" -> event.content == "real"
    e_both = SocialPostEvent.model_validate({
        "platform": "facebook",
        "external_post_id": "p_both",
        "content": "real",
        "content_snippet": "other",
        "workspace_id": 1,
    })
    assert e_both.content == "real"

    # content="real" + content_snippet="" -> event.content == "real"
    e_reverse = SocialPostEvent.model_validate({
        "platform": "facebook",
        "external_post_id": "p_rev",
        "content": "real",
        "content_snippet": "",
        "workspace_id": 1,
    })
    assert e_reverse.content == "real"

    # 3. Legacy content alone
    e3 = SocialPostEvent.model_validate({
        "platform": "facebook",
        "external_post_id": "p3",
        "content": "Legacy content",
        "workspace_id": 1,
    })
    assert e3.content == "Legacy content"
    assert e3.schema_version == 1

    # 4. Explicit schema_version
    e4 = SocialPostEvent.model_validate({
        "platform": "facebook",
        "external_post_id": "p4",
        "content_snippet": "Snippet",
        "workspace_id": 1,
        "schema_version": 2,
    })
    assert e4.schema_version == 2


def test_validate_event_schema_cases():
    # Happy paths
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": 1,
    })
    assert ok is True
    assert reason is None

    # Missing workspace_id and target_id null
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
    })
    assert ok is False
    assert reason == DLQ_REASON_MISSING_WORKSPACE_ID

    # Missing workspace_id and target_id invalid
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "target_id": "not_an_int",
    })
    assert ok is False
    assert reason == DLQ_REASON_MISSING_WORKSPACE_ID

    # P3: Missing target_id when workspace_id is provided
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "workspace_id": 1,
        "target_id": None,
    })
    assert ok is False
    assert reason == DLQ_REASON_MISSING_TARGET_ID

    # Missing content (both content and content_snippet missing)
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "workspace_id": 1,
        "target_id": 1,
    })
    assert ok is False
    assert reason == DLQ_REASON_MISSING_CONTENT

    # Missing content (both empty strings or whitespace)
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "workspace_id": 1,
        "target_id": 1,
        "content": "",
        "content_snippet": "   ",
    })
    assert ok is False
    assert reason == DLQ_REASON_MISSING_CONTENT

    # Unsupported schema_version > max
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": SUPPORTED_SCHEMA_VERSION_MAX + 1,
    })
    assert ok is False
    assert reason == DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION

    # P2: Non-positive schema_version (0 and -1)
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": 0,
    })
    assert ok is False
    assert reason == DLQ_REASON_INVALID_SCHEMA_VERSION

    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": -1,
    })
    assert ok is False
    assert reason == DLQ_REASON_INVALID_SCHEMA_VERSION

    # Invalid schema_version (cannot parse int)
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": "abc",
    })
    assert ok is False
    assert reason == DLQ_REASON_INVALID_SCHEMA_VERSION

    # Invalid schema_version (boolean)
    ok, reason = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": True,
    })
    assert ok is False
    assert reason == DLQ_REASON_INVALID_SCHEMA_VERSION

    # Non-dict payload
    ok, reason = _validate_event_schema("not-a-dict")
    assert ok is False
    assert reason == DLQ_REASON_SCHEMA_VALIDATION_ERROR

    # Pydantic validation error: empty platform
    res = _validate_event_schema({
        "platform": "",
        "external_post_id": "p1",
        "content_snippet": "Hi there",
        "workspace_id": 1,
        "target_id": 1,
    })
    assert res.ok is False
    assert res.dlq_reason == DLQ_REASON_SCHEMA_VALIDATION_ERROR
    assert res.errors is not None


def test_safe_serialize_payload():
    from datetime import UTC, datetime
    from decimal import Decimal
    from uuid import uuid4

    valid = {"a": 1, "b": "hello"}
    assert _safe_serialize_payload(valid) == json.dumps(valid)

    # P11: default=str supports datetime, UUID, Decimal without error
    u = uuid4()
    now = datetime.now(UTC)
    dec = Decimal("45.67")
    payload = {"dt": now, "uuid": u, "dec": dec}
    serialized = _safe_serialize_payload(payload)
    assert str(u) in serialized
    assert "45.67" in serialized

    # Circular dict cannot be serialized by json.dumps even with default=str -> falls back to repr()
    circular: dict[str, Any] = {"key": "val"}
    circular["self"] = circular
    assert _safe_serialize_payload(circular) == repr(circular)


@pytest.mark.asyncio
async def test_consumer_schema_violation_routes_to_dlq_and_xacks():
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    bad_msg = (
        "1001-0",
        {
            "platform": "facebook",
            "external_post_id": "p1",
            "content_snippet": "Hello world",
            "workspace_id": 1,
            "schema_version": 2,
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [bad_msg])]

    processed = await run_social_stream_consumer(
        redis_client=mock_redis,
        max_loops=1,
    )

    assert processed == 0
    # Verified xadd to dead-letter stream
    assert mock_redis.xadd.await_count == 1
    call_args = mock_redis.xadd.await_args
    assert call_args.args[0] == STREAM_SOCIAL_DEAD_LETTER
    assert call_args.args[1]["original_id"] == "1001-0"
    assert call_args.args[1]["dlq_reason"] == DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION

    # Verified xack to acknowledge message
    assert mock_redis.xack.await_count == 1
    xack_args = mock_redis.xack.await_args
    assert xack_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "1001-0")


@pytest.mark.asyncio
async def test_consumer_missing_workspace_routes_to_dlq_and_xacks():
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    bad_msg = (
        "1002-0",
        {
            "platform": "facebook",
            "external_post_id": "p2",
            "content_snippet": "Missing workspace post",
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [bad_msg])]

    processed = await run_social_stream_consumer(
        redis_client=mock_redis,
        max_loops=1,
    )

    assert processed == 0
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.args[1]["dlq_reason"] == DLQ_REASON_MISSING_WORKSPACE_ID
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "1002-0")


@pytest.mark.asyncio
async def test_consumer_unresolvable_target_id_in_db_routes_to_dlq_and_xacks():
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    msg = (
        "1003-0",
        {
            "platform": "facebook",
            "external_post_id": "p3",
            "content_snippet": "Valid snippet",
            "target_id": 999,
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [msg])]

    fake_session = _FakeSession(target=None)

    with mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker:
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    assert processed == 0
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.args[1]["dlq_reason"] == DLQ_REASON_MISSING_WORKSPACE_ID
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "1003-0")


@pytest.mark.asyncio
async def test_dlq_xadd_failure_still_attempts_xack():
    mock_redis = mock.AsyncMock()
    mock_redis.xadd.side_effect = Exception("Redis connection failed")

    await _route_to_dlq(
        redis_client=mock_redis,
        msg_id="1004-0",
        payload={"platform": "fb"},
        dlq_reason=DLQ_REASON_SCHEMA_VALIDATION_ERROR,
    )

    # Even though xadd raised, xack was still called in finally block
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "1004-0")


@pytest.mark.asyncio
async def test_consumer_runtime_failure_routes_to_dlq_and_xacks():
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    msg = (
        "1005-0",
        {
            "platform": "facebook",
            "external_post_id": "p5",
            "content_snippet": "Valid snippet",
            "workspace_id": 1,
            "target_id": 1,
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [msg])]

    fake_session = _FakeSession()

    with (
        mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker,
        mock.patch(
            "app.tasks.social_stream_worker.process_social_post_event",
            side_effect=RuntimeError("Unexpected runtime crash"),
        ),
    ):
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    assert processed == 0
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.args[1]["dlq_reason"] == DLQ_REASON_RUNTIME_FAILURE
    assert "Unexpected runtime crash" in mock_redis.xadd.await_args.args[1]["error"]
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "1005-0")


@pytest.mark.asyncio
async def test_check_stream_lag_warns_when_pending_exceeds_threshold(caplog):
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [
        {"name": CONSUMER_GROUP_NAME, "lag": 42, "consumers": 3}
    ]
    mock_redis.xpending.return_value = {"pending": 2500}

    with caplog.at_level(logging.WARNING):
        metrics = await _check_stream_lag(mock_redis)

    assert metrics is not None
    assert metrics["pending_count"] == 2500
    assert metrics["lag"] == 42
    assert metrics["consumer_count"] == 3

    assert any(
        "pending=2500" in record.message
        and "consumer_count=3" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    )


@pytest.mark.asyncio
async def test_check_stream_lag_handles_nogroup_gracefully(caplog):
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.side_effect = ResponseError("NOGROUP No such consumer group")

    with caplog.at_level(logging.WARNING):
        metrics = await _check_stream_lag(mock_redis)

    assert metrics is None
    # No warning emitted
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


@pytest.mark.asyncio
async def test_check_stream_lag_handles_generic_exception_gracefully(caplog):
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.side_effect = ConnectionError("Redis down")

    with caplog.at_level(logging.WARNING):
        metrics = await _check_stream_lag(mock_redis)

    assert metrics is None
    # No warning emitted
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


@pytest.mark.asyncio
async def test_consumer_happy_path_with_content_snippet_xacks():
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    msg = (
        "1006-0",
        {
            "platform": "facebook",
            "external_post_id": "p6",
            "content_snippet": "Bán căn hộ 2PN",
            "workspace_id": 1,
            "target_id": 1,
            "schema_version": 1,
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [msg])]

    fake_session = _FakeSession()

    with (
        mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker,
        mock.patch(
            "app.tasks.social_stream_worker.process_social_post_event",
            return_value={"id": 1, "platform": "facebook"},
        ) as mock_process,
    ):
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    assert processed == 1
    assert mock_process.await_count == 1
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "1006-0")
    assert mock_redis.xadd.await_count == 0


@pytest.mark.asyncio
async def test_consumer_upsert_sqlalchemy_error_routes_to_runtime_failure():
    """P4: SQLAlchemyError in process_social_post_event raises and routes to DLQ as RUNTIME_FAILURE."""
    from sqlalchemy.exc import SQLAlchemyError

    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    msg = (
        "1007-0",
        {
            "platform": "facebook",
            "external_post_id": "p7",
            "content": "Bán đất Quận 2",
            "workspace_id": 1,
            "target_id": 1,
            "schema_version": 1,
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [msg])]

    fake_session = _FakeSession()
    fake_session.execute = mock.AsyncMock(side_effect=SQLAlchemyError("DB deadlock/timeout"))

    with mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker:
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    assert processed == 0
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.args[1]["dlq_reason"] == DLQ_REASON_RUNTIME_FAILURE
    assert "DB deadlock/timeout" in mock_redis.xadd.await_args.args[1]["error"]
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "1007-0")


@pytest.mark.asyncio
async def test_consumer_rollback_failure_does_not_crash_consumer():
    """P5: session.rollback() raising in exception handler does not crash consumer."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    msg = (
        "1008-0",
        {
            "platform": "facebook",
            "external_post_id": "p8",
            "content": "Bán đất",
            "workspace_id": 1,
            "target_id": 1,
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [msg])]

    fake_session = _FakeSession()
    fake_session.execute = mock.AsyncMock(side_effect=RuntimeError("Fatal query error"))
    fake_session.rollback = mock.AsyncMock(
        side_effect=ConnectionResetError("DB disconnected during rollback")
    )

    with mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker:
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    assert processed == 0
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.args[1]["dlq_reason"] == DLQ_REASON_RUNTIME_FAILURE
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "1008-0")


@pytest.mark.asyncio
async def test_check_stream_lag_warns_when_lag_exceeds_threshold(caplog):
    """P6: Warning is emitted when lag > threshold even if pending is 0."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [
        {"name": CONSUMER_GROUP_NAME, "lag": 2000, "consumers": 2}
    ]
    mock_redis.xpending.return_value = {"pending": 0}

    with caplog.at_level(logging.WARNING):
        metrics = await _check_stream_lag(mock_redis)

    assert metrics is not None
    assert metrics["pending_count"] == 0
    assert metrics["lag"] == 2000
    assert any(
        "lag=2000" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    )


@pytest.mark.asyncio
async def test_consumer_throttles_lag_probe():
    """P7: _check_stream_lag is throttled to once every 30 seconds."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}
    mock_redis.xreadgroup.return_value = []

    await run_social_stream_consumer(
        redis_client=mock_redis,
        max_loops=3,
    )

    # Across 3 consecutive iterations in milliseconds, xinfo_groups is called only once
    assert mock_redis.xinfo_groups.await_count == 1


@pytest.mark.asyncio
async def test_check_stream_lag_handles_byte_keys():
    """P8: _check_stream_lag correctly handles byte keys for name, pending, lag, and consumers."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [
        {b"name": CONSUMER_GROUP_NAME.encode(), b"lag": 50, b"consumers": 2}
    ]
    mock_redis.xpending.return_value = {b"pending": 100}

    metrics = await _check_stream_lag(mock_redis)
    assert metrics is not None
    assert metrics["pending_count"] == 100
    assert metrics["lag"] == 50
    assert metrics["consumer_count"] == 2


@pytest.mark.asyncio
async def test_route_to_dlq_sets_consistent_error_field():
    """P9: _route_to_dlq sets error field with human-readable diagnostic when errors is passed."""
    mock_redis = mock.AsyncMock()

    # When errors is provided, error should contain the errors content
    await _route_to_dlq(
        redis_client=mock_redis,
        msg_id="2001-0",
        payload={"platform": "fb"},
        dlq_reason=DLQ_REASON_SCHEMA_VALIDATION_ERROR,
        errors="Field 'platform' must not be empty",
    )
    call_data = mock_redis.xadd.await_args.args[1]
    assert call_data["error"] == "Field 'platform' must not be empty"
    assert call_data["errors"] == "Field 'platform' must not be empty"

    # When only error is provided
    await _route_to_dlq(
        redis_client=mock_redis,
        msg_id="2002-0",
        payload={"platform": "fb"},
        dlq_reason=DLQ_REASON_RUNTIME_FAILURE,
        error="Database connection timed out",
    )
    call_data2 = mock_redis.xadd.await_args.args[1]
    assert call_data2["error"] == "Database connection timed out"
    assert call_data2["errors"] == ""

    # When neither error nor errors is provided
    await _route_to_dlq(
        redis_client=mock_redis,
        msg_id="2003-0",
        payload={"platform": "fb"},
        dlq_reason=DLQ_REASON_MISSING_CONTENT,
    )
    call_data3 = mock_redis.xadd.await_args.args[1]
    assert call_data3["error"] == DLQ_REASON_MISSING_CONTENT
    assert call_data3["errors"] == ""


@pytest.mark.asyncio
async def test_route_to_dlq_uses_maxlen():
    """P10: DLQ xadd sets maxlen=50000 and approximate=True."""
    mock_redis = mock.AsyncMock()
    await _route_to_dlq(
        redis_client=mock_redis,
        msg_id="2004-0",
        payload={"a": 1},
        dlq_reason=DLQ_REASON_MISSING_CONTENT,
    )
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.kwargs.get("maxlen") == 50000
    assert mock_redis.xadd.await_args.kwargs.get("approximate") is True


@pytest.mark.asyncio
async def test_process_social_post_event_reuses_event_instance():
    """P12: process_social_post_event skips model_validate when event is provided."""
    event = SocialPostEvent(
        platform="facebook",
        external_post_id="p99",
        content="Testing reuse",
        workspace_id=1,
        target_id=1,
    )
    with mock.patch("app.tasks.social_stream_worker.SocialPostEvent.model_validate") as mock_val:
        res = await process_social_post_event(
            payload={"any": "payload"},
            event=event,
        )
        assert res is not None
        assert res["external_post_id"] == "p99"
        mock_val.assert_not_called()


@pytest.mark.asyncio
async def test_consumer_sleep_outside_session_context():
    """P13: asyncio.sleep is invoked outside async_session_maker context manager."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}
    mock_redis.xreadgroup.return_value = [
        (
            STREAM_SOCIAL_RAW_POSTS,
            [
                (
                    "3001-0",
                    {
                        "platform": "facebook",
                        "external_post_id": "p3001",
                        "content_snippet": "Snippet",
                        "workspace_id": 1,
                        "target_id": 1,
                    },
                )
            ],
        )
    ]

    session_active_during_sleep = []
    fake_session = _FakeSession()

    class TrackedSessionContext:
        def __init__(self):
            self.in_context = False

        async def __aenter__(self):
            self.in_context = True
            return fake_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.in_context = False
            return None

    ctx = TrackedSessionContext()

    async def fake_sleep(_duration):
        session_active_during_sleep.append(ctx.in_context)

    with (
        mock.patch("app.tasks.social_stream_worker.async_session_maker", return_value=ctx),
        mock.patch(
            "app.tasks.social_stream_worker.process_social_post_event",
            return_value={"id": 1},
        ),
        mock.patch("asyncio.sleep", side_effect=fake_sleep),
    ):
        await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    assert session_active_during_sleep == [False]


def test_validation_result_bool():
    """P14: ValidationResult bool conversion reflects ok attribute."""
    res_ok = ValidationResult(True, None, None, None)
    assert bool(res_ok) is True
    assert res_ok

    res_fail = ValidationResult(False, "SOME_REASON", "Some error", None)
    assert bool(res_fail) is False
    assert not res_fail


@pytest.mark.asyncio
async def test_consumer_persists_lag_check_across_invocations():
    """P15: _LAG_STATE persists across run_social_stream_consumer invocations."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}
    mock_redis.xreadgroup.return_value = []

    # First invocation runs lag probe
    await run_social_stream_consumer(
        redis_client=mock_redis,
        max_loops=1,
    )
    assert mock_redis.xinfo_groups.await_count == 1

    # Second invocation immediately after throttles lag probe
    await run_social_stream_consumer(
        redis_client=mock_redis,
        max_loops=1,
    )
    assert mock_redis.xinfo_groups.await_count == 1


@pytest.mark.asyncio
async def test_check_stream_lag_warns_when_both_pending_and_lag_exceed(caplog):
    """P16: Warning message contains both metrics when both exceed threshold."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [
        {"name": CONSUMER_GROUP_NAME, "lag": 1500, "consumers": 3}
    ]
    mock_redis.xpending.return_value = {"pending": 2000}

    with caplog.at_level(logging.WARNING):
        metrics = await _check_stream_lag(mock_redis)

    assert metrics is not None
    assert any(
        "pending=2000, lag=1500" in record.message
        and "consumer_count=3" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    )


def test_validate_event_schema_pydantic_error_is_valid_json():
    """P17: ValidationError.errors() is serialized as valid JSON."""
    res = _validate_event_schema({
        "platform": "",
        "external_post_id": "p1",
        "content": "Valid content",
        "workspace_id": 1,
        "target_id": 1,
    })
    assert res.ok is False
    assert res.dlq_reason == DLQ_REASON_SCHEMA_VALIDATION_ERROR
    assert res.errors is not None
    parsed = json.loads(res.errors)
    assert isinstance(parsed, list)
    assert len(parsed) > 0
    assert any(err["loc"] == ["platform"] for err in parsed)


@pytest.mark.asyncio
async def test_route_to_dlq_ensures_error_and_errors_keys_always_present():
    """P18: _route_to_dlq always includes error and errors keys."""
    mock_redis = mock.AsyncMock()
    await _route_to_dlq(
        redis_client=mock_redis,
        msg_id="2005-0",
        payload={"platform": "fb"},
        dlq_reason=DLQ_REASON_MISSING_CONTENT,
    )
    call_data = mock_redis.xadd.await_args.args[1]
    assert "error" in call_data
    assert "errors" in call_data
    assert call_data["error"] == DLQ_REASON_MISSING_CONTENT
    assert call_data["errors"] == ""


def test_validate_event_schema_rejects_float_and_none_versions():
    """P19 & P20: Reject non-integer float versions and schema_version=None."""
    # P19: float version 1.5
    res_float = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p_float",
        "content": "Hi",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": 1.5,
    })
    assert res_float.ok is False
    assert res_float.dlq_reason == DLQ_REASON_INVALID_SCHEMA_VERSION

    # integer float like 1.0 is valid
    res_float_int = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p_float_int",
        "content": "Hi",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": 1.0,
    })
    assert res_float_int.ok is True
    assert res_float_int.event.schema_version == 1

    # P20: schema_version is None
    res_none = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p_none",
        "content": "Hi",
        "workspace_id": 1,
        "target_id": 1,
        "schema_version": None,
    })
    assert res_none.ok is False
    assert res_none.dlq_reason == DLQ_REASON_INVALID_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_process_social_post_event_resolves_workspace_from_target():
    """P22: workspace_id=None with valid target_id resolves workspace_id from target."""
    from app.db import SocialMonitoredTarget

    fake_target = SocialMonitoredTarget(
        id=10,
        workspace_id=42,
        target_name="Monitored Target 10",
    )
    fake_session = _FakeSession(target=fake_target)

    event = SocialPostEvent(
        platform="facebook",
        external_post_id="p_target_ws_res",
        content="Testing target workspace resolution",
        target_id=10,
        workspace_id=None,
    )

    result = await process_social_post_event(
        session=fake_session,
        event=event,
    )

    assert result is not None
    assert result["workspace_id"] == 42
    assert event.workspace_id == 42
    assert fake_session.committed == 1


def test_validate_event_schema_missing_schema_version_defaults_to_1():
    """P23: Event without schema_version key validates successfully and defaults schema_version to 1."""
    payload = {
        "platform": "facebook",
        "external_post_id": "p_no_ver",
        "content_snippet": "Valid content snippet",
        "workspace_id": 1,
        "target_id": 1,
    }
    assert "schema_version" not in payload
    result = _validate_event_schema(payload)
    assert result.ok is True
    assert result.dlq_reason is None
    assert result.event is not None
    assert result.event.schema_version == 1


@pytest.mark.asyncio
async def test_consumer_session_corruption_breaks_batch_early():
    """P24: When DB session is corrupted (rollback fails), batch processing aborts early."""
    from sqlalchemy.exc import SQLAlchemyError

    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    msg1 = (
        "2001-0",
        {
            "platform": "facebook",
            "external_post_id": "p2001",
            "content_snippet": "First post",
            "workspace_id": 1,
            "target_id": 1,
        },
    )
    msg2 = (
        "2002-0",
        {
            "platform": "facebook",
            "external_post_id": "p2002",
            "content_snippet": "Second post",
            "workspace_id": 1,
            "target_id": 1,
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [msg1, msg2])]

    fake_session = _FakeSession()
    fake_session.execute = mock.AsyncMock(side_effect=SQLAlchemyError("Connection closed unexpectedly"))
    fake_session.rollback = mock.AsyncMock(side_effect=SQLAlchemyError("Rollback failed on dead connection"))

    with mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker:
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    assert processed == 0
    # Exactly one message was routed to DLQ (the first message)
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.args[1]["original_id"] == "2001-0"
    assert mock_redis.xadd.await_args.args[1]["dlq_reason"] == DLQ_REASON_RUNTIME_FAILURE
    # Exactly one message was ACK'd (the first message during DLQ routing)
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "2001-0")


@pytest.mark.asyncio
async def test_consumer_process_returns_none_routes_to_dlq():
    """P25: When process_social_post_event returns None (workspace/target
    resolution failed), caller routes to DLQ with MISSING_WORKSPACE_ID per spec
    row 51 — `target_id`-null fallback is handled inside _validate_event_schema,
    so process-layer failure means workspace_id could not be resolved."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    msg = (
        "2003-0",
        {
            "platform": "facebook",
            "external_post_id": "p2003",
            "content_snippet": "Valid snippet",
            "workspace_id": 1,
            "target_id": 1,
        },
    )
    mock_redis.xreadgroup.return_value = [(STREAM_SOCIAL_RAW_POSTS, [msg])]

    fake_session = _FakeSession()

    with (
        mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker,
        mock.patch(
            "app.tasks.social_stream_worker.process_social_post_event",
            return_value=None,
        ),
    ):
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    assert processed == 0
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.args[1]["original_id"] == "2003-0"
    assert mock_redis.xadd.await_args.args[1]["dlq_reason"] == DLQ_REASON_MISSING_WORKSPACE_ID
    assert "workspace_id could not be resolved" in mock_redis.xadd.await_args.args[1]["error"]
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, "2003-0")


@pytest.mark.asyncio
async def test_lag_probe_throttled_across_iterations():
    """P26: _check_stream_lag is throttled across iterations in the same consumer run with non-empty entries."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [{"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}]
    mock_redis.xpending.return_value = {"pending": 0}

    msg1 = (
        "3001-0",
        {
            "platform": "facebook",
            "external_post_id": "p3001",
            "content_snippet": "First iteration post",
            "workspace_id": 1,
            "target_id": 1,
        },
    )
    msg2 = (
        "3002-0",
        {
            "platform": "facebook",
            "external_post_id": "p3002",
            "content_snippet": "Second iteration post",
            "workspace_id": 1,
            "target_id": 1,
        },
    )

    mock_redis.xreadgroup.side_effect = [
        [(STREAM_SOCIAL_RAW_POSTS, [msg1])],
        [(STREAM_SOCIAL_RAW_POSTS, [msg2])],
    ]

    fake_session = _FakeSession()

    with (
        mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker,
        mock.patch(
            "app.tasks.social_stream_worker.process_social_post_event",
            return_value={"id": 1},
        ),
    ):
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=2,
        )

    assert processed == 2
    assert mock_redis.xreadgroup.await_count == 2
    # Despite 2 loop iterations, xinfo_groups and xpending were called only once
    assert mock_redis.xinfo_groups.await_count == 1
    assert mock_redis.xpending.await_count == 1


# ---------------------------------------------------------------------------
# Story 36.5 gap-fill tests — DLQ contract end-to-end, consumer-loop error
# branches, and edge-case gates. Appended by bmad-testarch-automate.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_to_dlq_serializes_non_serializable_payload_via_repr():
    """G1 [P1]: _route_to_dlq end-to-end — json.dumps fails on circular payload,
    so xadd receives payload=repr(payload) and original message is still XACK'd."""
    mock_redis = mock.AsyncMock()

    circular: dict[str, Any] = {"platform": "fb"}
    circular["self"] = circular  # json.dumps cannot serialize even with default=str

    await _route_to_dlq(
        redis_client=mock_redis,
        msg_id="4001-0",
        payload=circular,
        dlq_reason=DLQ_REASON_SCHEMA_VALIDATION_ERROR,
    )

    assert mock_redis.xadd.await_count == 1
    call_data = mock_redis.xadd.await_args.args[1]
    assert call_data["original_id"] == "4001-0"
    # payload fell back to repr() of the circular dict
    assert call_data["payload"] == repr(circular)
    assert call_data["dlq_reason"] == DLQ_REASON_SCHEMA_VALIDATION_ERROR
    # Original message still acknowledged despite serialization fallback
    assert mock_redis.xack.await_count == 1
    assert mock_redis.xack.await_args.args == (
        STREAM_SOCIAL_RAW_POSTS,
        CONSUMER_GROUP_NAME,
        "4001-0",
    )


@pytest.mark.asyncio
async def test_route_to_dlq_xack_failure_does_not_propagate(caplog):
    """G2 [P1]: When the DLQ-path XACK itself raises, the exception is logged and
    swallowed inside the finally block — _route_to_dlq never propagates."""
    mock_redis = mock.AsyncMock()
    mock_redis.xack.side_effect = ConnectionError("Redis reset during XACK")

    with caplog.at_level(logging.ERROR):
        # Must not raise
        await _route_to_dlq(
            redis_client=mock_redis,
            msg_id="4002-0",
            payload={"platform": "fb"},
            dlq_reason=DLQ_REASON_MISSING_CONTENT,
        )

    # xadd succeeded, xack attempted and failed — logged via logger.exception
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xack.await_count == 1
    assert any(
        "Failed to ACK social stream message 4002-0" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_consumer_xreadgroup_error_breaks_and_returns_partial_count():
    """G3 [P1]: xreadgroup raising mid-loop breaks the consumer and returns the
    count of messages already processed — the exception never propagates."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [
        {"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}
    ]
    mock_redis.xpending.return_value = {"pending": 0}

    good_msg = (
        "4003-0",
        {
            "platform": "facebook",
            "external_post_id": "p4003",
            "content_snippet": "Valid first-batch post",
            "workspace_id": 1,
            "target_id": 1,
        },
    )

    # First read returns a processable message; second read raises.
    mock_redis.xreadgroup.side_effect = [
        [(STREAM_SOCIAL_RAW_POSTS, [good_msg])],
        ConnectionError("Redis stream read failed"),
    ]

    fake_session = _FakeSession()
    with (
        mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker,
        mock.patch(
            "app.tasks.social_stream_worker.process_social_post_event",
            return_value={"id": 1},
        ),
    ):
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=3,
        )

    # Loop broke on the read error; the one already-processed message is counted.
    assert processed == 1
    assert mock_redis.xreadgroup.await_count == 2


@pytest.mark.asyncio
async def test_consumer_group_create_non_busygroup_error_returns_zero():
    """G4 [P1]: A non-BUSYGROUP ResponseError from xgroup_create aborts the
    consumer with return 0 before any xreadgroup call."""
    mock_redis = mock.AsyncMock()
    mock_redis.xgroup_create.side_effect = ResponseError(
        "ERR unknown command or stream error"
    )

    processed = await run_social_stream_consumer(
        redis_client=mock_redis,
        max_loops=1,
    )

    assert processed == 0
    assert mock_redis.xreadgroup.await_count == 0
    assert mock_redis.xadd.await_count == 0


@pytest.mark.asyncio
async def test_check_stream_lag_handles_int_pending_info():
    """G5 [P2]: XPENDING returning a bare int (not a dict) still parses to
    pending_count correctly."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [
        {"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}
    ]
    mock_redis.xpending.return_value = 2500  # bare int, not dict

    metrics = await _check_stream_lag(mock_redis)

    assert metrics is not None
    assert metrics["pending_count"] == 2500


def test_validate_event_schema_zero_and_negative_ids_count_as_missing():
    """G6 [P1]: target_id=0 / workspace_id=0 (and negatives) fail the int>0 gate
    and are treated as missing rather than valid identifiers."""
    # target_id=0 -> missing target; workspace_id present -> MISSING_TARGET_ID
    res = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p_zero_t",
        "content_snippet": "Hello",
        "workspace_id": 1,
        "target_id": 0,
    })
    assert res.ok is False
    assert res.dlq_reason == DLQ_REASON_MISSING_TARGET_ID

    # workspace_id=0 and target_id=0 -> both missing -> MISSING_WORKSPACE_ID
    res = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p_zero_both",
        "content_snippet": "Hello",
        "workspace_id": 0,
        "target_id": 0,
    })
    assert res.ok is False
    assert res.dlq_reason == DLQ_REASON_MISSING_WORKSPACE_ID

    # negative target_id -> missing target
    res = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p_neg_t",
        "content_snippet": "Hello",
        "workspace_id": 1,
        "target_id": -5,
    })
    assert res.ok is False
    assert res.dlq_reason == DLQ_REASON_MISSING_TARGET_ID


def test_validate_event_schema_non_string_truthy_content_passes():
    """G7 [P2]: A non-string but truthy content value (e.g. int 123) satisfies the
    has_content gate via str(content).strip() — so it is NOT dropped as
    MISSING_CONTENT. It then fails Pydantic type coercion and routes to DLQ as
    SCHEMA_VALIDATION_ERROR instead (the stage-4 contract, not the stage-2 gate)."""
    res = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p_int_content",
        "content": 123,
        "workspace_id": 1,
        "target_id": 1,
    })
    # Stage-2 content gate passed (str(123).strip() is truthy), but stage-4
    # Pydantic validation rejects int for a `str` field -> SCHEMA_VALIDATION_ERROR.
    assert res.ok is False
    assert res.dlq_reason == DLQ_REASON_SCHEMA_VALIDATION_ERROR
    # Distinctly not MISSING_CONTENT — the point of this test.
    assert res.dlq_reason != DLQ_REASON_MISSING_CONTENT


@pytest.mark.asyncio
async def test_consumer_mixed_batch_valid_and_invalid_messages():
    """G8 [P1]: One batch containing a valid message and a schema-violation —
    the valid one is processed + XACK'd, the invalid one routed to DLQ + XACK'd,
    and total_processed reflects only the valid message."""
    mock_redis = mock.AsyncMock()
    mock_redis.xinfo_groups.return_value = [
        {"name": CONSUMER_GROUP_NAME, "lag": 0, "consumers": 1}
    ]
    mock_redis.xpending.return_value = {"pending": 0}

    valid_msg = (
        "4004-0",
        {
            "platform": "facebook",
            "external_post_id": "p4004",
            "content_snippet": "Valid mixed-batch post",
            "workspace_id": 1,
            "target_id": 1,
        },
    )
    invalid_msg = (
        "4005-0",
        {
            "platform": "facebook",
            "external_post_id": "p4005",
            "content_snippet": "Future schema",
            "workspace_id": 1,
            "target_id": 1,
            "schema_version": SUPPORTED_SCHEMA_VERSION_MAX + 1,
        },
    )
    mock_redis.xreadgroup.return_value = [
        (STREAM_SOCIAL_RAW_POSTS, [valid_msg, invalid_msg])
    ]

    fake_session = _FakeSession()
    with (
        mock.patch("app.tasks.social_stream_worker.async_session_maker") as mock_maker,
        mock.patch(
            "app.tasks.social_stream_worker.process_social_post_event",
            return_value={"id": 1},
        ) as mock_process,
    ):
        mock_ctx = mock.AsyncMock()
        mock_ctx.__aenter__.return_value = fake_session
        mock_ctx.__aexit__.return_value = None
        mock_maker.return_value = mock_ctx

        processed = await run_social_stream_consumer(
            redis_client=mock_redis,
            max_loops=1,
        )

    # Only the valid message counts toward processed.
    assert processed == 1
    # process_social_post_event invoked once (invalid skipped via `continue`).
    assert mock_process.await_count == 1
    # DLQ write for the invalid message only.
    assert mock_redis.xadd.await_count == 1
    assert mock_redis.xadd.await_args.args[1]["original_id"] == "4005-0"
    assert (
        mock_redis.xadd.await_args.args[1]["dlq_reason"]
        == DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION
    )
    # Both messages ACK'd: one via success path, one via DLQ path.
    assert mock_redis.xack.await_count == 2
    acked_ids = {call.args[2] for call in mock_redis.xack.await_args_list}
    assert acked_ids == {"4004-0", "4005-0"}


def test_validate_event_schema_string_schema_version_from_stream():
    """G9 [P1]: Redis xadd emits every field as a string — schema_version arriving
    as "1" must parse to int 1 and validate successfully (REQ-X2 realistic shape)."""
    res = _validate_event_schema({
        "platform": "facebook",
        "external_post_id": "p_str_ver",
        "content_snippet": "String version event",
        "workspace_id": "1",  # also arrives as string from Redis
        "target_id": "1",
        "schema_version": "1",
    })
    assert res.ok is True
    assert res.dlq_reason is None
    assert res.event is not None
    assert res.event.schema_version == 1


@pytest.mark.asyncio
async def test_route_to_dlq_entry_shape_and_payload_deserializable():
    """G10 [P2]: The DLQ entry written to stream:social:failed carries the full
    contract shape and the serialized payload is JSON-deserializable for replay."""
    mock_redis = mock.AsyncMock()
    payload = {
        "platform": "facebook",
        "external_post_id": "p_shape",
        "content_snippet": "DLQ shape check",
        "workspace_id": 1,
    }

    await _route_to_dlq(
        redis_client=mock_redis,
        msg_id="4006-0",
        payload=payload,
        dlq_reason=DLQ_REASON_MISSING_TARGET_ID,
        error="target_id is missing",
    )

    call_data = mock_redis.xadd.await_args.args[1]
    # Full contract shape present
    for key in (
        "original_id",
        "payload",
        "dlq_reason",
        "error",
        "errors",
        "failed_at",
    ):
        assert key in call_data

    # payload field is valid JSON that round-trips back to the original dict
    restored = json.loads(call_data["payload"])
    assert restored == payload
    assert call_data["original_id"] == "4006-0"
    # failed_at is an ISO-8601 timestamp string
    datetime.fromisoformat(call_data["failed_at"])
