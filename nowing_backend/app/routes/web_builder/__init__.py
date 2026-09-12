"""Web builder routes package (split from web_builder_routes.py)."""

from __future__ import annotations

from fastapi import APIRouter

from .apps import router as apps_router
from .generate import router as generate_router
from .host import host_router
from .preview import router as preview_router

router = APIRouter(prefix="/api/v1/web-builder", tags=["web-builder"])
router.include_router(generate_router)
router.include_router(apps_router)
router.include_router(preview_router)

__all__ = ["host_router", "router"]
