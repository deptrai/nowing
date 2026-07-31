"""Test-only endpoint to archive a document for E2E real-time sync checks.

Mounted only by tests/e2e/run_backend.py. Production never sees this router.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select

from app.db import Document, WorkspaceMembership, get_async_session
from app.users import get_auth_context

router = APIRouter(prefix="/__e2e__", tags=["__e2e__"])


def _install(app) -> None:
    app.include_router(router)


@router.post("/documents/{document_id}/archive", status_code=status.HTTP_200_OK)
async def archive_document_for_e2e(
    document_id: int,
    session=Depends(get_async_session),
    auth=Depends(get_auth_context),
):
    """Set archived_at on a document if the caller is a workspace member."""
    result = await session.execute(select(Document).filter(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    membership_result = await session.execute(
        select(WorkspaceMembership).filter(
            WorkspaceMembership.workspace_id == document.workspace_id,
            WorkspaceMembership.user_id == auth.user.id,
        )
    )
    if membership_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a workspace member")

    document.archived_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True}
