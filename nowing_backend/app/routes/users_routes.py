"""Cookie-aware user profile routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.context import AuthContext
from app.schemas import UserRead
from app.schemas.users import (
    ChangePasswordRequest,
    UserNotificationPreferencesUpdate,
    UserUpdate,
)
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


@router.post("/me/change-password", response_model=UserRead)
async def change_current_user_password(
    body: ChangePasswordRequest,
    request: Request,
    auth: AuthContext = Depends(require_session_context),
    user_manager: UserManager = Depends(get_user_manager),
):
    """Change the current user's password after verifying the current one."""
    user = auth.user

    if user.hashed_password:
        is_valid, _ = user_manager.password_helper.verify_and_update(
            body.current_password, user.hashed_password
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_CURRENT_PASSWORD",
            )

    await user_manager.validate_password(body.new_password, user)
    hashed_password = user_manager.password_helper.hash(body.new_password)
    updated_user = await user_manager._update(user, {"hashed_password": hashed_password})
    await user_manager.on_after_update(updated_user, {"hashed_password": hashed_password}, request)
    return updated_user
