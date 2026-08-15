"""Pattern 6 (SQL) integration tests for signal AlertRule trigger/diff/snapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.engine.execute import execute_alert_rule
from app.alerts.schemas import AlertRuleCreate
from app.alerts.services import create_alert_rule
from app.capabilities.core.store import CapabilityRegistry
from app.capabilities.core.types import Capability
from app.db import AlertRule, AlertSnapshot, User, Workspace
from app.lead_intelligence.signals.schemas import (
    SignalEventRead,
    SignalInput,
    SignalOutput,
)
from app.lead_intelligence.signals.service import SignalDetectionService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _ensure_funding_signal_capability() -> Capability:
    """Return the funding.signal capability, registering a test double only if needed."""
    try:
        return CapabilityRegistry.get("funding.signal")
    except KeyError:
        cap = Capability(
            name="funding.signal",
            description="Funding signal capability",
            input_schema=SignalInput,
            output_schema=SignalOutput,
            executor=mock.AsyncMock(
                return_value=SignalOutput(
                    items=[],
                    cost_micros=0,
                    degraded=False,
                )
            ),
            billing_unit=None,
            metadata={"emits_signals": True, "signal_types": ["funding"]},
        )
        CapabilityRegistry.register(cap)
        return cap


async def test_funding_signal_alert_rule_triggers_and_creates_snapshot(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: funding.signal rule runs, diffs, and writes AlertSnapshot with new_items_count."""
    assert SignalDetectionService is not None
    await _ensure_funding_signal_capability()

    id1 = uuid4()
    id2 = uuid4()
    id3 = uuid4()
    now = datetime.now(UTC)

    outputs = [
        SignalOutput(
            items=[
                SignalEventRead(
                    id=id1,
                    workspace_id=db_workspace.id,
                    client_id=None,
                    company_name="FPT",
                    signal_type="funding",
                    source_url="https://example.com/funding-1",
                    chunk_id=None,
                    confidence=85.0,
                    detected_at=now,
                    processed=False,
                ),
                SignalEventRead(
                    id=id2,
                    workspace_id=db_workspace.id,
                    client_id=None,
                    company_name="FPT",
                    signal_type="funding",
                    source_url="https://example.com/funding-2",
                    chunk_id=None,
                    confidence=90.0,
                    detected_at=now,
                    processed=False,
                ),
            ],
            cost_micros=2000,
            degraded=False,
        ),
        SignalOutput(
            items=[
                SignalEventRead(
                    id=id2,
                    workspace_id=db_workspace.id,
                    client_id=None,
                    company_name="FPT",
                    signal_type="funding",
                    source_url="https://example.com/funding-2",
                    chunk_id=None,
                    confidence=90.0,
                    detected_at=now,
                    processed=False,
                ),
                SignalEventRead(
                    id=id3,
                    workspace_id=db_workspace.id,
                    client_id=None,
                    company_name="FPT",
                    signal_type="funding",
                    source_url="https://example.com/funding-3",
                    chunk_id=None,
                    confidence=70.0,
                    detected_at=now,
                    processed=False,
                ),
            ],
            cost_micros=2000,
            degraded=False,
        ),
    ]

    async def _fake_detect(*args: Any, **kwargs: Any) -> SignalOutput:
        return outputs.pop(0)

    monkeypatch.setattr(
        "app.lead_intelligence.signals.service.SignalDetectionService.detect",
        _fake_detect,
        raising=False,
    )

    with mock.patch(
        "app.alerts.engine.execute.notify_alert_run", new=mock.AsyncMock()
    ) as notify_mock:
        rule: AlertRule = await create_alert_rule(
            session=db_session,
            workspace_id=db_workspace.id,
            client_id=None,
            user_id=db_user.id,
            data=AlertRuleCreate(
                name="Funding signal alert",
                capability_id="funding.signal",
                query={"company_name": "FPT"},
                schedule="none",
                timezone="UTC",
                diff_strategy="new_items",
                notification_channels=["in_app"],
            ),
        )

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

    assert first.new_items_count == 0
    assert first.run_status == "succeeded"
    assert sorted(first.snapshot_json["source_ids"]) == sorted([str(id1), str(id2)])

    assert second.new_items_count == 1
    assert second.removed_items_count == 1
    assert second.changed_items_count == 0
    assert sorted(second.snapshot_json["source_ids"]) == sorted([str(id2), str(id3)])
    assert second.snapshot_json.get("_delta", {}).get("new_item_ids") == [str(id3)]
    assert second.snapshot_json.get("_delta", {}).get("removed_item_ids") == [str(id1)]

    assert notify_mock.call_count == 1


async def test_funding_signal_alert_rule_stores_snapshot_in_postgres(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The snapshot row is queryable from the alert_snapshots table."""
    assert SignalDetectionService is not None
    await _ensure_funding_signal_capability()

    async def _fake_detect(*args: Any, **kwargs: Any) -> SignalOutput:
        return SignalOutput(
            items=[
                SignalEventRead(
                    id=uuid4(),
                    workspace_id=db_workspace.id,
                    client_id=None,
                    company_name="FPT",
                    signal_type="funding",
                    source_url="https://example.com/funding",
                    chunk_id=None,
                    confidence=85.0,
                    detected_at=datetime.now(UTC),
                    processed=False,
                )
            ],
            cost_micros=1000,
            degraded=False,
        )

    monkeypatch.setattr(
        "app.lead_intelligence.signals.service.SignalDetectionService.detect",
        _fake_detect,
        raising=False,
    )

    with mock.patch("app.alerts.engine.execute.notify_alert_run", new=mock.AsyncMock()):
        rule: AlertRule = await create_alert_rule(
            session=db_session,
            workspace_id=db_workspace.id,
            client_id=None,
            user_id=db_user.id,
            data=AlertRuleCreate(
                name="Funding baseline",
                capability_id="funding.signal",
                query={"company_name": "FPT"},
                schedule="none",
                timezone="UTC",
                diff_strategy="new_items",
                notification_channels=["in_app"],
            ),
        )

        snapshot = await execute_alert_rule(
            session=db_session,
            alert_rule=rule,
            fired_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )

    result = await db_session.execute(
        select(AlertSnapshot).where(AlertSnapshot.alert_rule_id == rule.id)
    )
    row = result.scalar_one()
    assert row.id == snapshot.id
    assert row.new_items_count == 0
    assert row.run_status == "succeeded"
    assert row.snapshot_json["source_ids"]
