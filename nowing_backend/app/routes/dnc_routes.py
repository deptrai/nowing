"""REST routes for Do-Not-Call (DNC) and Compliance Engine (Story 21.14 / Decree 91 / Decree 13)."""

from __future__ import annotations

import csv
import io
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, WorkspaceDncRecord, get_async_session
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_domain,
    normalize_email,
    normalize_phone_e164,
    normalize_tax_id,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.schemas.dnc import (
    DncCsvImportResponse,
    DncListResponse,
    DncRecordCreate,
    DncRecordRead,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter(tags=["DNC & Compliance"])


def _normalize_dnc_value(
    record_type: str, raw_value: str
) -> tuple[str | None, str | None]:
    """Normalize input value and return (normalized_display_value, value_hmac)."""
    if record_type == "phone":
        e164 = normalize_phone_e164(raw_value)
        if not e164:
            return None, None
        return e164, hash_phone_hmac(e164)
    elif record_type == "domain":
        dom = normalize_domain(raw_value)
        if not dom:
            return None, None
        return dom, hash_phone_hmac(dom)
    elif record_type == "email":
        mail = normalize_email(raw_value)
        if not mail:
            return None, None
        return mail, hash_phone_hmac(mail)
    elif record_type == "tax_id":
        tax = normalize_tax_id(raw_value)
        if not tax:
            return None, None
        return tax, hash_phone_hmac(tax)
    return None, None


async def create_dnc_record_service(
    session: AsyncSession,
    workspace_id: int,
    body: DncRecordCreate,
    source: str = "manual",
) -> dict:
    """Helper creating a single DNC record with HMAC computation and cache invalidation."""
    norm_val, val_hmac = _normalize_dnc_value(body.record_type, body.value)
    if not norm_val or not val_hmac:
        raise ValueError(f"Invalid format for {body.record_type}: '{body.value}'")

    stmt = (
        pg_insert(WorkspaceDncRecord)
        .values(
            workspace_id=workspace_id,
            record_type=body.record_type,
            value=norm_val,
            value_hmac=val_hmac,
            reason=body.reason or "Opt-out requested",
            source=source,
        )
        .on_conflict_do_update(
            constraint="uq_workspace_dnc_entry",
            set_={
                "reason": body.reason or "Opt-out requested",
                "source": source,
            },
        )
        .returning(WorkspaceDncRecord)
    )
    result = await session.execute(stmt)
    record = result.scalar_one()
    await session.commit()

    dnc_svc = DncComplianceService()
    await dnc_svc.invalidate_workspace_cache(workspace_id)

    return {
        "id": record.id,
        "workspace_id": record.workspace_id,
        "record_type": record.record_type,
        "value": record.value,
        "value_hmac": record.value_hmac,
        "reason": record.reason,
        "source": record.source,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


async def bulk_import_dnc_csv_service(
    session: AsyncSession,
    workspace_id: int,
    file_bytes: bytes,
) -> dict:
    """Helper parsing and inserting bulk DNC entries from CSV."""
    text_data = file_bytes.decode("utf-8-sig", errors="ignore")
    lines = text_data.splitlines()
    if len(lines) > 5001:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV exceeds maximum 5,000 rows limit",
        )

    reader = csv.DictReader(io.StringIO(text_data))

    imported = 0
    skipped = 0
    errors = []

    rows_dict = {}
    for line_no, row in enumerate(reader, start=2):
        r_type = (row.get("type") or row.get("record_type") or "phone").strip().lower()
        val = (row.get("value") or row.get("contact") or "").strip()
        reason = (row.get("reason") or "CSV Bulk Import").strip()

        if not val:
            skipped += 1
            continue

        norm_val, val_hmac = _normalize_dnc_value(r_type, val)
        if not norm_val or not val_hmac:
            errors.append(f"Line {line_no}: Invalid {r_type} '{val}'")
            skipped += 1
            continue

        key = (r_type, val_hmac)
        if key in rows_dict:
            skipped += 1
            continue

        rows_dict[key] = {
            "workspace_id": workspace_id,
            "record_type": r_type,
            "value": norm_val,
            "value_hmac": val_hmac,
            "reason": reason,
            "source": "csv_import",
        }

    rows_to_insert = list(rows_dict.values())
    chunk_size = 500
    if rows_to_insert:
        for i in range(0, len(rows_to_insert), chunk_size):
            chunk = rows_to_insert[i : i + chunk_size]
            stmt = (
                pg_insert(WorkspaceDncRecord)
                .values(chunk)
                .on_conflict_do_nothing(constraint="uq_workspace_dnc_entry")
            )
            await session.execute(stmt)
        await session.commit()
        imported = len(rows_to_insert)

        dnc_svc = DncComplianceService()
        await dnc_svc.invalidate_workspace_cache(workspace_id)

    return {
        "imported_count": imported,
        "skipped_count": skipped,
        "failed_count": len(errors),
        "errors": errors[:50],  # cap at 50 for response readability
    }


@router.get(
    "/workspaces/{workspace_id}/dnc",
    response_model=DncListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_dnc_records(
    workspace_id: int,
    record_type: str | None = Query(None, description="Filter by record_type"),
    search: str | None = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DncListResponse:
    """List and search workspace DNC entries with pagination."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view compliance records in this workspace",
    )

    query = select(WorkspaceDncRecord).where(
        WorkspaceDncRecord.workspace_id == workspace_id
    )
    count_query = select(func.count(WorkspaceDncRecord.id)).where(
        WorkspaceDncRecord.workspace_id == workspace_id
    )

    if record_type:
        query = query.where(WorkspaceDncRecord.record_type == record_type)
        count_query = count_query.where(WorkspaceDncRecord.record_type == record_type)

    if search:
        pattern = f"%{search.strip()}%"
        search_filter = or_(
            WorkspaceDncRecord.value.ilike(pattern),
            WorkspaceDncRecord.reason.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_count = (await session.execute(count_query)).scalar_one() or 0

    query = (
        query.order_by(desc(WorkspaceDncRecord.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = (await session.execute(query)).scalars().all()

    return DncListResponse(
        records=[DncRecordRead.model_validate(r) for r in records],
        total_count=total_count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/workspaces/{workspace_id}/dnc",
    response_model=DncRecordRead,
    status_code=status.HTTP_200_OK,
)
async def create_dnc_record(
    workspace_id: int,
    body: DncRecordCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DncRecordRead:
    """Add a single phone, email, domain or tax ID to the workspace DNC blacklist."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to modify compliance records in this workspace",
    )

    try:
        data = await create_dnc_record_service(
            session, workspace_id, body, source="manual"
        )
        return DncRecordRead.model_validate(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/workspaces/{workspace_id}/dnc/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dnc_record(
    workspace_id: int,
    record_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Remove an entry from the workspace DNC blacklist."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to modify compliance records in this workspace",
    )

    stmt = select(WorkspaceDncRecord).where(
        WorkspaceDncRecord.id == record_id,
        WorkspaceDncRecord.workspace_id == workspace_id,
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="DNC record not found"
        )

    await session.delete(record)
    await session.commit()

    dnc_svc = DncComplianceService()
    await dnc_svc.invalidate_workspace_cache(workspace_id)


@router.post(
    "/workspaces/{workspace_id}/dnc/import-csv",
    response_model=DncCsvImportResponse,
    status_code=status.HTTP_200_OK,
)
async def import_dnc_csv(
    workspace_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DncCsvImportResponse:
    """Bulk import DNC entries from CSV file (up to 5,000 rows)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to import compliance records in this workspace",
    )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty CSV file provided"
        )
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file size exceeds 5MB limit",
        )

    result = await bulk_import_dnc_csv_service(session, workspace_id, content)
    return DncCsvImportResponse.model_validate(result)
