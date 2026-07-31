"""Red-phase unit tests for each write-back action handler (Story 6.4)."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest

pytestmark = pytest.mark.unit

PROVIDERS: list[tuple[str, dict[str, Any]]] = [
    ("write_back_notion", {"title": "Weekly digest", "content": "Summary"}),
    ("write_back_linear", {"title": "Fix bug", "team_id": "TEAM"}),
    ("write_back_jira", {"project_key": "PROJ", "summary": "Fix bug"}),
    ("write_back_slack", {"channel": "#general", "text": "Hello"}),
]


def _load_invoke(module_name: str) -> Any:
    """Lazy-load the invoke module for a write-back action."""
    return importlib.import_module(
        f"app.automations.actions.builtin.{module_name}.invoke"
    )


def _ctx() -> Any:
    return SimpleNamespace(
        session=None,
        workspace_id=42,
        step_id="s1",
    )


def _tool() -> Any:
    async def _coroutine(**_kwargs: Any) -> str:
        return '{"id": "new-obj", "url": "https://example.com/new-obj"}'

    return SimpleNamespace(
        name="write_back_tool",
        coroutine=_coroutine,
        metadata={
            "mcp_input_schema": {
                "type": "object",
                "properties": {},
            },
        },
    )


@pytest.mark.parametrize("provider,params", PROVIDERS)
async def test_handler_creates_object_when_no_object_id_given(
    provider: str, params: dict[str, Any]
):
    """Each write-back handler creates a new object when object_id is omitted."""
    invoke = _load_invoke(provider)
    result = await invoke.write_back(
        ctx=_ctx(),
        params=params,
        tool=_tool(),
    )
    assert result["object_id"] == "new-obj"
    assert result["url"] == "https://example.com/new-obj"
    assert result["provider"] == provider.replace("write_back_", "")


@pytest.mark.parametrize("provider,params", PROVIDERS)
async def test_handler_updates_object_when_object_id_given(
    provider: str, params: dict[str, Any]
):
    """Each write-back handler switches to update mode when object_id is provided."""
    invoke = _load_invoke(provider)

    async def _update_coroutine(**_kwargs: Any) -> str:
        return '{"id": "existing-obj", "url": "https://example.com/existing-obj"}'

    tool = SimpleNamespace(
        name="write_back_tool",
        coroutine=_update_coroutine,
        metadata={"mcp_input_schema": {"type": "object", "properties": {}}},
    )
    result = await invoke.write_back(
        ctx=_ctx(),
        params={**params, "object_id": "existing-obj"},
        tool=tool,
    )
    assert result["object_id"] == "existing-obj"


@pytest.mark.parametrize("provider,_params", PROVIDERS)
async def test_handler_fails_when_no_connector_available(
    provider: str, _params: dict[str, Any]
):
    """A clear error is raised when no MCP connector is configured for the provider."""
    invoke = _load_invoke(provider)
    with pytest.raises(RuntimeError, match=r"No .* connector configured"):
        await invoke.write_back(
            ctx=_ctx(),
            params=_params,
            connectors=[],
        )
