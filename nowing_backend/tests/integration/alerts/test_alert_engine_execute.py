"""Integration tests for alert rule execute -> diff -> snapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.engine.execute import execute_alert_rule
from app.alerts.schemas import AlertRuleCreate
from app.alerts.services import create_alert_rule
from app.db import User, Workspace

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _FakeInput(BaseModel):
    keyword: str


class _FakeOutput(BaseModel):
    items: list[dict[str, Any]]
    degraded: bool = False
    degradation_reasons: list[str] | None = None


async def test_alert_rule_execute_and_diff(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    rule = await create_alert_rule(
        session=db_session,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        data=AlertRuleCreate(
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            schedule="none",
            timezone="UTC",
        ),
    )

    fake_cap = SimpleNamespace(
        name="vn_jobs.aggregate",
        input_schema=_FakeInput,
        executor=mock.AsyncMock(
            side_effect=[
                _FakeOutput(
                    items=[
                        {"id": "job-1", "title": "Senior Python"},
                        {"id": "job-2", "title": "Data Engineer"},
                    ]
                ),
                _FakeOutput(
                    items=[
                        {"id": "job-2", "title": "Data Engineer"},
                        {"id": "job-3", "title": "ML Engineer"},
                    ]
                ),
            ]
        ),
    )

    with (
        mock.patch(
            "app.alerts.engine.execute.CapabilityRegistry.get",
            return_value=fake_cap,
        ),
        mock.patch(
            "app.alerts.engine.notify.notify_alert_run", new=mock.AsyncMock()
        ),
    ):
        first = await execute_alert_rule(
            session=db_session,
            alert_rule=rule,
            fired_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )
        second = await execute_alert_rule(
            session=db_session,
            alert_rule=rule,
            fired_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
        )

    # First run has no previous snapshot, so everything is "new" by count but the
    # diff strategy labels the first run as baseline (new_items_count = 0).
    assert first.new_items_count == 0
    assert first.snapshot_json["source_ids"] == ["job-1", "job-2"]

    # Second run diffs against the first snapshot.
    assert second.new_items_count == 1
    assert second.removed_items_count == 1
    assert second.changed_items_count == 0
    assert second.snapshot_json["source_ids"] == ["job-2", "job-3"]
    assert second.snapshot_json.get("_delta", {}).get("new_item_ids") == ["job-3"]
    assert second.snapshot_json.get("_delta", {}).get("removed_item_ids") == ["job-1"]
