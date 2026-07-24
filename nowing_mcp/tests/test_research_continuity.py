"""ATDD acceptance tests for Story 4.6 — Research Continuity (MCP tool side).

Activated during ``dev-story``. These assert that ``nowing_continue_research``
(a) returns the thread's previous citations alongside its recalled memories and
(b) surfaces a clear error when the thread does not exist (no implicit create).

The tool now calls the backend endpoint
``GET /workspaces/{id}/research-threads/{id}/context`` and renders BOTH the
ranked memories and the thread's previous citations; a 404 from the backend
becomes a clear "research thread not found" tool error.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

_BACKEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "nowing_backend")
)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.lowlevel.server import request_ctx as mcp_request_ctx  # noqa: E402
from mcp_server.config import Settings  # noqa: E402
from mcp_server.core.workspace_context import Workspace, WorkspaceContext  # noqa: E402
from mcp_server.features import memory  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest.fixture
def settings() -> Settings:
    return Settings(
        base_url="http://localhost:8000",
        api_key="nw_pat_test",
        api_prefix="/api/v1",
        timeout=5.0,
        default_workspace="Test",
        host="127.0.0.1",
        port=8080,
    )


async def test_continue_research_renders_memories_and_citations(settings):
    """AC-1: the tool output includes both recalled memories and prior citations."""

    # Fake client returns the NEW context endpoint shape (memories + citations).
    class _FakeClient:
        async def request(self, method, path, **_kwargs):
            assert method == "GET"
            assert "/research-threads/" in path and path.endswith("/context")
            return {
                "thread_id": 7,
                "title": "Q3 research",
                "memories": [
                    {"id": 1, "type": "semantic", "confidence": 0.9,
                     "content": "Competitor X raised prices by 10% in Q3."}
                ],
                "citations": [
                    {"label": "pricing page", "url": "https://example.com/pricing"},
                    {"label": "tier note", "url": "https://example.com/tier"},
                ],
            }

    result = await _invoke_continue_research(
        _server_with_client(_FakeClient()), research_thread_id=7
    )

    assert "Competitor X raised prices" in result  # memory rendered
    assert "https://example.com/pricing" in result  # citation rendered
    assert "https://example.com/tier" in result


async def test_continue_research_missing_thread_returns_clear_error(settings):
    """AC-2: a backend 404 surfaces as a clear 'not found' error; no implicit creation."""
    from mcp_server.core.client import ToolError

    class _NotFoundClient:
        async def request(self, method, path, **_kwargs):
            raise ToolError("Research thread not found")

    with pytest.raises(Exception) as exc:  # ToolError or rendered error string
        await _invoke_continue_research(
            _server_with_client(_NotFoundClient()), research_thread_id=404404
        )
    assert "not found" in str(exc.value).lower()


# --- helpers that drive the registered tool against a fake client ---------------


async def _invoke_continue_research(server, *, research_thread_id):
    """Call the registered nowing_continue_research tool and return its text.

    A request context is set so FastMCP can build a call context; the tool
    itself takes no Context param, so no backend session is needed.
    """
    token = mcp_request_ctx.set(SimpleNamespace())
    try:
        result = await server.call_tool(
            "nowing_continue_research",
            {"research_thread_id": research_thread_id},
        )
        return str(result)
    finally:
        mcp_request_ctx.reset(token)


def _server_with_client(client):
    """Build a minimal MCP server with the memory tools bound to ``client``.

    Uses a plain FastMCP (not the workspace-aware wrapper) so tool dispatch does
    not fetch the workspace tool-enablement manifest — the fake client only
    serves the research-thread context endpoint. The active workspace is seeded
    under the local (unbound) identity so ``context.resolve(None)`` inside the
    tool resolves without a network call.
    """
    context = WorkspaceContext(client, preferred_reference=None)
    mcp = FastMCP("Nowing-test")
    memory.register(mcp, client, context)
    context.remember(Workspace(id=1, name="Test"))
    return mcp
