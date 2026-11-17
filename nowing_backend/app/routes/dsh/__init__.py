"""DSH routes package."""

from __future__ import annotations

from fastapi import APIRouter

dsh_public_router = APIRouter()
dsh_internal_router = APIRouter()

from app.routes.dsh import cdp, missions, takeover  # noqa: E402, F401

__all__ = ["dsh_internal_router", "dsh_public_router"]
