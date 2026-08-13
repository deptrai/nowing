"""Unit tests for alert diff strategies."""

from __future__ import annotations

import pytest

from app.alerts.engine.diff import (
    diff_new_items,
    diff_price_change,
    diff_snapshots,
    diff_threshold_cross,
)

pytestmark = pytest.mark.unit


def test_diff_new_items_detects_added_and_removed():
    previous = {
        "items": [
            {"id": "job-1", "title": "Senior Python"},
            {"id": "job-2", "title": "Data Engineer"},
        ],
    }
    current = {
        "items": [
            {"id": "job-2", "title": "Data Engineer"},
            {"id": "job-3", "title": "ML Engineer"},
        ],
    }

    delta = diff_new_items(previous, current)

    assert delta["new_items_count"] == 1
    assert delta["removed_items_count"] == 1
    assert delta["changed_items_count"] == 0
    assert delta["new_item_ids"] == ["job-3"]
    assert delta["removed_item_ids"] == ["job-1"]


def test_diff_detects_changed_items():
    previous = {
        "items": [{"id": "job-1", "title": "Senior Python", "salary": "1000"}],
    }
    current = {
        "items": [{"id": "job-1", "title": "Senior Python", "salary": "1200"}],
    }

    delta = diff_new_items(previous, current)

    assert delta["new_items_count"] == 0
    assert delta["removed_items_count"] == 0
    assert delta["changed_items_count"] == 1
    assert delta["changed_item_ids"] == ["job-1"]


def test_diff_first_run_empty_previous():
    current = {
        "items": [{"id": "job-1", "title": "Senior Python"}],
    }

    delta = diff_new_items({}, current)

    assert delta["new_items_count"] == 1
    assert delta["removed_items_count"] == 0
    assert delta["new_item_ids"] == ["job-1"]


def test_diff_uses_alternative_id_fields():
    previous = {
        "items": [{"source_id": "job-a", "title": "A"}],
    }
    current = {
        "items": [
            {"source_id": "job-a", "title": "A"},
            {"canonical_id": "job-b", "title": "B"},
        ],
    }

    delta = diff_new_items(previous, current)

    assert delta["new_items_count"] == 1
    assert delta["new_item_ids"] == ["job-b"]


def test_diff_price_change_triggers_on_absolute_delta():
    previous = {"items": [{"id": "stock-1", "price": 100}]}
    current = {"items": [{"id": "stock-1", "price": 1100}]}

    delta = diff_price_change(previous, current, threshold={"absolute_delta": 1000})

    assert delta["changed_items_count"] == 1
    assert delta["triggered_count"] == 1
    assert delta["changed_item_ids"] == ["stock-1"]


def test_diff_price_change_ignores_small_changes():
    previous = {"items": [{"id": "stock-1", "price": 100}]}
    current = {"items": [{"id": "stock-1", "price": 105}]}

    delta = diff_price_change(previous, current, threshold={"absolute_delta": 10})

    assert delta["changed_items_count"] == 0
    assert delta["triggered_count"] == 0


def test_diff_price_change_triggers_on_percent_delta():
    previous = {"items": [{"id": "stock-1", "price": 100}]}
    current = {"items": [{"id": "stock-1", "price": 106}]}

    delta = diff_price_change(previous, current, threshold={"percent_delta": 0.05})

    assert delta["changed_items_count"] == 1
    assert delta["triggered_count"] == 1


def test_diff_price_change_parses_vietnamese_formatted_price():
    previous = {"items": [{"id": "bds-1", "price": "3.500.000"}]}
    current = {"items": [{"id": "bds-1", "price": "3.600.000"}]}

    delta = diff_price_change(previous, current, threshold={"absolute_delta": 50000})

    assert delta["changed_items_count"] == 1
    assert delta["triggered_count"] == 1


def test_diff_price_change_custom_field():
    previous = {"items": [{"id": "stock-1", "metrics": {"close": 100}}]}
    current = {"items": [{"id": "stock-1", "metrics": {"close": 130}}]}

    delta = diff_price_change(
        previous,
        current,
        threshold={"field": "metrics.close", "absolute_delta": 20},
    )

    assert delta["changed_items_count"] == 1
    assert delta["changed_item_ids"] == ["stock-1"]


def test_diff_threshold_cross_above():
    current = {
        "items": [
            {"id": "stock-1", "price": 110},
            {"id": "stock-2", "price": 90},
        ],
    }

    delta = diff_threshold_cross(
        {}, current, threshold={"field": "price", "value": 100, "direction": "above"}
    )

    assert delta["new_items_count"] == 1
    assert delta["triggered_count"] == 1
    assert delta["matched_item_ids"] == ["stock-1"]


def test_diff_threshold_cross_below():
    current = {
        "items": [
            {"id": "stock-1", "price": 90},
            {"id": "stock-2", "price": 110},
        ],
    }

    delta = diff_threshold_cross(
        {}, current, threshold={"field": "price", "value": 100, "direction": "below"}
    )

    assert delta["new_items_count"] == 1
    assert delta["triggered_count"] == 1
    assert delta["matched_item_ids"] == ["stock-1"]


def test_diff_threshold_cross_custom_field():
    current = {
        "items": [
            {"id": "lead-1", "score": 85},
            {"id": "lead-2", "score": 70},
        ],
    }

    delta = diff_threshold_cross(
        {}, current, threshold={"field": "score", "value": 80, "direction": "above"}
    )

    assert delta["new_items_count"] == 1
    assert delta["matched_item_ids"] == ["lead-1"]


def test_diff_snapshots_dispatches_by_strategy():
    previous = {"items": [{"id": "stock-1", "price": 100}]}
    current = {"items": [{"id": "stock-1", "price": 1100}]}

    delta = diff_snapshots(
        "price_change", previous, current, threshold={"absolute_delta": 1000}
    )

    assert delta["changed_items_count"] == 1


def test_diff_snapshots_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="unknown diff strategy"):
        diff_snapshots("nope", {}, {}, None)
