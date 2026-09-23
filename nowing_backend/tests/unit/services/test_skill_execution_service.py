"""Unit tests for SkillExecutionService (Story 3.18 AC-5)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import DshMission, DshMissionStatus, WorkspaceSkill
from app.services.dsh_mission_service import DshMissionService
from app.services.skill_execution_service import SkillExecutionService

pytestmark = pytest.mark.unit


def _make_skill(
    *,
    skill_type: str = "prompt",
    content_markdown: str = "Summarize {{topic}}.",
    slug: str = "summarize",
) -> WorkspaceSkill:
    skill = MagicMock(spec=WorkspaceSkill)
    skill.id = 1
    skill.slug = slug
    skill.skill_type = skill_type
    skill.content_markdown = content_markdown
    skill.is_active = True
    return skill


@pytest.mark.asyncio
async def test_execute_prompt_skill_replaces_placeholders() -> None:
    """Prompt skill should render {{key}} placeholders with escaped values."""
    session = AsyncMock(spec=AsyncSession)
    skill = _make_skill(
        content_markdown="Analyze {{topic}} for {{location}}.",
        slug="market-analysis",
    )
    service = SkillExecutionService()

    result = await service.execute(
        session=session,
        skill=skill,
        workspace_id=42,
        user_id=uuid4(),
        parameters={"topic": "real estate", "location": "District 2"},
    )

    assert result["type"] == "prompt"
    assert result["skill_id"] == skill.id
    assert result["skill_slug"] == "market-analysis"
    assert "Analyze real estate for District 2" in result["content"]


@pytest.mark.asyncio
async def test_execute_prompt_skill_keeps_unset_placeholder() -> None:
    """Missing parameter should leave the placeholder intact."""
    session = AsyncMock(spec=AsyncSession)
    skill = _make_skill(content_markdown="Summarize {{topic}}.")
    service = SkillExecutionService()

    result = await service.execute(
        session=session,
        skill=skill,
        workspace_id=42,
        user_id=None,
        parameters={},
    )

    assert result["type"] == "prompt"
    assert "{{topic}}" in result["content"]


@pytest.mark.asyncio
async def test_execute_prompt_skill_prevents_recursive_template_injection() -> None:
    """Parameter values containing {{...}} must be escaped to avoid recursion."""
    session = AsyncMock(spec=AsyncSession)
    skill = _make_skill(content_markdown="Value is {{payload}}.")
    service = SkillExecutionService()

    result = await service.execute(
        session=session,
        skill=skill,
        workspace_id=42,
        user_id=None,
        parameters={"payload": "{{injection}}"},
    )

    assert "[[injection]]" in result["content"]
    assert "{{injection}}" not in result["content"]


@pytest.mark.asyncio
async def test_execute_workflow_skill_dispatches_dsh_mission() -> None:
    """Workflow skill should create a DSH mission with skill payload."""
    session = AsyncMock(spec=AsyncSession)
    dsh_service = AsyncMock(spec=DshMissionService)
    mission = MagicMock(spec=DshMission)
    mission.id = uuid4()
    mission.status = DshMissionStatus.PENDING
    dsh_service.create_mission.return_value = mission

    skill = _make_skill(skill_type="workflow", slug="scrape-leads")
    service = SkillExecutionService(dsh_service=dsh_service)

    result = await service.execute(
        session=session,
        skill=skill,
        workspace_id=42,
        user_id=uuid4(),
        parameters={"competitor": "VinGroup"},
    )

    assert result["type"] == "workflow"
    assert result["skill_id"] == skill.id
    assert result["skill_slug"] == "scrape-leads"
    assert result["mission_id"] == str(mission.id)
    assert result["status"] == DshMissionStatus.PENDING.value

    dsh_service.create_mission.assert_awaited_once()
    call_kwargs = dsh_service.create_mission.await_args.kwargs
    assert call_kwargs["mission_type"] == "skill"
    assert call_kwargs["payload"]["skill_id"] == skill.id
    assert call_kwargs["payload"]["skill_slug"] == "scrape-leads"
    assert call_kwargs["payload"]["parameters"]["competitor"] == "VinGroup"
    assert call_kwargs["workspace_id"] == 42


@pytest.mark.asyncio
async def test_execute_workflow_skill_without_user_id() -> None:
    """Workflow dispatch should allow anonymous/system execution."""
    session = AsyncMock(spec=AsyncSession)
    dsh_service = AsyncMock(spec=DshMissionService)
    mission = MagicMock(spec=DshMission)
    mission.id = uuid4()
    mission.status = DshMissionStatus.PENDING
    dsh_service.create_mission.return_value = mission

    skill = _make_skill(skill_type="workflow", slug="auto-report")
    service = SkillExecutionService(dsh_service=dsh_service)

    result = await service.execute(
        session=session,
        skill=skill,
        workspace_id=7,
        user_id=None,
        parameters={},
    )

    assert result["type"] == "workflow"
    assert result["skill_id"] == skill.id
    assert result["skill_slug"] == "auto-report"
    assert result["mission_id"] == str(mission.id)

    call_kwargs = dsh_service.create_mission.await_args.kwargs
    assert call_kwargs["user_id"] is None
    assert call_kwargs["workspace_id"] == 7


@pytest.mark.asyncio
async def test_execute_default_parameters_empty() -> None:
    """Service should treat None parameters as empty dict."""
    session = AsyncMock(spec=AsyncSession)
    skill = _make_skill(content_markdown="Hello.")
    service = SkillExecutionService()

    result = await service.execute(
        session=session,
        skill=skill,
        workspace_id=1,
        user_id=None,
        parameters=None,
    )

    assert result["type"] == "prompt"
    assert result["content"] == "Hello."
