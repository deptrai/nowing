"""Diff strategies for alert rule execution snapshots.

Strategies are keyed by ``AlertRule.diff_strategy``. All strategies return a
normalized delta dict with ``*_count`` and ``*_items`` keys so ``execute.py``
can store a single, strategy-agnostic summary.
"""

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


def _numeric(value: Any) -> float | None:
    """Coerce a value to float for threshold/price math."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace(".", "").replace("₫", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _field_value(item: dict[str, Any], field: str) -> float | None:
    """Extract a numeric value from an item by dotted field path."""
    value = item
    for part in field.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return _numeric(value)


def diff_new_items(
    previous: dict[str, Any],
    current: dict[str, Any],
    threshold: dict[str, Any] | None = None,
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
        "matched_items_count": 0,
        "matched_items": [],
        "triggered_count": len(new_ids),
    }


def diff_price_change(
    previous: dict[str, Any],
    current: dict[str, Any],
    threshold: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return items whose numeric price field changed beyond a threshold.

    ``threshold`` may contain:
      - ``field``: dotted path to the price value (default: ``"price"``)
      - ``absolute_delta``: minimum absolute change to trigger
      - ``percent_delta``: minimum percent change (0.05 = 5%) to trigger

    ponytail: naive O(n) scan; if a price field is missing or non-numeric the
    item is ignored. The known ceiling is Vietnamese-formatted strings with
    mixed separators — ``_numeric`` strips common punctuation.
    """
    threshold = threshold or {}
    field = threshold.get("field", "price")
    absolute_delta = threshold.get("absolute_delta")
    percent_delta = threshold.get("percent_delta")

    prev_items = _item_by_id(previous.get("items", []))
    curr_items = _item_by_id(current.get("items", []))

    changed_items: list[dict[str, Any]] = []
    for sid, curr in curr_items.items():
        prev = prev_items.get(sid)
        if prev is None:
            continue
        prev_price = _field_value(prev, field)
        curr_price = _field_value(curr, field)
        if prev_price is None or curr_price is None:
            continue
        delta = curr_price - prev_price
        triggered = False
        if absolute_delta is not None and abs(delta) >= absolute_delta:
            triggered = True
        if percent_delta is not None and prev_price != 0 and abs(delta / prev_price) >= percent_delta:
            triggered = True
        if triggered:
            changed_items.append({**curr, "_delta_price": delta})

    return {
        "new_items": [],
        "removed_items": [],
        "changed_items": changed_items,
        "new_item_ids": [],
        "removed_item_ids": [],
        "changed_item_ids": [i.get("id") or i.get("source_id") or i.get("canonical_id") for i in changed_items],
        "new_items_count": 0,
        "removed_items_count": 0,
        "changed_items_count": len(changed_items),
        "matched_items_count": len(changed_items),
        "matched_items": changed_items,
        "triggered_count": len(changed_items),
    }


def diff_threshold_cross(
    previous: dict[str, Any],
    current: dict[str, Any],
    threshold: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return current items whose numeric field crosses a threshold value.

    ``threshold`` must contain:
      - ``field``: dotted path to the value to test
      - ``value``: the threshold value
      - ``direction``: ``"above"`` or ``"below"``

    ``previous`` is ignored for the cross itself, but the strategy still returns
    items from ``current`` so notifications can show what crossed.
    """
    threshold = threshold or {}
    field = threshold.get("field", "price")
    value = _numeric(threshold.get("value"))
    direction = threshold.get("direction", "above")

    matched_items: list[dict[str, Any]] = []
    if value is not None:
        for item in _item_by_id(current.get("items", [])).values():
            item_value = _field_value(item, field)
            if item_value is None:
                continue
            if (direction == "above" and item_value > value) or (
                direction == "below" and item_value < value
            ):
                matched_items.append(item)

    matched_item_ids = [
        i.get("id") or i.get("source_id") or i.get("canonical_id")
        for i in matched_items
    ]

    return {
        "new_items": [],
        "removed_items": [],
        "changed_items": [],
        "new_item_ids": [],
        "removed_item_ids": [],
        "changed_item_ids": [],
        "new_items_count": len(matched_items),
        "removed_items_count": 0,
        "changed_items_count": 0,
        "matched_items_count": len(matched_items),
        "matched_items": matched_items,
        "matched_item_ids": matched_item_ids,
        "triggered_count": len(matched_items),
    }


def diff_trend_detect(
    previous: dict[str, Any],
    current: dict[str, Any],
    threshold: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Placeholder for ``trend_detect``; currently treated as a no-op diff.

    Trend detection requires time-series snapshots and is deferred until a
    consumer story (e.g., 15-4 financial trend) needs it.
    """
    return {
        "new_items": [],
        "removed_items": [],
        "changed_items": [],
        "new_item_ids": [],
        "removed_item_ids": [],
        "changed_item_ids": [],
        "new_items_count": 0,
        "removed_items_count": 0,
        "changed_items_count": 0,
        "matched_items_count": 0,
        "matched_items": [],
        "triggered_count": 0,
    }


_DIFF_STRATEGIES: dict[
    str,
    Any,
] = {
    "new_items": diff_new_items,
    "price_change": diff_price_change,
    "threshold_cross": diff_threshold_cross,
    "trend_detect": diff_trend_detect,
}


def diff_snapshots(
    strategy: str,
    previous: dict[str, Any],
    current: dict[str, Any],
    threshold: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch to the registered diff strategy and return a normalized delta."""
    if strategy not in _DIFF_STRATEGIES:
        raise ValueError(f"unknown diff strategy: {strategy}")
    return _DIFF_STRATEGIES[strategy](previous, current, threshold)
