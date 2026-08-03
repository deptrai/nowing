"""Unit tests for the automation-run Telegram message formatter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.automations.persistence.enums.run_status import RunStatus
from app.automations.services.telegram_notifications import (
    format_automation_run_message,
)
from app.gateway.telegram.formatting import _utf16_len

pytestmark = pytest.mark.unit


class _FakeAutomation:
    id = 123
    name = "Test Automation"
    workspace_id = 42


class _FakeAutomationWithReservedName:
    id = 456
    name = "My*Bot!"
    workspace_id = 7


def _fake_run(status: RunStatus, *, output=None, error=None):
    return SimpleNamespace(id=7, status=status, output=output, error=error)


@pytest.fixture(autouse=True)
def _patch_config(monkeypatch):
    from app.config import config

    monkeypatch.setattr(config, "NEXT_FRONTEND_URL", "https://app.nowing.net")


def test_success_message_format() -> None:
    run = _fake_run(RunStatus.SUCCEEDED)
    chunks = format_automation_run_message(run, _FakeAutomation())

    assert len(chunks) == 1
    assert "✅ Automation *'Test Automation'* finished successfully" in chunks[0]
    assert (
        "[Open run](https://app.nowing.net/dashboard/42/automations/123?run_id=7)"
        in chunks[0]
    )


def test_failure_message_includes_first_error_line() -> None:
    run = _fake_run(
        RunStatus.FAILED,
        error={"message": "Something went wrong\nsecond line", "type": "RuntimeError"},
    )
    chunks = format_automation_run_message(run, _FakeAutomation(), run_error=run.error)

    assert len(chunks) == 1
    assert "❌ Automation *'Test Automation'* failed" in chunks[0]
    assert "Something went wrong" in chunks[0]
    assert "second line" not in chunks[0]
    assert "[Open run]" in chunks[0]


def test_cancelled_message_format() -> None:
    run = _fake_run(RunStatus.CANCELLED)
    chunks = format_automation_run_message(run, _FakeAutomation())

    assert len(chunks) == 1
    assert "⚠️ Automation *'Test Automation'* cancelled" in chunks[0]
    assert "[Open run]" in chunks[0]


def test_timed_out_message_format() -> None:
    run = _fake_run(RunStatus.TIMED_OUT)
    chunks = format_automation_run_message(run, _FakeAutomation())

    assert len(chunks) == 1
    assert "⏱ Automation *'Test Automation'* timed out" in chunks[0]
    assert "[Open run]" in chunks[0]


def test_large_output_chunks_and_first_chunk_has_deep_link() -> None:
    large_output = "word " * 2000
    run = _fake_run(RunStatus.SUCCEEDED, output=large_output)
    chunks = format_automation_run_message(run, _FakeAutomation())

    assert len(chunks) > 1
    assert _utf16_len(chunks[0]) <= 4096
    assert "[Open run]" in chunks[0]
    assert "word" in chunks[1]


def test_name_with_reserved_markdown_characters_is_escaped() -> None:
    run = _fake_run(RunStatus.SUCCEEDED)
    chunks = format_automation_run_message(run, _FakeAutomationWithReservedName())

    assert len(chunks) == 1
    # The raw reserved characters should not appear inside the bold name.
    assert "My*Bot!" not in chunks[0]
    assert "My\\*Bot\\!" in chunks[0]
    assert "[Open run]" in chunks[0]


def test_empty_next_frontend_url_omits_open_run_link(monkeypatch) -> None:
    from app.config import config

    monkeypatch.setattr(config, "NEXT_FRONTEND_URL", "")
    run = _fake_run(RunStatus.SUCCEEDED)
    chunks = format_automation_run_message(run, _FakeAutomation())

    assert len(chunks) == 1
    assert "✅ Automation *'Test Automation'* finished successfully" in chunks[0]
    assert "[Open run]" not in chunks[0]
