"""REST API endpoints for Web Builder (Story 27.1 / Story 27.1b / AD-113 / AD-113a / AD-114)."""

import asyncio
import contextlib
import html
import logging
import mimetypes
import re
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Permission, Workspace, WorkspaceApp, get_async_session
from app.routes.rbac_routes import check_permission
from app.services.token_tracking_service import UsageType, record_token_usage
from app.services.web_builder.builder import BuilderService
from app.services.web_builder.deploy_service import WebAppDeployService
from app.services.web_builder.generator import WebBuilderService
from app.services.web_builder.mark_tool import JSX_FILE_SUFFIXES, MarkToolASTMutator
from app.services.web_builder.preview_renderer import WEB_BUILDER_CSP, PreviewRenderer
from app.services.web_builder.project_writer import ProjectWriter
from app.services.web_builder.schemas import (
    BuildLogsOutput,
    BuildProjectInput,
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


def is_web_builder_enabled_for_workspace(ws: Workspace | None) -> bool:
    """Check both global and workspace-level Web Builder feature flags."""
    if not config.WEB_BUILDER_ENABLED:
        return False
    return not (ws and ws.web_builder_enabled is False)


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

    # Fail-closed per-workspace feature gate (AC-4 / P2).
    ws = (
        (await session.execute(select(Workspace).where(Workspace.id == workspace_id)))
        .scalars()
        .first()
    )
    if not is_web_builder_enabled_for_workspace(ws):
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


async def _get_workspace_for_build(
    session: AsyncSession, workspace_id: int
) -> Workspace:
    """Fetch workspace or raise 404; used by build quota gate."""
    ws = (
        (await session.execute(select(Workspace).where(Workspace.id == workspace_id)))
        .scalars()
        .first()
    )
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return ws


async def require_build_quota(
    session: AsyncSession,
    auth: AuthContext | None = None,
    workspace_id: int = 0,
) -> Workspace:
    """Fail-closed build quota gate using plan tier and workspace credit balance.

    Debits the build cost immediately when the workspace has sufficient credit.
    """
    ws = await _get_workspace_for_build(session, workspace_id)
    cost = config.WEB_BUILDER_BUILD_COST_MICROS
    if cost <= 0:
        return ws
    if ws.credit_micros_balance < cost:
        detail = (
            "Insufficient workspace credit balance for build. "
            f"Required: {cost} micros, "
            f"available: {ws.credit_micros_balance} micros."
        )
        if ws.plan_tier == "free":
            detail += " Upgrade your workspace plan to continue building."
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail)
    ws.credit_micros_balance -= cost
    await session.commit()
    return ws


def _is_valid_fqdn(domain: str) -> bool:
    """Validate a fully-qualified domain name (no IPs, no localhost, valid labels)."""
    clean = domain.strip().lower()
    if not clean or len(clean) > 255:
        return False
    # Reject raw IP addresses
    if re.match(r"^\d+\.\d+\.\d+\.\d+$|^\[[0-9a-f:]+\]$", clean):
        return False
    # Reject localhost / local suffixes
    if clean == "localhost" or clean.endswith(".local") or clean.endswith(".localhost"):
        return False
    # Must contain at least one dot and end in a TLD of >=2 letters
    if not re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$", clean):
        return False
    for label in clean.split("."):
        if not label or label.startswith("-") or label.endswith("-"):
            return False
        if len(label) > 63:
            return False
    return True


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
    if result.status == "generated":
        # The async worker handles status, quota debit, and duplicate-guard (R-02).
        await BuilderService.trigger_async_build(result.app_id, payload.workspace_id)
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
    except Exception as exc:
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
        except Exception as exc:
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
    except Exception:
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


def _resolve_and_validate_project_dir(
    app_entity: WorkspaceApp,
    app_id: str,
    workspace_id: int,
) -> Path:
    """Resolve storage_path and ensure it points to the expected app-scoped workspace directory.

    Allows tests and deployments that use a temporary or configured root, as long as
    the resolved path ends with ``web-app/{workspace_id}/{app_id}`` and is not a symlink.
    """
    from app.config import config

    base_path = Path(config.FILE_STORAGE_LOCAL_PATH).resolve()
    expected_scoped_dir = (base_path / "web-app" / str(workspace_id) / app_id).resolve()
    expected_suffix = Path("web-app") / str(workspace_id) / app_id

    if app_entity and app_entity.storage_path:
        project_dir = Path(app_entity.storage_path)
    else:
        project_dir = expected_scoped_dir

    # Reject paths containing parent references before resolving
    if ".." in project_dir.parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid application storage path",
        )

    try:
        resolved_dir = project_dir.resolve()
    except (OSError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid application storage path: {e}",
        ) from e

    suffix_ok = (
        resolved_dir.parts[-len(expected_suffix.parts) :] == expected_suffix.parts
    )
    if not resolved_dir.is_relative_to(expected_scoped_dir) and not suffix_ok:
        logger.error(
            "Security violation: preview/files path traversal. target=%s, expected=%s",
            resolved_dir,
            expected_scoped_dir,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid application storage path",
        )

    if not resolved_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application source files not found",
        )
    return resolved_dir


