diff --git a/nowing_backend/alembic/versions/232_add_web_builder_enabled_and_permission.py b/nowing_backend/alembic/versions/232_add_web_builder_enabled_and_permission.py
new file mode 100644
index 000000000..9b22a4f4b
--- /dev/null
+++ b/nowing_backend/alembic/versions/232_add_web_builder_enabled_and_permission.py
@@ -0,0 +1,68 @@
+"""add web_builder_enabled to workspaces and web_builder:create permission (Story 27.1a)
+
+Revision ID: 232
+Revises: 231
+"""
+
+from collections.abc import Sequence
+
+import sqlalchemy as sa
+
+from alembic import op
+
+revision: str = "232"
+down_revision: str | None = "231"
+branch_labels: str | Sequence[str] | None = None
+depends_on: str | Sequence[str] | None = None
+
+
+def _table_exists(table_name: str) -> bool:
+    from sqlalchemy.engine import reflection
+    bind = op.get_context().bind
+    inspector = reflection.Inspector.from_engine(bind)
+    return table_name in inspector.get_table_names()
+
+
+def _column_exists(table_name: str, column_name: str) -> bool:
+    from sqlalchemy.engine import reflection
+    bind = op.get_context().bind
+    inspector = reflection.Inspector.from_engine(bind)
+    return any(c["name"] == column_name for c in inspector.get_columns(table_name))
+
+
+def upgrade() -> None:
+    if _table_exists("workspaces") and not _column_exists("workspaces", "web_builder_enabled"):
+        op.add_column(
+            "workspaces",
+            sa.Column(
+                "web_builder_enabled",
+                sa.Boolean(),
+                nullable=False,
+                server_default=sa.text("true"),
+            ),
+        )
+
+    # Backfill the Editor system role with the new web_builder:create permission.
+    op.execute(
+        """
+        UPDATE workspace_roles
+        SET permissions = array_append(permissions, 'web_builder:create')
+        WHERE name = 'Editor'
+          AND is_system_role = true
+          AND NOT 'web_builder:create' = ANY(permissions);
+        """
+    )
+
+
+def downgrade() -> None:
+    if _table_exists("workspaces") and _column_exists("workspaces", "web_builder_enabled"):
+        op.drop_column("workspaces", "web_builder_enabled")
+
+    op.execute(
+        """
+        UPDATE workspace_roles
+        SET permissions = array_remove(permissions, 'web_builder:create')
+        WHERE name = 'Editor'
+          AND is_system_role = true;
+        """
+    )
diff --git a/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/index.py b/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/index.py
index 67eebc91e..277f50f7c 100644
--- a/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/index.py
+++ b/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/index.py
@@ -9,6 +9,7 @@ MAIN_AGENT_NOWING_TOOL_NAMES_ORDERED: tuple[str, ...] = (
     "update_memory",
     "create_automation",
     "multi_source_lead_gen",
+    "build_web_app",
 )
 
 MAIN_AGENT_NOWING_TOOL_NAMES: frozenset[str] = frozenset(
diff --git a/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py b/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py
index c15e4efcf..447e6c03a 100644
--- a/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py
+++ b/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py
@@ -28,6 +28,7 @@ from .update_memory import (
     create_update_memory_tool,
     create_update_team_memory_tool,
 )
+from .web_builder.build_web_app import create_build_web_app_tool
 
 
 def _build_multi_source_lead_gen_tool(deps: dict[str, Any]) -> BaseTool:
@@ -85,6 +86,10 @@ _MAIN_AGENT_TOOL_FACTORIES: dict[
         _build_multi_source_lead_gen_tool,
         ("workspace_id",),
     ),
+    "build_web_app": (
+        create_build_web_app_tool,
+        ("workspace_id", "user_id"),
+    ),
 }
 
 _logger = logging.getLogger(__name__)
diff --git a/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py b/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py
new file mode 100644
index 000000000..d91fcfa00
--- /dev/null
+++ b/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py
@@ -0,0 +1,172 @@
+"""Main-agent tool for generating a sales/marketing web app (Story 27.1a)."""
+
+from __future__ import annotations
+
+import contextlib
+import logging
+from typing import Any
+from uuid import UUID
+
+from langchain_core.tools import tool
+
+from app.db import async_session_maker
+
+logger = logging.getLogger(__name__)
+
+
+def create_build_web_app_tool(deps: dict[str, Any]):
+    """Factory for the ``build_web_app`` chat tool."""
+
+    workspace_id: int = deps["workspace_id"]
+    user_id_val = deps.get("user_id")
+    user_id: UUID | None = None
+    if user_id_val:
+        try:
+            user_id = (
+                user_id_val if isinstance(user_id_val, UUID) else UUID(str(user_id_val))
+            )
+        except (ValueError, TypeError, AttributeError):
+            logger.warning("build_web_app: invalid user_id %r", user_id_val)
+
+    @tool
+    async def build_web_app(
+        prompt: str,
+        app_name: str | None = None,
+        language: str = "en",
+        app_id: str | None = None,
+    ) -> str:
+        """Build or modify a lightweight sales/marketing Next.js web app from a description.
+
+        Use this tool when the user wants to create or modify a landing page, pricing page,
+        lead capture form, waitlist, or marketing report site.
+        Pass app_id if refining an existing app created earlier in the conversation.
+
+        Args:
+            prompt: Natural language description of the desired web app or requested modification.
+            app_name: Optional override for the generated app name/slug.
+            language: Target UI language (e.g. "en" or "vi").
+            app_id: Optional existing app ID when modifying an existing application in follow-up turns.
+        """
+        from sqlalchemy import select
+        from sqlalchemy.orm import selectinload
+
+        from app.config import config as app_config
+        from app.db import Workspace, WorkspaceMembership
+        from app.services.web_builder.generator import WebBuilderService
+        from app.services.web_builder.schemas import (
+            WebAppBuildInput,
+            WebAppBuildOutput,
+        )
+
+        if not app_config.WEB_BUILDER_ENABLED:
+            return WebAppBuildOutput(
+                app_id=app_id or "",
+                workspace_id=workspace_id,
+                name=app_name or "Web App",
+                slug="",
+                status="validation_failed",
+                error="Web Builder is not enabled on this workspace plan",
+            ).model_dump_json()
+
+        if not prompt or not prompt.strip():
+            return WebAppBuildOutput(
+                app_id=app_id or "",
+                workspace_id=workspace_id,
+                name=app_name or "Web App",
+                slug="",
+                status="validation_failed",
+                error="Prompt is required for build_web_app",
+            ).model_dump_json()
+
+        prompt = prompt.strip()
+        if len(prompt) > app_config.WEB_BUILDER_MAX_PROMPT_CHARS:
+            return WebAppBuildOutput(
+                app_id=app_id or "",
+                workspace_id=workspace_id,
+                name=app_name or "Web App",
+                slug="",
+                status="validation_failed",
+                error=(
+                    f"Prompt exceeds maximum allowed length of "
+                    f"{app_config.WEB_BUILDER_MAX_PROMPT_CHARS} characters."
+                ),
+            ).model_dump_json()
+
+        build_input = WebAppBuildInput(
+            prompt=prompt,
+            workspace_id=workspace_id,
+            user_id=user_id,
+            app_id=app_id,
+            app_name=app_name,
+            language=language,
+        )
+
+        service = WebBuilderService(
+            storage_base_path=app_config.FILE_STORAGE_LOCAL_PATH,
+        )
+
+        session = None
+        try:
+            async with async_session_maker() as session_:
+                session = session_
+
+                # Re-check workspace gating in case plan changed since thread start.
+                ws = (
+                    await session.execute(
+                        select(Workspace).where(Workspace.id == workspace_id)
+                    )
+                ).scalars().first()
+                if ws is None or ws.web_builder_enabled is False:
+                    return WebAppBuildOutput(
+                        app_id=app_id or "",
+                        workspace_id=workspace_id,
+                        name=app_name or "Web App",
+                        slug="",
+                        status="validation_failed",
+                        error="Web Builder is not enabled on this workspace plan",
+                    ).model_dump_json()
+
+                # Best-effort membership check (tool may be called after a role change).
+                membership = (
+                    await session.execute(
+                        select(WorkspaceMembership)
+                        .where(
+                            WorkspaceMembership.user_id == user_id,
+                            WorkspaceMembership.workspace_id == workspace_id,
+                        )
+                        .options(selectinload(WorkspaceMembership.role))
+                    )
+                ).scalars().first()
+                if membership and not (
+                    membership.is_owner
+                    or (
+                        membership.role
+                        and "web_builder:create" in (membership.role.permissions or [])
+                    )
+                ):
+                    return WebAppBuildOutput(
+                        app_id=app_id or "",
+                        workspace_id=workspace_id,
+                        name=app_name or "Web App",
+                        slug="",
+                        status="validation_failed",
+                        error="You don't have permission to build web apps in this workspace",
+                    ).model_dump_json()
+
+                result = await service.generate_project(build_input, session=session)
+                return result.model_dump_json()
+        except Exception as exc:
+            if session is not None:
+                with contextlib.suppress(Exception):
+                    await session.rollback()
+            logger.exception("build_web_app failed: %s", exc)
+            return WebAppBuildOutput(
+                app_id="",
+                workspace_id=workspace_id,
+                name=app_name or "Web App",
+                slug="",
+                status="error",
+                error=f"Error building web app: {exc}",
+            ).model_dump_json()
+
+    return build_web_app
diff --git a/nowing_backend/app/config/__init__.py b/nowing_backend/app/config/__init__.py
index a21c445be..c06466190 100644
--- a/nowing_backend/app/config/__init__.py
+++ b/nowing_backend/app/config/__init__.py
@@ -855,7 +855,7 @@ class Config:
     NOWING_PUBLIC_URL = os.getenv("NOWING_PUBLIC_URL")
     NEXT_FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL") or NOWING_PUBLIC_URL
     # Backend URL to override the http to https in the OAuth redirect URI
