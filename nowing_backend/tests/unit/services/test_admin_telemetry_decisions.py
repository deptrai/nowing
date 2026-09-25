"""Unit tests for DecisionTelemetryMixin (Story 39.7).

Mock-session tests covering the spec's I/O matrix: aggregations,
accuracy-null, alert dedup/acked, drift, and window clamping. Session
``execute`` calls run in a fixed order inside ``get_decision_telemetry``:

1. totals            (.one())
2. daily x task      (.all())
3. by_task           (.all())
4. models            (.all())
5. today cost        (.one())
6. advisory lock     (result unused) — only when today's cost exceeds the threshold
7. alert dedupe      (.first()) — only when today's cost exceeds the threshold
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.config.decision as decision_config
from app.models.admin_health import AdminHealthAlert
from app.services.admin_telemetry_service import AdminTelemetryService

pytestmark = pytest.mark.unit


class _Row:
    """Simple row container for mocking SQLAlchemy result rows."""

    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _MockResult:
    """Minimal async result mock."""

    def __init__(self, rows: list[Any] | None = None):
        self._rows = rows or []

    def one(self) -> Any:
        return self._rows[0]

    def one_or_none(self) -> Any | None:
        return self._rows[0] if self._rows else None

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return self._rows

    def scalar_one_or_none(self) -> Any | None:
        return self._rows[0] if self._rows else None


def _totals(
    calls: int = 0,
    cost_micros: int = 0,
    median_ms: float | None = None,
    labeled: int = 0,
    correct: int = 0,
) -> _Row:
    return _Row(
        calls=calls,
        cost_micros=cost_micros,
        median_ms=median_ms,
        labeled=labeled,
        correct=correct,
    )


def _results(
    *,
    totals: _Row | None = None,
    daily: list[_Row] | None = None,
    by_task: list[_Row] | None = None,
    models: list[_Row] | None = None,
    today_cost_micros: int = 0,
    dedupe: list[_Row] | None = None,
    exceeded: bool = False,
) -> list[_MockResult]:
    """Build the execute() side_effect sequence for one telemetry read."""
    t = totals or _totals()
    results = [
        _MockResult([_Row(labeled=t.labeled, correct=t.correct)]),  # accuracy
        _MockResult([t]),
        _MockResult(daily or []),
        _MockResult(by_task or []),
        _MockResult(models or []),
        _MockResult([_Row(cost_micros=today_cost_micros)]),
    ]
    if exceeded:
        results.append(_MockResult())  # pg_advisory_xact_lock
        results.append(_MockResult(dedupe or []))  # dedupe select
    return results


@pytest.fixture
def service() -> AdminTelemetryService:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return AdminTelemetryService(session)


# ---------------------------------------------------------------------------
# Aggregation / accuracy / drift
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_data_returns_zeros(service: AdminTelemetryService) -> None:
    """NO_DATA: zero decision rows → zeros, accuracy null, no alert."""
    service.session.execute = AsyncMock(side_effect=_results())
    result = await service.get_decision_telemetry(24)

    assert result["window_hours"] == 24
    assert result["total_calls"] == 0
    assert result["total_cost_micros"] == 0
    assert result["median_latency_ms"] is None
    assert result["accuracy"] is None
    assert result["labeled"] == 0
    assert result["models"] == []
    assert result["daily"] == []
    assert result["by_task"] == []
    assert result["drift_detected"] is False
    assert result["cost_alert"]["exceeded"] is False
    service.session.add.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_aggregates(service: AdminTelemetryService) -> None:
    """HAPPY: daily buckets grouped by (period, task); totals/by_task consistent."""
    service.session.execute = AsyncMock(
        side_effect=_results(
            totals=_totals(
                calls=10, cost_micros=420, median_ms=133.5, labeled=4, correct=3
            ),
            daily=[
                _Row(
                    period="2026-09-22",
                    task="routing",
                    calls=7,
                    median_ms=120.0,
                    cost_micros=300,
                ),
                _Row(
                    period="2026-09-22",
                    task="intent",
                    calls=3,
                    median_ms=180.0,
                    cost_micros=120,
                ),
            ],
            by_task=[
                _Row(
                    task="routing",
                    calls=7,
                    median_ms=120.0,
                    cost_micros=300,
                    input_tokens=7000,
                    output_tokens=70,
                ),
                _Row(
                    task="intent",
                    calls=3,
                    median_ms=180.0,
                    cost_micros=120,
                    input_tokens=3000,
                    output_tokens=30,
                ),
            ],
            models=[
                _Row(
                    model="jev-1.13.0",
                    backend="jev",
                    calls=10,
                    first_seen=None,
                    last_seen=None,
                )
            ],
        )
    )
    result = await service.get_decision_telemetry(24, workspace_id=7)

    assert result["workspace_id"] == 7
    assert result["total_calls"] == 10
    assert result["total_cost_micros"] == 420
    assert result["median_latency_ms"] == 133.5
    assert result["accuracy"] == 0.75
    assert result["labeled"] == 4
    assert result["correct"] == 3
    assert [d["task"] for d in result["daily"]] == ["routing", "intent"]
    assert result["daily"][0]["calls"] == 7
    assert result["daily"][0]["median_latency_ms"] == 120.0
    assert {t["task"]: t["calls"] for t in result["by_task"]} == {
        "routing": 7,
        "intent": 3,
    }
    assert result["by_task"][0]["input_tokens"] == 7000
    assert result["models"][0]["model"] == "jev-1.13.0"
    assert result["drift_detected"] is False


@pytest.mark.asyncio
async def test_accuracy_is_correct_over_labeled(
    service: AdminTelemetryService,
) -> None:
    """ACC_LABELED: 4 labeled rows, 3 correct → accuracy 0.75."""
    service.session.execute = AsyncMock(
        side_effect=_results(totals=_totals(calls=9, labeled=4, correct=3))
    )
    result = await service.get_decision_telemetry(24)
    assert result["accuracy"] == 0.75
    assert result["labeled"] == 4


@pytest.mark.asyncio
async def test_accuracy_null_when_nothing_labeled(
    service: AdminTelemetryService,
) -> None:
    """ACC_NONE: rows exist but none labeled → accuracy null, never 0.0."""
    service.session.execute = AsyncMock(
        side_effect=_results(totals=_totals(calls=9, labeled=0, correct=0))
    )
    result = await service.get_decision_telemetry(24)
    assert result["accuracy"] is None
    assert result["labeled"] == 0


@pytest.mark.asyncio
async def test_drift_detected_with_multiple_jev_models(
    service: AdminTelemetryService,
) -> None:
    """DRIFT: two distinct jev models in window → drift_detected."""
    service.session.execute = AsyncMock(
        side_effect=_results(
            models=[
                _Row(
                    model="jev-1.13.0",
                    backend="jev",
                    calls=5,
                    first_seen=None,
                    last_seen=None,
                ),
                _Row(
                    model="jev-1.14.0",
                    backend="jev",
                    calls=3,
                    first_seen=None,
                    last_seen=None,
                ),
            ]
        )
    )
    result = await service.get_decision_telemetry(24)
    assert result["drift_detected"] is True
    assert {m["model"] for m in result["models"]} == {
        "jev-1.13.0",
        "jev-1.14.0",
    }


@pytest.mark.asyncio
async def test_drift_detected_when_jev_model_differs_from_pin(
    service: AdminTelemetryService,
) -> None:
    """A single jev model that isn't the pin still counts as drift."""
    service.session.execute = AsyncMock(
        side_effect=_results(
            models=[
                _Row(
                    model="jev-1.14.0",
                    backend="jev",
                    calls=5,
                    first_seen=None,
                    last_seen=None,
                )
            ]
        )
    )
    result = await service.get_decision_telemetry(24)
    assert result["pinned_model"] == decision_config.DECISION_JEV_MODEL
    assert result["drift_detected"] is True


