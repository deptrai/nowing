"""Unit tests for canonical tenant context helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.canonical.tenant_context import (
    canonical_workspace_context,
    get_canonical_workspace_id,
    set_request_tenant_context,
)


class _FakeSession:
    """Minimal fake AsyncSession that records set_config calls."""

    def __init__(self) -> None:
        self.info: dict[str, Any] = {}
        self.executed: list[tuple[str, dict[str, str]]] = []
        self.execute = AsyncMock(side_effect=self._execute)

    async def _execute(self, stmt: Any, params: dict[str, str] | None = None) -> Any:
        self.executed.append((str(stmt), params or {}))
        return MagicMock()


def _guc_value(executed: list[tuple[str, dict[str, str]]], guc: str) -> str:
    """Return the parameter value for a given GUC from recorded execute calls."""
    key_map = {
        "app.workspace_id": "wid",
        "app.current_client_id": "cid",
        "app.current_agent_id": "aid",
        "app.run_id": "rid",
        "app.memory_id": "mid",
        "app.current_user_id": "uid",
    }
    for stmt, params in executed:
        if guc in stmt:
            return params[key_map[guc]]
    raise KeyError(guc)


@pytest.mark.asyncio
async def test_set_request_tenant_context_sets_all_gucs():
    """All tenant GUCs are set, with None written as empty string."""
    session = _FakeSession()
    await set_request_tenant_context(
        session,
        workspace_id=42,
        client_id="client-1",
        agent_id="agent-1",
        run_id="run-1",
        memory_id=7,
        user_id="user-1",
    )

    assert len(session.executed) == 6

    assert _guc_value(session.executed, "app.workspace_id") == "42"
    assert _guc_value(session.executed, "app.current_client_id") == "client-1"
    assert _guc_value(session.executed, "app.current_agent_id") == "agent-1"
    assert _guc_value(session.executed, "app.run_id") == "run-1"
    assert _guc_value(session.executed, "app.memory_id") == "7"
    assert _guc_value(session.executed, "app.current_user_id") == "user-1"

    assert session.info["canonical_workspace_id"] == 42
    assert session.info["current_client_id"] == "client-1"
    assert session.info["current_agent_id"] == "agent-1"
    assert session.info["current_run_id"] == "run-1"
    assert session.info["current_memory_id"] == 7
    assert session.info["current_user_id"] == "user-1"


@pytest.mark.asyncio
async def test_set_request_tenant_context_clears_gucs_with_none():
    """None values clear any prior GUC by writing an empty string."""
    session = _FakeSession()
    await set_request_tenant_context(session)

    assert len(session.executed) == 6
    for guc in (
        "app.workspace_id",
        "app.current_client_id",
        "app.current_agent_id",
        "app.run_id",
        "app.memory_id",
        "app.current_user_id",
    ):
        assert _guc_value(session.executed, guc) == ""


@pytest.mark.asyncio
async def test_canonical_workspace_context_yields_and_clears():
    """Context manager sets and removes the canonical workspace marker."""
    session = _FakeSession()

    async with canonical_workspace_context(session, 99) as yielded:
        assert yielded is session
        assert get_canonical_workspace_id(session) == 99

    assert get_canonical_workspace_id(session) is None
