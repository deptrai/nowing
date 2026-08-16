"""REST routes for Lead Clipper Chrome Extension (Story 24.4 / INV-24.5).

Implements 1-Click lead capturing from Facebook Groups, Batdongsan, TopCV, and other platforms.
Enforces:
1. PAT Scope `leads:clipper:write` gating & workspace authorization.
2. SHA-256 deduplication hashing: SHA256(workspace_id + source_canonical_url + normalized_phone).
3. URL canonicalization and Vietnamese phone number normalization.
4. Concurrency rollback recovery and multi-tenant client_id propagation.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Lead, Permission, VerifiedContact, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()

CLIPPER_REQUIRED_SCOPE = "leads:clipper:write"

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
    "_ga",
    "_gl",
    "gad_source",
    "gbraid",
    "wbraid",
    "igshid",
    "fb_action_ids",
    "fb_action_types",
    "mc_cid",
    "mc_eid",
}


def normalize_vietnamese_phone_raw(phone: str | None) -> str:
    """Normalize Vietnamese phone numbers to standard format (e.g., 0912345678 or +84912345678)."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("84") and len(digits) >= 10:
        digits = "0" + digits[2:].lstrip("0")
    elif not digits.startswith("0") and len(digits) == 9:
        digits = "0" + digits
    return digits


def canonicalize_url(url: str) -> str:
    """Strip tracking query parameters (utm_*, fbclid, etc.) and normalize URL structure."""
    if not url:
        return ""
    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        clean_url = f"https://{clean_url}"
    parsed = urlparse(clean_url)
    # Filter out tracking query params
    filtered_query = [
        (k, v)
        for k, v in parse_qsl(parsed.query)
        if not k.startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    clean_query = urlencode(filtered_query)
    clean_path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
    return urlunparse(
        (
            parsed.scheme.lower() or "https",
            parsed.netloc.lower(),
            clean_path,
            parsed.params,
            clean_query,
            "",  # strip fragment
        )
    )


def compute_clipper_dedupe_hash(
    workspace_id: int,
    source_canonical_url: str,
    phone: str | None = None,
) -> str:
    """Compute deterministic SHA-256 deduplication hash according to INV-24.5.

    dedupe_hash = SHA256(workspace_id + source_canonical_url + normalized_phone)
    """
    clean_url = canonicalize_url(source_canonical_url)
    norm_phone = normalize_vietnamese_phone_raw(phone)
    raw_key = f"{workspace_id}:{clean_url}:{norm_phone}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class LeadClipRequest(BaseModel):
    """Pydantic model validating lead clipper payloads."""

    source_canonical_url: str = Field(..., description="Canonical URL of listing or profile")
    source_platform: str = Field(
        ...,
        description="Source platform: facebook, batdongsan, topcv, linkedin, chotot, custom",
    )
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    post_content: str | None = Field(default=None)
    price: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)
    dedupe_hash: str | None = Field(default=None)


class LeadClipResponse(BaseModel):
    """Response returned upon successful lead clipping."""

    success: bool = True
    lead_id: UUID
    workspace_id: int
    dedupe_hash: str
    is_duplicate: bool
    source_platform: str
    message: str = "Lead clipped successfully"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


async def _verify_clipper_auth(
    auth: AuthContext,
    workspace_id: int,
    session: AsyncSession,
) -> None:
    """Verify PAT scope or session membership permissions for clipping leads."""
    if auth.method == "pat":
        if auth.pat is None or not getattr(auth.pat, "is_valid", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Personal Access Token is expired or revoked",
            )
        scopes = getattr(auth.pat, "scopes", []) or []
        if CLIPPER_REQUIRED_SCOPE not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"PAT missing required scope: {CLIPPER_REQUIRED_SCOPE}",
            )
        pat_workspace_id = getattr(auth.pat, "workspace_id", None)
        if pat_workspace_id is not None and pat_workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="PAT not authorized for target workspace",
            )
    elif auth.method == "session":
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.LEADS_WRITE.value,
            error_message="You don't have permission to create leads in this workspace",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )


@router.post(
    "/workspaces/{workspace_id}/leads/clip",
    response_model=LeadClipResponse,
    status_code=status.HTTP_200_OK,
)
async def clip_lead(
    workspace_id: int,
    body: LeadClipRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> LeadClipResponse:
    """Clip a lead from external web platforms with SHA-256 deduplication and PAT auth."""
    await _verify_clipper_auth(auth, workspace_id, session)

    clean_url = canonicalize_url(body.source_canonical_url)
    dedupe_hash = compute_clipper_dedupe_hash(
        workspace_id=workspace_id,
        source_canonical_url=clean_url,
        phone=body.phone,
    )

    # Check for existing lead with identical dedupe hash in the workspace
    stmt = select(Lead).where(
        Lead.workspace_id == workspace_id,
        Lead.value_hmac == dedupe_hash,
    )
    result = await session.execute(stmt)
    existing_lead = result.scalars().first()

    if existing_lead is not None:
        return LeadClipResponse(
            success=True,
            lead_id=existing_lead.id,
            workspace_id=workspace_id,
            dedupe_hash=dedupe_hash,
            is_duplicate=True,
            source_platform=body.source_platform,
            message="Lead already exists in workspace (deduplicated)",
        )

    # Multi-tenant and domain resolution
    client_id = getattr(auth, "client_id", None)
    parsed_domain = urlparse(clean_url).netloc.lower() or None

    # Create new Lead record
    company_or_author = body.company_name or body.contact_name or "Khách hàng tiềm năng"
    new_lead = Lead(
        id=uuid4(),
        workspace_id=workspace_id,
        client_id=client_id,
        source=body.source_platform,
        source_url=clean_url,
        domain=parsed_domain,
        company_name=company_or_author,
        location=body.location,
        value_hmac=dedupe_hash,
        status="new",
        enriched=False,
    )
    session.add(new_lead)

    if body.phone or body.email or body.contact_name:
        contact_title = body.price or (body.post_content[:200] if body.post_content else None)
        verified_contact = VerifiedContact(
            id=uuid4(),
            workspace_id=workspace_id,
            client_id=client_id,
            lead_id=new_lead.id,
            name=body.contact_name,
            title=contact_title,
            phone=normalize_vietnamese_phone_raw(body.phone) or body.phone,
            email=body.email.strip().lower() if body.email else None,
            verification_status="unverified",
        )
        session.add(verified_contact)

    try:
        await session.commit()
        await session.refresh(new_lead)
    except Exception as exc:
        await session.rollback()
        logger.warning(
            "Clipper commit conflict or IntegrityError in workspace %s: %s",
            workspace_id,
            exc,
        )
        # Attempt to recover by fetching existing lead with identical dedupe hash
        stmt_recover = select(Lead).where(
            Lead.workspace_id == workspace_id,
            Lead.value_hmac == dedupe_hash,
        )
        res_recover = await session.execute(stmt_recover)
        duplicate_lead = res_recover.scalars().first()
        if duplicate_lead is not None:
            return LeadClipResponse(
                success=True,
                lead_id=duplicate_lead.id,
                workspace_id=workspace_id,
                dedupe_hash=dedupe_hash,
                is_duplicate=True,
                source_platform=body.source_platform,
                message="Lead already exists in workspace (deduplicated via rollback)",
            )
        raise

    return LeadClipResponse(
        success=True,
        lead_id=new_lead.id,
        workspace_id=workspace_id,
        dedupe_hash=dedupe_hash,
        is_duplicate=False,
        source_platform=body.source_platform,
        message="Lead clipped successfully",
    )

