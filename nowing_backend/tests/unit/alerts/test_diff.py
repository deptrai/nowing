"""Unit tests for alert diff strategies."""

from __future__ import annotations

import pytest

from app.alerts.engine.diff import diff_new_items

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