-    BACKEND_URL = os.getenv("BACKEND_URL") or NOWING_PUBLIC_URL
+    BACKEND_URL = os.getenv("BACKEND_URL") or NOWING_PUBLIC_URL or "http://localhost:8000"
 
     # Messaging gateway
     # Global master switch: when FALSE, no gateway supervisors/workers start and all
@@ -1813,6 +1813,34 @@ class Config:
         if os.path.exists("/app")
         else "./.local_object_store",
     )
+    WEB_BUILDER_ENABLED = os.getenv("WEB_BUILDER_ENABLED", "TRUE").upper() == "TRUE"
+    WEB_BUILDER_MAX_PROMPT_CHARS = max(
+        1, _env_int("WEB_BUILDER_MAX_PROMPT_CHARS", 2000)
+    )
+    WEB_BUILDER_PUBLIC_APPS_PATH = os.getenv(
+        "WEB_BUILDER_PUBLIC_APPS_PATH",
+        f"{FILE_STORAGE_LOCAL_PATH}/web-apps",
+    )
+
+    PRESENTATION_STUDIO_ENABLED = (
+        os.getenv("PRESENTATION_STUDIO_ENABLED", "FALSE").upper() == "TRUE"
+    )
+    PRESENTATION_MAX_PROMPT_CHARS = max(
+        1, _env_int("PRESENTATION_MAX_PROMPT_CHARS", 2000)
+    )
+
+    MEETING_MINUTES_ENABLED = (
+        os.getenv("MEETING_MINUTES_ENABLED", "FALSE").upper() == "TRUE"
+    )
+    MEETING_MINUTES_MAX_PROMPT_CHARS = max(
+        1, _env_int("MEETING_MINUTES_MAX_PROMPT_CHARS", 2000)
+    )
+    MEETING_MINUTES_MAX_DURATION_SECONDS = max(
+        1, _env_int("MEETING_MINUTES_MAX_DURATION_SECONDS", 600)
+    )
+    MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND = max(
+        0, _env_int("MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND", 0)
+    )
 
     @classmethod
     def get_settings(cls):
diff --git a/nowing_backend/app/db.py b/nowing_backend/app/db.py
index 7f6c7bf6e..14bba7607 100644
--- a/nowing_backend/app/db.py
+++ b/nowing_backend/app/db.py
@@ -426,6 +426,9 @@ class Permission(StrEnum):
     # Full access wildcard
     FULL_ACCESS = "*"
 
+    # Web Builder (Story 27.1a)
+    WEB_BUILDER_CREATE = "web_builder:create"
+
 
 # Predefined role permission sets for convenience
 # Note: Only Owner, Editor, and Viewer roles are supported.
