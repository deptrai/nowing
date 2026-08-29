"""Document routes package."""

from __future__ import annotations

from fastapi import APIRouter

from app.routes.documents.crud import router as crud_router
from app.routes.documents.folders import router as folders_router
from app.routes.documents.upload import router as upload_router
from app.routes.documents.versions import router as versions_router

router = APIRouter()
router.include_router(crud_router)
router.include_router(upload_router)
router.include_router(versions_router)
router.include_router(folders_router)

__all__ = ["router"]
