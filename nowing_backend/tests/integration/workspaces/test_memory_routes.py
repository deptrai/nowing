"""Red-phase acceptance tests for unified long-term memory (Story 3.8).

These tests describe the expected HTTP contract for the new
`/api/v1/workspaces/{workspace_id}/memories` endpoints and the legacy
memory bridge. They will fail until Story 3.8 is implemented.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.memory]

BASE = "/api/v1/workspaces"


async def test_owner_can_create_memory(client, db_workspace):
    """POST /workspaces/{id}/memories returns 201 with memory payload."""
    payload = {
        "content": "Competitor X raised prices by 10% in Q2 2026.",
        "type": "semantic",
        "tags": ["competitor", "pricing"],
        "confidence": 0.95,
        "source_type": "manual",
    }
    resp = await client.post(f"{BASE}/{db_workspace.id}/memories", json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["workspace_id"] == db_workspace.id
    assert body["content"] == payload["content"]
    assert body["type"] == "semantic"
    assert body["tags"] == ["competitor", "pricing"]
    assert body["confidence"] == pytest.approx(0.95)
    assert "id" in body


async def test_search_memory_isolated_from_other_workspace(
    client, db_workspace, db_user, db_session
):
    """Memory created in workspace A must not appear in workspace B search."""
    from app.db import Workspace
    from app.routes.workspaces_routes import create_default_roles_and_membership

    # Create a second workspace owned by the same user.
    other_workspace = Workspace(name="Other Space", user_id=db_user.id)
    db_session.add(other_workspace)
    await db_session.flush()
    await create_default_roles_and_membership(
        db_session, other_workspace.id, db_user.id
    )
    await db_session.flush()

    create_payload = {
        "content": "Workspace A secret fact.",
        "type": "semantic",
        "source_type": "manual",
    }
    create_resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories", json=create_payload
    )
    assert create_resp.status_code == 201

    # Searching workspace A should find the memory.
    search_a = await client.post(
        f"{BASE}/{db_workspace.id}/memories/search",
        json={"query": "secret fact", "top_k": 5},
    )
    assert search_a.status_code == 200
    assert len(search_a.json()["items"]) == 1

    # Searching workspace B should return no results.
    search_b = await client.post(
        f"{BASE}/{other_workspace.id}/memories/search",
        json={"query": "secret fact", "top_k": 5},
    )
    assert search_b.status_code == 200
    assert search_b.json()["items"] == []


async def test_viewer_cannot_create_memory(client_as_viewer, db_workspace):
    """Viewer lacks memory:create and receives 403."""
    payload = {
        "content": "A fact",
        "type": "semantic",
        "source_type": "manual",
    }
    resp = await client_as_viewer.post(
        f"{BASE}/{db_workspace.id}/memories", json=payload
    )
    assert resp.status_code == 403


async def test_editor_can_create_but_not_delete_memory(
    client_as_editor, db_workspace
):
    """Editor can create and update memory, but not delete it."""
    create_payload = {
        "content": "Editor fact",
        "type": "semantic",
        "source_type": "manual",
    }
    create_resp = await client_as_editor.post(
        f"{BASE}/{db_workspace.id}/memories", json=create_payload
    )
    assert create_resp.status_code == 201
    memory_id = create_resp.json()["id"]

    update_resp = await client_as_editor.patch(
        f"/api/v1/memories/{memory_id}",
        json={"corrected_content": "Editor corrected fact"},
    )
    assert update_resp.status_code == 200

    delete_resp = await client_as_editor.delete(f"/api/v1/memories/{memory_id}")
    assert delete_resp.status_code == 403


async def test_update_memory_preserves_version(client, db_workspace):
    """PATCH /memories/{id} updates content and keeps previous version."""
    create_resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories",
        json={
            "content": "Original fact",
            "type": "semantic",
            "source_type": "manual",
        },
    )
    assert create_resp.status_code == 201
    memory_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/memories/{memory_id}",
        json={"corrected_content": "Corrected fact"},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["content"] == "Corrected fact"
    assert len(body["previous_versions"]) == 1
    assert body["previous_versions"][0]["previous_content"] == "Original fact"


async def test_delete_memory_cascades_versions_and_relations(client, db_workspace):
    """DELETE /memories/{id} removes memory, versions, and relations."""
    create_resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories",
        json={
            "content": "Fact to delete",
            "type": "semantic",
            "source_type": "manual",
        },
    )
    assert create_resp.status_code == 201
    memory_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/memories/{memory_id}")
    assert delete_resp.status_code == 204

    search_resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories/search",
        json={"query": "Fact to delete", "top_k": 5},
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["items"] == []


async def test_legacy_get_team_memory_returns_markdown(client, db_workspace):
    """GET /workspaces/{id}/memory still returns {memory_md, limits}."""
    # Seed a memory through the new API first.
    await client.post(
        f"{BASE}/{db_workspace.id}/memories",
        json={
            "content": "Team memory fact.",
            "type": "semantic",
            "source_type": "manual",
        },
    )

    resp = await client.get(f"{BASE}/{db_workspace.id}/memory")
    assert resp.status_code == 200
    body = resp.json()
    assert "memory_md" in body
    assert "limits" in body
    assert "Team memory fact" in body["memory_md"]


async def test_legacy_put_team_memory_parses_into_structured_memory(
    client, db_workspace
):
    """PUT /workspaces/{id}/memory parses markdown into Memory rows."""
    put_resp = await client.put(
        f"{BASE}/{db_workspace.id}/memory",
        json={
            "memory_md": "## Facts\n- 2026-07-22: Team memory fact parsed from markdown.\n"
        },
    )
    assert put_resp.status_code == 200

    search_resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories/search",
        json={"query": "parsed from markdown", "top_k": 5},
    )
    assert search_resp.status_code == 200
    assert any(
        "parsed from markdown" in item["content"]
        for item in search_resp.json()["items"]
    )


async def test_legacy_get_user_memory_returns_markdown(client):
    """GET /users/me/memory still returns {memory_md, limits}."""
    resp = await client.get("/api/v1/users/me/memory")
    assert resp.status_code == 200
    body = resp.json()
    assert "memory_md" in body
    assert "limits" in body


async def test_search_memory_with_tag_filter(client, db_workspace):
    """Search can filter by tags."""
    await client.post(
        f"{BASE}/{db_workspace.id}/memories",
        json={
            "content": "Tagged fact",
            "type": "semantic",
            "tags": ["priority"],
            "source_type": "manual",
        },
    )
    await client.post(
        f"{BASE}/{db_workspace.id}/memories",
        json={
            "content": "Untagged fact",
            "type": "semantic",
            "source_type": "manual",
        },
    )

    resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories/search",
        json={"query": "fact", "top_k": 5, "tags": ["priority"]},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["content"] == "Tagged fact"


async def test_search_memory_with_research_thread_filter(client, db_workspace):
    """Search can filter by research_thread_id."""
    # TODO: create research_thread fixture once Story 4.6 scaffolds it.
    resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories/search",
        json={"query": "fact", "top_k": 5, "research_thread_id": 1},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json()["items"], list)