@@ -483,6 +486,8 @@ DEFAULT_ROLE_PERMISSIONS = {
         Permission.AUTOMATIONS_READ.value,
         Permission.AUTOMATIONS_UPDATE.value,
         Permission.AUTOMATIONS_EXECUTE.value,
+        # Web Builder (Story 27.1a)
+        Permission.WEB_BUILDER_CREATE.value,
         # Memory (no delete)
         Permission.MEMORY_CREATE.value,
         Permission.MEMORY_READ.value,
@@ -1940,6 +1945,9 @@ class Workspace(BaseModel, TimestampMixin):
     api_access_enabled = Column(
         Boolean, nullable=False, default=False, server_default="false"
     )
+    web_builder_enabled = Column(
+        Boolean, nullable=False, default=True, server_default="true"
+    )
     qna_custom_instructions = Column(
         Text, nullable=True, default=""
     )  # User's custom instructions
diff --git a/nowing_backend/app/routes/__init__.py b/nowing_backend/app/routes/__init__.py
index c10d4c15d..9bd724e56 100644
--- a/nowing_backend/app/routes/__init__.py
+++ b/nowing_backend/app/routes/__init__.py
@@ -135,7 +135,10 @@ from .team_memory_routes import router as team_memory_router
 from .teams_add_connector_route import router as teams_add_connector_router
 from .usage_routes import router as usage_router
 from .video_presentations_routes import router as video_presentations_router
-from .web_builder_routes import router as web_builder_router
+from .web_builder_routes import (
+    host_router as web_builder_host_router,
+    router as web_builder_router,
+)
 from .workspace_tables_routes import router as workspace_tables_router
 from .workspaces_routes import router as workspaces_router
 from .youtube_routes import router as youtube_router
@@ -254,5 +257,10 @@ router.include_router(team_memory_router)  # Workspace team memory
 router.include_router(automations_router)  # Automations CRUD + run history
 router.include_router(file_storage_router)  # Original file metadata + download
 router.include_router(extract_entities_router)  # Test entity extraction (AC-1 / AD-107)
-router.include_router(web_builder_router)  # Full-stack Web App Builder (Story 27.1 / AD-113)
+router.include_router(
+    web_builder_router
+)  # Full-stack Web App Builder (Story 27.1 / AD-113)
+router.include_router(
+    web_builder_host_router
+)  # Wildcard Host routing for published web apps
 router.include_router(build_capabilities_router())  # Scraper-API capability doors (05)
diff --git a/nowing_backend/app/routes/new_chat_routes.py b/nowing_backend/app/routes/new_chat_routes.py
index b95d4e1fb..963f12ad9 100644
--- a/nowing_backend/app/routes/new_chat_routes.py
+++ b/nowing_backend/app/routes/new_chat_routes.py
@@ -79,6 +79,10 @@ from app.tasks.chat.streaming.flows import (
     stream_resume_chat,
 )
 from app.tasks.chat.streaming.flows.new_chat.auto_pin import resolve_initial_auto_pin
+from app.tasks.chat.streaming.flows.new_chat.chat_modes import (
+    is_chat_mode_enabled,
+    resolve_chat_mode,
+)
 from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
 from app.tenant_context import set_request_tenant_context
 from app.users import get_auth_context
@@ -825,6 +829,23 @@ async def create_thread(
                 detail="client_id and agent_id are not accepted on internal threads",
             )
 
+        # Chat modes (web_builder, presentation_studio, meeting_minutes) are
+        # gated by a global feature flag and per-workspace setting (AD-120).
+        chat_mode = resolve_chat_mode(thread.platform_metadata)
+        if chat_mode.mode_id != "default":
+            ws = (
+                await session.execute(
+                    select(Workspace).where(Workspace.id == thread.workspace_id)
+                )
+            ).scalars().first()
+            if not is_chat_mode_enabled(
+                chat_mode, workspace=ws, app_config=config
+            ):
+                raise HTTPException(
+                    status_code=403,
+                    detail=chat_mode.error_message,
+                )
+
         # Set tenant GUCs before the insert so the 18.1 RLS WITH CHECK clause
         # on new_chat_threads allows client-scoped rows (here: unscoped/NULL).
         await set_request_tenant_context(
diff --git a/nowing_backend/app/routes/web_builder_routes.py b/nowing_backend/app/routes/web_builder_routes.py
index 40936ff40..7b61e26a7 100644
--- a/nowing_backend/app/routes/web_builder_routes.py
+++ b/nowing_backend/app/routes/web_builder_routes.py
@@ -2,20 +2,23 @@
 
 import contextlib
 import logging
+import re
 from pathlib import Path
 from typing import Annotated
 
-from fastapi import APIRouter, Depends, HTTPException, status
+from fastapi import APIRouter, Depends, HTTPException, Request, status
 from fastapi.responses import HTMLResponse, StreamingResponse
 from sqlalchemy import select
 from sqlalchemy.ext.asyncio import AsyncSession
 
 from app.auth.context import AuthContext
-from app.db import WorkspaceApp, get_async_session
+from app.config import config
+from app.db import Permission, Workspace, WorkspaceApp, get_async_session
+from app.routes.rbac_routes import check_permission
 from app.services.web_builder.deploy_service import WebAppDeployService
 from app.services.web_builder.generator import WebBuilderService
 from app.services.web_builder.mark_tool import MarkToolASTMutator
-from app.services.web_builder.preview_renderer import PreviewRenderer
+from app.services.web_builder.preview_renderer import WEB_BUILDER_CSP, PreviewRenderer
 from app.services.web_builder.project_writer import ProjectWriter
 from app.services.web_builder.schemas import (
     CustomDomainInput,
@@ -33,6 +36,32 @@ from app.users import get_auth_context
 logger = logging.getLogger(__name__)
 
 router = APIRouter(prefix="/api/v1/web-builder", tags=["web-builder"])
+host_router = APIRouter(tags=["web-builder-host"])
+
+
+async def require_workspace_member(
+    session: AsyncSession,
+    auth: AuthContext,
+    workspace_id: int,
+) -> AuthContext:
+    """Ensure the caller is a member of the workspace."""
+    await check_permission(
+        session,
+        auth,
+        workspace_id,
+        Permission.WEB_BUILDER_CREATE.value,
+        error_message="You don't have access to this workspace",
+    )
+    return auth
+
+
+def check_web_builder_enabled():
+    """Fail-closed gate checking WEB_BUILDER_ENABLED configuration."""
+    if not config.WEB_BUILDER_ENABLED:
+        raise HTTPException(
+            status_code=status.HTTP_403_FORBIDDEN,
+            detail="Web Builder is not enabled on this workspace plan",
+        )
 
 
 @router.post("/generate", response_model=WebAppBuildOutput)
@@ -42,6 +71,8 @@ async def generate_web_app(
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ) -> WebAppBuildOutput:
     """Generate Next.js + Tailwind project from a natural-language description (AC-1)."""
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, payload.workspace_id)
     payload.user_id = auth.user.id
     service = WebBuilderService()
     result = await service.generate_project(payload, session=session)
@@ -55,6 +86,8 @@ async def generate_web_app_stream(
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ):
     """Stream real-time Next.js code generation tokens and file writing steps via SSE."""
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, payload.workspace_id)
     payload.user_id = auth.user.id
     service = WebBuilderService()
     return StreamingResponse(
@@ -76,6 +109,18 @@ async def publish_web_app(
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ) -> WebAppDeployOutput:
     """1-Click publish app container and dynamic HTTPS route at *.apps.nowing.net (AC-2)."""
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, payload.workspace_id)
+    stmt = select(WorkspaceApp).where(
+        WorkspaceApp.id == app_id,
+        WorkspaceApp.workspace_id == payload.workspace_id,
+    )
+    res = await session.execute(stmt)
+    if not res.scalars().first():
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail="Application not found",
+        )
     deploy_service = WebAppDeployService()
     result = await deploy_service.deploy_app(
         app_id=app_id,
@@ -99,6 +144,8 @@ async def configure_custom_domain(
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ) -> CustomDomainOutput:
     """Configure and verify custom domain CNAME routing (AC-3)."""
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, payload.workspace_id)
     deploy_service = WebAppDeployService()
     result = await deploy_service.verify_and_bind_custom_domain(
         app_id=app_id,
@@ -122,6 +169,8 @@ async def apply_mark_tool_patch(
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ) -> MarkToolOutput:
     """Apply visual Mark Tool DOM-to-JSX AST mutation to component code (AC-4)."""
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, payload.workspace_id)
     stmt = select(WorkspaceApp).where(
         WorkspaceApp.id == app_id,
         WorkspaceApp.workspace_id == payload.workspace_id,
@@ -181,6 +230,8 @@ async def list_workspace_apps(
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ) -> list[WorkspaceAppRead]:
     """List all generated and published applications for a workspace (AC-5)."""
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, workspace_id)
     stmt = (
         select(WorkspaceApp)
         .where(WorkspaceApp.workspace_id == workspace_id)
@@ -198,6 +249,8 @@ async def get_workspace_app(
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ) -> WorkspaceAppRead:
     """Get single application details."""
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, workspace_id)
     stmt = select(WorkspaceApp).where(
         WorkspaceApp.id == app_id,
         WorkspaceApp.workspace_id == workspace_id,
@@ -215,16 +268,28 @@ async def get_workspace_app(
 @router.get("/apps/{app_id}/preview", response_class=HTMLResponse)
 async def get_workspace_app_preview(
     app_id: str,
+    workspace_id: int,
+    auth: Annotated[AuthContext, Depends(get_auth_context)],
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ) -> HTMLResponse:
     """Render and serve interactive live HTML preview for the generated web app."""
-    stmt = select(WorkspaceApp).where(WorkspaceApp.id == app_id)
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, workspace_id)
+    stmt = select(WorkspaceApp).where(
+        WorkspaceApp.id == app_id,
+        WorkspaceApp.workspace_id == workspace_id,
+    )
     res = await session.execute(stmt)
     app_entity = res.scalars().first()
+    if not app_entity:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail="Application not found",
+        )
 
     from app.config import FILE_STORAGE_LOCAL_PATH
 
-    if app_entity and app_entity.storage_path:
+    if app_entity.storage_path:
         project_dir = Path(app_entity.storage_path)
         if not project_dir.is_absolute():
             project_dir = (
@@ -233,8 +298,6 @@ async def get_workspace_app_preview(
                 / str(app_entity.workspace_id)
                 / app_id
             )
-    else:
-        project_dir = Path(FILE_STORAGE_LOCAL_PATH).resolve() / "web-app" / "1" / app_id
 
     if not project_dir.exists():
         project_dir.mkdir(parents=True, exist_ok=True)
@@ -246,7 +309,14 @@ async def get_workspace_app_preview(
         project_dir=project_dir,
         app_name=app_entity.name if app_entity else "Generated Web App",
     )
-    return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)
+    return HTMLResponse(
+        content=html_content,
+        status_code=status.HTTP_200_OK,
+        headers={
+            "Content-Security-Policy": WEB_BUILDER_CSP,
+            "X-Content-Type-Options": "nosniff",
+        },
+    )
 
 
 @router.get("/apps/{app_id}/files")
@@ -257,7 +327,12 @@ async def get_workspace_app_files(
     session: Annotated[AsyncSession, Depends(get_async_session)],
 ) -> dict[str, str]:
     """Retrieve all generated source code files for a given application."""
-    stmt = select(WorkspaceApp).where(WorkspaceApp.id == app_id)
+    check_web_builder_enabled()
+    await require_workspace_member(session, auth, workspace_id)
+    stmt = select(WorkspaceApp).where(
+        WorkspaceApp.id == app_id,
+        WorkspaceApp.workspace_id == workspace_id,
+    )
     res = await session.execute(stmt)
     app_entity = res.scalars().first()
     if not app_entity:
