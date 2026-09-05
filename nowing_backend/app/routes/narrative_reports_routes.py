"""Routes for Narrative Reports over indexed and scraped data (Story 6.12)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    Permission,
    get_async_session,
)
from app.reports.narrative import (
    NarrativeReportCreateRequest,
    NarrativeSynthesisEngine,
    NarrativeTemplate,
    NarrativeTemplateRegistry,
)
from app.schemas.reports import ReportContentRead
from app.users import get_auth_context
from app.utils.rbac import check_permission, check_workspace_access

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/reports/narrative",
    tags=["narrative-reports"],
)


@router.get("/templates", response_model=list[NarrativeTemplate])
async def list_narrative_templates_route(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List available pre-configured narrative report templates."""
    await check_workspace_access(session, auth, workspace_id)
    return NarrativeTemplateRegistry.list_all()


@router.post("", response_model=ReportContentRead, status_code=status.HTTP_201_CREATED)
async def generate_narrative_report_route(
    workspace_id: int,
    data: NarrativeReportCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Generate and persist a structured narrative report with grounded citations."""
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.AUTOMATIONS_CREATE.value,
        "You don't have permission to generate narrative reports in this workspace",
    )

    template = NarrativeTemplateRegistry.get(data.template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Narrative template '{data.template_id}' not found",
        )

    report = await NarrativeSynthesisEngine.generate_report(
        session=session,
        workspace_id=workspace_id,
        template=template,
        parameters=data.parameters,
        custom_title=data.title,
    )

    return ReportContentRead(
        id=report.id,
        title=report.title,
        content=report.content,
        content_type=report.content_type,
        report_metadata=report.report_metadata,
        report_group_id=report.report_group_id,
        versions=[],
    )
