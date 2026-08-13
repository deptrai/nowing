"""Grouping helper for alert notifications (AC-4).

Pure functions: no DB or framework objects, so they are unit-testable in
isolation. Input notifications follow the API response shape (``metadata``
dict with ``alert_rule_id``, ``rule_name``, ``new_items_count``).
"""

from __future__ import annotations

from typing import Any, TypedDict


class AlertNotificationGroup(TypedDict):
    """A group of alert notifications for one saved search."""

    alert_rule_id: str
    rule_name: str
    match_count: int
    notifications: list[dict[str, Any]]


def _metadata(notification: dict[str, Any]) -> dict[str, Any]:
    meta = notification.get("metadata")
    return meta if isinstance(meta, dict) else {}


def _rule_id(notification: dict[str, Any]) -> str | None:
    rule_id = _metadata(notification).get("alert_rule_id")
    return rule_id if isinstance(rule_id, str) and rule_id else None


def group_alert_notifications(
    notifications: list[dict[str, Any]],
) -> list[AlertNotificationGroup]:
    """Group ``alert_run_complete`` notifications by ``alert_rule_id``.

    Returns groups ordered by the first notification of each rule, newest
    notification first. Notifications without an ``alert_rule_id`` are skipped.
    """
    groups: dict[str, AlertNotificationGroup] = {}
    order: list[str] = []

    for notification in notifications:
        rule_id = _rule_id(notification)
        if rule_id is None:
            continue

        if rule_id not in groups:
            meta = _metadata(notification)
            groups[rule_id] = {
                "alert_rule_id": rule_id,
                "rule_name": meta.get("rule_name") or "Saved search",
                "match_count": 0,
                "notifications": [],
            }
            order.append(rule_id)

        group = groups[rule_id]
        if not group["notifications"]:
            group["rule_name"] = _metadata(notification).get("rule_name") or group[
                "rule_name"
            ]
        group["match_count"] += int(
            _metadata(notification).get("new_items_count") or 0
        )
        group["notifications"].append(notification)

    return [groups[rule_id] for rule_id in order]
