"""REST API endpoints for Web Builder (Story 27.1 / Story 27.1b / AD-113 / AD-113a / AD-114)."""

import asyncio
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
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import WorkspaceApp, get_async_session
from app.services.web_builder.builder import BuilderService
from app.services.web_builder.preview_renderer import WEB_BUILDER_CSP, PreviewRenderer
from app.services.web_builder.project_writer import ProjectWriter
from app.users import get_auth_context

from ._helpers import check_web_builder_enabled, require_workspace_member

logger = logging.getLogger(__name__)


router = APIRouter()


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
            except (OSError, RuntimeError) as exc:
                logger.debug("Suppressed %r", exc)
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
                    except Exception as exc:
                        logger.debug("Suppressed %r", exc)
                        continue
        except (OSError, PermissionError) as exc:
            logger.debug("Suppressed %r", exc)
            continue

    return files_dict
