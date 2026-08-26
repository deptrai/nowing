import uuid
from typing import Any

from fastapi_users import schemas
from pydantic import BaseModel, field_validator


class UserRead(schemas.BaseUser[uuid.UUID]):
    credit_micros_balance: int
    display_name: str | None = None
    avatar_url: str | None = None
    notification_preferences: dict[str, Any] | None = None


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    avatar_url: str | None = None
    notification_preferences: dict[str, Any] | None = None

    @field_validator("notification_preferences", mode="before")
    @classmethod
    def _coerce_notification_preferences(cls, value: Any) -> dict[str, Any]:
        return {} if value is None else value


class UserNotificationPreferencesUpdate(BaseModel):
    notification_preferences: dict[str, Any]


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
