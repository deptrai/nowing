"""REST API endpoints for Web Builder (Story 27.1 / AD-113 / AD-114)."""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import WorkspaceApp, get_async_session
from app.services.web_builder.deploy_service import WebAppDeployService
from app.services.web_builder.generator import WebBuilderService
from app.services.web_builder.mark_tool import MarkToolASTMutator
from app.services.web_builder.schemas import (
    CustomDomainInput,
    CustomDomainOutput,
    MarkToolInput,
    MarkToolOutput,
    WebAppBuildInput,
    WebAppBuildOutput,
    WebAppDeployInput,
    WebAppDeployOutput,
    WorkspaceAppRead,
)
from app.users import get_auth_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/web-builder", tags=["web-builder"])


@router.post("/generate", response_model=WebAppBuildOutput)
async def generate_web_app(
    payload: WebAppBuildInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WebAppBuildOutput:
    """Generate Next.js + Tailwind project from a natural-language description (AC-1)."""
    payload.user_id = auth.user.id
    service = WebBuilderService()
    result = await service.generate_project(payload, session=session)
    return result


@router.post("/apps/{app_id}/publish", response_model=WebAppDeployOutput)
async def publish_web_app(
    app_id: str,
    payload: WebAppDeployInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WebAppDeployOutput:
    """1-Click publish app container and dynamic HTTPS route at *.apps.nowing.net (AC-2)."""
    deploy_service = WebAppDeployService()
    result = await deploy_service.deploy_app(
        app_id=app_id,
        workspace_id=payload.workspace_id,
        slug_override=payload.slug,
        session=session,
    )
    if result.status == "deploy_failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.message or "Deployment failed",
        )
    return result


@router.post("/apps/{app_id}/custom-domain", response_model=CustomDomainOutput)
async def configure_custom_domain(
    app_id: str,
    payload: CustomDomainInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CustomDomainOutput:
    """Configure and verify custom domain CNAME routing (AC-3)."""
    deploy_service = WebAppDeployService()
    result = await deploy_service.verify_and_bind_custom_domain(
        app_id=app_id,
        workspace_id=payload.workspace_id,
        custom_domain=payload.custom_domain,
        session=session,
    )
    if result.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.message,
        )
    return result


@router.post("/apps/{app_id}/mark", response_model=MarkToolOutput)
async def apply_mark_tool_patch(
    app_id: str,
    payload: MarkToolInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> MarkToolOutput:
    """Apply visual Mark Tool DOM-to-JSX AST mutation to component code (AC-4)."""
    stmt = select(WorkspaceApp).where(
        WorkspaceApp.id == app_id,
        WorkspaceApp.workspace_id == payload.workspace_id,
    )
    res = await session.execute(stmt)
    app_entity = res.scalars().first()

    if not app_entity or not app_entity.storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found in workspace",
        )

    project_dir = Path(app_entity.storage_path)
    target_file = (project_dir / payload.file_path).resolve()

    # Safety boundary check
    try:
        target_file.relative_to(project_dir)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path inside project",
        ) from err

    if not target_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component file not found: {payload.file_path}",
        )

    jsx_code = target_file.read_text(encoding="utf-8")
    mutator = MarkToolASTMutator()
    result = mutator.apply_patch(
        jsx_code=jsx_code,
        selector=payload.selector,
        patch=payload.patch.model_dump(),
    )

    if result.status == "patched":
        target_file.write_text(result.patched_code, encoding="utf-8")

    return MarkToolOutput(
        app_id=app_id,
        workspace_id=payload.workspace_id,
        status=result.status,
        file_path=payload.file_path,
        patched_code=result.patched_code if result.status == "patched" else None,
        message=result.message,
    )


@router.get("/apps", response_model=list[WorkspaceAppRead])
async def list_workspace_apps(
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[WorkspaceAppRead]:
    """List all generated and published applications for a workspace (AC-5)."""
    stmt = (
        select(WorkspaceApp)
        .where(WorkspaceApp.workspace_id == workspace_id)
        .order_by(WorkspaceApp.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/apps/{app_id}", response_model=WorkspaceAppRead)
async def get_workspace_app(
    app_id: str,
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WorkspaceAppRead:
    """Get single application details."""
    stmt = select(WorkspaceApp).where(
        WorkspaceApp.id == app_id,
        WorkspaceApp.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    app_entity = result.scalars().first()
    if not app_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return app_entity
