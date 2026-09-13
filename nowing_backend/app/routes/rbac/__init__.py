"""RBAC routes package (split from rbac_routes.py)."""

from __future__ import annotations

from fastapi import APIRouter

from .invites import router as invites_router
from .members import router as members_router
from .roles import router as roles_router

router = APIRouter()
router.include_router(roles_router)
router.include_router(members_router)
router.include_router(invites_router)

__all__ = ["router"]
