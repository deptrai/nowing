"""Public catalog of registered actions."""

from __future__ import annotations

from fastapi import APIRouter

import app.automations  # noqa: F401  -- ensure bundled actions are registered
from app.automations.actions.store import all_actions
from app.automations.schemas.api.action import ActionCatalogItem

router = APIRouter()


@router.get("/automations/actions")
async def list_actions() -> list[ActionCatalogItem]:
    """Return every registered action with its params schema and UI metadata."""
    return [
        ActionCatalogItem(
            type=action.type,
            name=action.business_name or action.name,
            description=action.description,
            params_schema=action.params_schema,
            verticals=action.verticals,
            business_name=action.business_name,
        )
        for action in all_actions().values()
    ]
