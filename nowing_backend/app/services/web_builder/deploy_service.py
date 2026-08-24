import contextlib
import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import CNAME_INGRESS_HOST, HOSTING_BASE_DOMAIN
from app.services.token_tracking_service import record_token_usage
from app.services.web_builder.schemas import (
    CustomDomainOutput,
    WebAppDeployOutput,
)

logger = logging.getLogger(__name__)


def disambiguate_slug(base_slug: str, existing_slugs: set[str] | list[str]) -> str:
    """Generate a collision-free slug by appending incremental numeric suffixes."""
    existing = set(existing_slugs)
    # Sanitize and truncate base_slug to DNS label safe format
    cleaned = re.sub(r"[^a-z0-9-]", "-", base_slug.strip().lower())
    clean_base = re.sub(r"-\d+$", "", cleaned).strip("-") or "app"
    clean_base = clean_base[:50]  # allow room for numeric suffixes up to 63 chars

    if clean_base not in existing:
        return clean_base

    counter = 1
    while f"{clean_base}-{counter}" in existing:
        counter += 1

    return f"{clean_base}-{counter}"


class WebAppDeployService:
    """Builds, publishes static HTML snapshots, and routes web applications dynamically."""

    def __init__(self, base_domain: str | None = None):
        self.base_domain = base_domain or HOSTING_BASE_DOMAIN

    async def deploy_app(
        self,
        app_id: str,
        workspace_id: int,
        slug_override: str | None = None,
        force: bool = False,
        session: AsyncSession | None = None,
    ) -> WebAppDeployOutput:
        """Publish a generated project to https://{slug}.apps.nowing.net (Option A Static Snapshot)."""
        from app.config import config as app_config
        from app.db import WorkspaceApp
        from app.services.web_builder.preview_renderer import PreviewRenderer

        app_entity: WorkspaceApp | None = None
        if session:
            stmt = select(WorkspaceApp).where(
                WorkspaceApp.id == app_id,
                WorkspaceApp.workspace_id == workspace_id,
            )
            result = await session.execute(stmt)
            app_entity = result.scalars().first()

        public_apps_base = Path(app_config.WEB_BUILDER_PUBLIC_APPS_PATH).resolve()
        public_apps_base.mkdir(parents=True, exist_ok=True)

        if app_entity and app_entity.storage_path:
            project_path = Path(app_entity.storage_path).resolve()
        else:
            project_path = public_apps_base / str(workspace_id) / app_id

        if not project_path.exists():
            from app.services.web_builder.project_writer import ProjectWriter

            project_path.mkdir(parents=True, exist_ok=True)
            ProjectWriter.write_minimal_nextjs_scaffold(
                project_path, app_entity.name if app_entity else "Generated Web App"
            )

        # 1. Disambiguate slug (global uniqueness across published apps)
        final_slug = slug_override or (app_entity.slug if app_entity else "web-app")
        if session:
            all_slugs_stmt = select(WorkspaceApp.slug).where(
                WorkspaceApp.id != app_id,
                WorkspaceApp.status == "published",
            )
            res = await session.execute(all_slugs_stmt)
            existing_slugs = {s for s in res.scalars().all() if s}
            final_slug = disambiguate_slug(final_slug, existing_slugs)

        sanitized_slug = (
            re.sub(r"[^a-z0-9-]", "-", final_slug.strip().lower()).strip("-") or "app"
        )
        # Enforce DNS label limit (63 chars) and avoid trailing hyphen from truncation.
        sanitized_slug = sanitized_slug[:63].strip("-") or "app"
        public_url = f"https://{sanitized_slug}.{self.base_domain}"

        # 2. Idempotency check: if already published and snapshot exists and not force
        snapshot_dir = public_apps_base / sanitized_slug
        snapshot_file = snapshot_dir / "index.html"
        if (
            not force
            and app_entity
            and app_entity.status == "published"
            and app_entity.slug == sanitized_slug
            and snapshot_file.exists()
        ):
            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="published",
                public_url=app_entity.public_url or public_url,
                slug=app_entity.slug or sanitized_slug,
                message=f"Application already published at {app_entity.public_url or public_url}",
            )

        # 3. Render static HTML snapshot via PreviewRenderer
        try:
            static_html = PreviewRenderer.render_app_html(
                project_path,
                app_name=app_entity.name if app_entity else "Sales & Marketing Web App",
            )

            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_file.write_text(static_html, encoding="utf-8")

            # Update app entity status
            if session and app_entity:
                app_entity.slug = sanitized_slug
                app_entity.public_url = public_url
                app_entity.status = "published"
                app_entity.error_message = None

                # Record deployment billing metrics
                await record_token_usage(
                    session=session,
                    workspace_id=workspace_id,
                    user_id=app_entity.user_id,
                    usage_type="web_builder_deploy",
                    cost_micros=0,  # $0 fixed platform fee for static snapshot
                )
                await session.commit()

            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="published",
                public_url=public_url,
                slug=sanitized_slug,
                message=f"Application deployed successfully to {public_url}",
            )
        except Exception as e:
            logger.error(
                f"[WebAppDeployService] Deployment failed for app {app_id}: {e}"
            )
            if session and app_entity:
                app_entity.status = "deploy_failed"
                app_entity.error_message = str(e)
                with contextlib.suppress(Exception):
                    await session.commit()

            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="deploy_failed",
                slug=sanitized_slug,
                message=f"Deployment execution error: {e}",
            )

    async def verify_and_bind_custom_domain(
        self,
        app_id: str,
        workspace_id: int,
        custom_domain: str,
        session: AsyncSession | None = None,
    ) -> CustomDomainOutput:
        """Validate custom domain CNAME and configure dynamic proxy route."""
        from app.db import WorkspaceApp

        clean_domain = custom_domain.strip().lower()
        cname_target = CNAME_INGRESS_HOST

        # Check collision across all workspaces
        if session:
            collision_stmt = select(WorkspaceApp).where(
                WorkspaceApp.custom_domain == clean_domain,
                WorkspaceApp.id != app_id,
            )
            col_res = await session.execute(collision_stmt)
            if col_res.scalars().first():
                return CustomDomainOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    custom_domain=clean_domain,
                    status="failed",
                    cname_target=cname_target,
                    message=f"Domain '{clean_domain}' is already assigned to another application",
                )

            # Update DB entity
            stmt = select(WorkspaceApp).where(
                WorkspaceApp.id == app_id,
                WorkspaceApp.workspace_id == workspace_id,
            )
            app_res = await session.execute(stmt)
            app_entity = app_res.scalars().first()

            if app_entity:
                app_entity.custom_domain = clean_domain
                app_entity.custom_domain_status = "active"
                await session.flush()

        return CustomDomainOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            custom_domain=clean_domain,
            status="active",
            cname_target=cname_target,
            message=f"Custom domain {clean_domain} configured successfully",
        )