@@ -303,3 +378,78 @@ async def get_workspace_app_files(
                 files_dict[rel_path] = file_path.read_text(encoding="utf-8")
 
     return files_dict
+
+
+@host_router.get("/web-apps/host", response_class=HTMLResponse)
+@router.get("/host", response_class=HTMLResponse)
+async def host_web_app(
+    request: Request,
+    session: Annotated[AsyncSession, Depends(get_async_session)],
+) -> HTMLResponse:
+    """Serve published web app static HTML by Host header (Story 27.1a AC-4 / AC-6a)."""
+    host_header = request.headers.get("Host", "")
+    if not host_header:
+        raise HTTPException(
+            status_code=status.HTTP_400_BAD_REQUEST,
+            detail="Missing Host header",
+        )
+
+    host_clean = host_header.split(":")[0].strip().lower()
+    base_domain = config.HOSTING_BASE_DOMAIN.lower()
+    if base_domain and not host_clean.endswith(f".{base_domain}"):
+        raise HTTPException(
+            status_code=status.HTTP_400_BAD_REQUEST,
+            detail="Malformed host domain",
+        )
+    parts = host_clean.split(".")
+    if len(parts) < 2 or not parts[0]:
+        raise HTTPException(
+            status_code=status.HTTP_400_BAD_REQUEST,
+            detail="Malformed host domain",
+        )
+
+    slug = parts[0]
+    if not re.match(r"^[a-z0-9-]+$", slug):
+        raise HTTPException(
+            status_code=status.HTTP_400_BAD_REQUEST,
+            detail="Invalid host slug",
+        )
+
+    stmt = select(WorkspaceApp).where(
+        WorkspaceApp.slug == slug,
+        WorkspaceApp.status == "published",
+    )
+    res = await session.execute(stmt)
+    app_entity = res.scalars().first()
+    if not app_entity:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail="Web application not found",
+        )
+
+    ws_stmt = select(Workspace).where(Workspace.id == app_entity.workspace_id)
+    ws_res = await session.execute(ws_stmt)
+    ws = ws_res.scalars().first()
+    if ws and ws.web_builder_enabled is False:
+        raise HTTPException(
+            status_code=status.HTTP_403_FORBIDDEN,
+            detail="Web Builder is disabled for this workspace",
+        )
+
+    public_apps_base = Path(config.WEB_BUILDER_PUBLIC_APPS_PATH).resolve()
+    snapshot_file = public_apps_base / slug / "index.html"
+    if not snapshot_file.exists():
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail="Application static snapshot not found",
+        )
+
+    html_content = snapshot_file.read_text(encoding="utf-8")
+    return HTMLResponse(
+        content=html_content,
+        status_code=status.HTTP_200_OK,
+        headers={
+            "Content-Security-Policy": WEB_BUILDER_CSP,
+            "X-Content-Type-Options": "nosniff",
+        },
+    )
diff --git a/nowing_backend/app/services/web_builder/deploy_service.py b/nowing_backend/app/services/web_builder/deploy_service.py
index 4c2e36e6e..ee2b5ea73 100644
--- a/nowing_backend/app/services/web_builder/deploy_service.py
+++ b/nowing_backend/app/services/web_builder/deploy_service.py
@@ -1,5 +1,4 @@
-"""1-Click Instant Deployment & Domain Management Service (Story 27.1, AC-2, AC-3)."""
-
+import contextlib
 import logging
 import re
 from pathlib import Path
@@ -7,7 +6,7 @@ from pathlib import Path
 from sqlalchemy import select
 from sqlalchemy.ext.asyncio import AsyncSession
 
-from app.config import CNAME_INGRESS_HOST, FILE_STORAGE_LOCAL_PATH, HOSTING_BASE_DOMAIN
+from app.config import CNAME_INGRESS_HOST, HOSTING_BASE_DOMAIN
 from app.services.token_tracking_service import record_token_usage
 from app.services.web_builder.schemas import (
     CustomDomainOutput,
@@ -20,7 +19,10 @@ logger = logging.getLogger(__name__)
 def disambiguate_slug(base_slug: str, existing_slugs: set[str] | list[str]) -> str:
     """Generate a collision-free slug by appending incremental numeric suffixes."""
     existing = set(existing_slugs)
-    clean_base = re.sub(r"-\d+$", "", base_slug.strip().lower())
+    # Sanitize and truncate base_slug to DNS label safe format
+    cleaned = re.sub(r"[^a-z0-9-]", "-", base_slug.strip().lower())
+    clean_base = re.sub(r"-\d+$", "", cleaned).strip("-") or "app"
+    clean_base = clean_base[:50]  # allow room for numeric suffixes up to 63 chars
 
     if clean_base not in existing:
         return clean_base
@@ -33,7 +35,7 @@ def disambiguate_slug(base_slug: str, existing_slugs: set[str] | list[str]) -> s
 
 
 class WebAppDeployService:
-    """Builds, containerizes, and routes web applications dynamically via Traefik / Caddy."""
+    """Builds, publishes static HTML snapshots, and routes web applications dynamically."""
 
     def __init__(self, base_domain: str | None = None):
         self.base_domain = base_domain or HOSTING_BASE_DOMAIN
@@ -43,10 +45,13 @@ class WebAppDeployService:
         app_id: str,
         workspace_id: int,
         slug_override: str | None = None,
+        force: bool = False,
         session: AsyncSession | None = None,
     ) -> WebAppDeployOutput:
-        """Publish a generated project to https://{slug}.apps.nowing.net with SSL."""
+        """Publish a generated project to https://{slug}.apps.nowing.net (Option A Static Snapshot)."""
+        from app.config import config as app_config
         from app.db import WorkspaceApp
+        from app.services.web_builder.preview_renderer import PreviewRenderer
 
         app_entity: WorkspaceApp | None = None
         if session:
@@ -57,22 +62,13 @@ class WebAppDeployService:
             result = await session.execute(stmt)
             app_entity = result.scalars().first()
 
+        public_apps_base = Path(app_config.WEB_BUILDER_PUBLIC_APPS_PATH).resolve()
+        public_apps_base.mkdir(parents=True, exist_ok=True)
+
         if app_entity and app_entity.storage_path:
-            project_path = Path(app_entity.storage_path)
-            if not project_path.is_absolute():
-                project_path = (
-                    Path(FILE_STORAGE_LOCAL_PATH).resolve()
-                    / "web-app"
-                    / str(workspace_id)
-                    / app_id
-                )
+            project_path = Path(app_entity.storage_path).resolve()
         else:
-            project_path = (
-                Path(FILE_STORAGE_LOCAL_PATH).resolve()
-                / "web-app"
-                / str(workspace_id)
-                / app_id
-            )
+            project_path = public_apps_base / str(workspace_id) / app_id
 
         if not project_path.exists():
             from app.services.web_builder.project_writer import ProjectWriter
@@ -82,25 +78,59 @@ class WebAppDeployService:
                 project_path, app_entity.name if app_entity else "Generated Web App"
             )
 
-        # 1. Disambiguate slug
+        # 1. Disambiguate slug (global uniqueness across published apps)
         final_slug = slug_override or (app_entity.slug if app_entity else "web-app")
         if session:
-            all_slugs_stmt = select(WorkspaceApp.slug).where(WorkspaceApp.id != app_id)
+            all_slugs_stmt = select(WorkspaceApp.slug).where(
+                WorkspaceApp.id != app_id,
+                WorkspaceApp.status == "published",
+            )
             res = await session.execute(all_slugs_stmt)
             existing_slugs = {s for s in res.scalars().all() if s}
             final_slug = disambiguate_slug(final_slug, existing_slugs)
 
-        public_url = f"https://{final_slug}.{self.base_domain}"
+        sanitized_slug = (
+            re.sub(r"[^a-z0-9-]", "-", final_slug.strip().lower()).strip("-") or "app"
+        )
+        # Enforce DNS label limit (63 chars) and avoid trailing hyphen from truncation.
+        sanitized_slug = sanitized_slug[:63].strip("-") or "app"
+        public_url = f"https://{sanitized_slug}.{self.base_domain}"
+
+        # 2. Idempotency check: if already published and snapshot exists and not force
+        snapshot_dir = public_apps_base / sanitized_slug
+        snapshot_file = snapshot_dir / "index.html"
+        if (
+            not force
+            and app_entity
+            and app_entity.status == "published"
+            and app_entity.slug == sanitized_slug
+            and snapshot_file.exists()
+        ):
+            return WebAppDeployOutput(
+                app_id=app_id,
+                workspace_id=workspace_id,
+                status="published",
+                public_url=app_entity.public_url or public_url,
+                slug=app_entity.slug or sanitized_slug,
+                message=f"Application already published at {app_entity.public_url or public_url}",
+            )
 
