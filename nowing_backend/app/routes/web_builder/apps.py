"""REST API endpoints for Web Builder (Story 27.1 / Story 27.1b / AD-113 / AD-113a / AD-114)."""

import asyncio
import contextlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import (
    JSONResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, WorkspaceApp, WorkspaceMembership, get_async_session
from app.dependencies.auth import (
    RequirePermission,
    RequirePermissionFromBody,
)
from app.services.token_tracking_service import UsageType, record_token_usage
from app.services.web_builder.builder import BuilderService
from app.services.web_builder.deploy_service import WebAppDeployService
from app.services.web_builder.mark_tool import JSX_FILE_SUFFIXES, MarkToolASTMutator
from app.services.web_builder.schemas import (
    BuildLogsOutput,
    BuildProjectInput,
    CustomDomainInput,
    CustomDomainOutput,
    MarkToolInput,
    MarkToolOutput,
    WebAppDeployInput,
    WebAppDeployOutput,
    WorkspaceAppRead,
)
from app.users import get_auth_context

from ._helpers import (
    _is_valid_fqdn,
    check_web_builder_enabled,
    require_workspace_member,
)
from .preview import _resolve_and_validate_project_dir

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/apps/{app_id}/publish", response_model=WebAppDeployOutput)
async def publish_web_app(
    app_id: str,
    payload: WebAppDeployInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    _membership: WorkspaceMembership = Depends(
        RequirePermissionFromBody(
            Permission.WEB_BUILDER_CREATE.value,
            "You don't have access to this workspace",
        )
    ),
) -> WebAppDeployOutput:
    """1-Click publish app container and dynamic HTTPS route at *.apps.nowing.net (AC-2)."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, payload.workspace_id)
    stmt = select(WorkspaceApp).where(
        WorkspaceApp.id == app_id,
        WorkspaceApp.workspace_id == payload.workspace_id,
    )
    res = await session.execute(stmt)
    if not res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    deploy_service = WebAppDeployService()
    result = await deploy_service.deploy_app(
        app_id=app_id,
        workspace_id=payload.workspace_id,
        slug_override=payload.slug,
        session=session,
    )
    if result.status == "deploy_failed":
        # Feature-gate / permission failures must surface as 403, not 422.
        if result.message and (
            "Web Builder is not enabled" in result.message
            or "workspace plan" in result.message
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.message,
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.message or "Deployment failed",
        )
    return result


@router.post("/apps/{app_id}/build")
async def trigger_build_web_app(
    app_id: str,
    payload: BuildProjectInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    _membership: WorkspaceMembership = Depends(
        RequirePermissionFromBody(
            Permission.WEB_BUILDER_CREATE.value,
            "You don't have access to this workspace",
        )
    ),
):
    """Trigger Next.js build compilation for an application (Story 27.1b AC-2)."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, payload.workspace_id)
    stmt = select(WorkspaceApp).where(
        WorkspaceApp.id == app_id,
        WorkspaceApp.workspace_id == payload.workspace_id,
    )
    res = await session.execute(stmt)
    app_entity = res.scalars().first()
    if not app_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # The async worker handles status, quota debit, and duplicate-guard (R-02).
    await BuilderService.trigger_async_build(app_id, payload.workspace_id)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "building",
            "app_id": app_id,
            "message": "Build started",
            "build_log_url": f"/api/v1/web-builder/apps/{app_id}/build-logs?workspace_id={payload.workspace_id}",
        },
    )


@router.get("/apps/{app_id}/build-logs", response_model=BuildLogsOutput)
async def get_web_app_build_logs(
    app_id: str,
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.WEB_BUILDER_CREATE.value,
            "You don't have access to this workspace",
        )
    ),
) -> BuildLogsOutput:
    """Retrieve build stdout/stderr logs for an application (Story 27.1b AC-5)."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, workspace_id)
    stmt = select(WorkspaceApp).where(
        WorkspaceApp.id == app_id,
        WorkspaceApp.workspace_id == workspace_id,
    )
    res = await session.execute(stmt)
    app_entity = res.scalars().first()
    if not app_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    logs_text, line_count = await BuilderService.get_build_logs(
        app_id, workspace_id, storage_path=app_entity.storage_path
    )
    return BuildLogsOutput(
        app_id=app_id,
        workspace_id=workspace_id,
        logs=logs_text,
        lines=line_count,
        status=app_entity.status,
    )


@router.post("/apps/{app_id}/custom-domain", response_model=CustomDomainOutput)
async def configure_custom_domain(
    app_id: str,
    payload: CustomDomainInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    _membership: WorkspaceMembership = Depends(
        RequirePermissionFromBody(
            Permission.WEB_BUILDER_CREATE.value,
            "You don't have access to this workspace",
        )
    ),
) -> CustomDomainOutput:
    """Bind a custom CNAME domain to a published web application (Story 27.1c handoff)."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, payload.workspace_id)
    if not _is_valid_fqdn(payload.custom_domain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid custom domain. Provide a valid FQDN (e.g. app.mycompany.com).",
        )
    deploy_service = WebAppDeployService()
    result = await deploy_service.verify_and_bind_custom_domain(
        app_id=app_id,
        workspace_id=payload.workspace_id,
        custom_domain=payload.custom_domain,
        session=session,
    )
    if result.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.message or "Custom domain configuration failed",
        )
    return result


