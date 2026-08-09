"""Red-phase unit tests for ``app.services.agent_chat.audit.log_public_call`` (Story 18.1)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def _patch_metric_recorder(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace the public-call metrics recorder with a spy."""
    from app.observability import metrics

    spy = MagicMock()
    monkeypatch.setattr(metrics, "record_agent_chat_public_call", spy, raising=False)
    return spy


async def test_log_public_call_logs_required_fields_and_excludes_message_content(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-11: the audit log records the allowed fields and never the message body."""
    from app.services.agent_chat import audit as audit_mod

    spy = _patch_metric_recorder(monkeypatch)
    content = "sensitive user message body that must not be logged"

    logger_name = getattr(audit_mod, "logger", None)
    if logger_name is None:
        logger_name = logging.getLogger("app.services.agent_chat.audit")

    with caplog.at_level(logging.INFO, logger=logger_name.name):
        await audit_mod.log_public_call(
            actor_user_id="u-1",
            pat_id="pat-abc",
            workspace_id=42,
            client_id="bdsai.vn",
            agent_id="bdsai-listing-assistant",
            route="POST /api/v1/workspaces/42/agent-chat/threads",
            status=201,
            run_id="run-abc",
            content=content,
        )

    audit_records = [
        r for r in caplog.records if r.name == "app.services.agent_chat.audit"
    ]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record.message == "agent_chat.public_call"
    assert record.actor_user_id == "u-1"
    assert record.pat_id == "pat-abc"
    assert record.workspace_id in (42, "42")
    assert record.client_id == "bdsai.vn"
    assert record.agent_id == "bdsai-listing-assistant"
    assert record.route == "POST /api/v1/workspaces/42/agent-chat/threads"
    assert record.status in (201, "201")
    assert record.run_id == "run-abc"
    assert "content" not in record.__dict__
    assert content not in caplog.text

    assert spy.call_count == 1
    labels = spy.call_args.kwargs
    assert set(labels) == {"workspace_id", "client_id", "agent_id", "route", "status"}
    assert labels["workspace_id"] in (42, "42")
    assert labels["client_id"] == "bdsai.vn"
    assert labels["agent_id"] == "bdsai-listing-assistant"
    assert labels["route"] == "POST /api/v1/workspaces/42/agent-chat/threads"
    assert labels["status"] in (201, "201")
    assert content not in labels.values()


async def test_log_public_call_emits_metrics_with_bounded_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-11 Pattern 4: the metric carries only the bounded, low-cardinality labels."""
    from app.services.agent_chat import audit as audit_mod

    spy = _patch_metric_recorder(monkeypatch)

    await audit_mod.log_public_call(
        actor_user_id="u-2",
        pat_id="pat-xyz",
        workspace_id=7,
        client_id=None,
        agent_id=None,
        route="POST /api/v1/workspaces/7/agent-chat/threads/123/messages",
        status=503,
        run_id="run-xyz",
    )

    assert spy.call_count == 1
    labels = spy.call_args.kwargs
    assert set(labels) == {"workspace_id", "client_id", "agent_id", "route", "status"}
    assert labels["client_id"] == ""
    assert labels["agent_id"] == ""
    assert labels["workspace_id"] in (7, "7")
    assert (
        labels["route"] == "POST /api/v1/workspaces/7/agent-chat/threads/123/messages"
    )
    assert labels["status"] in (503, "503")
    assert "content" not in labels


async def test_log_public_call_handles_logger_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the logger fails, the audit call must still return and still emit metrics."""
    from app.services.agent_chat import audit as audit_mod

    spy = _patch_metric_recorder(monkeypatch)

    logger = getattr(audit_mod, "logger", None)
    if logger is None:
        logger = logging.getLogger("app.services.agent_chat.audit")

    monkeypatch.setattr(
        logger,
        "info",
        MagicMock(side_effect=RuntimeError("log backend exploded")),
    )

    await audit_mod.log_public_call(
        actor_user_id="u-3",
        pat_id="pat-123",
        workspace_id=1,
        client_id="bdsai.vn",
        agent_id="bdsai-listing-assistant",
        route="GET /api/v1/workspaces/1/agent-chat/threads",
        status=403,
        run_id="run-123",
    )

    assert spy.call_count == 1
    labels = spy.call_args.kwargs
    assert labels["client_id"] == "bdsai.vn"
    assert labels["status"] in (403, "403")
