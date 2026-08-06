"""HTTP routes for the ``Playbook`` resource."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.automations.persistence.models.playbook import Playbook
from app.automations.schemas.api import (
    AutomationDetail,
    PlaybookCreate,
    PlaybookDetail,
    PlaybookInstantiate,
    PlaybookList,
    PlaybookSummary,
    PlaybookUpdate,
)
from app.automations.services import PlaybookService, get_playbook_service

router = APIRouter()


def _playbook_detail(playbook: Playbook) -> PlaybookDetail:
    detail = PlaybookDetail.model_validate(playbook)
    definition = playbook.definition or {}
    metadata = definition.get("metadata") or {}
    if "derived_from_automation_id" in metadata:
        detail.source_automation_id = metadata["derived_from_automation_id"]
    return detail


@router.post(
    "/playbooks",
    response_model=PlaybookDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_playbook(
    payload: PlaybookCreate,
    service: PlaybookService = Depends(get_playbook_service),
) -> PlaybookDetail:
    """Save an existing automation as a playbook template."""
    playbook = await service.create_from_automation(payload)
    return _playbook_detail(playbook)


@router.get("/playbooks", response_model=PlaybookList)
async def list_playbooks(
    workspace_id: int = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: PlaybookService = Depends(get_playbook_service),
) -> PlaybookList:
    """List playbooks for a workspace, including system playbooks."""
    items, total = await service.list_playbooks(
        workspace_id=workspace_id, limit=limit, offset=offset
    )
    return PlaybookList(
        items=[PlaybookSummary.model_validate(p) for p in items],
        total=total,
    )


@router.get("/playbooks/{playbook_id}", response_model=PlaybookDetail)
async def get_playbook(
    playbook_id: int,
    service: PlaybookService = Depends(get_playbook_service),
) -> PlaybookDetail:
    """Get a playbook template."""
    playbook = await service.get(playbook_id)
    return _playbook_detail(playbook)


@router.patch("/playbooks/{playbook_id}", response_model=PlaybookDetail)
async def update_playbook(
    playbook_id: int,
    patch: PlaybookUpdate,
    service: PlaybookService = Depends(get_playbook_service),
) -> PlaybookDetail:
    """Update a playbook. Definition changes bump the version."""
    playbook = await service.update(playbook_id, patch)
    return _playbook_detail(playbook)


@router.post(
    "/playbooks/{playbook_id}/instantiate",
    response_model=AutomationDetail,
    status_code=status.HTTP_201_CREATED,
)
async def instantiate_playbook(
    playbook_id: int,
    payload: PlaybookInstantiate,
    service: PlaybookService = Depends(get_playbook_service),
) -> AutomationDetail:
    """Create a new automation from a playbook, validating the supplied inputs."""
    automation = await service.instantiate(playbook_id, payload)
    return AutomationDetail.model_validate(automation)
