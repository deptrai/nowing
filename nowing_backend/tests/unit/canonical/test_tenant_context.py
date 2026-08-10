"""Unit tests for ``set_request_tenant_context`` (Stories 18.1/18.8)."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit

_SET_CONFIG_RE = re.compile(
    r"set_config\(\s*'([^']+)'\s*,\s*:([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(true|false)\s*\)",
    re.IGNORECASE,
)


def _sql_text(sql) -> str:
    return sql.text if hasattr(sql, "text") else str(sql)


def _params(call) -> dict:
    if len(call.args) > 1:
        return call.args[1]
    return call.kwargs.get("params") or call.kwargs.get("parameters") or {}


def _parse_set_config_call(call) -> tuple[str, str, bool]:
    """Return (guc_name, value, is_local) for a ``set_config(...)`` call."""
    sql = call.args[0] if call.args else call.kwargs.get("statement") or call.kwargs.get("sql")
    sql_text = _sql_text(sql)
    params = _params(call)
    match = _SET_CONFIG_RE.search(sql_text)
    if not match:
        raise AssertionError(f"Expected set_config SQL, got {sql_text!r}")
    name, param_key, local = match.groups()
    return name, str(params.get(param_key, "")), local.lower() == "true"


_ALL_GUC_KEYS = {
    "app.workspace_id",
    "app.current_client_id",
    "app.current_agent_id",
    "app.run_id",
    "app.memory_id",
    "app.current_user_id",
}


async def test_set_request_tenant_context_sets_all_gucs():
    """``set_request_tenant_context`` sets the full tenant GUC set."""
    from app.canonical.tenant_context import set_request_tenant_context

    session = AsyncMock()
    session.info = {}

    await set_request_tenant_context(session, 42, "bdsai.vn", "bdsai-listing-assistant")

    assert len(session.execute.call_args_list) == 6
    gucs = {}
    for call in session.execute.call_args_list:
        name, value, is_local = _parse_set_config_call(call)
        assert is_local is True, f"{name} must be set with is_local=true"
        gucs[name] = value

    assert gucs == {
        "app.workspace_id": "42",
        "app.current_client_id": "bdsai.vn",
        "app.current_agent_id": "bdsai-listing-assistant",
        "app.run_id": "",
        "app.memory_id": "",
        "app.current_user_id": "",
    }


async def test_set_request_tenant_context_uses_is_local_true():
    """Every ``set_config`` call must use ``is_local=true`` (``SET LOCAL``)."""
    from app.canonical.tenant_context import set_request_tenant_context

    session = AsyncMock()
    session.info = {}

    await set_request_tenant_context(session, 1, "client-1", "agent-1")

    for call in session.execute.call_args_list:
        _, _, is_local = _parse_set_config_call(call)
        assert is_local is True


async def test_set_request_tenant_context_writes_empty_string_for_none_client_id():
    """A missing ``client_id`` clears the GUC by writing an empty string."""
    from app.canonical.tenant_context import set_request_tenant_context

    session = AsyncMock()
    session.info = {}

    await set_request_tenant_context(session, 42, None, "agent-1")

    gucs = {}
    for call in session.execute.call_args_list:
        name, value, _ = _parse_set_config_call(call)
        gucs[name] = value

    assert gucs["app.workspace_id"] == "42"
    assert gucs["app.current_client_id"] == ""
    assert gucs["app.current_agent_id"] == "agent-1"


async def test_set_request_tenant_context_writes_empty_string_for_none_agent_id():
    """A missing ``agent_id`` clears the GUC by writing an empty string."""
    from app.canonical.tenant_context import set_request_tenant_context

    session = AsyncMock()
    session.info = {}

    await set_request_tenant_context(session, 42, "client-1")

    gucs = {}
    for call in session.execute.call_args_list:
        name, value, _ = _parse_set_config_call(call)
        gucs[name] = value

    assert gucs["app.workspace_id"] == "42"
    assert gucs["app.current_client_id"] == "client-1"
    assert gucs["app.current_agent_id"] == ""


class _RollbackSession:
    """Mock async session that simulates transaction-local GUC reset on rollback."""

    def __init__(self) -> None:
        self.info: dict = {}
        self.gucs: dict[str, str] = {}
        self.calls: list[str] = []

    async def execute(self, sql, params=None) -> None:
        text = _sql_text(sql)
        params = params or {}
        match = _SET_CONFIG_RE.search(text)
        if match:
            name, param, local = match.groups()
            if local.lower() == "true":
                self.gucs[name] = str(params.get(param, ""))
            self.calls.append(name)

    async def rollback(self) -> None:
        """``SET LOCAL`` values are discarded when the transaction rolls back."""
        self.gucs.clear()


async def test_set_request_tenant_context_resets_on_rollback():
    """GUCs set with ``SET LOCAL`` must disappear when the session rolls back."""
    from app.canonical.tenant_context import set_request_tenant_context

    session = _RollbackSession()

    await set_request_tenant_context(session, 7, "client-x", "agent-y")

    assert len(session.calls) == 6
    assert set(session.gucs.keys()) == _ALL_GUC_KEYS
    assert session.gucs == {
        "app.workspace_id": "7",
        "app.current_client_id": "client-x",
        "app.current_agent_id": "agent-y",
        "app.run_id": "",
        "app.memory_id": "",
        "app.current_user_id": "",
    }

    await session.rollback()

    assert session.gucs == {}
