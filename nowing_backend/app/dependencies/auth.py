"""Permission-based FastAPI dependencies for RBAC endpoints.

This module provides declarative wrappers around ``app.utils.rbac.check_permission``
and ``check_workspace_access`` so endpoints can declare access requirements
via ``Depends(RequirePermission(...))`` instead of manual inline calls.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import WorkspaceMembership, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission, check_workspace_access


async def _resolve_permission(
    workspace_id: int,
    session: AsyncSession,
    auth: AuthContext,
    permission: str,
    message: str,
) -> WorkspaceMembership:
    """Wrapper around rbac.check_permission compatible with Depends."""
    return await check_permission(
        session, auth, workspace_id, permission, message
    )


class RequirePermission:
    """FastAPI dependency factory that enforces a specific workspace permission.

    Usage::
        @router.put("/workspaces/{workspace_id}")
        async def update(
            workspace_id: int,
            _membership: Annotated[
                WorkspaceMembership,
                Depends(
                    RequirePermission(
                        Permission.SETTINGS_UPDATE.value,
                        "You don't have permission to update this workspace",
                    )
                ),
            ],
        ) -> dict:
            ...

    The dependency resolves ``workspace_id`` from path parameters and enforces
    the permission via ``check_permission``, returning the membership.
    """

    def __init__(
        self,
        permission: str,
        message: str = "You don't have permission to perform this action",
    ) -> None:
        self.permission = permission
        self.message = message

    async def __call__(
        self,
        workspace_id: int,
        session: Annotated[AsyncSession, Depends(get_async_session)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> WorkspaceMembership:
        """Enforce the permission and return the workspace membership."""
        return await _resolve_permission(
            workspace_id, session, auth, self.permission, self.message
        )


class RequireWorkspaceAccess:
    """FastAPI dependency that enforces workspace access (membership only)."""

    async def __call__(
        self,
        workspace_id: int,
        session: Annotated[AsyncSession, Depends(get_async_session)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> WorkspaceMembership:
        """Enforce workspace access and return the workspace membership."""
        return await check_workspace_access(session, auth, workspace_id)


__all__ = ["RequirePermission", "RequireWorkspaceAccess"]
