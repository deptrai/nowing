"""Diff strategies for alert rule execution snapshots."""

from __future__ import annotations

from typing import Any


def _source_ids(items: list[dict[str, Any]]) -> set[str]:
    """Extract stable source ids from a capability output item list."""
    ids: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            source_id = (
                item.get("id") or item.get("source_id") or item.get("canonical_id")
            )
            if source_id:
                ids.add(str(source_id))
    return ids


def _item_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict):
            source_id = (
                item.get("id") or item.get("source_id") or item.get("canonical_id")
            )
            if source_id:
                result[str(source_id)] = item
    return result


def diff_new_items(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    """Return new, changed, and removed source ids between two snapshots.

    The comparison uses ``sourceId`` (``id`` > ``source_id`` > ``canonical_id``)
    as the stable identity key.
    """
    prev_items = _item_by_id(previous.get("items", []))
    curr_items = _item_by_id(current.get("items", []))

    new_ids = sorted(set(curr_items) - set(prev_items))
    removed_ids = sorted(set(prev_items) - set(curr_items))
    changed_ids = []
    for sid in set(curr_items) & set(prev_items):
        if curr_items[sid] != prev_items[sid]:
            changed_ids.append(sid)
    changed_ids.sort()

    return {
        "new_items": [curr_items[sid] for sid in new_ids],
        "removed_items": [prev_items[sid] for sid in removed_ids],
        "changed_items": [curr_items[sid] for sid in changed_ids],
        "new_item_ids": new_ids,
        "removed_item_ids": removed_ids,
        "changed_item_ids": changed_ids,
        "new_items_count": len(new_ids),
        "removed_items_count": len(removed_ids),
        "changed_items_count": len(changed_ids),
    }
