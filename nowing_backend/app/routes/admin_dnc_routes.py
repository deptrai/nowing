"""Admin routes for Global DNC (Do-Not-Call) & PII Exclusion Blacklist (Story 25.6)."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.rate_limiter import get_real_client_ip
from app.schemas.admin_dnc import (
    GlobalDncCsvImportResponse,
    GlobalDncRecordCreate,
    GlobalDncRecordListResponse,
    GlobalDncRecordRead,
)
from app.services.admin_dnc_service import AdminDncService
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/dnc", tags=["admin"])


def _extract_request_meta(request: Request) -> tuple[str, str | None, str]:
    client_ip = get_real_client_ip(request)
    user_agent = request.headers.get("user-agent")
    endpoint = str(request.url.path)
    return client_ip, user_agent, endpoint


@router.get(
    "/global",
    response_model=GlobalDncRecordListResponse,
    summary="List paginated global DNC blacklist entries",
)
async def list_global_dnc(
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    record_type: Annotated[
        str | None,
        Query(description="Filter by record_type (phone, domain, email, tax_id)"),
    ] = None,
    search: Annotated[
        str | None, Query(description="Search masked value or reason")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> GlobalDncRecordListResponse:
    """Return paginated list of global DNC exclusions."""
    service = AdminDncService(session)
    result = await service.list_global_dnc_records(
        record_type=record_type, search=search, limit=limit, offset=offset
    )
    return GlobalDncRecordListResponse(
        items=[GlobalDncRecordRead.model_validate(r) for r in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.post(
    "/global",
    response_model=GlobalDncRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a single entry to the global DNC blacklist",
)
async def add_global_dnc_entry(
    request: Request,
    payload: GlobalDncRecordCreate,
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> GlobalDncRecordRead:
    """Add a new blacklist entry, write immutable AuditEvent, and invalidate Redis cache."""
    service = AdminDncService(session)
    client_ip, user_agent, endpoint = _extract_request_meta(request)

    try:
        entry = await service.add_global_dnc_record(
            record_type=payload.record_type,
            value=payload.value,
            reason=payload.reason,
            source=payload.source,
            actor_id=auth.user_id,
            ip_address=client_ip,
            user_agent=user_agent,
            endpoint=endpoint,
        )
        await session.commit()
        # Invalidate Redis cache post-commit to prevent stale cache race conditions
        await service.invalidate_cache()
        return GlobalDncRecordRead.model_validate(entry)
    except IntegrityError as exc:
        logger.warning("DNC add integrity error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This value is already on the global DNC blacklist.",
        ) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post(
    "/global/import-csv",
    response_model=GlobalDncCsvImportResponse,
    summary="Bulk import global DNC entries via CSV",
)
async def import_global_dnc_csv(
    request: Request,
    file: Annotated[
        UploadFile, File(description="CSV file with columns record_type, value, reason")
    ],
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> GlobalDncCsvImportResponse:
    """Bulk import DNC entries from CSV, deduplicate, write AuditEvent, and invalidate cache."""
    max_size = 10 * 1024 * 1024  # 10MB
    content_bytes = await file.read(max_size + 1)
    if len(content_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV file exceeds maximum size limit of 10MB",
        )

    content = content_bytes.decode("utf-8-sig", errors="replace")
    service = AdminDncService(session)
    client_ip, user_agent, endpoint = _extract_request_meta(request)

    try:
        summary = await service.import_dnc_csv(
            csv_content=content,
            source="csv_import",
            actor_id=auth.user_id,
            ip_address=client_ip,
            user_agent=user_agent,
            endpoint=endpoint,
        )
        await session.commit()
        # Invalidate Redis cache post-commit
        await service.invalidate_cache()
        return GlobalDncCsvImportResponse(**summary)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.delete(
    "/global/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an entry from the global DNC blacklist",
)
async def delete_global_dnc_entry(
    request: Request,
    record_id: Annotated[uuid.UUID, Path(description="UUID of the DNC record")],
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Delete a blacklist entry, write AuditEvent, and invalidate cache."""
    service = AdminDncService(session)
    client_ip, user_agent, endpoint = _extract_request_meta(request)

    deleted = await service.delete_global_dnc_record(
        record_id=record_id,
        actor_id=auth.user_id,
        ip_address=client_ip,
        user_agent=user_agent,
        endpoint=endpoint,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="DNC record not found"
        )
    await session.commit()
    # Invalidate Redis cache post-commit
    await service.invalidate_cache()
