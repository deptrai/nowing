"""Integration tests for the playbook API."""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture
async def billable_workspace(db_workspace, db_session):
    """Set explicit BYOK-style model ids so automations are billable."""
    db_workspace.chat_model_id = 1
    db_workspace.image_gen_model_id = 1
    db_workspace.vision_model_id = 1
    await db_session.flush()
    return db_workspace


@pytest.fixture
async def sample_automation(client: httpx.AsyncClient, billable_workspace, db_user):
    """Create a valid automation through the API."""
    from app.automations.schemas.definition import AutomationDefinition, Inputs
    from app.automations.schemas.definition.plan_step import PlanStep

    definition = AutomationDefinition(
        name="Deal radar",
        plan=[
            PlanStep(
                step_id="s1",
                action="agent_task",
                params={"query": "{{ inputs.query }}"},
            )
        ],
        inputs=Inputs(
            schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            }
        ),
    )

    resp = await client.post(
        "/api/v1/automations",
        json={
            "workspace_id": billable_workspace.id,
            "name": "Deal radar",
            "definition": definition.model_dump(mode="json", by_alias=True),
            "triggers": [],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_playbook_from_automation(
    client: httpx.AsyncClient,
    sample_automation: dict,
    billable_workspace,
):
    """A user can save an existing automation as a playbook."""
    resp = await client.post(
        "/api/v1/playbooks",
        json={
            "source_automation_id": sample_automation["id"],
            "name": "Deal radar playbook",
            "tool_scope": [],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Deal radar playbook"
    assert data["workspace_id"] == billable_workspace.id
    assert data["scope"] == "workspace"
    assert data["version"] == 1
    assert data["inputs_schema"]["type"] == "object"
    assert data["source_automation_id"] == sample_automation["id"]
    assert "agent_task" in data["tool_scope"]


async def test_list_playbooks_includes_workspace_playbooks(
    client: httpx.AsyncClient,
    sample_automation: dict,
    billable_workspace,
):
    """The playbook list returns workspace playbooks."""
    create = await client.post(
        "/api/v1/playbooks",
        json={
            "source_automation_id": sample_automation["id"],
            "name": "Listed playbook",
        },
    )
    assert create.status_code == 201

    resp = await client.get(
        "/api/v1/playbooks",
        params={"workspace_id": billable_workspace.id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(p["name"] == "Listed playbook" for p in data["items"])


async def test_instantiate_playbook_creates_automation_and_pins_version(
    client: httpx.AsyncClient,
    sample_automation: dict,
    billable_workspace,
):
    """Instantiating a playbook creates an automation pinned to the playbook version."""
    create = await client.post(
        "/api/v1/playbooks",
        json={
            "source_automation_id": sample_automation["id"],
            "name": "Template",
        },
    )
    assert create.status_code == 201
    playbook = create.json()

    resp = await client.post(
        f"/api/v1/playbooks/{playbook['id']}/instantiate",
        json={
            "workspace_id": billable_workspace.id,
            "inputs": {"query": "Hanoi apartments"},
        },
    )
    assert resp.status_code == 201
    automation = resp.json()
    assert automation["derived_from_playbook_id"] == playbook["id"]
    assert automation["playbook_version"] == playbook["version"]
    assert automation["name"] == "Template"


async def test_instantiate_rejects_inputs_not_matching_schema(
    client: httpx.AsyncClient,
    sample_automation: dict,
    billable_workspace,
):
    """Instantiation validates inputs against the playbook's ``inputs_schema``."""
    create = await client.post(
        "/api/v1/playbooks",
        json={
            "source_automation_id": sample_automation["id"],
            "name": "Template",
        },
    )
    assert create.status_code == 201
    playbook = create.json()

    resp = await client.post(
        f"/api/v1/playbooks/{playbook['id']}/instantiate",
        json={
            "workspace_id": billable_workspace.id,
            "inputs": {"query": 123},
        },
    )
    assert resp.status_code == 422


async def test_playbook_update_bumps_version_and_keeps_instance_pinned(
    client: httpx.AsyncClient,
    sample_automation: dict,
    billable_workspace,
):
    """Updating a playbook bumps its version but existing instances stay pinned."""
    from app.automations.schemas.definition import AutomationDefinition
    from app.automations.schemas.definition.plan_step import PlanStep

    create = await client.post(
        "/api/v1/playbooks",
        json={
            "source_automation_id": sample_automation["id"],
            "name": "Versioned",
        },
    )
    assert create.status_code == 201
    playbook = create.json()

    inst = await client.post(
        f"/api/v1/playbooks/{playbook['id']}/instantiate",
        json={
            "workspace_id": billable_workspace.id,
            "inputs": {"query": "old"},
        },
    )
    assert inst.status_code == 201
    automation_id = inst.json()["id"]

    new_definition = AutomationDefinition(
        name="Versioned",
        plan=[
            PlanStep(
                step_id="s1",
                action="agent_task",
                params={"query": "{{ inputs.query }}"},
            ),
            PlanStep(step_id="s2", action="agent_task", params={"query": "extra"}),
        ],
    )

    update = await client.patch(
        f"/api/v1/playbooks/{playbook['id']}",
        json={
            "definition": new_definition.model_dump(mode="json", by_alias=True),
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["version"] == playbook["version"] + 1
    assert len(updated["tool_scope"]) == 1

    get = await client.get(f"/api/v1/automations/{automation_id}")
    assert get.status_code == 200
    assert get.json()["playbook_version"] == playbook["version"]
