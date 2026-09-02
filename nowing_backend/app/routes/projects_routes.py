"""Routes for Projects persistent workspaces (CRUD, pinning documents, skills linking)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    Document,
    Project,
    ProjectPinnedDocument,
    get_async_session,
)
from app.schemas.projects_schemas import (
    ProjectCreate,
    ProjectPinnedDocumentRead,
    ProjectRead,
    ProjectUpdate,
)
from app.users import get_auth_context
from app.utils.rbac import Permission, check_permission

router = APIRouter(tags=["projects"])


async def _get_project_with_pins(
    session: AsyncSession, project_id: int, workspace_id: int
) -> Project | None:
    stmt = (
        select(Project)
        .options(
            selectinload(Project.pinned_documents).selectinload(
                ProjectPinnedDocument.document
            )
        )
        .where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    res = await session.execute(stmt)
    return res.scalars().first()


def _format_project_read(project: Project) -> ProjectRead:
    pins_read: list[ProjectPinnedDocumentRead] = []
    for pin in project.pinned_documents:
        pins_read.append(
            ProjectPinnedDocumentRead(
                id=pin.id,
                project_id=pin.project_id,
                document_id=pin.document_id,
                pinned_at=pin.pinned_at,
                document_title=pin.document.title if pin.document else None,
                document_type=pin.document.document_type if pin.document else None,
            )
        )

    return ProjectRead(
        id=project.id,
        workspace_id=project.workspace_id,
        created_by_id=project.created_by_id,
        name=project.name,
        description=project.description,
        master_instructions=project.master_instructions,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        pinned_documents=pins_read,
    )


@router.get(
    "/workspaces/{workspace_id}/projects",
    response_model=list[ProjectRead],
    status_code=status.HTTP_200_OK,
)
async def list_projects(
    workspace_id: int,
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[ProjectRead]:
    """List projects in a workspace with optional archived filtering."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PROJECTS_READ.value,
        "You don't have permission to view projects in this workspace",
    )

    stmt = (
        select(Project)
        .options(
            selectinload(Project.pinned_documents).selectinload(
                ProjectPinnedDocument.document
            )
        )
        .where(Project.workspace_id == workspace_id)
    )
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))

    stmt = stmt.order_by(Project.updated_at.desc()).offset(offset).limit(limit)
    res = await session.execute(stmt)
    projects = res.scalars().all()

    return [_format_project_read(p) for p in projects]


@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    workspace_id: int,
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ProjectRead:
    """Create a new project in the workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PROJECTS_CREATE.value,
        "You don't have permission to create projects in this workspace",
    )

    now = datetime.now(UTC)
    project = Project(
        workspace_id=workspace_id,
        created_by_id=auth.user.id if auth.user else None,
        name=payload.name,
        description=payload.description,
        master_instructions=payload.master_instructions,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)

    # Re-fetch with relations loaded
    loaded = await _get_project_with_pins(session, project.id, workspace_id)
    return _format_project_read(loaded or project)


@router.get(
    "/workspaces/{workspace_id}/projects/{project_id}",
    response_model=ProjectRead,
    status_code=status.HTTP_200_OK,
)
async def get_project(
    workspace_id: int,
    project_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ProjectRead:
    """Get project details with pinned documents."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PROJECTS_READ.value,
        "You don't have permission to view projects in this workspace",
    )

    stmt = (
        select(Project)
        .options(
            selectinload(Project.pinned_documents).selectinload(
                ProjectPinnedDocument.document
            )
        )
        .where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    res = await session.execute(stmt)
    project = res.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found in workspace {workspace_id}",
        )

    return _format_project_read(project)