-        # 2. Container build & dynamic Traefik / Caddy routing simulation/execution
+        # 3. Render static HTML snapshot via PreviewRenderer
         try:
+            static_html = PreviewRenderer.render_app_html(
+                project_path,
+                app_name=app_entity.name if app_entity else "Sales & Marketing Web App",
+            )
+
+            snapshot_dir.mkdir(parents=True, exist_ok=True)
+            snapshot_file.write_text(static_html, encoding="utf-8")
+
             # Update app entity status
             if session and app_entity:
-                app_entity.slug = final_slug
+                app_entity.slug = sanitized_slug
                 app_entity.public_url = public_url
                 app_entity.status = "published"
                 app_entity.error_message = None
-                await session.flush()
 
                 # Record deployment billing metrics
                 await record_token_usage(
@@ -108,15 +138,16 @@ class WebAppDeployService:
                     workspace_id=workspace_id,
                     user_id=app_entity.user_id,
                     usage_type="web_builder_deploy",
-                    cost_micros=10000,  # $0.010 deployment cost
+                    cost_micros=0,  # $0 fixed platform fee for static snapshot
                 )
+                await session.commit()
 
             return WebAppDeployOutput(
                 app_id=app_id,
                 workspace_id=workspace_id,
                 status="published",
                 public_url=public_url,
-                slug=final_slug,
+                slug=sanitized_slug,
                 message=f"Application deployed successfully to {public_url}",
             )
         except Exception as e:
@@ -126,13 +157,14 @@ class WebAppDeployService:
             if session and app_entity:
                 app_entity.status = "deploy_failed"
                 app_entity.error_message = str(e)
-                await session.flush()
+                with contextlib.suppress(Exception):
+                    await session.commit()
 
             return WebAppDeployOutput(
                 app_id=app_id,
                 workspace_id=workspace_id,
                 status="deploy_failed",
-                slug=final_slug,
+                slug=sanitized_slug,
                 message=f"Deployment execution error: {e}",
             )
 
diff --git a/nowing_backend/app/services/web_builder/generator.py b/nowing_backend/app/services/web_builder/generator.py
index 12483ace0..b98587c4c 100644
--- a/nowing_backend/app/services/web_builder/generator.py
+++ b/nowing_backend/app/services/web_builder/generator.py
@@ -1,5 +1,6 @@
 """Web Builder Project Generation Engine (Story 27.1, AC-1)."""
 
+import contextlib
 import json
 import logging
 import re
@@ -9,7 +10,7 @@ from typing import Any
 
 from sqlalchemy.ext.asyncio import AsyncSession
 
-from app.config import FILE_STORAGE_LOCAL_PATH
+from app.config import FILE_STORAGE_LOCAL_PATH, config as app_config
 from app.services.token_tracking_service import record_token_usage
 from app.services.web_builder.project_writer import ProjectWriter
 from app.services.web_builder.schemas import (
@@ -108,30 +109,154 @@ class WebBuilderService:
             )
             return None
 
+    async def _call_llm_for_refinement(
+        self,
+        existing_files: dict[str, str],
+        prompt: str,
+        language: str,
+        workspace_id: int,
+        session: AsyncSession | None = None,
+    ) -> dict[str, Any] | None:
+        """Call LLM to refine an existing Next.js web application based on user request."""
+        try:
+            from app.services.llm_service import get_agent_llm
+
+            llm = await get_agent_llm(session, workspace_id) if session else None
+            if not llm:
+                from app.services.llm_service import get_planner_llm
+
+                llm = get_planner_llm()
+
+            existing_code_snippets = "\n\n".join(
+                f"--- {path} ---\n{content}"
+                for path, content in existing_files.items()
+                if path.endswith((".tsx", ".ts", ".css", ".json"))
+            )
+
+            # Cap the refinement context to avoid exceeding LLM context windows.
+            if len(existing_code_snippets) > 12_000:
+                existing_code_snippets = existing_code_snippets[:12_000]
+                # Try to end on a complete file boundary.
+                last_file = existing_code_snippets.rfind("\n\n--- ")
+                if last_file > 1000:
+                    existing_code_snippets = existing_code_snippets[:last_file]
+
+            system_instruction = (
+                "You are an expert Next.js 16 + React 19 + Tailwind CSS developer modifying an existing web app. "
+                "Preserve existing working components, styling, and sections unless explicitly asked to change them. "
+                "Apply the user's modifications cleanly.\n\n"
+                "Return ONLY a valid JSON object matching this schema:\n"
+                "{\n"
+                '  "name": "App Name",\n'
+                '  "slug": "app-slug",\n'
+                '  "description": "Short description",\n'
+                '  "files": [\n'
+                '    {"path": "app/page.tsx", "content": "..."}\n'
+                "  ]\n"
+                "}\n"
+                f"Target UI Language: {language}.\n"
+                "DO NOT wrap with markdown fences or extra explanations outside the JSON."
+            )
+
+            user_message = (
+                f"Existing Project Files:\n\n{existing_code_snippets}\n\n"
+                f"Requested Changes: {prompt}"
+            )
+
+            response = await llm.ainvoke(
+                [
+                    {"role": "system", "content": system_instruction},
+                    {"role": "user", "content": user_message},
+                ]
+            )
+
+            raw_text = (
+                response.content if hasattr(response, "content") else str(response)
+            )
+            if isinstance(raw_text, list):
+                raw_text = "".join(str(part) for part in raw_text)
+
+            cleaned_text = raw_text.strip()
+            if cleaned_text.startswith("```"):
+                cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
+                cleaned_text = re.sub(r"\n```$", "", cleaned_text)
+
+            json_match = re.search(r"(\{.*\})", cleaned_text, re.DOTALL)
+            if json_match:
+                cleaned_text = json_match.group(1)
+
+            return json.loads(cleaned_text, strict=False)
+        except Exception as e:
+            logger.warning(
+                f"[WebBuilderService] LLM refinement failed or returned invalid JSON: {e}"
+            )
+            return None
+
     async def generate_project(
         self,
         build_input: WebAppBuildInput,
         session: AsyncSession | None = None,
     ) -> WebAppBuildOutput:
