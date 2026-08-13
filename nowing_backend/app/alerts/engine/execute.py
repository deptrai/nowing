"""Alert rule execution: capability call, diff, snapshot, and notification."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.core import execute_with_context
from app.capabilities.core.store import CapabilityRegistry
from app.capabilities.core.types import CapabilityContext
from app.db import AlertRule, AlertSnapshot

from .diff import diff_snapshots
from .notify import notify_alert_run

logger = logging.getLogger(__name__)


def _normalize_items(raw: Any) -> list[dict[str, Any]]:
    """Extract a JSON-safe item list from a capability output object."""
    if isinstance(raw, dict):
        return raw.get("items", []) if isinstance(raw.get("items"), list) else []
    if hasattr(raw, "items") and isinstance(raw.items, list):
        return [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in raw.items
        ]
    return []


def _degradation_reasons(raw: Any) -> list[str] | None:
    """Pull degradation reasons from capability output, if present."""
    if isinstance(raw, dict):
        reasons = raw.get("degradation_reasons") or raw.get("degradation_reason")
        if isinstance(reasons, list):
            return reasons
        if isinstance(reasons, str):
            return [reasons]
    if hasattr(raw, "degradation_reasons"):
        return raw.degradation_reasons
    if hasattr(raw, "degradation_reason") and raw.degradation_reason:
        return [raw.degradation_reason]
    return None


def _snapshot_from_output(raw: Any) -> dict[str, Any]:
    """Build a JSONB snapshot from capability output for diffing."""
    items = _validate_items(_normalize_items(raw))
    return {
        "source_ids": sorted({sid for sid in _source_ids(items) if sid}),
        "items": items,
    }


def _source_id(item: Any) -> str | None:
    if isinstance(item, dict):
        return item.get("id") or item.get("source_id") or item.get("canonical_id")
    return None


def _validate_items(items: list[Any]) -> list[dict[str, Any]]:
    """Ensure every item is a dict with a usable source id.

    ponytail: naive O(n) scan; if items lack an id we fail fast so diff/notify
    never operates on unidentifiable data.
    """
    validated: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"snapshot item at index {idx} is not a dict")
        sid = _source_id(item)
        if not sid:
            raise ValueError(
                f"snapshot item at index {idx} has no id/source_id/canonical_id"
            )
        validated.append(item)
    return validated


def _source_ids(items: list[dict[str, Any]]) -> list[str]:
    return [sid for sid in (_source_id(item) for item in items) if sid]


async def execute_alert_rule(
    *,
    session: AsyncSession,
    alert_rule: AlertRule,
    fired_at: datetime,
) -> AlertSnapshot:
    """Run one alert rule, diff against last snapshot, write new snapshot, notify.

    This is a synchronous-looking run; it is called from the Celery tick task.
    Capability execution, diff, and notification are all performed in the same
    async context.
    """
    try:
        capability = CapabilityRegistry.get(alert_rule.capability_id)
    except KeyError as exc:
        raise ValueError(
            f"capability {alert_rule.capability_id!r} is not registered"
        ) from exc
    payload = capability.input_schema.model_validate(alert_rule.query)
    ctx = CapabilityContext(session=session, workspace_id=alert_rule.workspace_id)

    snapshot = AlertSnapshot(
        alert_rule_id=alert_rule.id,
        run_status="succeeded",
        snapshot_json={"source_ids": [], "items": []},
        new_items_count=0,
        changed_items_count=0,
        removed_items_count=0,
    )

    try:
        output = await execute_with_context(
            capability.executor, payload=payload, ctx=ctx
        )
    except Exception as exc:
        logger.exception(
            "alert rule %s capability %s failed",
            alert_rule.id,
            alert_rule.capability_id,
        )
        snapshot.run_status = "failed"
        snapshot.snapshot_json = {"error": str(exc), "error_type": type(exc).__name__}
        session.add(snapshot)
        await session.commit()
        await notify_alert_run(
            session=session, alert_rule=alert_rule, snapshot=snapshot
        )
        return snapshot

    snapshot.snapshot_json = _snapshot_from_output(output)
    snapshot.degradation_reasons = _degradation_reasons(output)
    if snapshot.degradation_reasons or (
        isinstance(output, dict) and output.get("degraded")
    ):
        snapshot.run_status = "degraded"

    # Load the most recent previous snapshot.
    prev = (
        (
            await session.execute(
                select(AlertSnapshot)
                .where(AlertSnapshot.alert_rule_id == alert_rule.id)
                .order_by(AlertSnapshot.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )

    if prev is not None:
        try:
            delta = diff_snapshots(
                alert_rule.diff_strategy,
                prev.snapshot_json,
                snapshot.snapshot_json,
                alert_rule.threshold or {},
            )
        except ValueError as exc:
            logger.warning(
                "alert rule %s diff strategy %s failed: %s",
                alert_rule.id,
                alert_rule.diff_strategy,
                exc,
            )
            snapshot.run_status = "failed"
            snapshot.snapshot_json["_delta_error"] = str(exc)
        else:
            snapshot.new_items_count = delta["new_items_count"]
            snapshot.changed_items_count = delta["changed_items_count"]
            snapshot.removed_items_count = delta["removed_items_count"]
            # Store delta summary so notifications can reference it without re-diffing.
            snapshot.snapshot_json["_delta"] = {
                "new_item_ids": delta.get("new_item_ids", []),
                "removed_item_ids": delta.get("removed_item_ids", []),
                "changed_item_ids": delta.get("changed_item_ids", []),
                "matched_item_ids": [
                    i.get("id") or i.get("source_id") or i.get("canonical_id")
                    for i in delta.get("matched_items", [])
                ],
                "triggered_count": delta.get("triggered_count", 0),
            }

    session.add(snapshot)
    await session.commit()

    # ponytail: next_fire_at is advanced inside _claim_due_rules so the scheduler
    # does not lose a rule if the worker crashes between claim and execute.
    if _should_skip_notification(snapshot):
        if snapshot.run_status == "degraded":
            logger.info(
                "degraded_source alert_rule_id=%s workspace_id=%s degradation_reasons=%s",
                alert_rule.id,
                alert_rule.workspace_id,
                snapshot.degradation_reasons or [],
            )
        return snapshot

    await notify_alert_run(session=session, alert_rule=alert_rule, snapshot=snapshot)
    return snapshot


def _should_skip_notification(snapshot: AlertSnapshot) -> bool:
    """Return True when the alert must not notify.

    AC-2: no notification when the run surfaced nothing new or changed.
    AC-5: a degraded source with zero new items is skipped (and logged as
    ``degraded_source``); degraded runs that DO surface new postings still
    notify so nothing real is missed. Failed runs always notify so the user
    knows their saved search broke.
    """
    if snapshot.run_status == "failed":
        return False
    return snapshot.new_items_count == 0 and snapshot.changed_items_count == 0
