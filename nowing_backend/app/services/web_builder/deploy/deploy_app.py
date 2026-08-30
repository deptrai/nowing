"""Web builder app deploy orchestration."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.web_builder.deploy.utils import disambiguate_slug
from app.services.web_builder.schemas import WebAppDeployOutput

logger = logging.getLogger(__name__)


async def deploy_app(
    service,
    app_id: str,
    workspace_id: int,
    slug_override: str | None = None,
    force: bool = False,
    session: AsyncSession | None = None,
) -> WebAppDeployOutput:
    """Publish a generated project to https://{slug}.apps.nowing.net."""
    from app.config import config as app_config
    from app.db import Workspace, WorkspaceApp
    from app.services.web_builder.preview_renderer import PreviewRenderer

    public_apps_base = Path(app_config.WEB_BUILDER_PUBLIC_APPS_PATH).resolve()
    public_apps_base.mkdir(parents=True, exist_ok=True)

    if not session:
        return WebAppDeployOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            status="deploy_failed",
            slug="",
            message="Database session is required to publish an app",
        )

    # 0. Verify workspace and app gates (P3, P14).
    ws = (
        (
            await session.execute(
                select(Workspace).where(Workspace.id == workspace_id)
            )
        )
        .scalars()
        .first()
    )
    if ws is None or ws.web_builder_enabled is False:
        return WebAppDeployOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            status="deploy_failed",
            slug="",
            message="Web Builder is not enabled on this workspace plan",
        )

    stmt = select(WorkspaceApp).where(
        WorkspaceApp.id == app_id,
        WorkspaceApp.workspace_id == workspace_id,
    )
    app_entity = (await session.execute(stmt)).scalars().first()

    if app_entity is None:
        return WebAppDeployOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            status="deploy_failed",
            slug="",
            message="Application not found",
        )

    if not app_entity.storage_path:
        return WebAppDeployOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            status="deploy_failed",
            slug="",
            message="Application has no generated files to publish",
        )

    # Path-traversal guard before touching the filesystem.
    project_path = service._validate_storage_path(
        app_entity.storage_path, workspace_id, app_id, raise_on_error=False
    )
    if not project_path or not project_path.exists() or not any(project_path.iterdir()):
        return WebAppDeployOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            status="deploy_failed",
            slug="",
            message="Application source directory is missing or empty",
        )

    # Serialize deploys for this app so two publish clicks do not race on
    # slug selection, TokenUsage recording, or snapshot writes.
    deploy_lock = await service._acquire_deploy_lock(
        app_id, app_config.WEB_BUILDER_BUILD_TIMEOUT_SECONDS
    )
    try:
        async with deploy_lock:
            # 1. Disambiguate slug (global uniqueness across published apps).
            final_slug = slug_override or app_entity.slug or "web-app"
            all_slugs_stmt = select(WorkspaceApp.slug).where(
                WorkspaceApp.id != app_id,
                WorkspaceApp.status == "published",
            )
            res = await session.execute(all_slugs_stmt)
            existing_slugs = {s for s in res.scalars().all() if s}
            sanitized_slug = disambiguate_slug(final_slug, existing_slugs)
            public_url = f"https://{sanitized_slug}.{service.base_domain}"

            # 2. Idempotency check: if already published and (container running or
            # static snapshot exists) and not force.
            snapshot_dir = public_apps_base / sanitized_slug
            snapshot_file = snapshot_dir / "index.html"
            is_live = False
            if (
                not force
                and app_entity.status == "published"
                and app_entity.slug == sanitized_slug
            ):
                if app_config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED:
                    if app_entity.container_id and await service._is_container_running(
                        app_entity.container_id
                    ):
                        is_live = True
                elif snapshot_file.exists():
                    is_live = True

                if is_live:
                    return WebAppDeployOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        status="published",
                        public_url=app_entity.public_url or public_url,
                        slug=app_entity.slug or sanitized_slug,
                        message=f"Application already published at {app_entity.public_url or public_url}",
                    )

            # 3. Render static HTML snapshot (prefer compiled standalone build if exists, fallback to PreviewRenderer).
            try:
                candidate_index_paths = [
                    project_path / ".next" / "server" / "app" / "index.html",
                    project_path / ".next" / "server" / "app" / "page.html",
                    project_path
                    / ".next"
                    / "standalone"
                    / ".next"
                    / "server"
                    / "app"
                    / "index.html",
                    project_path / ".next" / "standalone" / "index.html",
                    project_path / "out" / "index.html",
                ]
                static_html = None
                for candidate in candidate_index_paths:
                    if candidate.exists():
                        static_html = candidate.read_text(encoding="utf-8")
                        break
                if not static_html:
                    static_html = PreviewRenderer.render_app_html(
                        project_path,
                        app_name=app_entity.name,
                    )
            except Exception as e:
                logger.error(
                    f"[WebAppDeployService] Rendering failed for app {app_id}: {e}"
                )
                app_entity.status = "deploy_failed"
                app_entity.error_message = f"Rendering failed: {e}"
                await session.commit()
                return WebAppDeployOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    status="deploy_failed",
                    slug=sanitized_slug,
                    message=f"Rendering failed: {e}",
                )

            # 4. Container deployment (if enabled). On failure, fail hard and
            # do NOT fall back to the static snapshot (Story 27.1c decision).
            container_id = None
            port = None
            if app_config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED:
                try:
                    container_id, port = await service.deploy_container(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        project_path=project_path,
                        slug=sanitized_slug,
                        custom_domain=app_entity.custom_domain,
                    )
                except Exception as e:
                    logger.error(
                        f"[WebAppDeployService] Container deploy failed for app {app_id}: {e}"
                    )
                    app_entity.status = "deploy_failed"
                    app_entity.error_message = f"Container deploy failed: {e}"
                    app_entity.public_url = public_url
                    app_entity.slug = sanitized_slug
                    with contextlib.suppress(Exception):
                        await session.commit()
                    return WebAppDeployOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        status="deploy_failed",
                        slug=sanitized_slug,
                        message=f"Container deploy failed: {e}",
                    )

            # Commit the published state to the database *before* writing the
            # snapshot file so a failed file write does not leave a published URL
            # with no matching static file (P16).
            try:
                app_entity.slug = sanitized_slug
                app_entity.public_url = public_url
                if container_id:
                    app_entity.container_id = container_id
                    app_entity.port = port
                app_entity.status = "published"
                app_entity.error_message = None

                # Record deployment billing metrics.
                from app.services.web_builder.deploy_service import record_token_usage

                await record_token_usage(
                    session=session,
                    workspace_id=workspace_id,
                    user_id=app_entity.user_id,
                    usage_type="web_builder_deploy",
                    cost_micros=app_config.WEB_BUILDER_DEPLOY_COST_MICROS,
                )
                await session.commit()
            except Exception as e:
                logger.error(
                    f"[WebAppDeployService] Database publish failed for app {app_id}: {e}"
                )
                if container_id:
                    await service._stop_container(container_id)
                return WebAppDeployOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    status="deploy_failed",
                    slug=sanitized_slug,
                    message=f"Database publish failed: {e}",
                )

            # 5. Write per-app Caddy snippet (service-host ingress).
            try:
                await service._write_caddy_snippet_for_app(
                    app_entity, container_id=container_id
                )
            except Exception as e:
                logger.error(
                    f"[WebAppDeployService] Caddy snippet write failed for app {app_id}: {e}"
                )
                await service._stop_container(container_id or "")
                app_entity.status = "deploy_failed"
                app_entity.error_message = f"Caddy snippet write failed: {e}"
                with contextlib.suppress(Exception):
                    await session.commit()
                return WebAppDeployOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    status="deploy_failed",
                    slug=sanitized_slug,
                    message=f"Caddy snippet write failed: {e}",
                )

            # 6. Write the static snapshot after the DB is committed.
            try:
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                snapshot_file.write_text(static_html, encoding="utf-8")
            except Exception as e:
                logger.error(
                    f"[WebAppDeployService] Snapshot file write failed for app {app_id}: {e}"
                )
                # Roll back the published state and stop the container.
                try:
                    if container_id:
                        await service._stop_container(container_id)
                    app_entity.status = "deploy_failed"
                    app_entity.error_message = f"Snapshot write failed: {e}"
                    await session.commit()
                except Exception as db_err:
                    logger.error(
                        f"[WebAppDeployService] Failed to mark app {app_id} as deploy_failed: {db_err}"
                    )
                return WebAppDeployOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    status="deploy_failed",
                    slug=sanitized_slug,
                    message=f"Snapshot write failed: {e}",
                )

            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="published",
                public_url=public_url,
                slug=sanitized_slug,
                message=f"Application deployed successfully to {public_url}",
            )
    finally:
        await service._release_deploy_lock(app_id)


__all__ = ["deploy_app"]
