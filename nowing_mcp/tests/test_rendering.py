"""Output shaping: clipping oversized text and JSON serialization."""

from __future__ import annotations

from mcp_server.core.rendering import clip, compact_items, to_json


def test_clip_leaves_short_text_untouched():
    assert clip("short", limit=100) == "short"


def test_clip_truncates_and_marks_dropped_characters():
    clipped = clip("x" * 50, limit=10)
    assert clipped.startswith("x" * 10)
    assert "40 more characters truncated" in clipped


def test_to_json_serializes_non_native_values():
    from datetime import datetime

    rendered = to_json({"at": datetime(2026, 1, 2, 3, 4, 5)})
    assert "2026-01-02" in rendered


def test_compact_items_drops_html_and_excerpts_long_fields():
    result = {
        "items": [
            {"title": "t", "body": "b" * 5_000, "html": "<p>dup</p>", "upVotes": 3}
        ]
    }
    compacted = compact_items(result, field_limit=100)
    item = compacted["items"][0]
    assert "html" not in item
    assert len(item["body"]) < 200 and "truncated" in item["body"]
    assert item["upVotes"] == 3
    # original untouched
    assert "html" in result["items"][0]


def test_compact_items_passes_through_non_item_results():
    assert compact_items({"ok": True}) == {"ok": True}
    assert compact_items([1, 2]) == [1, 2]


# ── Run provenance in recall markdown (Story 3.13, T5 / AC-3) ────────────────
# The JSON payload is an untyped pass-through, so it gained `source_run_id` and
# `citation` for free. Markdown is hand-rendered and therefore silently dropped
# them -- these two pin the fix and the no-regression case.


def test_render_recall_surfaces_the_run_citation():
    import uuid

    from mcp_server.features.memory import _render_recall

    run_id = uuid.uuid4()
    rendered = _render_recall(
        "widget pricing",
        [
            {
                "id": 11,
                "type": "semantic",
                "confidence": 0.9,
                "content": "Competitor X sells the widget at 19.99 USD",
                "source_type": "scraper_run",
                "source_run_id": str(run_id),
                "citation": f"run_{run_id}",
            }
        ],
    )

    assert f"run_{run_id}" in rendered


def test_render_recall_unchanged_for_memory_without_citation():
    from mcp_server.features.memory import _render_recall

    rendered = _render_recall(
        "pricing",
        [
            {
                "id": 12,
                "type": "semantic",
                "confidence": 0.8,
                "content": "chat-derived fact",
                "source_type": "chat_message",
            }
        ],
    )

    assert "source:" not in rendered
    assert "chat-derived fact" in rendered
