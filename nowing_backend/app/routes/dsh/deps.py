from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request, status

from app.auth.context import AuthContext
from app.config import config
from app.db import DshMission
from app.users import get_auth_context


def _verify_dsh_worker_secret(request: Request) -> bool:
    """Constant-time compare the sidecar secret header to the configured secret."""
    header_secret = request.headers.get("X-Dsh-Worker-Secret", "")
    expected = config.DSH_WORKER_SECRET
    if not expected or not header_secret:
        return False
    return hmac.compare_digest(header_secret, expected)


async def require_dsh_worker(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Internal dependency for sidecar -> checkpoint route.

    Verifies the shared ``X-Dsh-Worker-Secret`` and that the caller is
    PAT-authenticated. Workspace scoping is checked against the mission row
    inside the route.
    """
    if not _verify_dsh_worker_secret(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid DSH worker secret",
        )
    if auth.pat is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSH worker requires a PAT",
        )
    return auth


def _require_pat_workspace_scope(
    auth: AuthContext,
    mission_workspace_id: int,
) -> None:
    """Reject global PATs and workspace mismatches on internal routes."""
    if auth.pat is None or auth.pat.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSH worker PAT must be workspace-scoped",
        )
    if auth.pat.workspace_id != mission_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PAT workspace does not match mission workspace",
        )


def _require_mission_access(auth: AuthContext, mission: DshMission) -> None:
    """Verify the caller owns or has workspace-scoped PAT access to the mission."""
    if auth.method == "pat":
        if auth.pat is None or auth.pat.workspace_id != mission.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="PAT workspace does not match mission workspace",
            )
    else:
        if mission.user_id != auth.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )


__all__ = [
    "_require_mission_access",
    "_require_pat_workspace_scope",
    "_verify_dsh_worker_secret",
    "require_dsh_worker",
]
