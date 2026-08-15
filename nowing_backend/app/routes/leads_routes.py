"""REST routes for Lead Intelligence Panel and Company Graph (Story 21.4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    Lead,
    LinkedinJob,
    Permission,
    VerifiedContact,
    Workspace,
    get_async_session,
)
from app.lead_intelligence.schemas import (
    CompanyGraphRead,
    DecisionMakerRead,
    HiringSignalRead,
    LeadListResponse,
    LeadRead,
    LeadStatusUpdate,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


def _escape_ilike_term(term: str | None) -> str | None:
    """Escape PostgreSQL LIKE wildcard characters in a user-supplied term."""
    if term is None:
        return None
    return term.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _map_lead_to_read(lead: Lead) -> LeadRead:
    """Helper to transform ORM Lead to LeadRead schema."""
    phone = None
    if getattr(lead, "verified_contacts", None):
        for contact in lead.verified_contacts:
            if contact.phone:
                phone = contact.phone
                break

    # Determine intent tag based on industry, source or scores
    intent = "BÁN"
    if lead.source in {"muasamcong", "tender"}:
        intent = "ĐẤU THẦU"
    elif lead.source in {"topcv", "itviec", "vietnamworks", "jobs"}:
        intent = "TUYỂN DỤNG"
    elif lead.source in {"shopee", "tiktok_shop", "ecommerce"}:
        intent = "MUA"
    elif lead.source in {"linkedin", "b2b"}:
        intent = "HỢP TÁC"

    fit_score = getattr(lead, "fit_score", None) if getattr(lead, "fit_score", None) is not None else getattr(lead, "composite_score", None)

    return LeadRead(
        id=lead.id,
        workspace_id=lead.workspace_id,
        client_id=getattr(lead, "client_id", None),
        source=lead.source,
        source_url=getattr(lead, "source_url", None),
        company_name=lead.company_name,
        domain=getattr(lead, "domain", None),
        industry=getattr(lead, "industry", None),
        company_size=getattr(lead, "company_size", None),
        location=getattr(lead, "location", None),
        tech_stack=getattr(lead, "tech_stack", None) or [],
        fit_score=fit_score,
        intent_score=getattr(lead, "intent_score", None),
        composite_score=(
            getattr(lead, "composite_score", None)
            if getattr(lead, "composite_score", None) is not None
            else fit_score
        ),
        status=lead.status,
        intent=intent,
        phone=phone,
        price_estimate=None,
        content_snippet=getattr(lead, "description", None) or f"Lead tiềm năng từ {lead.source.capitalize()} - {lead.company_name}",
        author="Nowing Scraper Agent",
        enriched=getattr(lead, "enriched", False),
        created_at=getattr(lead, "created_at", None) or datetime.now(UTC),
        updated_at=getattr(lead, "updated_at", None),
    )


@router.get(
    "/workspaces/{workspace_id}/leads",
    response_model=LeadListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_workspace_leads(
    workspace_id: int,
    client_id: str | None = None,
    source: str | None = None,
    intent: str | None = None,
    min_score: float | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    sort: str = Query(default="-created_at"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> LeadListResponse:
    """List leads with multi-source filtering, scoring breakdown, and pagination."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view leads in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    stmt = select(Lead).where(Lead.workspace_id == workspace_id).options(
        selectinload(Lead.verified_contacts)
    )

    if client_id is not None:
        stmt = stmt.where(Lead.client_id == client_id)
    if source:
        escaped = _escape_ilike_term(source)
        stmt = stmt.where(Lead.source.ilike(f"%{escaped}%", escape="!"))
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    if min_score is not None:
        stmt = stmt.where(
            or_(
                Lead.fit_score >= min_score,
                Lead.composite_score >= min_score,
            )
        )
    if search:
        escaped = _escape_ilike_term(search)
        term = f"%{escaped}%"
        stmt = stmt.where(
            or_(
                Lead.company_name.ilike(term, escape="!"),
                Lead.location.ilike(term, escape="!"),
                Lead.industry.ilike(term, escape="!"),
            )
        )

    # Count query
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one() or 0

    # Sorting
    if sort == "-fit_score" or sort == "-score":
        stmt = stmt.order_by(desc(Lead.fit_score), desc(Lead.created_at))
    elif sort == "fit_score" or sort == "score":
        stmt = stmt.order_by(Lead.fit_score, desc(Lead.created_at))
    elif sort == "created_at":
        stmt = stmt.order_by(Lead.created_at.asc())
    else:
        stmt = stmt.order_by(desc(Lead.created_at))

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    leads = result.scalars().all()

    items = [_map_lead_to_read(lead) for lead in leads]
    return LeadListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/workspaces/{workspace_id}/leads/{lead_id}",
    response_model=LeadRead,
    status_code=status.HTTP_200_OK,
)
async def get_lead_detail(
    workspace_id: int,
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> LeadRead:
    """Get single lead detail with contact info."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view leads in this workspace",
    )

    stmt = (
        select(Lead)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.id == lead_id,
        )
        .options(selectinload(Lead.verified_contacts))
    )
    result = await session.execute(stmt)
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    return _map_lead_to_read(lead)


@router.patch(
    "/workspaces/{workspace_id}/leads/{lead_id}/status",
    response_model=LeadRead,
    status_code=status.HTTP_200_OK,
)
async def update_lead_status(
    workspace_id: int,
    lead_id: UUID,
    body: LeadStatusUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> LeadRead:
    """Update lead pipeline status (AC-4 / Zero Cache sync trigger)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to update leads in this workspace",
    )

    stmt = (
        select(Lead)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.id == lead_id,
        )
        .options(selectinload(Lead.verified_contacts))
    )
    result = await session.execute(stmt)
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    lead.status = body.status
    lead.updated_at = datetime.now(UTC)
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    return _map_lead_to_read(lead)


