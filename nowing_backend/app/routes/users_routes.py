"""Cookie-aware user profile routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import User, get_async_session
from app.schemas import UserRead
from app.schemas.users import UserNotificationPreferencesUpdate, UserUpdate
from app.users import (
    UserManager,
    get_auth_context,
    get_user_manager,
    require_session_context,
)

router = APIRouter(prefix="/users", tags=["users"])


def _merge_notification_preferences(
    current: dict[str, Any] | None,
    incoming: dict[str, Any],
) -> dict[str, Any]:
    """Deep-merge incoming notification preferences into the existing map."""
    merged: dict[str, Any] = dict(current) if isinstance(current, dict) else {}
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_notification_preferences(merged[key], value)
        else:
            merged[key] = value
    return merged


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    auth: AuthContext = Depends(get_auth_context),
):
    return auth.user


@router.patch("/me", response_model=UserRead)
async def update_current_user_profile(
    update: UserUpdate,
    request: Request,
    auth: AuthContext = Depends(require_session_context),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_async_session),
):
    # Lock the user row to prevent races on concurrent profile updates.
    stmt = (
        select(User)
        .where(User.id == auth.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    locked_user = result.scalar_one_or_none()
    if locked_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Deep-merge notification preferences so a partial update does not clobber
    # unrelated channels.
    if update.notification_preferences is not None:
        merged = _merge_notification_preferences(
            locked_user.notification_preferences,
            update.notification_preferences,
        )
        update = update.model_copy(update={"notification_preferences": merged})

    updated_user = await user_manager.update(
        update, locked_user, safe=True, request=request
    )
    return updated_user


@router.patch("/me/notification-preferences", response_model=UserRead)
async def update_current_user_notification_preferences(
    update: UserNotificationPreferencesUpdate,
    request: Request,
    auth: AuthContext = Depends(require_session_context),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_async_session),
):
    # Lock the user row to prevent race conditions during concurrent merges (Story 30.4)
    stmt = (
        select(User)
        .where(User.id == auth.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    locked_user = result.scalar_one_or_none()
    if locked_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    merged = _merge_notification_preferences(
        locked_user.notification_preferences,
        update.notification_preferences,
    )
    updated_user = await user_manager.update(
        UserUpdate(notification_preferences=merged),
        locked_user,
        safe=True,
        request=request,
    )
    return updated_user
