"""Permission-based FastAPI dependencies for RBAC endpoints.

This module provides declarative wrappers around ``app.utils.rbac.check_permission``
and ``check_workspace_access`` so endpoints can declare access requirements
via ``Depends(RequirePermission(...))`` instead of manual inline calls.
"""

from typing import Annotated

from fastapi import Depends, Request
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



# --- Dynamic workspace_id resolvers ---


def _get_model_class(model_name: str) -> type:
    """Resolve a model class by name from app.db."""
    import app.db as db_module

    cls = getattr(db_module, model_name, None)
    if cls is None:
        raise ValueError(f"Unknown model: {model_name}")
    return cls


class RequirePermissionFromEntity:
    """Enforce permission by resolving ``workspace_id`` from a DB entity.

    The entity is looked up by a path/query parameter (e.g. ``folder_id``),
    then ``entity.workspace_id`` is checked against ``check_permission``.

    Usage::

        @router.get("/folders/{folder_id}")
        async def get_folder(
            folder_id: int,
            _membership: WorkspaceMembership = Depends(
                RequirePermissionFromEntity(
                    "Folder", "folder_id",
                    Permission.DOCUMENTS_READ.value,
                    "You don't have permission to read folders",
                )
            ),
        ):
            ...
    """

    def __init__(
        self,
        model_name: str,
        id_param: str,
        permission: str,
        message: str = "You don't have permission to perform this action",
        not_found_detail: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.id_param = id_param
        self.permission = permission
        self.message = message
        self.not_found_detail = not_found_detail or f"{model_name} not found"

    async def __call__(
        self,
        request: "Request",
        session: Annotated[AsyncSession, Depends(get_async_session)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> WorkspaceMembership:
        from fastapi import HTTPException
        from sqlalchemy import select

        # Resolve the entity ID from path params or query params
        entity_id_str = request.path_params.get(self.id_param)
        if entity_id_str is None:
            entity_id_str = request.query_params.get(self.id_param)
        if entity_id_str is None:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required parameter: {self.id_param}",
            )
        try:
            entity_id = int(entity_id_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {self.id_param}: must be an integer",
            ) from None

        model_cls = _get_model_class(self.model_name)
        result = await session.execute(
            select(model_cls).where(model_cls.id == entity_id)
        )
        entity = result.scalars().first()
        if entity is None:
            raise HTTPException(status_code=404, detail=self.not_found_detail)

        workspace_id = entity.workspace_id
        if workspace_id is None:
            raise HTTPException(
                status_code=403,
                detail="Resource does not belong to a workspace",
            )

        return await _resolve_permission(
            workspace_id, session, auth, self.permission, self.message
        )


class RequireWorkspaceAccessFromEntity:
    """Enforce workspace access by resolving ``workspace_id`` from a DB entity.

    Same as ``RequirePermissionFromEntity`` but calls ``check_workspace_access``
    (membership check only, no specific permission).
    """

    def __init__(
        self,
        model_name: str,
        id_param: str,
        not_found_detail: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.id_param = id_param
        self.not_found_detail = not_found_detail or f"{model_name} not found"

    async def __call__(
        self,
        request: "Request",
        session: Annotated[AsyncSession, Depends(get_async_session)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> WorkspaceMembership:
        from fastapi import HTTPException
        from sqlalchemy import select

        entity_id_str = request.path_params.get(self.id_param)
        if entity_id_str is None:
            entity_id_str = request.query_params.get(self.id_param)
        if entity_id_str is None:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required parameter: {self.id_param}",
            )
        try:
            entity_id = int(entity_id_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {self.id_param}: must be an integer",
            ) from None

        model_cls = _get_model_class(self.model_name)
        result = await session.execute(
            select(model_cls).where(model_cls.id == entity_id)
        )
        entity = result.scalars().first()
        if entity is None:
            raise HTTPException(status_code=404, detail=self.not_found_detail)

        workspace_id = entity.workspace_id
        if workspace_id is None:
            raise HTTPException(
                status_code=403,
                detail="Resource does not belong to a workspace",
            )

        return await check_workspace_access(session, auth, workspace_id)


class RequirePermissionFromBody:
    """Enforce permission by resolving ``workspace_id`` from the request body.

    The body is parsed as JSON and ``workspace_id`` is extracted from it.
    Works with any body param name (``request``, ``body``, ``data``, etc.)
    as long as the body has a ``workspace_id`` field.

    Usage::

        @router.post("/folders")
        async def create_folder(
            request: FolderCreate,
            _membership: WorkspaceMembership = Depends(
                RequirePermissionFromBody(
                    Permission.DOCUMENTS_CREATE.value,
                    "You don't have permission to create folders",
                )
            ),
        ):
            ...
    """

    def __init__(
        self,
        permission: str,
        message: str = "You don't have permission to perform this action",
        body_field: str = "workspace_id",
    ) -> None:
        self.permission = permission
        self.message = message
        self.body_field = body_field

    async def __call__(
        self,
        request: "Request",
        session: Annotated[AsyncSession, Depends(get_async_session)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> WorkspaceMembership:
        from fastapi import HTTPException

        body = await request.json()
        workspace_id = body.get(self.body_field)
        if workspace_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {self.body_field}",
            )

        return await _resolve_permission(
            workspace_id, session, auth, self.permission, self.message
        )


class RequireWorkspaceAccessFromBody:
    """Enforce workspace access by resolving ``workspace_id`` from request body."""

    def __init__(self, body_field: str = "workspace_id") -> None:
        self.body_field = body_field

    async def __call__(
        self,
        request: "Request",
        session: Annotated[AsyncSession, Depends(get_async_session)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> WorkspaceMembership:
        from fastapi import HTTPException

        body = await request.json()
        workspace_id = body.get(self.body_field)
        if workspace_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {self.body_field}",
            )

        return await check_workspace_access(session, auth, workspace_id)


__all__ = [
    "RequirePermission",
    "RequirePermissionFromBody",
    "RequirePermissionFromEntity",
    "RequireWorkspaceAccess",
    "RequireWorkspaceAccessFromBody",
    "RequireWorkspaceAccessFromEntity",
]
