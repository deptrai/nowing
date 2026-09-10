"""Integration tests for workspace modular skills routes (Story 3.18)."""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.db import WorkspaceSkill

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


SAMPLE_SKILL_MD = """---
name: Test Skill
slug: test-skill
description: A sample skill for testing.
trigger_pattern: "test"
skill_type: prompt
parameters_schema:
  type: object
  properties:
    topic:
      type: string
---

Run the test for {{ topic }}.
"""


@pytest_asyncio.fixture
async def db_skill(db_session, db_workspace, db_user):
    skill = WorkspaceSkill(
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        name="Test Skill",
        slug="test-skill",
        description="A test skill",
        trigger_pattern="test",
        skill_type="prompt",
        parameters_schema={"type": "object", "properties": {}},
        content_markdown="Run the test.",
        is_active=True,
    )
    db_session.add(skill)
    await db_session.flush()
    return skill


async def test_parse_skill_file(client_as_regular_user, db_workspace):
    response = await client_as_regular_user.post(
        f"/workspaces/{db_workspace.id}/skills/parse",
        json={"file_content": SAMPLE_SKILL_MD},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Skill"
    assert data["slug"] == "test-skill"
    assert data["skill_type"] == "prompt"


async def test_create_skill(client_as_regular_user, db_workspace):
    response = await client_as_regular_user.post(
        f"/workspaces/{db_workspace.id}/skills",
        json={
            "name": "New Skill",
            "slug": "new-skill",
            "description": "A new skill",
            "trigger_pattern": "new",
            "skill_type": "prompt",
            "parameters_schema": {"type": "object", "properties": {}},
            "content_markdown": "Run the new skill.",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Skill"
    assert data["slug"] == "new-skill"
    assert data["workspace_id"] == db_workspace.id


async def test_create_skill_duplicate_slug(client_as_regular_user, db_workspace, db_skill):
    response = await client_as_regular_user.post(
        f"/workspaces/{db_workspace.id}/skills",
        json={
            "name": "Duplicate Skill",
            "slug": db_skill.slug,
            "description": "Duplicate slug",
            "trigger_pattern": "dup",
            "skill_type": "prompt",
            "parameters_schema": {"type": "object", "properties": {}},
            "content_markdown": "Duplicate.",
            "is_active": True,
        },
    )
    assert response.status_code == 409


async def test_list_skills(client_as_regular_user, db_workspace, db_skill):
    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/skills"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == db_skill.id


async def test_list_skills_excludes_inactive(client_as_regular_user, db_workspace, db_skill, db_session):
    db_skill.is_active = False
    await db_session.flush()

    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/skills"
    )
    assert response.status_code == 200
    data = response.json()
    assert data == []

    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/skills?include_inactive=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


async def test_get_skill(client_as_regular_user, db_workspace, db_skill):
    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/skills/{db_skill.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == db_skill.id
    assert data["name"] == "Test Skill"


async def test_get_skill_not_found(client_as_regular_user, db_workspace):
    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/skills/999999"
    )
    assert response.status_code == 404


async def test_update_skill(client_as_regular_user, db_workspace, db_skill):
    response = await client_as_regular_user.patch(
        f"/workspaces/{db_workspace.id}/skills/{db_skill.id}",
        json={"name": "Updated Skill", "description": "Updated"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Skill"
    assert data["description"] == "Updated"


async def test_update_skill_duplicate_slug(client_as_regular_user, db_workspace, db_skill, db_session):
    other = WorkspaceSkill(
        workspace_id=db_workspace.id,
        created_by_id=db_skill.created_by_id,
        name="Other Skill",
        slug="other-skill",
        description="Other",
        trigger_pattern="other",
        skill_type="prompt",
        parameters_schema={},
        content_markdown="Other.",
        is_active=True,
    )
    db_session.add(other)
    await db_session.flush()

    response = await client_as_regular_user.patch(
        f"/workspaces/{db_workspace.id}/skills/{db_skill.id}",
        json={"slug": "other-skill"},
    )
    assert response.status_code == 409


async def test_delete_skill(client_as_regular_user, db_workspace, db_skill):
    response = await client_as_regular_user.delete(
        f"/workspaces/{db_workspace.id}/skills/{db_skill.id}"
    )
    assert response.status_code == 204

    response = await client_as_regular_user.get(
        f"/workspaces/{db_workspace.id}/skills/{db_skill.id}"
    )
    assert response.status_code == 404


async def test_skill_routes_forbidden_for_non_member(
    client_as_other, db_workspace, db_skill
):
    response = await client_as_other.get(
        f"/workspaces/{db_workspace.id}/skills"
    )
    assert response.status_code == 403

    response = await client_as_other.post(
        f"/workspaces/{db_workspace.id}/skills",
        json={
            "name": "Evil Skill",
            "slug": "evil-skill",
            "description": "Evil",
            "trigger_pattern": "evil",
            "skill_type": "prompt",
            "parameters_schema": {},
            "content_markdown": "Evil.",
            "is_active": True,
        },
    )
    assert response.status_code == 403

    response = await client_as_other.get(
        f"/workspaces/{db_workspace.id}/skills/{db_skill.id}"
    )
    assert response.status_code == 403
