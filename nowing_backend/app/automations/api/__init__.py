"""HTTP layer for the automations feature."""

from __future__ import annotations

from fastapi import APIRouter

from .action_catalog import router as action_catalog_router
from .automation import router as automation_router
from .playbook import router as playbook_router
from .run import router as run_router
from .trigger import router as trigger_router

router = APIRouter()
# Catalog is mounted first so ``/actions`` does not shadow the
# ``/{automation_id}`` path under ``/automations``.
router.include_router(action_catalog_router)
router.include_router(automation_router)
router.include_router(playbook_router)
router.include_router(trigger_router)
router.include_router(run_router)

__all__ = ["router"]
