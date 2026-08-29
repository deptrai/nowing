"""Cookie-aware user profile routes."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.auth.context import AuthContext
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
):
    updated_user = await user_manager.update(
        update, auth.user, safe=True, request=request
    )
    return updated_user


@router.patch("/me/notification-preferences", response_model=UserRead)
async def update_current_user_notification_preferences(
    update: UserNotificationPreferencesUpdate,
    request: Request,
    auth: AuthContext = Depends(require_session_context),
    user_manager: UserManager = Depends(get_user_manager),
):
    merged = _merge_notification_preferences(
        auth.user.notification_preferences,
        update.notification_preferences,
    )
    updated_user = await user_manager.update(
        UserUpdate(notification_preferences=merged),
        auth.user,
        safe=True,
        request=request,
    )
    return updated_user
