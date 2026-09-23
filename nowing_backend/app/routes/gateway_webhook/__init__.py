"""Gateway webhook routes package (split from gateway_webhook_routes.py)."""

from __future__ import annotations

from fastapi import APIRouter

from .bindings import router as bindings_router
from .config_ep import config_router
from .oauth import router as oauth_router
from .webhooks import router as webhooks_router

router = APIRouter(prefix="/gateway", tags=["gateway"])
router.include_router(oauth_router)
router.include_router(webhooks_router)
router.include_router(bindings_router)

__all__ = ["config_router", "router"]
