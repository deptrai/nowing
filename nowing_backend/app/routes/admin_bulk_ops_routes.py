"""Superadmin Bulk Operations Console routes (Story 29.4 / AD-54).

Prefix: /admin/saas/bulk-ops
Guarded by: require_superuser (Superadmin only)
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas.bulk_ops import (
    BulkOpErrorRead,
    CancelJobResponse,
    DryRunRequest,
    DryRunResponse,
    ExecuteRequest,
    ExecuteResponse,
    JobStatusResponse,
)
from app.services.bulk_ops_service import bulk_ops_service
from app.users import get_user_manager, require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/saas/bulk-ops", tags=["admin-bulk-ops"])


@router.post("/dry-run", response_model=DryRunResponse)
async def dry_run_bulk_op(
    request: DryRunRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> DryRunResponse:
    """Preview affected entities, warnings, and conflicts for a bulk operation."""
    return await bulk_ops_service.dry_run(
        session=session,
        action=request.action,
        filter_spec=request.filter_spec,
        action_params=request.action_params,
        workspace_id=request.workspace_id,
    )


@router.post("", response_model=ExecuteResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/execute", response_model=ExecuteResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_bulk_op(
    request: ExecuteRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
    user_manager=Depends(get_user_manager),
) -> ExecuteResponse:
    """Queue a bulk operation job with an Idempotency-Key guard."""
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'Idempotency-Key' is required",
        )
    return await bulk_ops_service.execute(
        session=session,
        action=request.action,
        filter_spec=request.filter_spec,
        action_params=request.action_params,
        actor=auth.user,
        workspace_id=request.workspace_id,
        idempotency_key=idempotency_key,
        password=request.password,
        mfa_token=request.mfa_token,
        user_manager=user_manager,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_bulk_op_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> JobStatusResponse:
    """Fetch status and progress for a bulk operation job."""
    return await bulk_ops_service.get_job(
        session=session,
        job_id=job_id,
        actor=auth.user,
        workspace_id=None,
    )


@router.post("/{job_id}/cancel", response_model=CancelJobResponse)
async def cancel_bulk_op_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> CancelJobResponse:
    """Cancel a queued or running bulk operation job."""
    return await bulk_ops_service.cancel_job(
        session=session,
        job_id=job_id,
        actor=auth.user,
        workspace_id=None,
    )


@router.get("/{job_id}/errors", response_model=list[BulkOpErrorRead])
async def get_bulk_op_errors(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> list[BulkOpErrorRead]:
    """Retrieve error records for failed subjects in a bulk job."""
    return await bulk_ops_service.get_job_errors(
        session=session,
        job_id=job_id,
        actor=auth.user,
        workspace_id=None,
    )
