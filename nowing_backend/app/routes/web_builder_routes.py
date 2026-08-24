"""REST API endpoints for Web Builder (Story 27.1 / AD-113 / AD-114)."""

import contextlib
import logging
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Permission, Workspace, WorkspaceApp, get_async_session
from app.routes.rbac_routes import check_permission
from app.services.web_builder.deploy_service import WebAppDeployService
from app.services.web_builder.generator import WebBuilderService
from app.services.web_builder.preview_renderer import WEB_BUILDER_CSP, PreviewRenderer
from app.services.web_builder.project_writer import ProjectWriter
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
host_router = APIRouter(tags=["web-builder-host"])


async def require_workspace_member(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> AuthContext:
    """Ensure the caller is a member and that Web Builder is enabled."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.WEB_BUILDER_CREATE.value,
        error_message="You don't have access to this workspace",
    )

    # Fail-closed per-workspace feature gate (P2).
    ws = (
        await session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
    ).scalars().first()
    if not ws or ws.web_builder_enabled is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web Builder is not enabled on this workspace plan",
        )
    return auth


def check_web_builder_enabled():
    """Fail-closed gate checking WEB_BUILDER_ENABLED configuration."""
    if not config.WEB_BUILDER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web Builder is not enabled on this workspace plan",
        )


@router.post("/generate", response_model=WebAppBuildOutput)
async def generate_web_app(
    payload: WebAppBuildInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WebAppBuildOutput:
    """Generate Next.js + Tailwind project from a natural-language description (AC-1)."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, payload.workspace_id)
    payload.user_id = auth.user.id
    service = WebBuilderService()
    result = await service.generate_project(payload, session=session)
    return result


@router.post("/generate/stream")
async def generate_web_app_stream(
    payload: WebAppBuildInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Stream real-time Next.js code generation tokens and file writing steps via SSE."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, payload.workspace_id)
    payload.user_id = auth.user.id
    service = WebBuilderService()
    return StreamingResponse(
        service.generate_project_stream(payload, session=session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/apps/{app_id}/publish", response_model=WebAppDeployOutput)
async def publish_web_app(
    app_id: str,
    payload: WebAppDeployInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.message or "Deployment failed",
        )
    return result


async def configure_custom_domain(
    app_id: str,
    payload: CustomDomainInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CustomDomainOutput:
    """Custom CNAME binding is out of scope for Story 27.1a (P27)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Custom domain CNAME binding is not available in this version",
    )


async def apply_mark_tool_patch(
    app_id: str,
    payload: MarkToolInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> MarkToolOutput:
    """AST mutation from the Mark Tool is out of scope for Story 27.1a (P26)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Mark Tool AST mutation is not available in this version",
    )


@router.get("/apps", response_model=list[WorkspaceAppRead])
async def list_workspace_apps(
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
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


@router.get("/apps/{app_id}/preview", response_class=HTMLResponse)
async def get_workspace_app_preview(
    app_id: str,
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> HTMLResponse:
    """Render and serve interactive live HTML preview for the generated web app."""
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

    from app.config import FILE_STORAGE_LOCAL_PATH

    if not app_entity.storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application source files not found",
        )

    project_dir = Path(app_entity.storage_path)
    if not project_dir.is_absolute():
        project_dir = (
            Path(FILE_STORAGE_LOCAL_PATH).resolve()
            / "web-app"
            / str(app_entity.workspace_id)
            / app_id
        )

    if not project_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application source files not found",
        )

    html_content = PreviewRenderer.render_app_html(
        project_dir=project_dir,
        app_name=app_entity.name if app_entity else "Generated Web App",
    )
    return HTMLResponse(
        content=html_content,
        status_code=status.HTTP_200_OK,
        headers={
            "Content-Security-Policy": WEB_BUILDER_CSP,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/apps/{app_id}/files")
async def get_workspace_app_files(
    app_id: str,
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, str]:
    """Retrieve all generated source code files for a given application."""
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

    from app.config import FILE_STORAGE_LOCAL_PATH

    if app_entity and app_entity.storage_path:
        project_dir = Path(app_entity.storage_path)
        if not project_dir.is_absolute():
            project_dir = (
                Path(FILE_STORAGE_LOCAL_PATH).resolve()
                / "web-app"
                / str(workspace_id)
                / app_id
            )
    else:
        project_dir = (
            Path(FILE_STORAGE_LOCAL_PATH).resolve()
            / "web-app"
            / str(workspace_id)
            / app_id
        )

    if not project_dir.exists():
        project_dir.mkdir(parents=True, exist_ok=True)
        ProjectWriter.write_minimal_nextjs_scaffold(
            project_dir, app_entity.name if app_entity else "Generated App"
        )

    files_dict: dict[str, str] = {}
    for file_path in project_dir.rglob("*"):
        if (
            file_path.is_file()
            and "node_modules" not in file_path.parts
            and ".next" not in file_path.parts
        ):
            rel_path = str(file_path.relative_to(project_dir))
            with contextlib.suppress(Exception):
                files_dict[rel_path] = file_path.read_text(encoding="utf-8")

    return files_dict


async def host_web_app(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> HTMLResponse:
    """Serve published web app static HTML by Host header (Story 27.1a AC-4 / AC-6a)."""
    if not config.WEB_BUILDER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web Builder is not enabled",
        )

    host_header = request.headers.get("Host", "")
    if not host_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Host header",
        )

    host_clean = host_header.split(":")[0].strip().lower()
    base_domain = config.HOSTING_BASE_DOMAIN.lower()
    if not base_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hosting base domain is not configured",
        )

    if not host_clean.endswith(f".{base_domain}"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed host domain",
        )

    parts = host_clean.split(".")
    base_parts = base_domain.split(".")
    if len(parts) != len(base_parts) + 1 or not parts[0]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed host domain",
        )

    slug = parts[0]
    if not re.match(r"^[a-z0-9-]+$", slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid host slug",
        )

    stmt = select(WorkspaceApp).where(
        WorkspaceApp.slug == slug,
        WorkspaceApp.status == "published",
    )
    res = await session.execute(stmt)
    app_entity = res.scalars().first()
    if not app_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Web application not found",
        )

    ws_stmt = select(Workspace).where(Workspace.id == app_entity.workspace_id)
    ws_res = await session.execute(ws_stmt)
    ws = ws_res.scalars().first()
    if ws and ws.web_builder_enabled is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web Builder is disabled for this workspace",
        )

    public_apps_base = Path(config.WEB_BUILDER_PUBLIC_APPS_PATH).resolve()
    snapshot_file = public_apps_base / slug / "index.html"
    if not snapshot_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application static snapshot not found",
        )

    html_content = snapshot_file.read_text(encoding="utf-8")
    return HTMLResponse(
        content=html_content,
        status_code=status.HTTP_200_OK,
        headers={
            "Content-Security-Policy": WEB_BUILDER_CSP,
            "X-Content-Type-Options": "nosniff",
        },
    )