@pytest.mark.asyncio
async def test_no_drift_when_only_pinned_model(
    service: AdminTelemetryService,
) -> None:
    service.session.execute = AsyncMock(
        side_effect=_results(
            models=[
                _Row(
                    model=decision_config.DECISION_JEV_MODEL,
                    backend="jev",
                    calls=5,
                    first_seen=None,
                    last_seen=None,
                ),
                # non-jev backends never participate in the drift check
                _Row(
                    model="claude-haiku-4-5-20251001",
                    backend="llm_json",
                    calls=2,
                    first_seen=None,
                    last_seen=None,
                ),
            ]
        )
    )
    result = await service.get_decision_telemetry(24)
    assert result["drift_detected"] is False


# ---------------------------------------------------------------------------
# Daily cost alert (on-read, deduped)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cost_alert_fires_and_inserts_once(
    service: AdminTelemetryService, monkeypatch
) -> None:
    """ALERT_FIRE: exceeded + no open alert → exceeded=true + one insert."""
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=_results(today_cost_micros=11_000_000, exceeded=True)
    )
    result = await service.get_decision_telemetry(24)

    assert result["cost_alert"]["exceeded"] is True
    assert result["cost_alert"]["today_cost_micros"] == 11_000_000
    assert result["cost_alert"]["threshold_usd"] == 10.0
    service.session.add.assert_called_once()
    alert = service.session.add.call_args.args[0]
    assert isinstance(alert, AdminHealthAlert)
    assert alert.service_id == "decision.jev_daily_cost"
    assert alert.severity == "high"
    assert alert.status == "open"
    assert "$11.0000" in alert.message  # today's spend
    assert "$10.00" in alert.message  # the breached threshold
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cost_alert_dedupes_existing_open(
    service: AdminTelemetryService, monkeypatch
) -> None:
    """ALERT_DEDUP: exceeded + open alert exists → no new row."""
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=_results(
            today_cost_micros=11_000_000,
            exceeded=True,
            dedupe=[_Row(id=42)],
        )
    )
    result = await service.get_decision_telemetry(24)
    assert result["cost_alert"]["exceeded"] is True
    service.session.add.assert_not_called()
    service.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cost_alert_dedupes_acknowledged(
    service: AdminTelemetryService, monkeypatch
) -> None:
    """ALERT_ACKED: an acknowledged alert still suppresses a new insert —
    the admin already saw it. Asserts the compiled dedupe statement
    really filters on BOTH 'open' and 'acknowledged' statuses."""
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=_results(
            today_cost_micros=11_000_000,
            exceeded=True,
            dedupe=[_Row(id=42)],
        )
    )
    result = await service.get_decision_telemetry(24)
    assert result["cost_alert"]["exceeded"] is True
    service.session.add.assert_not_called()

    dedupe_stmt = service.session.execute.call_args_list[-1].args[0]
    sql = str(dedupe_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "admin_health_alerts.status" in sql
    assert "open" in sql
    assert "acknowledged" in sql


@pytest.mark.asyncio
async def test_cost_alert_not_exceeded_skips_dedupe_query(
    service: AdminTelemetryService, monkeypatch
) -> None:
    """Below threshold → no lock/dedupe SELECT at all (6 executes total)."""
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=_results(today_cost_micros=1_000)
    )
    result = await service.get_decision_telemetry(24)
    assert result["cost_alert"]["exceeded"] is False
    assert service.session.execute.await_count == 6
    service.session.add.assert_not_called()


