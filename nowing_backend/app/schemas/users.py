import uuid
from datetime import datetime

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    pages_limit: int
    pages_used: int
    monthly_token_limit: int
    tokens_used_this_month: int
    purchased_tokens: int = 0
    plan_id: str
    subscription_status: str
    subscription_current_period_end: datetime | None = None
    display_name: str | None = None
    avatar_url: str | None = None


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    avatar_url: str | None = None