@router.post("/apps/{app_id}/mark", response_model=MarkToolOutput)
async def apply_mark_tool_patch(
    app_id: str,
    payload: MarkToolInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    _membership: WorkspaceMembership = Depends(
        RequirePermissionFromBody(
            Permission.WEB_BUILDER_CREATE.value,
            "You don't have access to this workspace",
        )
    ),
) -> MarkToolOutput:
    """Apply a visual Mark Tool patch to a JSX/TSX source file and rebuild the preview (AC-2 / AC-4)."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, payload.workspace_id)

    stmt = select(WorkspaceApp).where(
        WorkspaceApp.id == app_id,
        WorkspaceApp.workspace_id == payload.workspace_id,
    )
    res = await session.execute(stmt)
    app_entity = res.scalars().first()
    if not app_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    project_dir = _resolve_and_validate_project_dir(
        app_entity, app_id, payload.workspace_id
    )
    file_path = payload.file_path or "app/page.tsx"
    target_file = (project_dir / file_path).resolve()
    if (
        not target_file.is_relative_to(project_dir)
        or not target_file.exists()
        or not target_file.is_file()
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target component file not found",
        )
    if target_file.suffix.lower() not in JSX_FILE_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Target file must be a .tsx or .jsx component",
        )

    try:
        jsx_code = await asyncio.to_thread(target_file.read_text, encoding="utf-8")
    except Exception as exc:  # local file read failure → surface as typed HTTP error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read target file: {exc}",
        ) from exc

    mutator = MarkToolASTMutator()
    patch_dict = (
        payload.patch.model_dump()
        if hasattr(payload.patch, "model_dump")
        else dict(payload.patch)
    )
    result = mutator.apply_patch(
        jsx_code=jsx_code,
        selector=payload.selector,
        patch=patch_dict,
    )

    if result.status == "patched":
        try:
            await asyncio.to_thread(
                target_file.write_text, result.patched_code, encoding="utf-8"
            )
        except Exception as exc:  # local file write failure → surface as typed HTTP error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not write target file: {exc}",
            ) from exc

    # Record usage for every mark attempt, including unresolvable ones (NFR-3).
    # Patched attempts are recorded only after the file write succeeds.
    try:
        call_details = {
            "app_id": app_id,
            "selector": payload.selector,
            "patch_type": patch_dict.get("type"),
            "file_path": file_path,
            "rect": payload.rect.model_dump() if payload.rect else None,
            "component_hint": payload.component_hint,
            "status": result.status,
        }
        await record_token_usage(
            session=session,
            usage_type=UsageType.WEB_BUILDER_MARK,
            workspace_id=payload.workspace_id,
            user_id=auth.user.id,
            cost_micros=0,
            call_details=call_details,
        )
        await session.commit()
    except Exception:  # best-effort token usage tracking; failure doesn't fail primary op
        logger.exception("Failed to record web_builder_mark token usage")
        with contextlib.suppress(Exception):
            await session.rollback()

    if result.status == "patched":
        # Force a free rebuild so preview_ready apps recompile mutated source.
        await BuilderService.trigger_async_build(
            app_id, payload.workspace_id, force=True, skip_debit=True
        )

    return MarkToolOutput(
        app_id=app_id,
        workspace_id=payload.workspace_id,
        status=result.status,
        file_path=file_path,
        patched_code=result.patched_code if result.status == "patched" else None,
        message=result.message,
    )


@router.get("/apps", response_model=list[WorkspaceAppRead])
async def list_workspace_apps(
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.WEB_BUILDER_CREATE.value,
            "You don't have access to this workspace",
        )
    ),
) -> list[WorkspaceAppRead]:
    """List all generated and published applications for a workspace (AC-5)."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, workspace_id)
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
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.WEB_BUILDER_CREATE.value,
            "You don't have access to this workspace",
        )
    ),
) -> WorkspaceAppRead:
    """Get single application details."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, workspace_id)
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