@pytest.mark.asyncio
async def test_cost_alert_insert_failure_still_returns(
    service: AdminTelemetryService, monkeypatch
) -> None:
    """A lock/dedupe/insert failure logs a warning; response still returns."""
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=[
            *_results(today_cost_micros=11_000_000),
            RuntimeError("db down"),
        ]
    )
    result = await service.get_decision_telemetry(24)
    assert result["cost_alert"]["exceeded"] is True
    service.session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Compiled-SQL honesty — the mocks can't verify WHERE clauses, so compile
# the statements and check them directly.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compiled_sql_carries_decision_filter_and_dedupe_statuses(
    service: AdminTelemetryService, monkeypatch
) -> None:
    """The usage_type='decision' filter is on every aggregate statement and
    the dedupe SELECT filters admin_health_alerts.status IN (open, acknowledged)."""
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=_results(today_cost_micros=11_000_000, exceeded=True)
    )
    await service.get_decision_telemetry(24)

    compiled: list[str] = []
    for call in service.session.execute.call_args_list:
        stmt = call.args[0]
        try:
            compiled.append(
                str(stmt.compile(compile_kwargs={"literal_binds": True}))
            )
        except Exception:
            compiled.append(str(stmt.compile()))

    assert any("token_usage.usage_type" in sql for sql in compiled)
    dedupe_sql = compiled[-1]
    assert "admin_health_alerts.status IN" in dedupe_sql
    assert "open" in dedupe_sql
    assert "acknowledged" in dedupe_sql


# ---------------------------------------------------------------------------
# Periodic cost-alert entry point (Celery beat) — fires without a dashboard
# read. Same deduped insert path as the read-time check.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_daily_cost_alert_inserts_on_breach(
    service: AdminTelemetryService, monkeypatch
) -> None:
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult([_Row(cost_micros=12_000_000)]),  # today cost
            _MockResult(),  # pg_advisory_xact_lock
            _MockResult([]),  # dedupe: no existing alert
        ]
    )
    result = await service.check_daily_cost_alert()
    assert result["exceeded"] is True
    assert result["alert_inserted"] is True
    service.session.add.assert_called_once()
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_daily_cost_alert_dedupes_existing(
    service: AdminTelemetryService, monkeypatch
) -> None:
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=[
            _MockResult([_Row(cost_micros=12_000_000)]),
            _MockResult(),  # lock
            _MockResult([_Row(id=9)]),  # existing open alert
        ]
    )
    result = await service.check_daily_cost_alert()
    assert result["exceeded"] is True
    assert result["alert_inserted"] is False
    service.session.add.assert_not_called()


