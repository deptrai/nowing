"""Integration tests for project routes (Story 3.18)."""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.db import Document, DocumentType, Project

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def db_project(db_session, db_workspace, db_user):
    project = Project(
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        name="Test Project",
        description="A test project",
        master_instructions="Follow the test instructions.",
        is_archived=False,
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def db_document(db_session, db_workspace, db_user):
    doc = Document(
        title="Test Document",
        content="## Test\nContent",
        content_hash="test-doc-001-hash",
        unique_identifier_hash="test-doc-001-hash",
        source_markdown="## Test\nContent",
        document_type=DocumentType.FILE,
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


async def test_create_project(client_as_regular_user, db_workspace):
    response = await client_as_regular_user.post(
        f"/workspaces/{db_workspace.id}/projects",
        json={
            "name": "New Project",
            "description": "Created from test",
            "master_instructions": "Test instructions",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Project"
    assert data["workspace_id"] == db_workspace.id
    assert data["description"] == "Created from test"
    assert data["master_instructions"] == "Test instructions"
    assert data["is_archived"] is False


async def test_list_projects(client_as_regular_user, db_workspace, db_project):
    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/projects"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == db_project.id


async def test_list_projects_excludes_archived(client_as_regular_user, db_workspace, db_project, db_session):
    db_project.is_archived = True
    await db_session.flush()

    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/projects"
    )
    assert response.status_code == 200
    data = response.json()
    assert data == []

    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/projects?include_archived=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


async def test_get_project(client_as_regular_user, db_workspace, db_project):
    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/projects/{db_project.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == db_project.id
    assert data["name"] == "Test Project"


async def test_get_project_not_found(client_as_regular_user, db_workspace):
    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/projects/999999"
    )
    assert response.status_code == 404


async def test_update_project(client_as_regular_user, db_workspace, db_project):
    response = await client_as_regular_user.patch(
        f"/workspaces/{db_workspace.id}/projects/{db_project.id}",
        json={"name": "Updated Project", "description": "Updated description"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Project"
    assert data["description"] == "Updated description"


async def test_archive_project(client_as_regular_user, db_workspace, db_project):
    response = await client_as_regular_user.post(
        f"/workspaces/{db_workspace.id}/projects/{db_project.id}/archive"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_archived"] is True


async def test_delete_project(client_as_regular_user, db_workspace, db_project):
    response = await client_as_regular_user.delete(
        f"/workspaces/{db_workspace.id}/projects/{db_project.id}"
    )
    assert response.status_code == 204

    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/projects/{db_project.id}"
    )
    assert response.status_code == 404


async def test_pin_and_unpin_document(
    client_as_regular_user, db_workspace, db_project, db_document, db_session
):
    workspace_id = db_workspace.id
    project_id = db_project.id
    document_id = db_document.id

    pin_response = await client_as_regular_user.post(
        f"/workspaces/{workspace_id}/projects/{project_id}/documents/{document_id}/pin"
    )
    assert pin_response.status_code == 200
    assert pin_response.json()["status"] == "ok"

    # Expire the cached project so the route's selectinload fetches the new pin.
    db_session.expire(db_project)

    get_response = await client_as_regular_user.get(
        f"/workspaces/{workspace_id}/projects/{project_id}"
    )
    data = get_response.json()
    assert len(data["pinned_documents"]) == 1
    assert data["pinned_documents"][0]["document_id"] == document_id

    unpin_response = await client_as_regular_user.delete(
        f"/workspaces/{workspace_id}/projects/{project_id}/documents/{document_id}/pin"
    )
    assert unpin_response.status_code == 200
    assert unpin_response.json()["status"] == "ok"

    db_session.expire(db_project)
    get_response = await client_as_regular_user.get(
        f"/workspaces/{workspace_id}/projects/{project_id}"
    )
    data = get_response.json()
    assert data["pinned_documents"] == []


async def test_project_routes_forbidden_for_non_member(
    client_as_other, db_workspace, db_project
):
    response = await client_as_other.get(
        f"/workspaces/{db_workspace.id}/projects"
    )
    assert response.status_code == 403

    response = await client_as_other.post(
        f"/workspaces/{db_workspace.id}/projects",
        json={"name": "Evil Project"},
    )
    assert response.status_code == 403

    response = await client_as_other.get(
        f"/workspaces/{db_workspace.id}/projects/{db_project.id}"
    )
    assert response.status_code == 403
