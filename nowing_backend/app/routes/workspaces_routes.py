"""Compat shim — workspace routes split into ``app/routes/workspaces/`` package.

Keeps ``from app.routes.workspaces_routes import router`` and
``create_default_roles_and_membership`` imports working for tests/app wiring.
"""

from app.routes.workspaces import create_default_roles_and_membership, router

__all__ = ["create_default_roles_and_membership", "router"]