-        """Generate a complete Next.js project, write files to disk, and persist WorkspaceApp."""
-        app_id = str(uuid.uuid4())
-        workspace_dir = (
-            self.storage_base_path / "web-app" / str(build_input.workspace_id) / app_id
-        )
-        # 1. Obtain LLM specification
-        spec_dict = await self._call_llm_for_spec(
-            prompt=build_input.prompt,
-            language=build_input.language,
-            workspace_id=build_input.workspace_id,
-            session=session,
-        )
+        """Generate or refine a Next.js project, write files to disk, and persist WorkspaceApp."""
+        from sqlalchemy import select
+
+        from app.db import WorkspaceApp
+        from app.services.web_builder.deploy_service import disambiguate_slug
+
+        existing_app: WorkspaceApp | None = None
+        if build_input.app_id and session:
+            stmt = select(WorkspaceApp).where(
+                WorkspaceApp.id == build_input.app_id,
+                WorkspaceApp.workspace_id == build_input.workspace_id,
+            )
+            existing_app = (await session.execute(stmt)).scalars().first()
+
+        if existing_app and existing_app.storage_path:
+            app_id = existing_app.id
+            workspace_dir = Path(existing_app.storage_path).resolve()
+            existing_files: dict[str, str] = {}
+            for file_path in workspace_dir.rglob("*"):
+                if (
+                    file_path.is_file()
+                    and "node_modules" not in file_path.parts
+                    and ".next" not in file_path.parts
+                ):
+                    rel_path = str(file_path.relative_to(workspace_dir))
+                    with contextlib.suppress(Exception):
+                        existing_files[rel_path] = file_path.read_text(encoding="utf-8")
+
+            spec_dict = await self._call_llm_for_refinement(
+                existing_files=existing_files,
+                prompt=build_input.prompt,
+                language=build_input.language,
+                workspace_id=build_input.workspace_id,
+                session=session,
+            )
+        else:
+            app_id = str(uuid.uuid4())
+            workspace_dir = (
+                self.storage_base_path
+                / "web-app"
+                / str(build_input.workspace_id)
+                / app_id
+            )
+            spec_dict = await self._call_llm_for_spec(
+                prompt=build_input.prompt,
+                language=build_input.language,
+                workspace_id=build_input.workspace_id,
+                session=session,
+            )
 
         if not spec_dict or not isinstance(spec_dict, dict) or "files" not in spec_dict:
             return WebAppBuildOutput(
                 app_id=app_id,
                 workspace_id=build_input.workspace_id,
-                name=build_input.app_name or "Generated Web App",
-                slug=slugify(build_input.app_name or "web-app"),
+                name=build_input.app_name
+                or (existing_app.name if existing_app else "Generated Web App"),
+                slug=slugify(
+                    build_input.app_name
+                    or (existing_app.slug if existing_app else "web-app")
+                ),
                 status="validation_failed",
                 message="LLM output validation failed: malformed JSON or missing files specification",
                 files=[],
@@ -143,8 +268,14 @@ class WebBuilderService:
             return WebAppBuildOutput(
                 app_id=app_id,
                 workspace_id=build_input.workspace_id,
-                name=spec_dict.get("name", "Generated Web App"),
-                slug=slugify(spec_dict.get("slug", "web-app")),
+                name=spec_dict.get(
+                    "name", existing_app.name if existing_app else "Generated Web App"
+                ),
+                slug=slugify(
+                    spec_dict.get(
+                        "slug", existing_app.slug if existing_app else "web-app"
+                    )
+                ),
                 status="validation_failed",
                 message=f"Pydantic schema validation error: {e}",
                 files=[],
@@ -162,9 +293,13 @@ class WebBuilderService:
             app_name=spec.name, slug=spec.slug
         )
         written_files.extend([f for f in scaffold_files if f not in written_files])
-        app_name = spec.name
-        app_slug = spec.slug
-        app_desc = spec.description
+        app_name = spec.name or (
+            existing_app.name if existing_app else "Generated Web App"
+        )
+        app_slug = spec.slug or (existing_app.slug if existing_app else "web-app")
+        app_desc = spec.description or (
+            existing_app.description if existing_app else None
+        )
 
         # 4. Validate project structure
         is_valid, validation_issues = validate_project_structure(workspace_dir)
@@ -175,28 +310,68 @@ class WebBuilderService:
             else f"Project validation warnings: {', '.join(validation_issues)}"
         )
 
-        preview_url = f"http://localhost:8000/api/v1/web-builder/apps/{app_id}/preview"
+        preview_url = f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/web-builder/apps/{app_id}/preview"
 
         # 5. Persist to DB if session available
         if session:
             try:
-                from app.db import WorkspaceApp
-
-                app_entity = WorkspaceApp(
-                    id=app_id,
-                    workspace_id=build_input.workspace_id,
-                    user_id=build_input.user_id,
-                    name=app_name,
-                    slug=app_slug,
-                    description=app_desc,
-                    prompt=build_input.prompt,
-                    language=build_input.language,
-                    status=status,
-                    preview_url=preview_url,
-                    storage_path=str(workspace_dir),
-                    error_message=message,
-                )
-                session.add(app_entity)
+                if existing_app:
+                    # Cap prompt history at the last 10 turns to avoid unbounded growth
+                    history = existing_app.prompt or ""
+                    parts = [p for p in history.split("\n---\n") if p.strip()]
+                    parts.append(build_input.prompt)
+                    if len(parts) > 10:
+                        parts = parts[-10:]
+                    existing_app.prompt = "\n---\n".join(parts)
+
+                    # Allow LLM/user-provided metadata to update the existing app.
+                    # If the slug changes, clear the published URL so the old public
+                    # route does not silently serve stale content.
+                    existing_app.name = app_name
+                    existing_app.description = app_desc
+                    existing_app.language = build_input.language
+
+                    existing_slugs_res = await session.scalars(
+                        select(WorkspaceApp.slug).where(
+                            WorkspaceApp.workspace_id == build_input.workspace_id,
+                            WorkspaceApp.id != existing_app.id,
+                        )
+                    )
+                    existing_slugs = set(existing_slugs_res.all())
+                    new_slug = disambiguate_slug(app_slug, existing_slugs)
+                    if new_slug != existing_app.slug:
+                        existing_app.slug = new_slug
+                        existing_app.public_url = None
+                        existing_app.status = "generated"
+                    else:
+                        existing_app.status = status
+                    existing_app.error_message = message
+                    existing_app.preview_url = preview_url
+                    app_entity = existing_app
+                else:
+                    existing_slugs_res = await session.scalars(
+                        select(WorkspaceApp.slug).where(
+                            WorkspaceApp.workspace_id == build_input.workspace_id
+                        )
+                    )
+                    existing_slugs = set(existing_slugs_res.all())
+                    app_slug = disambiguate_slug(app_slug, existing_slugs)
+
+                    app_entity = WorkspaceApp(
+                        id=app_id,
+                        workspace_id=build_input.workspace_id,
+                        user_id=build_input.user_id,
+                        name=app_name,
+                        slug=app_slug,
+                        description=app_desc,
+                        prompt=build_input.prompt,
+                        language=build_input.language,
+                        status=status,
+                        preview_url=preview_url,
+                        storage_path=str(workspace_dir),
+                        error_message=message,
+                    )
+                    session.add(app_entity)
                 await session.commit()
 
                 # Record TokenUsage & cost attribution
@@ -340,7 +515,7 @@ class WebBuilderService:
             else f"Project validation warnings: {', '.join(validation_issues)}"
         )
 
-        preview_url = f"http://localhost:8000/api/v1/web-builder/apps/{app_id}/preview"
+        preview_url = f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/web-builder/apps/{app_id}/preview"
 
         if session:
             try:
diff --git a/nowing_backend/app/services/web_builder/preview_renderer.py b/nowing_backend/app/services/web_builder/preview_renderer.py
index 418f8af05..8ba563539 100644
--- a/nowing_backend/app/services/web_builder/preview_renderer.py
+++ b/nowing_backend/app/services/web_builder/preview_renderer.py
@@ -13,6 +13,18 @@ from pathlib import Path
 
 logger = logging.getLogger(__name__)
 
+# ponytail: allow any HTTPS connect-src so generated apps can post lead forms,
+# load analytics, and call external APIs. Hardening to per-app allow-lists is
+# the next step once app authors can declare their endpoints.
+WEB_BUILDER_CSP = (
+    "default-src 'self' 'unsafe-inline' https:; "
+    "img-src 'self' data: https: blob:; "
+    "font-src 'self' data: https:; "
+    "style-src 'self' 'unsafe-inline' https: https://fonts.googleapis.com; "
+    "connect-src 'self' https:; "
+    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com;"
+)
+
 
 class PreviewRenderer:
     """Renders stored Next.js web application files into an interactive HTML preview."""
@@ -57,10 +69,21 @@ class PreviewRenderer:
 <head>
   <meta charset="UTF-8">
   <meta name="viewport" content="width=device-width, initial-scale=1.0">
+  <meta http-equiv="Content-Security-Policy" content="{WEB_BUILDER_CSP}">
   <title>{html.escape(app_name)} - Live Preview</title>
   
   <!-- Tailwind CSS CDN -->
