"""Permission helpers used across routes, services, and tasks."""

from __future__ import annotations

from app.db.enums import (
    DEFAULT_ROLE_PERMISSIONS,
    Permission,
)


def has_permission(user_permissions: list[str], required_permission: str) -> bool:
    """Check if the user has the required permission.

    Supports wildcard (*) for full access.
    """
    if not user_permissions:
        return False

    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return required_permission in user_permissions


def has_any_permission(
    user_permissions: list[str], required_permissions: list[str]
) -> bool:
    """Check if the user has any of the required permissions."""
    if not user_permissions:
        return False

    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return any(perm in user_permissions for perm in required_permissions)


def has_all_permissions(
    user_permissions: list[str], required_permissions: list[str]
) -> bool:
    """Check if the user has all of the required permissions."""
    if not user_permissions:
        return False

    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return all(perm in user_permissions for perm in required_permissions)


def get_default_roles_config() -> list[dict]:
    """Get the configuration for default system roles.

    Only 3 roles are supported:
    - Owner: Full access to everything
    - Editor: Create/update but no delete, role management, or settings
    - Viewer: Read-only
    """
    return [
        {
            "name": "Owner",
            "description": "Full access to all workspace resources and settings",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Owner"],
            "is_default": False,
            "is_system_role": True,
        },
        {
            "name": "Editor",
            "description": "Can create and update content (no delete, role management, or settings access)",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Editor"],
            "is_default": True,
            "is_system_role": True,
        },
        {
            "name": "Viewer",
            "description": "Read-only access to workspace resources",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Viewer"],
            "is_default": False,
            "is_system_role": True,
        },
    ]
