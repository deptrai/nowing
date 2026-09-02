"""Routes for Modular Skills Hub (CRUD, parse .skill.md upload, execution)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import WorkspaceSkill, get_async_session
from app.schemas.skills_schemas import (
    SkillCreate,
    SkillExecuteRequest,
    SkillParseRequest,
    SkillParseResponse,
    SkillRead,
    SkillUpdate,
)
from app.services.skill_execution_service import SkillExecutionService
from app.services.skill_parser import SkillParseError, SkillParser
from app.users import get_auth_context
from app.utils.rbac import Permission, check_permission

router = APIRouter(tags=["skills"])


@router.post(
    "/workspaces/{workspace_id}/skills/parse",
    response_model=SkillParseResponse,
    status_code=status.HTTP_200_OK,
)
async def parse_skill_file(
    workspace_id: int,
    payload: SkillParseRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SkillParseResponse:
    """Parse raw .skill.md file content and return extracted metadata and markdown body."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SKILLS_READ.value,
        "You don't have permission to parse skills in this workspace",
    )

    try:
        parsed = SkillParser.parse(payload.file_content)
    except SkillParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    return SkillParseResponse(
        name=parsed.name,
        slug=parsed.slug,
        description=parsed.description,
        trigger_pattern=parsed.trigger_pattern,
        skill_type=parsed.skill_type,
        parameters_schema=parsed.parameters_schema,
        content_markdown=parsed.content_markdown,
    )


@router.get(
    "/workspaces/{workspace_id}/skills",
    response_model=list[SkillRead],
    status_code=status.HTTP_200_OK,
)
async def list_skills(
    workspace_id: int,
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[SkillRead]:
    """List skills configured in a workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SKILLS_READ.value,
        "You don't have permission to view skills in this workspace",
    )

    stmt = select(WorkspaceSkill).where(WorkspaceSkill.workspace_id == workspace_id)
    if not include_inactive:
        stmt = stmt.where(WorkspaceSkill.is_active.is_(True))

    stmt = stmt.order_by(WorkspaceSkill.updated_at.desc()).offset(offset).limit(limit)
    res = await session.execute(stmt)
    skills = res.scalars().all()

    return [SkillRead.model_validate(s) for s in skills]


@router.post(
    "/workspaces/{workspace_id}/skills",
    response_model=SkillRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_skill(
    workspace_id: int,
    payload: SkillCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SkillRead:
    """Create a new skill in the workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SKILLS_CREATE.value,
        "You don't have permission to create skills in this workspace",
    )

    # Check for duplicate slug in workspace
    existing_stmt = select(WorkspaceSkill).where(
        WorkspaceSkill.workspace_id == workspace_id,
        WorkspaceSkill.slug == payload.slug,
    )
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Skill with slug '{payload.slug}' already exists in this workspace",
        )

    now = datetime.now(UTC)
    skill = WorkspaceSkill(
        workspace_id=workspace_id,
        created_by_id=auth.user.id if auth.user else None,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        trigger_pattern=payload.trigger_pattern,
        content_markdown=payload.content_markdown,
        skill_type=payload.skill_type,
        parameters_schema=payload.parameters_schema,
        is_active=payload.is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)

    return SkillRead.model_validate(skill)


@router.get(
    "/workspaces/{workspace_id}/skills/{skill_id}",
    response_model=SkillRead,
    status_code=status.HTTP_200_OK,
)
async def get_skill(
    workspace_id: int,
    skill_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SkillRead:
    """Get a specific skill by ID."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SKILLS_READ.value,
        "You don't have permission to view skills in this workspace",
    )

    skill = await session.get(WorkspaceSkill, skill_id)
    if not skill or skill.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found in workspace {workspace_id}",
        )

    return SkillRead.model_validate(skill)


@router.patch(
    "/workspaces/{workspace_id}/skills/{skill_id}",
    response_model=SkillRead,
    status_code=status.HTTP_200_OK,
)
async def update_skill(
    workspace_id: int,
    skill_id: int,
    payload: SkillUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SkillRead:
    """Update a skill in the workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SKILLS_UPDATE.value,
        "You don't have permission to update skills in this workspace",
    )

    skill = await session.get(WorkspaceSkill, skill_id)
    if not skill or skill.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found in workspace {workspace_id}",
        )

    if payload.slug is not None and payload.slug != skill.slug:
        existing_stmt = select(WorkspaceSkill).where(
            WorkspaceSkill.workspace_id == workspace_id,
            WorkspaceSkill.slug == payload.slug,
            WorkspaceSkill.id != skill_id,
        )
        existing = (await session.execute(existing_stmt)).scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Skill with slug '{payload.slug}' already exists in this workspace",
            )
        skill.slug = payload.slug

    if payload.name is not None:
        skill.name = payload.name
    if payload.description is not None:
        skill.description = payload.description
    if payload.trigger_pattern is not None:
        skill.trigger_pattern = payload.trigger_pattern
    if payload.content_markdown is not None:
        skill.content_markdown = payload.content_markdown
    if payload.skill_type is not None:
        skill.skill_type = payload.skill_type
    if payload.parameters_schema is not None:
        skill.parameters_schema = payload.parameters_schema
    if payload.is_active is not None:
        skill.is_active = payload.is_active

    skill.updated_at = datetime.now(UTC)
    session.add(skill)
    await session.commit()
    await session.refresh(skill)

    return SkillRead.model_validate(skill)


@router.delete(
    "/workspaces/{workspace_id}/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_skill(
    workspace_id: int,
    skill_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete a skill from the workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SKILLS_DELETE.value,
        "You don't have permission to delete skills in this workspace",
    )

    skill = await session.get(WorkspaceSkill, skill_id)
    if not skill or skill.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found in workspace {workspace_id}",
        )

    await session.delete(skill)
    await session.commit()


@router.post(
    "/workspaces/{workspace_id}/skills/{skill_id}/execute",
    status_code=status.HTTP_200_OK,
)
async def execute_skill(
    workspace_id: int,
    skill_id: int,
    payload: SkillExecuteRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    """Execute a skill (renders prompt or dispatches workflow mission)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SKILLS_EXECUTE.value,
        "You don't have permission to execute skills in this workspace",
    )

    skill = await session.get(WorkspaceSkill, skill_id)
    if not skill or skill.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found in workspace {workspace_id}",
        )

    if not skill.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill {skill_id} is inactive",
        )

    service = SkillExecutionService()
    result = await service.execute(
        session=session,
        skill=skill,
        workspace_id=workspace_id,
        user_id=auth.user.id if auth.user else None,
        parameters=payload.parameters,
    )
    return result
