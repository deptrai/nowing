"""Compat shim — RBAC routes split into ``app/routes/rbac/`` package.

Keeps ``from app.routes.rbac_routes import router`` working and re-exports
``check_permission`` (historically imported from this module by other routes).
"""

from app.routes.rbac import router
from app.utils.rbac import check_permission

__all__ = ["check_permission", "router"]
