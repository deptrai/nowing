"""Web builder custom domain binding."""

from __future__ import annotations

import contextlib
import logging
import re
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import CNAME_INGRESS_HOST
from app.services.web_builder.schemas import CustomDomainOutput

logger = logging.getLogger(__name__)


async def verify_and_bind_custom_domain(
    service,
    app_id: str,
    workspace_id: int,
    custom_domain: str,
    session: AsyncSession | None = None,
) -> CustomDomainOutput:
    """Validate custom domain FQDN, verify DNS proof-of-control, and bind it."""
    from app.db import Workspace, WorkspaceApp

    clean_domain = custom_domain.strip().rstrip(".").lower()
    cname_target = CNAME_INGRESS_HOST

    if len(clean_domain) > 255:
        return CustomDomainOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            custom_domain=clean_domain,
            status="failed",
            cname_target=cname_target,
            message="Custom domain exceeds the maximum length of 255 characters.",
        )

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

    # Reserved / system infrastructure domain blacklist (config-driven)
    if service._is_system_domain(clean_domain):
        return CustomDomainOutput(
            app_id=app_id,
            workspace_id=workspace_id,
            custom_domain=clean_domain,
            status="failed",
            cname_target=cname_target,
            message="Cannot use system domain or reserved infrastructure domains.",
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
        # Verify workspace feature gate.
        ws = (
            await session.execute(
                select(Workspace).where(Workspace.id == workspace_id)
            )
        ).scalars().first()
        if ws and ws.web_builder_enabled is False:
            return CustomDomainOutput(
                app_id=app_id,
                workspace_id=workspace_id,
                custom_domain=clean_domain,
                status="failed",
                cname_target=cname_target,
                message="Web Builder is not enabled on this workspace plan",
            )

        # Serialize binding for this domain so two workspaces cannot race
        # on the collision check and both commit the same custom domain.
        domain_lock = await service._acquire_domain_lock(clean_domain, 60)
        try:
            async with domain_lock:
                # Check collision across workspaces for active/pending bindings.
                collision_stmt = select(WorkspaceApp).where(
                    WorkspaceApp.custom_domain == clean_domain,
                    WorkspaceApp.id != app_id,
                    WorkspaceApp.custom_domain_status.in_(
                        ["active", "pending_verification"]
                    ),
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

                # Fetch target app entity to ensure token exists and for subsequent updates.
                # with_for_update serializes token generation across concurrent binds of
                # different domains on the SAME app — the per-domain lock cannot, since
                # it keys on clean_domain, not app_id.
                stmt = (
                    select(WorkspaceApp)
                    .where(
                        WorkspaceApp.id == app_id,
                        WorkspaceApp.workspace_id == workspace_id,
                    )
                    .with_for_update()
                )
                app_res = await session.execute(stmt)
                app_entity = app_res.scalars().first()

                if not app_entity:
                    return CustomDomainOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        custom_domain=clean_domain,
                        status="failed",
                        cname_target=cname_target,
                        message="Application not found",
                        verify_stage="not_found",
                    )

                # Ensure verification token exists for app (generate + persist if NULL).
                if not app_entity.custom_domain_verify_token:
                    app_entity.custom_domain_verify_token = secrets.token_urlsafe(32)
                    await session.commit()

                # Step 1: DNS proof-of-ownership via TXT record.
                from app.config import (
                    WEB_BUILDER_TXT_VERIFY_LABEL,
                    WEB_BUILDER_TXT_VERIFY_PREFIX,
                )

                txt_detail: dict[str, str] = {}
                txt_ok = await service._verify_txt_ownership(
                    clean_domain,
                    app_entity.custom_domain_verify_token,
                    detail_out=txt_detail,
                )
                if not txt_ok:
                    txt_host = f"{WEB_BUILDER_TXT_VERIFY_LABEL}.{clean_domain}"
                    ttl_hint = (
                        " DNS may take a few minutes to propagate; wait for the"
                        " record TTL to expire if you just added it."
                    )
                    if txt_detail.get("reason") == "mismatch":
                        msg = f"Domain '{clean_domain}' TXT record at '{txt_host}' did not match the verification token."
                    elif txt_detail.get("reason") == "invalid":
                        msg = f"Verification hostname '{txt_host}' exceeds the maximum allowed length of 253 characters."
                        ttl_hint = ""
                    else:
                        expected_txt = f"{WEB_BUILDER_TXT_VERIFY_PREFIX}{app_entity.custom_domain_verify_token}"
                        msg = f"Domain '{clean_domain}' TXT record at '{txt_host}' with value '{expected_txt}' not found."
                    return CustomDomainOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        custom_domain=clean_domain,
                        status="failed",
                        cname_target=cname_target,
                        message=msg + ttl_hint,
                        verify_stage="txt",
                    )

                # Step 2: DNS proof-of-control: CNAME must point to the ingress host (R-11).
                dns_ok = await service._resolve_cname_ingress(
                    clean_domain, cname_target
                )
                if not dns_ok:
                    return CustomDomainOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        custom_domain=clean_domain,
                        status="failed",
                        cname_target=cname_target,
                        message=f"Domain '{clean_domain}' CNAME does not point to {cname_target}.",
                        verify_stage="cname",
                    )

                if app_entity.status != "published":
                    app_entity.custom_domain = clean_domain
                    app_entity.custom_domain_status = "pending_verification"
                    await session.commit()
                    return CustomDomainOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        custom_domain=clean_domain,
                        status="pending_verification",
                        cname_target=cname_target,
                        message=f"Custom domain {clean_domain} verified. It will become active after the app is published.",
                    )

                # For published apps, only mark active after a successful container
                # redeploy (if container deploy is enabled) and Caddy rewrite.
                from app.config import config as app_config

                # Preserve the previously-working binding so a failed re-bind does
                # not clobber a live domain — restore it on redeploy/Caddy failure.
                previous_domain = app_entity.custom_domain
                previous_status = app_entity.custom_domain_status
                previous_container_id = app_entity.container_id
                previous_port = app_entity.port

                app_entity.custom_domain = clean_domain
                app_entity.custom_domain_status = "pending_verification"
                await session.commit()

                if (
                    app_config.WEB_BUILDER_CONTAINER_DEPLOY_ENABLED
                    and app_entity.storage_path
                ):
                    try:
                        project_path = service._validate_storage_path(
                            app_entity.storage_path,
                            workspace_id,
                            app_id,
                            raise_on_error=True,
                        )
                        # Story 31.1: reuse the already-loaded workspace row
                        # for tier-scoped container limits; a missing row
                        # yields None -> free fallback inside deploy_container.
                        plan_tier = ws.plan_tier if ws is not None else None
                        container_id, port = await service.deploy_container(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            project_path=project_path,
                            slug=app_entity.slug,
                            custom_domain=clean_domain,
                            plan_tier=plan_tier,
                        )
                        app_entity.container_id = container_id
                        app_entity.port = port
                    except Exception as redeploy_err:  # redeploy failure → restore previous binding
                        logger.error(
                            "[WebAppDeployService] Container redeploy for custom domain failed: %s",
                            redeploy_err,
                        )
                        app_entity.custom_domain = previous_domain
                        app_entity.custom_domain_status = previous_status or "failed"
                        app_entity.container_id = previous_container_id
                        app_entity.port = previous_port
                        app_entity.error_message = f"Container redeploy failed: {redeploy_err}"
                        await session.commit()
                        return CustomDomainOutput(
                            app_id=app_id,
                            workspace_id=workspace_id,
                            custom_domain=clean_domain,
                            status="failed",
                            cname_target=cname_target,
                            message=f"Custom domain verified, but container redeploy failed: {redeploy_err}",
                        )

                # Rewrite the Caddy snippet with the new custom domain.
                try:
                    await service._write_caddy_snippet_for_app(app_entity)
                except Exception as caddy_err:  # snippet rewrite failure → restore previous binding
                    logger.error(
                        "[WebAppDeployService] Caddy snippet rewrite failed: %s", caddy_err
                    )
                    # If redeploy started a new container, stop it to prevent leakage
                    if app_entity.container_id and app_entity.container_id != previous_container_id:
                        with contextlib.suppress(Exception):
                            await service._stop_container(app_entity.container_id)
                    app_entity.custom_domain = previous_domain
                    app_entity.custom_domain_status = previous_status or "failed"
                    app_entity.container_id = previous_container_id
                    app_entity.port = previous_port
                    app_entity.error_message = f"Caddy snippet rewrite failed: {caddy_err}"
                    await session.commit()
                    return CustomDomainOutput(
                        app_id=app_id,
                        workspace_id=workspace_id,
                        custom_domain=clean_domain,
                        status="failed",
                        cname_target=cname_target,
                        message=f"Custom domain verified, but ingress update failed: {caddy_err}",
                    )

                app_entity.custom_domain_status = "active"
                await session.commit()

                return CustomDomainOutput(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    custom_domain=clean_domain,
                    status="active",
                    cname_target=cname_target,
                    message=f"Custom domain {clean_domain} verified and bound to {cname_target}.",
                )
        finally:
            await service._release_domain_lock(clean_domain)

    return CustomDomainOutput(
        app_id=app_id,
        workspace_id=workspace_id,
        custom_domain=clean_domain,
        status="pending_verification",
        cname_target=cname_target,
        message=f"Custom domain {clean_domain} configured. Point its CNAME to {cname_target}.",
    )


