"""REST API endpoints for Web Builder (Story 27.1 / Story 27.1b / AD-113 / AD-113a / AD-114)."""

import logging
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Workspace, WorkspaceApp, get_async_session
from app.services.web_builder.preview_renderer import WEB_BUILDER_CSP

logger = logging.getLogger(__name__)


host_router = APIRouter(tags=["web-builder-host"])


@host_router.get("/", response_class=HTMLResponse)
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

    if host_clean.endswith(f".{base_domain}"):
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
    else:
        # Custom domain lookup
        stmt = select(WorkspaceApp).where(
            WorkspaceApp.custom_domain == host_clean,
            WorkspaceApp.custom_domain_status == "active",
            WorkspaceApp.status == "published",
        )
    res = await session.execute(stmt)
    app_entity = res.scalars().first()
    if not app_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Web application not found",
        )
    slug = app_entity.slug

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


@host_router.get("/_next/static/{path:path}")
async def host_web_app_static(
    request: Request,
    path: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Serve Next.js static assets for a published web app by Host header (D1)."""
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

    if host_clean.endswith(f".{base_domain}"):
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
    else:
        # Custom domain lookup
        stmt = select(WorkspaceApp).where(
            WorkspaceApp.custom_domain == host_clean,
            WorkspaceApp.custom_domain_status == "active",
            WorkspaceApp.status == "published",
        )
    res = await session.execute(stmt)
    app_entity = res.scalars().first()
    if not app_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Web application not found",
        )
    slug = app_entity.slug

    ws_stmt = select(Workspace).where(Workspace.id == app_entity.workspace_id)
    ws_res = await session.execute(ws_stmt)
    ws = ws_res.scalars().first()
    if ws and ws.web_builder_enabled is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web Builder is disabled for this workspace",
        )

    if not app_entity.storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application source files not found",
        )

    project_dir = Path(app_entity.storage_path).resolve()
    for static_dir in (
        project_dir / ".next" / "standalone" / ".next" / "static",
        project_dir / ".next" / "static",
    ):
        if not static_dir.exists() or not static_dir.is_dir():
            continue
        asset = (static_dir / path).resolve()
        if (
            asset.is_relative_to(static_dir)
            and asset.exists()
            and asset.is_file()
            and not asset.is_symlink()
        ):
            return FileResponse(asset)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Static asset not found",
    )
