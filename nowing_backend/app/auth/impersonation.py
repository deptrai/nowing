from datetime import UTC, datetime

import jwt
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import config
from app.db import User
from app.users import SECRET


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


class ImpersonationGuardMiddleware(BaseHTTPMiddleware):
    """Block destructive security operations during an impersonation session.

    FastAPI-Users routers for /auth and /users do not expose per-route
    dependency injection, so we gate the sensitive paths at the ASGI layer.
    """

    # (method, path) pairs that mutate credentials or account state
    BLOCKED_PREFIXES: tuple[tuple[str, str], ...] = (
        ("DELETE", "/users/me"),
        ("PATCH", "/users/me"),
        ("POST", "/auth/reset-password"),
        ("POST", "/auth/forgot-password"),
        ("POST", "/auth/jwt/logout-all"),
    )

    def _is_blocked(self, method: str, path: str) -> bool:
        for m, prefix in self.BLOCKED_PREFIXES:
            if m == method and path.startswith(prefix):
                return True
        return False

    def _is_impersonation(self, request: Request) -> bool:
        token = None

        auth_header = request.headers.get("Authorization")
        if auth_header:
            scheme, _, credential = auth_header.partition(" ")
            if scheme.lower() == "bearer" and credential:
                token = credential

        if token is None:
            token = request.cookies.get(config.SESSION_COOKIE_NAME)

        if token is None:
            return False

        try:
            payload = jwt.decode(
                token,
                SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except Exception:
            return False

        return bool(payload.get("is_impersonation", False))

    async def dispatch(self, request: Request, call_next):
        if self._is_blocked(request.method, request.url.path) and self._is_impersonation(request):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "This action is not allowed during an impersonation session"},
            )

        return await call_next(request)