@router.get(
    "/workspaces/{workspace_id}/companies/{company_name}/graph",
    response_model=CompanyGraphRead,
    status_code=status.HTTP_200_OK,
)
async def get_company_graph(
    workspace_id: int,
    company_name: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> CompanyGraphRead:
    """Get aggregated relationship graph for enterprise/company (AC-3 / Widget U4)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view company graph in this workspace",
    )

    clean_name = company_name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company name must not be empty",
        )

    escaped_name = _escape_ilike_term(clean_name)
    ilike_pattern = f"%{escaped_name}%"

    # Query verified contacts from database for this company (Story 21.3)
    contacts_stmt = (
        select(VerifiedContact)
        .join(Lead, VerifiedContact.lead_id == Lead.id)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.company_name.ilike(ilike_pattern, escape="!"),
        )
        .distinct()
    )
    contacts_result = await session.execute(contacts_stmt)
    db_contacts = contacts_result.scalars().all()

    decision_makers: list[DecisionMakerRead] = []
    for c in db_contacts:
        if c.name:
            linkedin_slug = quote(c.name.lower().replace(" ", "-"), safe="")
            decision_makers.append(
                DecisionMakerRead(
                    name=c.name,
                    title=c.title or "Executive",
                    linkedin_url=f"https://linkedin.com/in/{linkedin_slug}",
                    email=c.email if c.email else None,
                    phone=c.phone,
                    confidence=c.confidence if c.confidence is not None else 0.95,
                )
            )

    # Query LinkedIn job postings for this company (Story 21.9 / Story 12.10)
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    jobs_stmt = (
        select(LinkedinJob)
        .where(
            LinkedinJob.company_name.ilike(ilike_pattern, escape="!"),
        )
        .order_by(LinkedinJob.posted_at.desc().nullslast())
        .limit(20)
    )
    jobs_result = await session.execute(jobs_stmt)
    db_jobs = jobs_result.scalars().all()

    active_jobs = [j for j in db_jobs if j.posted_at and j.posted_at >= thirty_days_ago]
    active_jobs_count = len(active_jobs)
    hiring_velocity_pct: float | None = None
    if len(db_jobs) > 0:
        # Simple velocity: ratio of active (last 30d) jobs to total returned
        hiring_velocity_pct = round((active_jobs_count / len(db_jobs)) * 100, 1)

    hiring_signals = [
        HiringSignalRead(
            title=j.title,
            department=j.workplace_type or j.employment_type or None,
            platform="LinkedIn",
            posted_date=j.posted_at,
            url=None,
        )
        for j in db_jobs
    ]

    return CompanyGraphRead(
        company_name=clean_name,
        legal_entity=None,
        decision_makers=decision_makers,
        tenders=[],
        hiring_signals=hiring_signals,
        hiring_velocity_pct=hiring_velocity_pct,
        active_jobs_count=active_jobs_count,
    )
