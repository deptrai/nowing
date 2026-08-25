"""REST API endpoints for Presentation Studio (Story 27.2a)."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import FILE_STORAGE_LOCAL_PATH, config
from app.db import (
    Permission,
    SlidePresentation,
    Workspace,
    get_async_session,
)
from app.routes.rbac_routes import check_permission
from app.services.presentation.schemas import (
    GeneratePresentationInput,
    GeneratePresentationOutput,
    SlidePresentationRead,
)
from app.services.presentation.service import PresentationStudioService
from app.users import get_auth_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/presentations", tags=["presentations"])

# Marp HTML is LLM-derived; do not allow script execution in the preview.
PRESENTATION_PREVIEW_CSP = (
    "default-src 'none'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "script-src 'none'; "
    "connect-src 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'self'; "
    "base-uri 'none'"
)


def is_presentation_studio_enabled_for_workspace(ws: Workspace | None) -> bool:
    """Check both global and workspace-level Presentation Studio feature flags."""
    if not config.PRESENTATION_STUDIO_ENABLED:
        return False
    if ws is None:
        return False
    return getattr(ws, "presentation_studio_enabled", None) is not False


async def require_workspace_member(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> AuthContext:
    """Ensure the caller is a member and that Presentation Studio is enabled."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.WEB_BUILDER_CREATE.value,
        error_message="You don't have access to this workspace",
    )

    ws = (
        (await session.execute(select(Workspace).where(Workspace.id == workspace_id)))
        .scalars()
        .first()
    )
    if not is_presentation_studio_enabled_for_workspace(ws):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Presentation Studio is not enabled on this workspace plan",
        )

    return auth


def _expected_presentation_dir(workspace_id: int, presentation_id: str) -> Path:
    storage_root = Path(FILE_STORAGE_LOCAL_PATH).resolve()
    scoped_root = (
        storage_root / config.PRESENTATION_FILE_STORAGE_SUBDIR / str(workspace_id)
    ).resolve()
    if not scoped_root.is_relative_to(storage_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid presentation storage path",
        )
    expected_dir = (scoped_root / presentation_id).resolve()
    if not expected_dir.is_relative_to(scoped_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid presentation storage path",
        )
    return expected_dir


def _resolve_storage_path(
    entity: SlidePresentation,
    workspace_id: int,
    presentation_id: str,
) -> Path:
    """Resolve the stored file and keep it inside this presentation's directory."""
    expected_dir = _expected_presentation_dir(workspace_id, presentation_id)

    if entity.file_path:
        file_path = Path(entity.file_path)
    else:
        pptx = expected_dir / "output.pptx"
        markdown = expected_dir / "output.md"
        if pptx.is_file():
            file_path = pptx
        elif markdown.is_file():
            file_path = markdown
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Presentation file not found",
            )

    try:
        resolved = file_path.resolve()
    except (OSError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid presentation storage path",
        ) from e

    if not resolved.is_relative_to(expected_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Presentation storage path escapes storage root",
        )
    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation file not found",
        )
    return resolved


@router.post("/generate", response_model=GeneratePresentationOutput)
async def generate_presentation(
    payload: GeneratePresentationInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> GeneratePresentationOutput:
    """Generate a new PPTX or Marp slide deck for the workspace."""
    await require_workspace_member(session, auth, payload.workspace_id)
    payload.user_id = auth.user.id

    service = PresentationStudioService()
    return await service.generate(
        session=session,
        build_input=payload,
    )


@router.get("", response_model=list[SlidePresentationRead])
async def list_presentations(
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[SlidePresentationRead]:
    """List all slide decks for a workspace."""
    await require_workspace_member(session, auth, workspace_id)
    stmt = (
        select(SlidePresentation)
        .where(SlidePresentation.workspace_id == workspace_id)
        .order_by(SlidePresentation.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{presentation_id}", response_model=SlidePresentationRead)
async def get_presentation(
    presentation_id: str,
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> SlidePresentationRead:
    """Get a single slide deck."""
    await require_workspace_member(session, auth, workspace_id)
    stmt = select(SlidePresentation).where(
        SlidePresentation.id == presentation_id,
        SlidePresentation.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    entity = result.scalars().first()
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation not found",
        )
    return entity


@router.get("/{presentation_id}/download")
async def download_presentation(
    presentation_id: str,
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> FileResponse:
    """Download the PPTX or Marp file for a presentation."""
    await require_workspace_member(session, auth, workspace_id)
    stmt = select(SlidePresentation).where(
        SlidePresentation.id == presentation_id,
        SlidePresentation.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    entity = result.scalars().first()
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation not found",
        )

    file_path = _resolve_storage_path(entity, entity.workspace_id, entity.id)
    media_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if entity.format == "pptx"
        else mimetypes.guess_type(str(file_path))[0] or "text/markdown"
    )
    extension = "pptx" if entity.format == "pptx" else "md"
    filename = f"{entity.slug}.{extension}"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


@router.get("/{presentation_id}/preview", response_class=HTMLResponse)
async def preview_presentation(
    presentation_id: str,
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> HTMLResponse:
    """Return the HTML preview for a Marp presentation, if available."""
    await require_workspace_member(session, auth, workspace_id)
    stmt = select(SlidePresentation).where(
        SlidePresentation.id == presentation_id,
        SlidePresentation.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    entity = result.scalars().first()
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation not found",
        )

    if entity.format != "marp" or not entity.preview_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not available for this presentation",
        )

    expected_dir = _expected_presentation_dir(entity.workspace_id, entity.id)
    html_file = (expected_dir / "output.html").resolve()
    if not html_file.is_relative_to(expected_dir) or not html_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview file not found",
        )

    try:
        html = html_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Preview file is not valid UTF-8",
        ) from exc

    return HTMLResponse(
        content=html,
        headers={
            "Content-Security-Policy": PRESENTATION_PREVIEW_CSP,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{presentation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_presentation(
    presentation_id: str,
    workspace_id: int,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Delete a slide deck and its files after member check."""
    await require_workspace_member(session, auth, workspace_id)
    stmt = select(SlidePresentation).where(
        SlidePresentation.id == presentation_id,
        SlidePresentation.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    entity = result.scalars().first()
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presentation not found",
        )

    expected_dir = _expected_presentation_dir(entity.workspace_id, entity.id)
    try:
        if expected_dir.is_dir():
            for child in expected_dir.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            if not any(expected_dir.iterdir()):
                expected_dir.rmdir()
    except OSError:
        logger.warning("Failed to delete presentation files under %s", expected_dir)

    await session.delete(entity)
    await session.commit()