async def rotate_domain_token(
    app_id: str,
    workspace_id: int,
    session: AsyncSession,
) -> str | None:
    """Rotate the per-app DNS TXT verification token.

    Returns the new token, or ``None`` when the app does not exist. When the app
    currently has an ``active`` custom domain, the status is reset to
    ``pending_verification`` so the new token must be re-verified before the
    domain is trusted again (fail-closed on token rotation).
    """
    from app.db import WorkspaceApp

    stmt = (
        select(WorkspaceApp)
        .where(
            WorkspaceApp.id == app_id,
            WorkspaceApp.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    app_entity = (await session.execute(stmt)).scalars().first()
    if not app_entity:
        return None

    new_token = secrets.token_urlsafe(32)
    app_entity.custom_domain_verify_token = new_token
    if app_entity.custom_domain_status == "active":
        app_entity.custom_domain_status = "pending_verification"
    await session.commit()
    return new_token


async def unbind_custom_domain(
    app_id: str,
    workspace_id: int,
    session: AsyncSession,
) -> bool:
    """Clear the bound custom domain + its verification token.

    Returns ``True`` when cleared, ``False`` when the app does not exist. The
    Caddy snippet / Traefik route is left to the next publish or manual cleanup —
    removing ingress config is intentionally out of scope for the unbind action.
    """
    from app.db import WorkspaceApp

    stmt = (
        select(WorkspaceApp)
        .where(
            WorkspaceApp.id == app_id,
            WorkspaceApp.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    app_entity = (await session.execute(stmt)).scalars().first()
    if not app_entity:
        return False

    app_entity.custom_domain = None
    app_entity.custom_domain_status = None
    app_entity.custom_domain_verify_token = None
    await session.commit()
    return True


__all__ = [
    "rotate_domain_token",
    "unbind_custom_domain",
    "verify_and_bind_custom_domain",
]
