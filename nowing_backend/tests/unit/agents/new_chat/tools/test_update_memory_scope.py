"""Unit tests for heading-based memory validation."""

import pytest

from app.services.memory.validation import (
    validate_bullet_format,
    validate_memory_scope,
)

pytestmark = pytest.mark.unit


def test_validate_memory_scope_rejects_new_personal_heading_in_team() -> None:
    content = "## Preferences\n- 2026-04-10: Prefers dark mode\n"
    result, _warnings = validate_memory_scope(content, "team")
    assert result is not None
    assert result["status"] == "error"
    assert "preferences" in result["message"]


def test_validate_memory_scope_allows_old_marker_payload_in_team_scope() -> None:
    content = "- (2026-04-10) [pref] Legacy personal marker remains readable\n"
    result, _warnings = validate_memory_scope(content, "team")
    assert result is None


def test_validate_memory_scope_allows_team_headings() -> None:
    content = "## Engineering Conventions\n- 2026-04-10: Uses PostgreSQL\n"
    result, _warnings = validate_memory_scope(content, "team")
    assert result is None


def test_validate_bullet_format_accepts_new_and_legacy_bullets() -> None:
    content = (
        "## Facts\n"
        "- 2026-04-10: Senior Python developer\n"
        "- (2026-04-10) [fact] Legacy fact is preserved\n"
    )
    warnings = validate_bullet_format(content)
    assert warnings == []


def test_validate_bullet_format_warns_on_nonstandard_bullet() -> None:
    content = "## Facts\n- Senior Python developer\n"
    warnings = validate_bullet_format(content)
    assert len(warnings) == 1
    assert "Non-standard memory bullet" in warnings[0]
