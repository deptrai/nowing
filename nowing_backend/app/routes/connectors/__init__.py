"""Connector routes package."""

from __future__ import annotations

from fastapi import APIRouter

from .crud import router as crud_router
from .indexing import router as indexing_router
from .mcp import router as mcp_router

router = APIRouter()

router.include_router(crud_router, tags=["connectors"])
router.include_router(indexing_router, tags=["connectors"])
router.include_router(mcp_router, tags=["connectors"])

__all__ = ["router"]
