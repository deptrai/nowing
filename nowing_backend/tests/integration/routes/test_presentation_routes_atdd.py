"""Green-phase integration tests for Story 27.2a — Presentation REST routes."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SlidePresentation, Workspace
from app.services.presentation.service import PresentationStudioService


@pytest.fixture(autouse=True)
def patch_llm_and_feature_flag(monkeypatch):
    """Stub the LLM call and enable the feature so tests run without a real model."""

    async def _fake_call(*args, **kwargs):
        return (
            {
                "title": "Pitch Deck",
                "slug": "pitch-deck",
                "description": "A pitch",
                "slides": [
                    {"title": "Problem", "bullets": ["pain"]},
                    {"title": "Solution", "bullets": ["feature"]},
                ],
            },
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    monkeypatch.setattr(PresentationStudioService, "_call_llm_for_deck", _fake_call)
    monkeypatch.setattr("app.config.config.PRESENTATION_STUDIO_ENABLED", True)
    monkeypatch.setattr(
        "app.routes.presentation_routes.config.PRESENTATION_STUDIO_ENABLED", True
    )


@pytest.mark.integration
async def test_list_presentations_requires_member(client_as_other, db_workspace):
    """AC-5: list route rejects non-members."""
    res = await client_as_other.get(
        f"/api/v1/presentations?workspace_id={db_workspace.id}"
    )
    assert res.status_code in (401, 403)


@pytest.mark.integration
async def test_create_presentation_403_when_flag_off(
    client_as_regular_user, db_workspace, db_session
):
    """AC-6: POST returns 403 when the workspace flag is off."""
    db_workspace.presentation_studio_enabled = False
    await db_session.flush()

    res = await client_as_regular_user.post(
        "/api/v1/presentations/generate",
        json={
            "workspace_id": db_workspace.id,
            "prompt": "Pitch deck",
            "output_format": "pptx",
        },
    )
    assert res.status_code == 403
    assert "not enabled" in res.json()["detail"].lower()


@pytest.mark.integration
async def test_all_routes_403_when_global_flag_off(
    client_as_regular_user, db_workspace, monkeypatch
):
    """AC-6: global PRESENTATION_STUDIO_ENABLED=false 403s list/get/download/preview/delete."""
    monkeypatch.setattr(
        "app.routes.presentation_routes.config.PRESENTATION_STUDIO_ENABLED", False
    )
    ws = db_workspace.id
    pid = "00000000-0000-0000-0000-000000000001"
    paths = [
        ("GET", f"/api/v1/presentations?workspace_id={ws}"),
        ("GET", f"/api/v1/presentations/{pid}?workspace_id={ws}"),
        ("GET", f"/api/v1/presentations/{pid}/download?workspace_id={ws}"),
        ("GET", f"/api/v1/presentations/{pid}/preview?workspace_id={ws}"),
        ("DELETE", f"/api/v1/presentations/{pid}?workspace_id={ws}"),
        ("POST", "/api/v1/presentations/generate"),
    ]
    for method, path in paths:
        if method == "POST":
            res = await client_as_regular_user.post(
                path,
                json={
                    "workspace_id": ws,
                    "prompt": "Pitch deck",
                    "output_format": "pptx",
                },
            )
        elif method == "DELETE":
            res = await client_as_regular_user.delete(path)
        else:
            res = await client_as_regular_user.get(path)
        assert res.status_code == 403, path
        assert "not enabled" in res.json()["detail"].lower()


@pytest.mark.integration
async def test_cross_workspace_presentation_returns_404(
    client_as_regular_user, db_workspace, db_user, db_session
):
    """AC-5: member of A cannot read B's presentation via workspace_id=A (no existence leak)."""
    other_workspace = Workspace(
        name="Other Space",
        user_id=db_user.id,
    )
    db_session.add(other_workspace)
    await db_session.flush()

    foreign = SlidePresentation(
        workspace_id=other_workspace.id,
        user_id=db_user.id,
        title="Foreign",
        slug="foreign-deck",
        format="pptx",
        status="ready",
    )
    db_session.add(foreign)
    await db_session.flush()

    res = await client_as_regular_user.get(
        f"/api/v1/presentations/{foreign.id}?workspace_id={db_workspace.id}",
    )
    assert res.status_code == 404

    res = await client_as_regular_user.get(
        f"/api/v1/presentations/{foreign.id}/download?workspace_id={db_workspace.id}",
    )
    assert res.status_code == 404


@pytest.mark.integration
async def test_generate_download_presentation(client_as_regular_user, db_workspace):
    """AC-2/AC-5: generate a PPTX and download it for the owner workspace."""
    res = await client_as_regular_user.post(
        "/api/v1/presentations/generate",
        json={
            "workspace_id": db_workspace.id,
            "prompt": "Pitch deck",
            "output_format": "pptx",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    presentation_id = data["presentation_id"]
    assert data.get("file_path") in (None, "")

    res = await client_as_regular_user.get(
        f"/api/v1/presentations/{presentation_id}/download?workspace_id={db_workspace.id}",
    )
    assert res.status_code == 200
    assert res.content[:4] == b"PK\x03\x04"


@pytest.mark.integration
async def test_list_scoped_to_workspace(
    client_as_regular_user, db_workspace, db_user, db_session
):
    """AC-5: list only returns SlidePresentation rows for the requested workspace."""
    other_workspace = Workspace(
        name="Other Space",
        user_id=db_user.id,
    )
    db_session.add(other_workspace)
    await db_session.flush()

    pres1 = SlidePresentation(
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        title="A",
        slug="a",
        format="pptx",
        status="ready",
    )
    pres2 = SlidePresentation(
        workspace_id=other_workspace.id,
        user_id=db_user.id,
        title="B",
        slug="b",
        format="pptx",
        status="ready",
    )
    db_session.add_all([pres1, pres2])
    await db_session.flush()

    res = await client_as_regular_user.get(
        f"/api/v1/presentations?workspace_id={db_workspace.id}",
    )
    assert res.status_code == 200
    data = res.json()
    assert all(p["workspace_id"] == db_workspace.id for p in data)


@pytest.mark.integration
async def test_delete_presentation_204_after_member_check(
    client_as_regular_user, db_workspace
):
    """AC-5: DELETE returns 204 and the row is gone."""
    res = await client_as_regular_user.post(
        "/api/v1/presentations/generate",
        json={
            "workspace_id": db_workspace.id,
            "prompt": "Delete me",
            "output_format": "pptx",
        },
    )
    assert res.status_code == 200
    presentation_id = res.json()["presentation_id"]

    res = await client_as_regular_user.delete(
        f"/api/v1/presentations/{presentation_id}?workspace_id={db_workspace.id}",
    )
    assert res.status_code == 204

    res = await client_as_regular_user.get(
        f"/api/v1/presentations/{presentation_id}?workspace_id={db_workspace.id}",
    )
    assert res.status_code == 404


@pytest.mark.integration
async def test_unique_slug_per_workspace_enforced_by_db(
    db_session, db_workspace, db_user
):
    """AC-4: UniqueConstraint (workspace_id, slug) is enforced by Postgres."""
    first = SlidePresentation(
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        title="One",
        slug="same-slug",
        format="pptx",
        status="ready",
    )
    db_session.add(first)
    await db_session.flush()

    duplicate = SlidePresentation(
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        title="Two",
        slug="same-slug",
        format="pptx",
        status="ready",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