@router.patch(
    "/workspaces/{workspace_id}/projects/{project_id}",
    response_model=ProjectRead,
    status_code=status.HTTP_200_OK,
)
async def update_project(
    workspace_id: int,
    project_id: int,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ProjectRead:
    """Update project fields (name, description, master instructions, archive status)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PROJECTS_UPDATE.value,
        "You don't have permission to update projects in this workspace",
    )

    stmt = (
        select(Project)
        .options(
            selectinload(Project.pinned_documents).selectinload(
                ProjectPinnedDocument.document
            )
        )
        .where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    res = await session.execute(stmt)
    project = res.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found in workspace {workspace_id}",
        )

    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    if payload.master_instructions is not None:
        project.master_instructions = payload.master_instructions
    if payload.is_archived is not None:
        project.is_archived = payload.is_archived

    project.updated_at = datetime.now(UTC)
    session.add(project)
    await session.commit()
    await session.refresh(project)

    return _format_project_read(project)


@router.delete(
    "/workspaces/{workspace_id}/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(
    workspace_id: int,
    project_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete a project completely."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PROJECTS_DELETE.value,
        "You don't have permission to delete projects in this workspace",
    )

    project = await session.get(Project, project_id)
    if not project or project.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found in workspace {workspace_id}",
        )

    await session.delete(project)
    await session.commit()


@router.post(
    "/workspaces/{workspace_id}/projects/{project_id}/archive",
    response_model=ProjectRead,
    status_code=status.HTTP_200_OK,
)
async def archive_project(
    workspace_id: int,
    project_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ProjectRead:
    """Convenience endpoint to toggle or mark a project as archived."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PROJECTS_UPDATE.value,
        "You don't have permission to archive projects in this workspace",
    )

    stmt = (
        select(Project)
        .options(
            selectinload(Project.pinned_documents).selectinload(
                ProjectPinnedDocument.document
            )
        )
        .where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    res = await session.execute(stmt)
    project = res.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found in workspace {workspace_id}",
        )

    project.is_archived = True
    project.updated_at = datetime.now(UTC)
    session.add(project)
    await session.commit()
    await session.refresh(project)

    return _format_project_read(project)


@router.post(
    "/workspaces/{workspace_id}/projects/{project_id}/documents/{document_id}/pin",
    status_code=status.HTTP_200_OK,
)
async def pin_document(
    workspace_id: int,
    project_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, str]:
    """Pin a document to a project (idempotent)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PROJECTS_UPDATE.value,
        "You don't have permission to update project pins in this workspace",
    )

    project = await session.get(Project, project_id)
    if not project or project.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found in workspace {workspace_id}",
        )

    doc = await session.get(Document, document_id)
    if not doc or doc.workspace_id != workspace_id or doc.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found in workspace {workspace_id}",
        )

    # Check existing pin
    existing_stmt = select(ProjectPinnedDocument).where(
        ProjectPinnedDocument.project_id == project_id,
        ProjectPinnedDocument.document_id == document_id,
    )
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing:
        return {"status": "ok", "message": "Document pinned successfully"}

    new_pin = ProjectPinnedDocument(
        project_id=project_id,
        document_id=document_id,
        pinned_at=datetime.now(UTC),
    )
    session.add(new_pin)
    project.updated_at = datetime.now(UTC)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # Concurrent duplicate pin is idempotent per spec.
        return {"status": "ok", "message": "Document pinned successfully"}

    return {"status": "ok", "message": "Document pinned successfully"}


@router.delete(
    "/workspaces/{workspace_id}/projects/{project_id}/documents/{document_id}/pin",
    status_code=status.HTTP_200_OK,
)
async def unpin_document(
    workspace_id: int,
    project_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, str]:
    """Unpin a document from a project without deleting the underlying document."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PROJECTS_UPDATE.value,
        "You don't have permission to update project pins in this workspace",
    )

    project = await session.get(Project, project_id)
    if not project or project.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found in workspace {workspace_id}",
        )

    existing_stmt = select(ProjectPinnedDocument).where(
        ProjectPinnedDocument.project_id == project_id,
        ProjectPinnedDocument.document_id == document_id,
    )
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing:
        await session.delete(existing)
        project.updated_at = datetime.now(UTC)
        await session.commit()

    return {"status": "ok", "message": "Document unpinned successfully"}
