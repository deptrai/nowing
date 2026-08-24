import asyncio
import logging
import re
import uuid
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


def disambiguate_slug(
    base_slug: str,
    existing_slugs: set[str] | list[str],
    max_length: int = 63,
    max_attempts: int = 100_000,
) -> str:
    """Generate a collision-free, DNS-label-safe slug.

    The result is always <= ``max_length`` and has a bounded number of suffix
    attempts to avoid an infinite loop (P15).
    """
    existing = set(existing_slugs)
    # Sanitize and truncate base_slug to DNS label safe format
    cleaned = re.sub(r"[^a-z0-9-]", "-", base_slug.strip().lower()).strip("-") or "app"
    # Remove a trailing numeric suffix so our own disambiguation scheme is
    # the only source of -{n} tails.
    cleaned = re.sub(r"-\d+$", "", cleaned).strip("-") or "app"
    # Reserve 6 characters for the -{counter} suffix (up to -99999).
    max_base = max_length - 6
    if len(cleaned) > max_base:
        cleaned = cleaned[:max_base].strip("-") or "app"

    if cleaned not in existing:
        return cleaned

    for counter in range(1, max_attempts + 1):
        candidate = f"{cleaned}-{counter}"
        if candidate not in existing:
            return candidate

    # Collisions exhausted the numeric range; append a short random tail.
    tail = uuid.uuid4().hex[:6]
    base = cleaned[: max_length - len(tail) - 1]
    return f"{base}-{tail}"


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

        project_path = Path(app_entity.storage_path).resolve()
        if not project_path.exists() or not any(project_path.iterdir()):
            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="deploy_failed",
                slug="",
                message="Application source directory is missing or empty",
            )

        # 1. Disambiguate slug (global uniqueness across published apps).
        final_slug = slug_override or app_entity.slug or "web-app"
        all_slugs_stmt = select(WorkspaceApp.slug).where(
            WorkspaceApp.id != app_id,
            WorkspaceApp.status == "published",
        )
        res = await session.execute(all_slugs_stmt)
        existing_slugs = {s for s in res.scalars().all() if s}
        sanitized_slug = disambiguate_slug(final_slug, existing_slugs)
        public_url = f"https://{sanitized_slug}.{self.base_domain}"

        # 2. Idempotency check: if already published and snapshot exists and not force.
        snapshot_dir = public_apps_base / sanitized_slug
        snapshot_file = snapshot_dir / "index.html"
        if (
            not force
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

        # 4. Commit the published state to the database *before* writing the
        # snapshot file so a failed file write does not leave a published URL
        # with no matching static file (P16).
        try:
            app_entity.slug = sanitized_slug
            app_entity.public_url = public_url
            app_entity.status = "published"
            app_entity.error_message = None

            # Record deployment billing metrics.
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
            return WebAppDeployOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                status="deploy_failed",
                slug=sanitized_slug,
                message=f"Database publish failed: {e}",
            )

        # 5. Write the static snapshot after the DB is committed.
        try:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_file.write_text(static_html, encoding="utf-8")
        except Exception as e:
            logger.error(
                f"[WebAppDeployService] Snapshot file write failed for app {app_id}: {e}"
            )
            # Roll back the published state if the static file cannot be saved.
            try:
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

    async def verify_and_bind_custom_domain(
        self,
        app_id: str,
        workspace_id: int,
        custom_domain: str,
        session: AsyncSession | None = None,
    ) -> CustomDomainOutput:
        """Validate custom domain FQDN, verify DNS proof-of-control, and bind it."""
        from app.db import WorkspaceApp

        clean_domain = custom_domain.strip().lower()
        cname_target = CNAME_INGRESS_HOST

        # Basic FQDN validation (no IPs, no localhost, valid labels)
        if not re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$", clean_domain):
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="Invalid custom domain. Provide a valid FQDN (e.g. app.mycompany.com).",
            )

        for label in clean_domain.split("."):
            if (
                not label
                or label.startswith("-")
                or label.endswith("-")
                or len(label) > 63
            ):
                return CustomDomainOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    custom_domain=clean_domain,
                    status="failed",
                    cname_target=cname_target,
                    message="Invalid custom domain label. Each DNS label must be 1-63 characters and not start/end with a hyphen.",
                )

        if re.match(r"^\d+\.\d+\.\d+\.\d+$|^\[[0-9a-f:]+\]$", clean_domain):
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="IP addresses are not valid custom domains.",
            )

        if clean_domain == "localhost" or clean_domain.endswith(".local"):
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="Local domains are not valid custom domains.",
            )

        if session:
            # Check collision across all workspaces
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

            # DNS proof-of-control: CNAME must point to the ingress host (R-11)
            try:
                import dns.resolver

                resolver = dns.resolver.Resolver()
                resolver.lifetime = 5
                answers = await asyncio.to_thread(
                    resolver.resolve, clean_domain, "CNAME"
                )
                cname_values = {
                    str(rdata.target).rstrip(".").lower() for rdata in answers
                }
            except dns.resolver.NoAnswer:
                cname_values = set()
            except dns.resolver.NXDOMAIN:
                return CustomDomainOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    custom_domain=clean_domain,
                    status="failed",
                    cname_target=cname_target,
                    message=f"DNS lookup failed: {clean_domain} does not exist.",
                )
            except Exception as e:
                return CustomDomainOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    custom_domain=clean_domain,
                    status="failed",
                    cname_target=cname_target,
                    message=f"DNS verification failed: {e}",
                )

            expected = cname_target.lower().rstrip(".")
            if expected not in cname_values:
                return CustomDomainOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    custom_domain=clean_domain,
                    status="failed",
                    cname_target=cname_target,
                    message=f"Domain '{clean_domain}' CNAME does not point to {cname_target}.",
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
                message=f"Custom domain {clean_domain} verified and bound to {cname_target}.",
            )

        return CustomDomainOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            custom_domain=clean_domain,
            status="pending_verification",
            cname_target=cname_target,
            message=f"Custom domain {clean_domain} configured. Point its CNAME to {cname_target}.",
        )
