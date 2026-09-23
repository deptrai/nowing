"""Workspace routes package (split from workspaces_routes.py)."""

from __future__ import annotations

from fastapi import APIRouter

from .bulk_ops import router as bulk_ops_router
from .core import create_default_roles_and_membership, router as core_router
from .settings import router as settings_router
from .subscriptions import router as subscriptions_router

router = APIRouter()
router.include_router(core_router)
router.include_router(settings_router)
router.include_router(subscriptions_router)
router.include_router(bulk_ops_router)

__all__ = ["create_default_roles_and_membership", "router"]