@pytest.mark.asyncio
async def test_check_daily_cost_alert_below_threshold(
    service: AdminTelemetryService, monkeypatch
) -> None:
    monkeypatch.setattr(
        decision_config, "DECISION_DAILY_COST_ALERT_USD", 10.0
    )
    service.session.execute = AsyncMock(
        side_effect=[_MockResult([_Row(cost_micros=5_000_000)])]
    )
    result = await service.check_daily_cost_alert()
    assert result["exceeded"] is False
    assert result["alert_inserted"] is False
    assert service.session.execute.await_count == 1  # no lock/dedupe


def test_decision_cost_alert_task_registered() -> None:
    """Beat schedule + task registration — the check must run without a
    dashboard read."""
    import app.tasks.celery_tasks.decision_telemetry_task  # noqa: F401
    from app.celery_app import celery_app

    assert "evaluate_decision_daily_cost_alert" in celery_app.tasks
    entry = celery_app.conf.beat_schedule["evaluate-decision-daily-cost-alert"]
    assert entry["task"] == "evaluate_decision_daily_cost_alert"


# ---------------------------------------------------------------------------
# Window clamp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_window_hours_clamped_low(service: AdminTelemetryService) -> None:
    """WINDOW: window_hours=0 clamps to 1."""
    service.session.execute = AsyncMock(side_effect=_results())
    result = await service.get_decision_telemetry(0)
    assert result["window_hours"] == 1


@pytest.mark.asyncio
async def test_window_hours_clamped_high(service: AdminTelemetryService) -> None:
    """WINDOW: window_hours > 720 clamps to 720."""
    service.session.execute = AsyncMock(side_effect=_results())
    result = await service.get_decision_telemetry(9999)
    assert result["window_hours"] == 720


# ---------------------------------------------------------------------------
# label_decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_label_decision_merges_correct(
    service: AdminTelemetryService,
) -> None:
    """LABEL: ``correct`` is merged into call_details and committed."""
    old_details = {"task": "routing", "model": "jev-1.13.0"}
    record = MagicMock()
    record.call_details = old_details
    service.session.execute = AsyncMock(
        side_effect=[_MockResult([record])]
    )

    result = await service.label_decision(usage_id=5, correct=False)

    assert result == {"usage_id": 5, "correct": False}
    # the dict is REASSIGNED, not mutated in place (JSONB tracking off)
    assert record.call_details is not old_details
    assert record.call_details == {
        "task": "routing",
        "model": "jev-1.13.0",
        "correct": False,
    }
    assert "correct" not in old_details
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_label_decision_overwrites_existing_label(
    service: AdminTelemetryService,
) -> None:
    record = MagicMock()
    record.call_details = {"task": "routing", "correct": True}
    service.session.execute = AsyncMock(
        side_effect=[_MockResult([record])]
    )

    result = await service.label_decision(usage_id=5, correct=False)

    assert result["correct"] is False
    assert record.call_details["correct"] is False


@pytest.mark.asyncio
async def test_label_decision_missing_row_returns_none(
    service: AdminTelemetryService,
) -> None:
    """LABEL_404: nonexistent or non-decision id → None (route maps 404)."""
    service.session.execute = AsyncMock(side_effect=[_MockResult([])])
    result = await service.label_decision(usage_id=999, correct=True)
    assert result is None
    service.session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Route-level checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_label_route_returns_404_on_missing_row(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.rate_limiter import limiter
    from app.routes import admin_telemetry_routes as routes
    from app.schemas.admin_telemetry import DecisionLabelRequest

    service = MagicMock()
    service.label_decision = AsyncMock(return_value=None)
    monkeypatch.setattr(routes, "AdminTelemetryService", lambda _s: service)
    # The endpoint is rate-limited; the slowapi wrapper would reject a
    # non-Request `request` arg — disable it for this direct call.
    monkeypatch.setattr(limiter, "enabled", False)

    with pytest.raises(HTTPException) as exc_info:
        await routes.label_decision(
            request=None,
            usage_id=999,
            payload=DecisionLabelRequest(correct=True),
            session=AsyncMock(),
            _auth=None,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_label_route_returns_result(monkeypatch) -> None:
    from app.rate_limiter import limiter
    from app.routes import admin_telemetry_routes as routes
    from app.schemas.admin_telemetry import DecisionLabelRequest

    service = MagicMock()
    service.label_decision = AsyncMock(
        return_value={"usage_id": 5, "correct": True}
    )
    monkeypatch.setattr(routes, "AdminTelemetryService", lambda _s: service)
    monkeypatch.setattr(limiter, "enabled", False)

    result = await routes.label_decision(
        request=None,
        usage_id=5,
        payload=DecisionLabelRequest(correct=True),
        session=AsyncMock(),
        _auth=None,
    )
    assert result == {"usage_id": 5, "correct": True}
