from datetime import UTC, datetime

import jwt
from fastapi import HTTPException, status

from app.config import config
from app.db import User


def create_impersonation_token(
    admin_user: User, target_user: User, ticket_ref: str, ttl_seconds: int = 900
) -> str:
    """
    Generate a scoped impersonation JWT.
    """
    if not admin_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can impersonate",
        )
    if not 1 <= ttl_seconds <= 3600:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ttl_seconds must be between 1 and 3600",
        )

    payload = {
        "sub": str(target_user.id),
        "aud": ["fastapi-users:auth"],
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(datetime.now(UTC).timestamp()) + ttl_seconds,
        "impersonated_by": str(admin_user.id),
        "target_user": str(target_user.id),
        "is_impersonation": True,
        "ticket_ref": ticket_ref,
    }
    
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")
