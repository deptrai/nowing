"""New chat routes package."""

from __future__ import annotations

from fastapi import APIRouter

from app.routes.new_chat.agent_tools import router as agent_tools_router
from app.routes.new_chat.chat import router as chat_router
from app.routes.new_chat.messages import router as messages_router
from app.routes.new_chat.regenerate import router as regenerate_router
from app.routes.new_chat.resume import router as resume_router
from app.routes.new_chat.snapshots import router as snapshots_router
from app.routes.new_chat.threads import router as threads_router

router = APIRouter()
router.include_router(threads_router)
router.include_router(snapshots_router)
router.include_router(messages_router)
router.include_router(agent_tools_router)
router.include_router(chat_router)
router.include_router(regenerate_router)
router.include_router(resume_router)

__all__ = ["router"]