def _rewrite_next_static_paths(html_content: str) -> str:
    """Make Next.js static asset references relative so they hit the app-scoped _next/static route."""
    # Rewrite both ./_next/static/ and /_next/static/ (after a quote) to _next/static/.
    html_content = re.sub(
        r'(["\'])(?:\./|/)_next/static/',
        r"\1_next/static/",
        html_content,
    )
    # Preserve an optional quote inside CSS url(...).
    html_content = re.sub(
        r'url\((["\']?)/_next/static/',
        r"url(\1_next/static/",
        html_content,
        flags=re.IGNORECASE,
    )
    return html_content


def _build_status_html(
    status: str,
    app_id: str,
    workspace_id: int,
    message: str | None = None,
    meta_refresh: bool = False,
) -> str:
    """Return a small HTML page for building/build_failed/generated preview states."""
    build_log_url = (
        f"/api/v1/web-builder/apps/{app_id}/build-logs?workspace_id={workspace_id}"
    )
    refresh_tag = '<meta http-equiv="refresh" content="5" />' if meta_refresh else ""
    safe_status = html.escape(status.replace("_", " ").title())
    safe_message = html.escape(message or "Your web application is being prepared.")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
{refresh_tag}
<title>Nowing Web Builder Preview</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, sans-serif; background: #020617; color: #e2e8f0; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
  .card {{ text-align: center; max-width: 480px; padding: 2rem; border-radius: 1rem; background: #0f172a; border: 1px solid #1e293b; }}
  h1 {{ font-size: 1.25rem; margin-bottom: 0.5rem; }}
  p {{ font-size: 0.875rem; color: #94a3b8; line-height: 1.5; }}
  a {{ color: #6366f1; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="card">
  <h1>{safe_status}</h1>
  <p>{safe_message}</p>
  <p><a href="{build_log_url}" target="_parent">View build logs</a></p>
</div>
</body>
</html>"""


def _origin_from_url(url: str | None) -> str:
    """Return scheme://netloc for an absolute URL, else empty string."""
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _www_origin_variants(origin: str) -> set[str]:
    variants = {origin}
    if "://www." in origin:
        variants.add(origin.replace("://www.", "://", 1))
    elif "://" in origin:
        variants.add(origin.replace("://", "://www.", 1))
    return variants


def _trusted_preview_parent_origins(config_origin: str | None) -> set[str]:
    """Allowlist of parent origins permitted to drive the Mark Tool bridge."""
    trusted: set[str] = set()
    for candidate in (
        config_origin,
        config.NEXT_FRONTEND_URL,
        getattr(config, "NOWING_PUBLIC_URL", None),
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ):
        origin = _origin_from_url(candidate)
        if origin:
            trusted.update(_www_origin_variants(origin))
    return trusted


def _allowed_preview_origin(referer: str | None, config_origin: str | None) -> str:
    """Derive the trusted parent origin for the preview iframe.

    Referer is used only when its origin is on the frontend allowlist.
    Arbitrary Referer values must not become window.__wbAllowedOrigin.
    """
    trusted = _trusted_preview_parent_origins(config_origin)
    referer_origin = _origin_from_url(referer)
    if referer_origin and referer_origin in trusted:
        return referer_origin
    fallback = _origin_from_url(config_origin) or _origin_from_url(
        config.NEXT_FRONTEND_URL
    )
    return fallback or ""


@router.get("/apps/{app_id}/preview", response_class=HTMLResponse)
async def get_workspace_app_preview(
    app_id: str,
    workspace_id: int,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Render and serve interactive live HTML preview for the generated web app (Story 27.1b Option A)."""
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

    # Option A status dispatch — all branches return HTML for 27.1a compatibility
    if app_entity.status == "generated":
        # The async worker handles status, quota debit, and duplicate-guard (R-02).
        await BuilderService.trigger_async_build(app_id, workspace_id)
        return HTMLResponse(
            content=_build_status_html(
                "building",
                app_id,
                workspace_id,
                message="Build initiated. This preview will refresh automatically when ready.",
                meta_refresh=True,
            ),
            status_code=status.HTTP_202_ACCEPTED,
            headers={
                "Content-Security-Policy": WEB_BUILDER_CSP,
                "X-Content-Type-Options": "nosniff",
            },
        )

    if app_entity.status == "building":
        return HTMLResponse(
            content=_build_status_html(
                "building",
                app_id,
                workspace_id,
                message="Build in progress. This preview will refresh automatically.",
                meta_refresh=True,
            ),
            status_code=status.HTTP_202_ACCEPTED,
            headers={
                "Content-Security-Policy": WEB_BUILDER_CSP,
                "X-Content-Type-Options": "nosniff",
            },
        )

    if app_entity.status == "build_failed":
        error_message = app_entity.error_message or "Next.js build failed"
        return HTMLResponse(
            content=_build_status_html(
                "build_failed",
                app_id,
                workspace_id,
                message=error_message,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            headers={
                "Content-Security-Policy": WEB_BUILDER_CSP,
                "X-Content-Type-Options": "nosniff",
            },
        )

    project_dir = _resolve_and_validate_project_dir(app_entity, app_id, workspace_id)

    # Check compiled standalone HTML candidate paths; otherwise fallback to PreviewRenderer
    candidate_index_paths = [
        project_dir / ".next" / "server" / "app" / "index.html",
        project_dir / ".next" / "server" / "app" / "page.html",
        project_dir
        / ".next"
        / "standalone"
        / ".next"
        / "server"
        / "app"
        / "index.html",
        project_dir / ".next" / "standalone" / "index.html",
        project_dir / "out" / "index.html",
    ]
    html_content = None
    for candidate in candidate_index_paths:
        if candidate.exists() and not candidate.is_symlink():
            try:
                resolved_candidate = candidate.resolve()
                if (
                    not resolved_candidate.is_relative_to(project_dir)
                    or not resolved_candidate.is_file()
                ):
                    continue
                html_content = await asyncio.to_thread(
                    resolved_candidate.read_text, encoding="utf-8"
                )
                break
            except (OSError, RuntimeError):
                continue

    allowed_origin = _allowed_preview_origin(
        request.headers.get("Referer"), config.NEXT_FRONTEND_URL
    )

    if not html_content:
        html_content = await asyncio.to_thread(
            PreviewRenderer.render_app_html,
            project_dir=project_dir,
            app_name=app_entity.name if app_entity else "Generated Web App",
            allowed_origin=allowed_origin,
        )
    else:
        # Make static asset references relative to the app-scoped preview URL
        html_content = _rewrite_next_static_paths(html_content)
        html_content = PreviewRenderer.inject_mark_tool_bridge(
            html_content, allowed_origin
        )

    return HTMLResponse(
        content=html_content,
        status_code=status.HTTP_200_OK,
        headers={
            "Content-Security-Policy": WEB_BUILDER_CSP,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/apps/{app_id}/_next/static/{path:path}")
async def get_workspace_app_static(
    app_id: str,
    workspace_id: int,
    path: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Serve a Next.js static asset for the app preview (D1)."""
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

    project_dir = _resolve_and_validate_project_dir(app_entity, app_id, workspace_id)

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


def _is_likely_binary_file(file_path: Path) -> bool:
    """Best-effort detection of binary/non-source files to avoid returning image/data blobs."""
    mime, _ = mimetypes.guess_type(str(file_path))
    if mime and not mime.startswith(
        ("text/", "application/json", "application/javascript")
    ):
        return True
    binary_suffixes = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".mp3",
        ".mp4",
        ".wav",
        ".ogg",
        ".webm",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".rar",
        ".7z",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
    }
    return file_path.suffix.lower() in binary_suffixes


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

    project_dir = _resolve_and_validate_project_dir(app_entity, app_id, workspace_id)

    if not project_dir.exists():
        project_dir.mkdir(parents=True, exist_ok=True)
        ProjectWriter.write_minimal_nextjs_scaffold(
            project_dir, app_entity.name if app_entity else "Generated App"
        )

    files_dict: dict[str, str] = {}
    skip_dirs = {"node_modules", ".next", ".build_logs", ".npm-cache"}
    max_depth = 8
    seen: set[Path] = set()
    queue: list[tuple[Path, int]] = [(project_dir, 0)]

    while queue:
        current_dir, depth = queue.pop(0)
        if depth > max_depth:
            continue
        try:
            for entry in current_dir.iterdir():
                if entry.is_symlink():
                    continue
                resolved = entry.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                if entry.is_dir():
                    if entry.name in skip_dirs:
                        continue
                    queue.append((entry, depth + 1))
                elif entry.is_file():
                    if not resolved.is_relative_to(project_dir):
                        continue
                    if _is_likely_binary_file(entry):
                        continue
                    rel_path = str(entry.relative_to(project_dir))
                    try:
                        files_dict[rel_path] = entry.read_text(encoding="utf-8")
                    except Exception:
                        continue
        except (OSError, PermissionError):
            continue

    return files_dict


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
