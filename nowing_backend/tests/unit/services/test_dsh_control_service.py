"""Red-phase ATDD unit tests for DSH MissionControlService (Story 26.5).

Covers token-velocity aggregation, PII-safe redaction, and fallback sources.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

pytestmark = [
    pytest.mark.unit,
]


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        if self._value is None:
            raise ValueError("No row found")
        return self._value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """AsyncSession stand-in with per-query result mapping."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self.query_map: dict[str, Any] = {}
        self.get_map: dict[tuple[type, Any], Any] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        text = str(stmt).lower()
        for key, value in self.query_map.items():
            if key.lower() in text:
                if isinstance(value, list):
                    return _FakeResult(rows=value)
                return _FakeResult(value=value)
        return _FakeResult()

    async def get(self, model: type, ident: Any) -> Any | None:
        return self.get_map.get((model, ident))

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, _obj: Any) -> None:
        pass


def _make_subtask(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults = {
        "id": f"subtask-{uuid4().hex[:6]}",
        "title": "Crawl",
        "status": "success",
        "phase": "crawl",
        "reasoning_content": "Crawl reasoning",
        "tokens_used": 1000,
        "tokens_per_second": 50.0,
        "run_id": str(uuid4()),
        "cost_micros": 5000,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    if overrides:
        defaults.update(overrides)
    return defaults


def _make_mission(overrides: dict[str, Any] | None = None) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "workspace_id": 1,
        "mission_type": "deep_lead_research",
        "status": "running",
        "phase": "reasoning",
        "progress_percent": 45,
        "current_subtask_id": "subtask-2",
        "payload": {"query": "secret query", "workspace_id": 1},
        "checkpoint": {
            "version": 3,
            "phase": "reasoning",
            "payload": {"query": "secret query"},
            "sources": [{"url": "https://example.com"}],
            "leads": [{"id": str(uuid4()), "phone": "0908***456"}],
            "subtasks": [
                _make_subtask(
                    {
                        "id": "subtask-1",
                        "title": "Crawl",
                        "phase": "crawl",
                        "tokens_used": 1200,
                        "tokens_per_second": 60.0,
                        "cost_micros": 5000,
                    }
                ),
                _make_subtask(
                    {
                        "id": "subtask-2",
                        "title": "Reasoning",
                        "phase": "reasoning",
                        "status": "running",
                        "tokens_used": 3000,
                        "tokens_per_second": 120.0,
                        "cost_micros": 10000,
                        "completed_at": None,
                    }
                ),
            ],
        },
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_list_missions_for_workspace_filters_status_and_hours() -> None:
    """P0: DshMissionService.list_missions_for_workspace filters by status/hours."""
    from app.services.dsh_mission_service import DshMissionService

    session = _FakeSession()
    session.query_map["dsh_missions"] = [
        SimpleNamespace(
            id=uuid4(),
            workspace_id=1,
            status="running",
            created_at=datetime.now(UTC),
        )
    ]

    result = await DshMissionService().list_missions_for_workspace(
        session,
        workspace_id=1,
        status_filter="running,pending",
        hours=24,
    )

    assert len(result) == 1
    assert result[0].workspace_id == 1


@pytest.mark.asyncio
async def test_build_control_data_redacts_payload_sources_and_leads() -> None:
    """P0: MissionControlService strips payload, sources, and leads."""
    import app.services.dsh_control_service as dsh_control

    session = _FakeSession()
    mission = _make_mission()

    result = await dsh_control.MissionControlService().build_control_data(
        session, mission
    )

    assert "payload" not in result.model_dump()
    assert "sources" not in result.model_dump()
    assert "leads" not in result.model_dump()
    assert "query" not in result.model_dump()


@pytest.mark.asyncio
async def test_build_control_data_computes_token_velocity_from_subtasks() -> None:
    """P0: token_velocity aggregates subtask tokens and cost."""
    import app.services.dsh_control_service as dsh_control

    session = _FakeSession()
    mission = _make_mission()

    result = await dsh_control.MissionControlService().build_control_data(
        session, mission
    )

    tv = result.token_velocity
    assert tv.tokens_total == 4200
    assert tv.tokens_per_second > 0
    assert tv.cost_micros == 15000
    assert tv.cost_credits == 0.015


@pytest.mark.asyncio
async def test_build_control_data_falls_back_to_token_usage() -> None:
    """P1: MissionControlService reconciles with TokenUsage rows by run_id."""
    import app.services.dsh_control_service as dsh_control
    from app.db import TokenUsage

    run_id = uuid4()
    mission = _make_mission(
        {
            "checkpoint": {
                "version": 1,
                "subtasks": [
                    _make_subtask(
                        {
                            "run_id": str(run_id),
                            "tokens_used": 0,
                            "tokens_per_second": 0.0,
                            "cost_micros": 0,
                        }
                    )
                ],
            }
        }
    )

    token_usage = SimpleNamespace(
        total_tokens=5000,
        cost_micros=8000,
    )
    session = _FakeSession()
    session.query_map["token_usage"] = [token_usage]
    session.get_map[(TokenUsage, run_id)] = token_usage

    result = await dsh_control.MissionControlService().build_control_data(
        session, mission
    )

    assert result.token_velocity.tokens_total == 5000
    assert result.token_velocity.cost_micros == 8000


@pytest.mark.asyncio
async def test_build_control_data_falls_back_to_run_cost_when_tokens_missing() -> None:
    """P1: If token counts are missing, fallback to Run.cost_micros."""
    import app.services.dsh_control_service as dsh_control
    from app.db import Run

    run_id = uuid4()
    mission = _make_mission(
        {
            "checkpoint": {
                "version": 1,
                "subtasks": [
                    {
                        "id": "subtask-1",
                        "title": "Crawl",
                        "status": "success",
                        "phase": "crawl",
                        "reasoning_content": "",
                        "run_id": str(run_id),
                        "started_at": datetime.now(UTC).isoformat(),
                        "completed_at": datetime.now(UTC).isoformat(),
                    }
                ],
            }
        }
    )

    session = _FakeSession()
    session.get_map[(Run, run_id)] = SimpleNamespace(cost_micros=12000)

    result = await dsh_control.MissionControlService().build_control_data(
        session, mission
    )

    assert result.token_velocity.tokens_per_second == 0
    assert result.token_velocity.cost_micros == 12000
    assert result.token_velocity.cost_credits == 0.012


@pytest.mark.asyncio
async def test_build_control_data_returns_zero_tokens_per_second_gracefully() -> None:
    """P1: Missing token counts display 0 tokens/sec without crashing."""
    import app.services.dsh_control_service as dsh_control

    mission = _make_mission(
        {
            "checkpoint": {
                "version": 1,
                "subtasks": [
                    _make_subtask(
                        {
                            "tokens_used": 0,
                            "tokens_per_second": 0.0,
                            "cost_micros": 0,
                        }
                    )
                ],
            }
        }
    )

    session = _FakeSession()

    result = await dsh_control.MissionControlService().build_control_data(
        session, mission
    )

    assert result.token_velocity.tokens_per_second == 0
    assert result.token_velocity.tokens_total == 0


@pytest.mark.asyncio
async def test_build_control_data_includes_redacted_subtasks() -> None:
    """P0: control response exposes allowed subtask fields only."""
    import app.services.dsh_control_service as dsh_control

    mission = _make_mission()
    session = _FakeSession()

    result = await dsh_control.MissionControlService().build_control_data(
        session, mission
    )

    assert len(result.subtasks) == 2
    first = result.subtasks[0]
    assert first.id == "subtask-1"
    assert first.title == "Crawl"
    assert first.status == "success"
    assert first.phase == "crawl"
    assert "reasoning_content" in first.model_dump()
    assert "tokens_used" in first.model_dump()


@pytest.mark.asyncio
async def test_build_control_data_rejects_cross_workspace_mission() -> None:
    """P2: requesting control for a mission in another workspace raises."""
    import app.services.dsh_control_service as dsh_control

    mission = _make_mission({"workspace_id": 2})
    session = _FakeSession()

    with pytest.raises((ValueError, RuntimeError)):
        await dsh_control.MissionControlService().build_control_data(
            session, mission, requested_workspace_id=1
        )
