"""Unit tests for AdminTelemetryService (Story 25.4).

These tests mock the database session, Redis, Celery, and HTTP clients so they
run without Postgres/Redis/Celery workers.
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.admin_telemetry_service import AdminTelemetryService

pytestmark = pytest.mark.unit


class _Row:
    """Simple row container for mocking SQLAlchemy result rows."""

    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _MockResult:
    """Minimal async result mock."""

    def __init__(self, rows: list[_Row] | None = None):
        self._rows = rows or []

    def one(self) -> _Row:
        return self._rows[0]

    def one_or_none(self) -> _Row | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[_Row]:
        return self._rows


@pytest.fixture
def service() -> AdminTelemetryService:
    session = AsyncMock()
    return AdminTelemetryService(session)


def _llm_cost_empty_results() -> list[_MockResult]:
    """Return the sequence of _MockResult objects for a no-data llm-cost call."""
    total = _Row(
        total_tokens=0,
        total_cost_micros=0,
        input_tokens=0,
        output_tokens=0,
        unreported_cost_rows=0,
    )
    billing = _Row(billing_cost_micros=0)
    return [
        _MockResult([total]),  # totals
        _MockResult([]),  # provider
        _MockResult([]),  # model
        _MockResult([]),  # workspace
        _MockResult([]),  # usage_type
        _MockResult([]),  # time_series
        _MockResult([billing]),  # billing cost
    ]


def _gross_margin_empty_results() -> list[_MockResult]:
    """Return the sequence of _MockResult objects for a no-data gross margin call."""
    return [
        _MockResult([]),  # revenue per bucket
        _MockResult([]),  # token cogs per bucket
        _MockResult([]),  # billing cogs per bucket
        _MockResult([]),  # workspace revenue
        _MockResult([]),  # workspace token cogs
        _MockResult([]),  # workspace billing cogs
        _MockResult([]),  # worst model
    ]


@pytest.mark.asyncio
async def test_clamp_window_rejects_negative(service: AdminTelemetryService) -> None:
    """AC-1/Q3: window_hours < 1 is clamped to 1."""
    service.session.execute = AsyncMock(side_effect=_llm_cost_empty_results())
    result = await service.get_llm_cost_breakdown(-5)
    assert result["window_hours"] == 1


@pytest.mark.asyncio
async def test_clamp_window_rejects_excessive(service: AdminTelemetryService) -> None:
    """AC-1/Q3: window_hours > 720 is clamped to 720."""
    service.session.execute = AsyncMock(side_effect=_llm_cost_empty_results())
    result = await service.get_llm_cost_breakdown(9999)
    assert result["window_hours"] == 720


@pytest.mark.asyncio
async def test_get_llm_cost_splits_billing_cost(service: AdminTelemetryService) -> None:
    """Billing cost is split out from total_cost_micros for visibility."""
    total = _Row(
        total_tokens=100,
        total_cost_micros=1234,
        input_tokens=60,
        output_tokens=40,
        unreported_cost_rows=2,
    )
    billing = _Row(billing_cost_micros=567)
    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult([total]),
            _MockResult([]),
            _MockResult([]),
            _MockResult([]),
            _MockResult([]),
            _MockResult([]),
            _MockResult([billing]),
        ]
    )
    result = await service.get_llm_cost_breakdown(24)
    assert result["total_cost_micros"] == 1234
    assert result["billing_cost_micros"] == 567
    assert result["non_llm_cost_micros"] == 567
    assert result["unreported_cost_rows"] == 2


@pytest.mark.asyncio
async def test_get_llm_cost_unknown_provider_buckets_to_unknown(
    service: AdminTelemetryService,
) -> None:
    """Non-allowed provider values are aggregated into the 'unknown' bucket."""
    total = _Row(
        total_tokens=10,
        total_cost_micros=100,
        input_tokens=5,
        output_tokens=5,
        unreported_cost_rows=0,
    )
    billing = _Row(billing_cost_micros=0)
    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult([total]),
            _MockResult([]),
            _MockResult([]),
            _MockResult([]),
            _MockResult([]),
            _MockResult([]),
            _MockResult([billing]),
        ]
    )
    result = await service.get_llm_cost_breakdown(24, provider="somevendor")
    assert result["window_hours"] == 24
    assert result["provider"] == "somevendor"


@pytest.mark.asyncio
async def test_gross_margin_handles_zero_revenue(
    service: AdminTelemetryService,
) -> None:
    """AC-1/Q3: revenue=0 returns N/A margin, not a division error."""
    service.session.execute = AsyncMock(side_effect=_gross_margin_empty_results())
    result = await service.get_gross_margin(24)
    assert result["overall_gross_margin"] is None
    assert result["total_revenue_micros"] == 0
    assert result["total_cogs_micros"] == 0
    assert result["worst_workspace_id"] is None
    assert result["worst_model"] is None


@pytest.mark.asyncio
async def test_gross_margin_computes_per_workspace_and_model(
    service: AdminTelemetryService,
) -> None:
    """Worst workspace margin uses per-workspace revenue/cogs; worst model is returned."""
    revenue = _Row(period="2024-08-26 00:00", revenue_micros=2_000_000)
    token_cogs = _Row(period="2024-08-26 00:00", cogs_micros=800_000)
    billing_cogs = _Row(period="2024-08-26 00:00", cogs_micros=100_000)
    ws_revenue = _Row(workspace_id=1, revenue_micros=2_000_000)
    ws_cogs = _Row(workspace_id=1, cogs_micros=1_500_000)
    worst_model = _Row(model="gpt-4o", cogs_micros=800_000)

    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult([revenue]),
            _MockResult([token_cogs]),
            _MockResult([billing_cogs]),
            _MockResult([ws_revenue]),
            _MockResult([ws_cogs]),
            _MockResult([]),
            _MockResult([worst_model]),
        ]
    )
    result = await service.get_gross_margin(24)
    assert result["total_revenue_micros"] == 2_000_000
    assert result["total_cogs_micros"] == 900_000
    assert result["overall_gross_margin"] == (2_000_000 - 900_000) / 2_000_000
    assert result["worst_workspace_id"] == 1
    assert result["worst_workspace_margin"] == (2_000_000 - 1_500_000) / 2_000_000
    assert result["worst_model"] == "gpt-4o"


@pytest.mark.asyncio
@patch("app.services.admin_telemetry_service.get_active_provider")
@patch(
    "app.services.admin_telemetry_service.get_proxy_health_snapshot", return_value=None
)
async def test_proxy_health_not_configured(
    _cache: MagicMock,
    get_active_provider: MagicMock,
    service: AdminTelemetryService,
) -> None:
    """AC-2/Q3: empty PROXY_URL returns not_configured without a network call."""
    provider = MagicMock()
    provider.name = "custom"
    provider.get_proxy_url.return_value = None
    get_active_provider.return_value = provider

    result = await service.get_proxy_health()
    assert result["status"] == "not_configured"
    assert result["snapshots"] == []


@pytest.mark.asyncio
@patch("app.services.admin_telemetry_service.get_active_provider")
@patch(
    "app.services.admin_telemetry_service.get_proxy_health_snapshot", return_value=None
)
@patch("app.services.admin_telemetry_service.httpx.AsyncClient")
async def test_proxy_health_probe_dead_on_timeout(
    client_cls: MagicMock,
    _cache: MagicMock,
    get_active_provider: MagicMock,
    service: AdminTelemetryService,
) -> None:
    """AC-2/Q4: probe timeout marks proxy dead and redacts credentials."""
    provider = MagicMock()
    provider.name = "dataimpulse"
    provider.get_proxy_url.return_value = "http://user:pass@gw.example:823"
    provider.get_requests_proxies.return_value = {
        "http": "http://user:pass@gw.example:823"
    }
    get_active_provider.return_value = provider

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.head = AsyncMock(side_effect=TimeoutError("probe timed out"))
    client_cls.return_value = client

    result = await service.get_proxy_health()
    assert result["status"] == "dead"
    assert result["snapshots"][0]["last_error"].startswith("TimeoutError")
    assert "user:pass" not in (result["snapshots"][0]["url"] or "")


@pytest.mark.asyncio
@patch("app.services.admin_telemetry_service.get_active_provider")
@patch(
    "app.services.admin_telemetry_service.get_proxy_health_snapshot", return_value=None
)
@patch("app.services.admin_telemetry_service.httpx.AsyncClient")
async def test_proxy_health_probe_success(
    client_cls: MagicMock,
    _cache: MagicMock,
    get_active_provider: MagicMock,
    service: AdminTelemetryService,
) -> None:
    """A successful probe reports healthy and redacts the proxy URL."""
    provider = MagicMock()
    provider.name = "dataimpulse"
    provider.get_proxy_url.return_value = "http://user:pass@gw.example:823"
    provider.get_requests_proxies.return_value = {
        "https": "http://user:pass@gw.example:823",
        "http": "http://user:pass@gw.example:823",
    }
    get_active_provider.return_value = provider

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    response = MagicMock()
    response.status_code = 200
    client.head = AsyncMock(return_value=response)
    client_cls.return_value = client

    result = await service.get_proxy_health()
    assert result["status"] == "healthy"
    assert result["snapshots"][0]["latency_ms"] is not None
    assert "user:pass" not in (result["snapshots"][0]["url"] or "")
    # httpx 0.28.1 uses ``proxy=`` with a string, not ``proxies=``.
    _, kwargs = client_cls.call_args
    assert "proxies" not in kwargs
    assert kwargs.get("proxy") == "http://user:pass@gw.example:823"


@pytest.mark.asyncio
@patch("app.services.admin_telemetry_service.celery_app")
async def test_celery_queue_stats_unavailable_when_broker_down(
    celery_app: MagicMock,
    service: AdminTelemetryService,
) -> None:
    """AC-3/Q4: unreachable broker returns 200 status unavailable, not 500."""
    celery_app.control.inspect.side_effect = Exception("broker down")

    result = await service.get_celery_queue_stats()
    assert result["status"] == "unavailable"
    assert result["active_workers"] == 0
    assert result["queues"] == []


@pytest.mark.asyncio
@patch("app.services.admin_telemetry_service._redis_queue_lengths")
@patch("app.services.admin_telemetry_service.celery_app")
async def test_celery_queue_stats_success(
    celery_app: MagicMock,
    queue_lengths: MagicMock,
    service: AdminTelemetryService,
) -> None:
    """AC-3: successful Celery inspection returns queue stats."""
    inspect = MagicMock()
    inspect.stats.return_value = {"worker1": {"total": {"tasks": {}}}}
    inspect.active.return_value = {
        "worker1": [{"delivery_info": {"routing_key": "celery"}}]
    }
    inspect.scheduled.return_value = {
        "worker1": [[{"delivery_info": {"routing_key": "celery"}}, "eta"]]
    }
    inspect.reserved.return_value = {"worker1": []}
    inspect.active_queues.return_value = {
        "worker1": [{"name": "celery"}, {"name": "celery.connectors"}]
    }
    celery_app.control.inspect.return_value = inspect
    queue_lengths.return_value = {"celery": 5, "celery.connectors": 0}

    result = await service.get_celery_queue_stats()
    assert result["status"] == "healthy"
    assert result["active_workers"] == 1
    assert any(q["name"] == "celery" for q in result["queues"])
    assert any(q["name"] == "celery.connectors" for q in result["queues"])


class _FakePipeline:
    def __init__(self, client: _FakeRedis) -> None:
        self.client = client

    async def __aenter__(self) -> _FakePipeline:
        return self

    async def __aexit__(self, *_: object) -> None:
        return

    def delete(self, name: str) -> None:
        self.client.deleted.append(name)

    def rpush(self, name: str, *values: bytes) -> None:
        self.client.repushed.extend(values)

    async def execute(self) -> None:
        return


class _FakeLock:
    async def acquire(self, blocking: bool = False) -> bool:
        return True

    async def release(self) -> None:
        return


class _FakeRedis:
    def __init__(self, messages: list[bytes]) -> None:
        self.messages = messages
        self.deleted: list[str] = []
        self.repushed: list[bytes] = []

    async def llen(self, name: str) -> int:
        return len(self.messages)

    async def lrange(self, name: str, start: int, stop: int) -> list[bytes]:
        if stop < 0:
            return self.messages[start:]
        return self.messages[start : stop + 1]

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        return _FakePipeline(self)

    def lock(self, name: str, timeout: int = 10) -> _FakeLock:
        return _FakeLock()

    async def aclose(self) -> None:
        return


def _celery_message(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode()


@pytest.mark.asyncio
@patch("redis.asyncio.from_url")
async def test_purge_dead_letter_queue_removes_stalled_messages(
    from_url: MagicMock,
    service: AdminTelemetryService,
) -> None:
    """Purge drops stalled messages using the correct wall vs monotonic clocks."""
    now_wall = time.time()
    now_mono = time.monotonic_ns()

    messages = [
        # Stalled via wall-clock timestamps["sent"].
        _celery_message({"properties": {"timestamps": {"sent": now_wall - 600}}}),
        # Stalled via nowing.enqueued_at_ns (monotonic).
        _celery_message(
            {"headers": {"nowing.enqueued_at_ns": str(now_mono - 600 * 1_000_000_000)}}
        ),
        # Fresh message.
        _celery_message({"headers": {"nowing.enqueued_at_ns": str(now_mono)}}),
    ]

    fake_client = _FakeRedis(messages)
    from_url.return_value = fake_client

    with patch(
        "app.services.admin_telemetry_service.config.CELERY_BROKER_URL",
        "redis://localhost:6379/0",
    ):
        result = await service.purge_dead_letter_queue("nowing")
    assert result["queue_name"] == "nowing"
    assert result["purged_count"] == 2
    assert len(fake_client.repushed) == 1


@pytest.mark.asyncio
@patch("redis.asyncio.from_url")
async def test_purge_uses_rediss_url(
    from_url: MagicMock,
    service: AdminTelemetryService,
) -> None:
    """rediss:// broker URLs are accepted and used."""
    with patch(
        "app.services.admin_telemetry_service.config.CELERY_BROKER_URL",
        "rediss://localhost:6379/0",
    ):
        fake_client = _FakeRedis([])
        from_url.return_value = fake_client
        result = await service.purge_dead_letter_queue("nowing")
        assert result["purged_count"] == 0
        assert result["queue_name"] == "nowing"
