"""Unit tests for HealthResultStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_health import AdminHealthHistory, AdminHealthStatus
from app.services.health.probe_base import HealthResult
from app.services.health.result_store import HealthResultStore


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return a mock AsyncSession with common async methods."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def base_result() -> HealthResult:
    """Return a base HealthResult for tests."""
    return HealthResult(
        service_id="test/service",
        service_name="Test Service",
        category="test",
        display_group="Test Group",
        status="healthy",
        latency_ms=10,
        error_rate_15m=0.0,
        success_rate_15m=100.0,
        metadata={"key": "value"},
        probed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_save_result_upserts_status_and_publishes(
    mock_session: AsyncMock,
    base_result: HealthResult,
) -> None:
    """save_result should insert history, upsert status, and publish to Redis."""
    mock_tot = MagicMock()
    mock_tot.scalar.return_value = 10
    mock_err = MagicMock()
    mock_err.scalar.return_value = 1

    mock_upsert = MagicMock()
    mock_upsert.scalar_one.return_value = AdminHealthStatus(
        id=1,
        service_id=base_result.service_id,
    )

    # execute returns different objects: tot_query, err_query, upsert, select
    mock_session.execute = AsyncMock(side_effect=[mock_tot, mock_err, mock_upsert, mock_upsert])

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()
    mock_redis.publish = AsyncMock()

    with patch("app.services.health.result_store.get_redis_client", new_callable=AsyncMock, return_value=mock_redis):
        record = await HealthResultStore.save_result(mock_session, base_result)

    assert record is not None
    assert record.service_id == base_result.service_id
    assert base_result.success_rate_15m == 90.0
    assert base_result.error_rate_15m == 10.0

    # History added
    assert mock_session.add.called

    # Status upserted and committed
    assert mock_session.commit.called
    assert mock_session.refresh.called

    # Redis snapshot + pub/sub
    assert mock_redis.set.called
    assert mock_redis.publish.called


@pytest.mark.asyncio
async def test_save_result_counts_degraded_as_error(
    mock_session: AsyncMock,
    base_result: HealthResult,
) -> None:
    """Rolling 15m rate should count degraded and unavailable as errors."""
    base_result.status = "degraded"
    base_result.error_rate_15m = 0.0
    base_result.success_rate_15m = 100.0

    mock_tot = MagicMock()
    mock_tot.scalar.return_value = 4
    mock_err = MagicMock()
    # 1 unavailable + current degraded = 2 errors
    mock_err.scalar.return_value = 2

    mock_upsert = MagicMock()
    mock_upsert.scalar_one.return_value = AdminHealthStatus(
        id=1,
        service_id=base_result.service_id,
        metadata_payload={},
        next_probe_at=datetime.now(UTC),
    )

    mock_session.execute = AsyncMock(side_effect=[mock_tot, mock_err, mock_upsert, mock_upsert])

    mock_redis = AsyncMock()
    with patch("app.services.health.result_store.get_redis_client", new_callable=AsyncMock, return_value=mock_redis):
        await HealthResultStore.save_result(mock_session, base_result)

    assert base_result.error_rate_15m == 50.0
    assert base_result.success_rate_15m == 50.0


@pytest.mark.asyncio
async def test_save_result_sanitizes_error_and_metadata(
    mock_session: AsyncMock,
    base_result: HealthResult,
) -> None:
    """Credentials in last_error and metadata should be redacted."""
    base_result.last_error = "api_key=super_secret failed"
    base_result.metadata = {"token": "token=leaked_token", "url": "https://example.com"}

    mock_tot = MagicMock()
    mock_tot.scalar.return_value = 1
    mock_err = MagicMock()
    mock_err.scalar.return_value = 0

    mock_upsert = MagicMock()
    status_record = AdminHealthStatus(id=1, service_id=base_result.service_id)
    mock_upsert.scalar_one.return_value = status_record

    captured_history = None

    def capture_add(instance: AdminHealthHistory) -> None:
        nonlocal captured_history
        captured_history = instance

    mock_session.add = MagicMock(side_effect=capture_add)
    mock_session.execute = AsyncMock(side_effect=[mock_tot, mock_err, mock_upsert, mock_upsert])

    status_record.next_probe_at = base_result.next_probe_at
    status_record.metadata_payload = {"token": "token=***", "url": "https://example.com"}

    mock_redis = AsyncMock()
    with patch("app.services.health.result_store.get_redis_client", new_callable=AsyncMock, return_value=mock_redis):
        await HealthResultStore.save_result(mock_session, base_result)

    assert captured_history is not None
    assert "api_key=***" in captured_history.error_message
    assert "super_secret" not in captured_history.error_message
    # Metadata with token redacted but url untouched
    assert "token=***" in status_record.metadata_payload.get("token", "")
    assert status_record.metadata_payload.get("url") == "https://example.com"


@pytest.mark.asyncio
async def test_save_result_uses_probe_interval_for_next_probe(
    mock_session: AsyncMock,
    base_result: HealthResult,
) -> None:
    """next_probe_at should be derived from result.interval_seconds or probe-provided value."""
    base_result.interval_seconds = 60
    base_result.next_probe_at = None

    mock_tot = MagicMock()
    mock_tot.scalar.return_value = 1
    mock_err = MagicMock()
    mock_err.scalar.return_value = 0

    expected_next = base_result.probed_at + timedelta(seconds=60)

    mock_upsert = MagicMock()
    status_record = AdminHealthStatus(
        id=1,
        service_id=base_result.service_id,
        next_probe_at=expected_next,
        metadata_payload={},
    )
    mock_upsert.scalar_one.return_value = status_record

    mock_session.execute = AsyncMock(side_effect=[mock_tot, mock_err, mock_upsert, mock_upsert])

    mock_redis = AsyncMock()
    with patch("app.services.health.result_store.get_redis_client", new_callable=AsyncMock, return_value=mock_redis):
        await HealthResultStore.save_result(mock_session, base_result)

    assert status_record.next_probe_at is not None
    # Allow small clock skew
    assert abs((status_record.next_probe_at - expected_next).total_seconds()) < 5


@pytest.mark.asyncio
async def test_save_result_redis_failure_does_not_raise(
    mock_session: AsyncMock,
    base_result: HealthResult,
) -> None:
    """Redis publish failures should be best-effort and not break persistence."""
    mock_tot = MagicMock()
    mock_tot.scalar.return_value = 1
    mock_err = MagicMock()
    mock_err.scalar.return_value = 0

    mock_upsert = MagicMock()
    mock_upsert.scalar_one.return_value = AdminHealthStatus(
        id=1,
        service_id=base_result.service_id,
        metadata_payload={},
        next_probe_at=datetime.now(UTC),
    )

    mock_session.execute = AsyncMock(side_effect=[mock_tot, mock_err, mock_upsert, mock_upsert])

    with patch("app.services.health.result_store.get_redis_client", new_callable=AsyncMock, side_effect=Exception("redis down")):
        record = await HealthResultStore.save_result(mock_session, base_result)

    assert record is not None
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_get_history_returns_records(mock_session: AsyncMock) -> None:
    """get_history should query and return history records."""
    expected = [
        AdminHealthHistory(
            id=1,
            service_id="test/service",
            status="healthy",
            probe_at=datetime.now(UTC) - timedelta(hours=1),
        ),
        AdminHealthHistory(
            id=2,
            service_id="test/service",
            status="degraded",
            probe_at=datetime.now(UTC) - timedelta(hours=2),
        ),
    ]
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = expected
    mock_session.execute = AsyncMock(return_value=mock_res)

    items = await HealthResultStore.get_history(mock_session, "test/service", hours=24)
    assert len(items) == 2
    assert items[0].status == "healthy"
