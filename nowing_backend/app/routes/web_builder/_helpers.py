"""REST API endpoints for Web Builder (Story 27.1 / Story 27.1b / AD-113 / AD-113a / AD-114)."""

import logging
import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Workspace

logger = logging.getLogger(__name__)


def is_web_builder_enabled_for_workspace(ws: Workspace | None) -> bool:
    """Check both global and workspace-level Web Builder feature flags."""
    if not config.WEB_BUILDER_ENABLED:
        return False
    return not (ws and ws.web_builder_enabled is False)


async def require_workspace_member(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> AuthContext:
    """Ensure that Web Builder is enabled for the workspace."""
    # Fail-closed per-workspace feature gate (AC-4 / P2).
    ws = (
        (await session.execute(select(Workspace).where(Workspace.id == workspace_id)))
        .scalars()
        .first()
    )
    if not is_web_builder_enabled_for_workspace(ws):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web Builder is not enabled on this workspace plan",
        )
    return auth


def check_web_builder_enabled():
    """Fail-closed gate checking WEB_BUILDER_ENABLED configuration."""
    if not config.WEB_BUILDER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web Builder is not enabled on this workspace plan",
        )


async def _get_workspace_for_build(
    session: AsyncSession, workspace_id: int
) -> Workspace:
    """Fetch workspace or raise 404; used by build quota gate."""
    ws = (
        (await session.execute(select(Workspace).where(Workspace.id == workspace_id)))
        .scalars()
        .first()
    )
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return ws


async def require_build_quota(
    session: AsyncSession,
    auth: AuthContext | None = None,
    workspace_id: int = 0,
) -> Workspace:
    """Fail-closed build quota gate using plan tier and workspace credit balance.

    Debits the build cost immediately when the workspace has sufficient credit.
    """
    ws = await _get_workspace_for_build(session, workspace_id)
    cost = config.WEB_BUILDER_BUILD_COST_MICROS
    if cost <= 0:
        return ws
    if ws.credit_micros_balance < cost:
        detail = (
            "Insufficient workspace credit balance for build. "
            f"Required: {cost} micros, "
            f"available: {ws.credit_micros_balance} micros."
        )
        if ws.plan_tier == "free":
            detail += " Upgrade your workspace plan to continue building."
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail)
    ws.credit_micros_balance -= cost
    await session.commit()
    return ws


def _is_valid_fqdn(domain: str) -> bool:
    """Validate a fully-qualified domain name (no IPs, no localhost, valid labels)."""
    clean = domain.strip().lower()
    if not clean or len(clean) > 255:
        return False
    # Reject raw IP addresses
    if re.match(r"^\d+\.\d+\.\d+\.\d+$|^\[[0-9a-f:]+\]$", clean):
        return False
    # Reject localhost / local suffixes
    if clean == "localhost" or clean.endswith(".local") or clean.endswith(".localhost"):
        return False
    # Must contain at least one dot and end in a TLD of >=2 letters
    if not re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$", clean):
        return False
    for label in clean.split("."):
        if not label or label.startswith("-") or label.endswith("-"):
            return False
        if len(label) > 63:
            return False
    return True