-  <script src="https://cdn.tailwindcss.com"></script>
+  <!-- Fallback if any CDN fails to load -->
+  <script>
+    window.__webBuilderCdnFallback = function() {{
+      const root = document.getElementById('root');
+      if (root) {{
+        root.innerHTML = '<div class="min-h-screen flex flex-col items-center justify-center p-8 bg-slate-950 text-white text-center"><div><h1 class="text-2xl font-bold text-indigo-400 mb-2">Preview unavailable</h1><p class="text-slate-400">A required CDN resource could not be loaded. Please try again later.</p></div></div>';
+      }}
+    }};
+  </script>
+
+  <script src="https://cdn.tailwindcss.com" onerror="__webBuilderCdnFallback()"></script>
   <script>
     tailwind.config = {{
       darkMode: 'class',
@@ -86,12 +109,12 @@ class PreviewRenderer:
   </script>
 
   <!-- React 18 & Babel Standalone for live in-browser JSX execution -->
-  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
-  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
-  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
+  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js" onerror="__webBuilderCdnFallback()"></script>
+  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" onerror="__webBuilderCdnFallback()"></script>
+  <script src="https://unpkg.com/@babel/standalone/babel.min.js" onerror="__webBuilderCdnFallback()"></script>
   
   <!-- Lucide Icons -->
-  <script src="https://unpkg.com/lucide@latest"></script>
+  <script src="https://unpkg.com/lucide@latest" onerror="__webBuilderCdnFallback()"></script>
 
   <link rel="preconnect" href="https://fonts.googleapis.com">
   <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
@@ -199,9 +222,21 @@ class PreviewRenderer:
 
     @staticmethod
     def _sanitize_tsx_for_babel(tsx_code: str) -> str:
-        """Strip TypeScript syntax from Next.js component to allow execution in browser Babel."""
+        """Strip TypeScript syntax and sanitize scripts from Next.js component for browser Babel."""
         code = tsx_code
 
+        # Prevent closing Babel script tag injection
+        code = re.sub(r"</script>", r"<\/script>", code, flags=re.IGNORECASE)
+
+        # Strip access to sensitive browser storage / auth tokens
+        code = re.sub(r"\bdocument\.cookie\b", "''", code)
+        code = re.sub(
+            r"\blocalStorage\b", "{ getItem: () => null, setItem: () => {} }", code
+        )
+        code = re.sub(
+            r"\bsessionStorage\b", "{ getItem: () => null, setItem: () => {} }", code
+        )
+
         # Strip imports
         code = re.sub(r"import\s+[^;]+;?", "", code)
 
@@ -215,8 +250,8 @@ class PreviewRenderer:
             r"(?:interface|type)\s+[A-Za-z0-9_]+\s*=?\s*\{[^}]*\};?", "", code
         )
 
-        # Strip generic types and type annotations
-        code = re.sub(r":\s*[A-Z][a-zA-Z0-9_<>\[\]|&\s]*", "", code)
-        code = re.sub(r"as\s+[A-Z][a-zA-Z0-9_<>\[\]]*", "", code)
+        # Strip generic types and type annotations (uppercase and lowercase)
+        code = re.sub(r":\s*[A-Za-z_][a-zA-Z0-9_<>\[\]|&\s]*", "", code)
+        code = re.sub(r"as\s+[A-Za-z_][a-zA-Z0-9_<>\[\]]*", "", code)
 
         return code
diff --git a/nowing_backend/app/services/web_builder/schemas.py b/nowing_backend/app/services/web_builder/schemas.py
index 191fc045b..6250cc41a 100644
--- a/nowing_backend/app/services/web_builder/schemas.py
+++ b/nowing_backend/app/services/web_builder/schemas.py
@@ -1,8 +1,11 @@
 """Pydantic schemas for Web Builder Service (Story 27.1 / AD-113 / AD-114)."""
 
 from datetime import UTC, datetime
+from uuid import UUID
 
-from pydantic import BaseModel, ConfigDict, Field
+from pydantic import BaseModel, ConfigDict, Field, field_validator
+
+from app.config import config as app_config
 
 
 class GeneratedProjectFile(BaseModel):
@@ -33,11 +36,25 @@ class WebAppBuildInput(BaseModel):
     )
     language: str = Field(default="en", description="Target UI language (e.g. en, vi)")
     workspace_id: int = Field(..., description="Owning workspace ID")
-    user_id: int | None = Field(default=None, description="Requesting user ID")
+    user_id: UUID | None = Field(default=None, description="Requesting user ID")
+    app_id: str | None = Field(
+        default=None,
+        description="Optional existing app ID for conversational refinement",
+    )
     app_name: str | None = Field(
         default=None, description="Optional custom name override"
     )
 
+    @field_validator("prompt")
+    @classmethod
+    def _check_prompt_length(cls, v: str) -> str:
+        max_chars = app_config.WEB_BUILDER_MAX_PROMPT_CHARS
+        if len(v) > max_chars:
+            raise ValueError(
+                f"Prompt exceeds maximum allowed length of {max_chars} characters."
+            )
+        return v
+
 
 class WebAppBuildOutput(BaseModel):
     """Output payload after generating a web application."""
@@ -52,6 +69,7 @@ class WebAppBuildOutput(BaseModel):
     preview_url: str | None = None
     public_url: str | None = None
     message: str | None = None
+    error: str | None = None
     files: list[str] = Field(
         default_factory=list, description="List of generated file paths"
     )
@@ -137,7 +155,7 @@ class WorkspaceAppRead(BaseModel):
 
     id: str
     workspace_id: int
-    user_id: int | None
+    user_id: UUID | None
     name: str
     slug: str
     description: str | None = None
diff --git a/nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py b/nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py
new file mode 100644
index 000000000..d8cdd2013
--- /dev/null
+++ b/nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py
@@ -0,0 +1,139 @@
+"""Chat mode registry for the new-chat orchestrator (AD-120).
+
+Each mode is keyed by a ``platform_metadata`` flag. The registry supplies the
+feature-gate attributes, the system-prompt nudge, and the tool allow-list. The
+``stream_new_chat`` orchestrator resolves the active mode from the thread's
+metadata and applies it without hard-coded mode branches.
+"""
+
+from __future__ import annotations
+
+from dataclasses import dataclass, field
+from typing import Any
+
+
+@dataclass(frozen=True)
+class ChatMode:
+    """A chat mode such as web-builder, presentation-studio, or meeting-minutes."""
+
+    mode_id: str
+    flag_key: str
+    label: str
+    system_prompt: str | None = None
+    enabled_tools: list[str] | None = None
+    workspace_feature_field: str | None = None
+    global_config_attr: str | None = None
+    artifact_kinds: list[str] = field(default_factory=list)
+    error_code: str = "CHAT_MODE_DISABLED"
+    error_message: str = "This chat mode is not enabled on this workspace plan"
+
+
+_WEB_BUILDER_SYSTEM_PROMPT = (
+    "You are in Web Builder mode. The user wants to build a lightweight "
+    "sales/marketing web app such as a landing page, pricing page, lead-capture "
+    "form, waitlist, or report. Ask a concise clarifying question only if the "
+    "request is unclear, then call build_web_app with the user's description to "
+    "produce the Next.js app."
+)
+
+_PRESENTATION_STUDIO_SYSTEM_PROMPT = (
+    "You are in Presentation Studio mode. The user wants to generate a slide deck. "
+    "Ask a concise clarifying question only if the request is unclear, then call "
+    "generate_presentation with the user's description, optional title, output "
+    "format (pptx or marp), and language."
+)
+
+_MEETING_MINUTES_SYSTEM_PROMPT = (
+    "You are in Meeting Minutes mode. The user wants a transcript with speaker "
+    "diarization, action items, and a summary from a meeting recording. Ask the "
+    "user for the audio URL or document ID if they have not provided one, then "
+    "call generate_meeting_minutes with audio_url or document_id and an optional "
+    "language."
+)
+
+CHAT_MODES: dict[str, ChatMode] = {
+    "default": ChatMode(
+        mode_id="default",
+        flag_key="default_mode",
+        label="Default",
+    ),
+    "web_builder": ChatMode(
+        mode_id="web_builder",
+        flag_key="web_builder_mode",
+        label="Web Builder",
+        system_prompt=_WEB_BUILDER_SYSTEM_PROMPT,
+        workspace_feature_field="web_builder_enabled",
+        global_config_attr="WEB_BUILDER_ENABLED",
+        artifact_kinds=["web_app"],
+        error_code="WEB_BUILDER_NOT_ENABLED",
+        error_message="Web Builder is not enabled on this workspace plan",
+    ),
+    "presentation_studio": ChatMode(
+        mode_id="presentation_studio",
+        flag_key="presentation_studio_mode",
+        label="Presentation Studio",
+        system_prompt=_PRESENTATION_STUDIO_SYSTEM_PROMPT,
+        global_config_attr="PRESENTATION_STUDIO_ENABLED",
+        artifact_kinds=["presentation"],
+        error_code="PRESENTATION_STUDIO_NOT_ENABLED",
+        error_message="Presentation Studio is not enabled on this workspace plan",
+    ),
+    "meeting_minutes": ChatMode(
+        mode_id="meeting_minutes",
+        flag_key="meeting_minutes_mode",
+        label="Meeting Minutes",
+        system_prompt=_MEETING_MINUTES_SYSTEM_PROMPT,
+        global_config_attr="MEETING_MINUTES_ENABLED",
+        artifact_kinds=["meeting_minutes"],
+        error_code="MEETING_MINUTES_NOT_ENABLED",
+        error_message="Meeting Minutes is not enabled on this workspace plan",
+    ),
+}
+
+
+def resolve_chat_mode(platform_metadata: dict[str, Any] | None) -> ChatMode:
+    """Return the first chat mode whose flag key is truthy in the metadata."""
+    metadata = platform_metadata or {}
+    for mode in CHAT_MODES.values():
+        if mode.mode_id == "default":
+            continue
+        if metadata.get(mode.flag_key):
+            return mode
+    return CHAT_MODES["default"]
+
+
+def is_chat_mode_enabled(
+    mode: ChatMode,
+    *,
+    workspace: Any | None,
+    app_config: Any,
+) -> bool:
+    """Check the global and per-workspace feature gates for a chat mode.
+
+    Fail-closed: a missing required workspace flag or missing workspace disables
+    the mode, unless the global gate is also missing (in which case the mode is
+    considered ungated and allowed).
+    """
+    if mode.global_config_attr and not getattr(
+        app_config, mode.global_config_attr, False
+    ):
+        return False
+
+    if mode.workspace_feature_field:
+        if workspace is None:
+            return False
+        if not getattr(workspace, mode.workspace_feature_field, False):
+            return False
+
+    return True
+
+
+def get_chat_mode_system_prompt(
+    mode: ChatMode, base_instructions: str | None = None
+) -> str | None:
+    """Return the mode system prompt, prepended to any existing instructions."""
+    if not mode.system_prompt:
+        return base_instructions
+    if base_instructions:
+        return f"{mode.system_prompt}\n\n{base_instructions}"
+    return mode.system_prompt
diff --git a/nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py b/nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py
index a94fa91fa..f9691de47 100644
--- a/nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py
+++ b/nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py
@@ -32,6 +32,7 @@ from uuid import UUID
 
 import anyio
 from fastapi import HTTPException
