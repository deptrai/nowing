"""Red-phase tests for MemorySearchRequest.type filter (Story 4.5).

These tests will fail until `MemoryHybridSearch.search` accepts and applies a
`type` filter and `memories_routes.search_memory` passes `body.type` through.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.memory]

BASE = "/api/v1/workspaces"


@pytest.mark.skip(reason="Story 4.5 red phase: type filter not implemented")
async def test_search_memory_filters_by_type(client, db_workspace):
    """POST /workspaces/{id}/memories/search with type returns only that type."""
    await client.post(
        f"{BASE}/{db_workspace.id}/memories",
        json={
            "content": "Competitor X raised prices by 10%.",
            "type": "semantic",
            "source_type": "manual",
        },
    )
    await client.post(
        f"{BASE}/{db_workspace.id}/memories",
        json={
            "content": "I felt excited when we launched the new feature.",
            "type": "episodic",
            "source_type": "manual",
        },
    )

    search_resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories/search",
        json={"query": "raised prices", "type": "semantic", "top_k": 5},
    )
    assert search_resp.status_code == 200
    items = search_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "semantic"


@pytest.mark.skip(reason="Story 4.5 red phase: type filter not implemented")
async def test_search_memory_with_unknown_type_returns_empty(client, db_workspace):
    """A type that matches no memories returns an empty result set."""
    await client.post(
        f"{BASE}/{db_workspace.id}/memories",
        json={
            "content": "A semantic fact.",
            "type": "semantic",
            "source_type": "manual",
        },
    )

    search_resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories/search",
        json={"query": "fact", "type": "procedural", "top_k": 5},
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["items"] == []
