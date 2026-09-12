"""Compat shim — web builder routes split into ``app/routes/web_builder/``.

Keeps ``from app.routes.web_builder_routes import router, host_router`` working
and re-exports symbols patched/imported by tests.
"""

from app.routes.web_builder import host_router, router
from app.routes.web_builder._helpers import (
    check_web_builder_enabled,
    is_web_builder_enabled_for_workspace,
    require_build_quota,
    require_workspace_member,
)
from app.routes.web_builder.apps import (
    BuilderService,
    WebAppDeployService,
    record_token_usage,
)
from app.routes.web_builder.generate import WebBuilderService
from app.routes.web_builder.preview import _allowed_preview_origin

__all__ = [
    "BuilderService",
    "WebAppDeployService",
    "WebBuilderService",
    "_allowed_preview_origin",
    "check_web_builder_enabled",
    "host_router",
    "is_web_builder_enabled_for_workspace",
    "record_token_usage",
    "require_build_quota",
    "require_workspace_member",
    "router",
]