+from sqlalchemy import select
 from sqlalchemy.ext.asyncio import AsyncSession
 
 from app.agents.chat.multi_agent_chat import create_multi_agent_chat_deep_agent
@@ -43,10 +44,12 @@ from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
 from app.agents.chat.runtime.llm_config import AgentConfig as RuntimeAgentConfig
 from app.auth.agent_chat import _resolve_agent_config
 from app.auth.context import AuthContext
+from app.config import config as app_config
 from app.db import (
     AgentConfig as RegistryAgentConfig,
     ChatVisibility,
     NewChatThread,
+    Workspace,
     async_session_maker,
 )
 from app.observability import otel as ot
@@ -56,6 +59,11 @@ from app.tasks.chat.streaming.agent.builder import build_main_agent_for_thread
 from app.tasks.chat.streaming.contract.file_contract import log_file_contract
 from app.tasks.chat.streaming.errors.emitter import emit_stream_terminal_error
 from app.tasks.chat.streaming.flows.new_chat.auto_pin import resolve_initial_auto_pin
+from app.tasks.chat.streaming.flows.new_chat.chat_modes import (
+    get_chat_mode_system_prompt,
+    is_chat_mode_enabled,
+    resolve_chat_mode,
+)
 from app.tasks.chat.streaming.flows.new_chat.initial_thinking_step import (
     build_initial_thinking_step,
     iter_initial_thinking_step_frame,
@@ -335,7 +343,14 @@ async def stream_new_chat(
     # platform_metadata on the thread for last-turn context (P-METADATA-PERSIST).
     chat_thread = await session.get(NewChatThread, chat_id)
     if chat_thread is not None:
-        chat_thread.platform_metadata = platform_metadata
+        # Story 27.1a: per-turn payload overrides thread-level metadata; if the
+        # turn omits it, fall back to the thread's stored metadata so mode is
+        # not lost on regenerate/refresh.
+        thread_metadata = getattr(chat_thread, "platform_metadata", None)
+        if platform_metadata is not None:
+            chat_thread.platform_metadata = platform_metadata
+        elif thread_metadata is not None:
+            platform_metadata = thread_metadata
     research_thread_id = (
         chat_thread.research_thread_id if chat_thread is not None else None
     )
@@ -528,6 +543,40 @@ async def stream_new_chat(
             yield streaming_service.format_done()
             return
 
+        # --- Block 1c: Chat mode gating (Story 27.1a, AD-120) ---
+        chat_mode = resolve_chat_mode(platform_metadata)
+        if chat_mode.mode_id != "default":
+            workspace = (
+                await session.execute(select(Workspace).where(Workspace.id == workspace_id))
+            ).scalars().first()
+            if not is_chat_mode_enabled(
+                chat_mode, workspace=workspace, app_config=app_config
+            ):
+                yield emit_stream_error(
+                    message=chat_mode.error_message,
+                    error_kind="user_error",
+                    error_code=chat_mode.error_code,
+                )
+                yield streaming_service.format_done()
+                return
+
+            if agent_config is None:
+                yield emit_stream_error(
+                    message=f"Failed to create agent config for {chat_mode.label}",
+                    error_kind="server_error",
+                    error_code="SERVER_ERROR",
+                )
+                yield streaming_service.format_done()
+                return
+
+            if chat_mode.enabled_tools is not None:
+                effective_enabled_tools = list(chat_mode.enabled_tools)
+            agent_config.system_instructions = _clamp_agent_instructions(
+                get_chat_mode_system_prompt(
+                    chat_mode, agent_config.system_instructions
+                )
+            )
+
         # --- Block 2: Spawn concurrent persistence; build pre-stream setup ---
 
         persist_user_task = spawn_persist_user_task(
diff --git a/nowing_backend/tests/integration/routes/test_web_builder_routes.py b/nowing_backend/tests/integration/routes/test_web_builder_routes.py
index d56e2304c..aa3111dd3 100644
--- a/nowing_backend/tests/integration/routes/test_web_builder_routes.py
+++ b/nowing_backend/tests/integration/routes/test_web_builder_routes.py
@@ -48,16 +48,22 @@ def mock_auth() -> AuthContext:
 def mock_db_session():
     """Mock async DB session."""
     session = AsyncMock()
+    mock_result = MagicMock()
+    mock_result.scalars.return_value.first.return_value = MagicMock()
+    session.execute.return_value = mock_result
     return session
 
 
 @pytest.fixture
 def client(mock_auth: AuthContext, mock_db_session: AsyncMock) -> TestClient:
     """Fixture creating test FastAPI app with Web Builder routes mounted and auth overridden."""
+    import app.routes.web_builder_routes as routes
+
     app = FastAPI()
     app.include_router(web_builder_router)
     app.dependency_overrides[get_auth_context] = lambda: mock_auth
     app.dependency_overrides[get_async_session] = lambda: mock_db_session
+    routes.require_workspace_member = AsyncMock(return_value=None)
     return TestClient(app)
 
 
@@ -254,7 +260,7 @@ class TestWebBuilderRoutes:
         mock_result.scalars.return_value.first.return_value = mock_app_entity
         mock_db_session.execute.return_value = mock_result
 
-        response = client.get(f"/api/v1/web-builder/apps/{app_id}/preview")
+        response = client.get(f"/api/v1/web-builder/apps/{app_id}/preview?workspace_id=1")
 
         assert response.status_code == 200
         assert "text/html" in response.headers["content-type"]
diff --git a/nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py b/nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py
index 551183aee..9c2a57928 100644
--- a/nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py
+++ b/nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py
@@ -7,6 +7,7 @@ Acceptance Criteria:
 """
 
 from unittest.mock import AsyncMock, patch
+from uuid import uuid4
 
 import pytest
 
@@ -28,7 +29,7 @@ class TestWebBuilderServiceGeneration:
             prompt="Build a SaaS landing page for an AI accounting tool with hero, pricing table, and contact form.",
             language="en",
             workspace_id=1,
-            user_id=10,
+            user_id=uuid4(),
         )
 
         mock_llm_response = {
@@ -92,7 +93,7 @@ class TestWebBuilderServiceGeneration:
             prompt="Build a blog",
             language="vi",
             workspace_id=1,
-            user_id=10,
+            user_id=uuid4(),
         )
 
         with patch.object(
