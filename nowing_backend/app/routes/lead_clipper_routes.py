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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    Lead,
    Permission,
    SignalEvent,
    VerifiedContact,
    get_async_session,
)
from app.lead_intelligence.dnc.normalizer import (
    compute_phone_hmac,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.redis_client import get_redis_client
from app.services.lead_assignment_service import LeadAssignmentService
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
from app.services.pitch_portal import ensure_pitch_portal, sanitize_text
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
    session_permission: str = Permission.LEADS_WRITE.value,
) -> None:
    """Verify PAT scope or session membership permissions for clipper endpoints."""
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
            session_permission,
            error_message="You don't have permission to access leads in this workspace",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )



async def _find_duplicate_lead(
    session: AsyncSession,
    workspace_id: int,
    dedupe_hash: str,
) -> Lead | None:
    """Return an existing lead in the workspace with the same dedupe hash."""
    stmt = select(Lead).where(
        Lead.workspace_id == workspace_id,
        Lead.value_hmac == dedupe_hash,
    )
    result = await session.execute(stmt)
    return result.scalars().first()


def _build_lead_record(
    body: LeadClipRequest,
    workspace_id: int,
    client_id: UUID | None,
    clean_url: str,
    dedupe_hash: str,
) -> Lead:
    """Construct a new Lead from the clip request."""
    parsed_domain = urlparse(clean_url).netloc.lower() or None
    company_or_author = body.company_name or body.contact_name or "Khách hàng tiềm năng"
    return Lead(
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


def _build_verified_contact(
    body: LeadClipRequest,
    workspace_id: int,
    client_id: UUID | None,
    lead_id: UUID,
) -> VerifiedContact | None:
    """Construct an encrypted VerifiedContact if any PII is present."""
    if not (body.phone or body.email or body.contact_name):
        return None

    contact_title = body.price or (body.post_content[:200] if body.post_content else None)
    contact_enc = VerifiedContactEncryption()
    encrypted = contact_enc.encrypt_contact(
        {
            "name": body.contact_name,
            "title": contact_title,
            "phone": normalize_vietnamese_phone_raw(body.phone) or body.phone,
            "email": body.email.strip().lower() if body.email else None,
            "verification_status": "unverified",
            "confidence": 0.0,
            "source_provider": "lead_clipper",
        }
    )
    return VerifiedContact(
        id=uuid4(),
        workspace_id=workspace_id,
        client_id=client_id,
        lead_id=lead_id,
        name=encrypted.get("name"),
        title=encrypted.get("title"),
        phone=encrypted.get("phone"),
        email=encrypted.get("email"),
        verification_status=encrypted.get("verification_status", "unverified"),
        confidence=encrypted.get("confidence", 0.0),
        source_provider=encrypted.get("source_provider", "fallback"),
    )


async def _assign_clipped_lead(
    session: AsyncSession,
    redis_client: Any,
    workspace_id: int,
    lead_id: UUID,
) -> None:
    """Trigger round-robin assignment, logging any non-fatal failure."""
    assignment_service = LeadAssignmentService(
        session=session,
        redis_client=redis_client,
    )
    try:
        await assignment_service.assign_leads_batch(
            workspace_id=workspace_id,
            lead_ids=[lead_id],
        )
    except Exception:  # best-effort lead auto-assignment; failure doesn't fail primary op
        logger.exception("Failed to auto-assign clipped lead in workspace %s", workspace_id)


async def _commit_or_recover_duplicate(
    session: AsyncSession,
    new_lead: Lead,
    workspace_id: int,
    dedupe_hash: str,
    body: LeadClipRequest,
) -> LeadClipResponse:
    """Commit the new lead, or recover an existing one on a dedupe race."""
    try:
        await session.commit()
        await session.refresh(new_lead)
    except IntegrityError:
        await session.rollback()
        duplicate_lead = await _find_duplicate_lead(session, workspace_id, dedupe_hash)
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
    redis_client: Any = Depends(get_redis_client),
) -> LeadClipResponse:
    """Clip a lead from external web platforms with SHA-256 deduplication and PAT auth."""
    await _verify_clipper_auth(auth, workspace_id, session)

    clean_url = canonicalize_url(body.source_canonical_url)
    dedupe_hash = compute_clipper_dedupe_hash(
        workspace_id=workspace_id,
        source_canonical_url=clean_url,
        phone=body.phone,
    )

    existing_lead = await _find_duplicate_lead(session, workspace_id, dedupe_hash)
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

    client_id = getattr(auth, "client_id", None)
    new_lead = _build_lead_record(body, workspace_id, client_id, clean_url, dedupe_hash)
    session.add(new_lead)

    verified_contact = _build_verified_contact(body, workspace_id, client_id, new_lead.id)
    if verified_contact is not None:
        session.add(verified_contact)

    await _assign_clipped_lead(session, redis_client, workspace_id, new_lead.id)

    return await _commit_or_recover_duplicate(
        session, new_lead, workspace_id, dedupe_hash, body
    )


# ---------------------------------------------------------------------------
# Story 37.4: Zalo Co-pilot overlay context (AC-1/AC-2/AC-4)
# ---------------------------------------------------------------------------

COPILOT_MAX_SIGNALS = 5


class ZaloCopilotSignal(BaseModel):
    """A recent intent signal attached to the matched prospect company."""

    signal_type: str
    confidence: float
    detected_at: datetime
    source_url: str | None = None


class ZaloCopilotLead(BaseModel):
    """Prospect company context rendered inside the Zalo drawer (AC-2)."""

    lead_id: UUID
    company_name: str
    contact_name: str | None = None
    contact_title: str | None = None
    industry: str | None = None
    location: str | None = None
    domain: str | None = None
    status: str
    intent_score: float | None = None


class ZaloCopilotContextResponse(BaseModel):
    """Context payload for the Zalo co-pilot drawer.

    ``matched=False`` means no *unlocked* lead owns this phone in the
    workspace — the extension hides the pill but still honours ``dnc_blocked``
    so a blacklisted number surfaces the red banner either way (AC-4).
    """

    matched: bool
    phone_e164: str | None = None
    dnc_blocked: bool = False
    dnc_reason: str | None = None
    lead: ZaloCopilotLead | None = None
    signals: list[ZaloCopilotSignal] = Field(default_factory=list)
    pitch_short: str | None = None
    pitch_with_link: str | None = None
    pitch_portal_url: str | None = None


def _decrypt_contact_field(value: str | None) -> str | None:
    """Best-effort PII decrypt for an unlocked contact; None on failure."""
    if not value:
        return None
    enc = VerifiedContactEncryption()
    if not enc.is_encrypted(value):
        return value
    try:
        return enc.decrypt(value)
    except Exception:  # corrupt ciphertext must not break the drawer
        return None


def _build_zalo_pitch_copy(
    lead: Lead,
    contact_name: str | None,
    portal_url: str | None,
) -> tuple[str, str]:
    """Deterministic Vietnamese pitch copy for the two drawer tabs (AC-2).

    ponytail: template-generated, not LLM-generated — the overlay must render
    instantly and deterministic copy keeps the endpoint idempotent. Upgrade
    path: LLM personalization keyed on lead content hash.
    """
    company = sanitize_text(getattr(lead, "company_name", None), 200) or (
        "doanh nghiệp mình"
    )
    industry = sanitize_text(getattr(lead, "industry", None), 100)
    ind_clause = f" trong lĩnh vực {industry}" if industry else ""
    name = sanitize_text(contact_name, 100)
    greeting = f"Chào anh/chị {name}" if name else "Chào anh/chị"

    short = (
        f"{greeting}, em bên Nowing ạ. "
        f"Em thấy {company} đang hoạt động{ind_clause}. "
        "Bên em giúp đội sales B2B tự động hoá tiếp cận khách hàng và bắt "
        "tín hiệu mua hàng theo thời gian thực — anh/chị cho em xin 10 phút "
        "trao đổi nhanh để xem có phù hợp không ạ?"
    )
    if portal_url:
        return short, (
            f"{short}\n\nEm gửi kèm mini-pitch cá nhân hoá cho {company} "
            f"tại đây ạ: {portal_url}"
        )
    return short, short


@router.get(
    "/workspaces/{workspace_id}/leads/copilot-context",
    response_model=ZaloCopilotContextResponse,
    status_code=status.HTTP_200_OK,
)
async def get_zalo_copilot_context(
    workspace_id: int,
    phone: str = Query(..., min_length=5, max_length=32),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    redis_client: Any = Depends(get_redis_client),
) -> ZaloCopilotContextResponse:
    """Resolve an open Zalo chat phone to an unlocked lead + pitch context.

    AC-1: match on ``verified_contacts.phone_hmac`` restricted to
    ``is_unlocked`` contacts. AC-4: DNC is checked against the raw phone even
    when no lead matches so the extension can still block insertion.
    """
    await _verify_clipper_auth(
        auth, workspace_id, session, session_permission=Permission.LEADS_READ.value
    )

    e164 = normalize_phone_e164(phone)
    if not e164:
        return ZaloCopilotContextResponse(matched=False)

    dnc = await DncComplianceService().is_blocked(
        workspace_id, phone=e164, session=session
    )
    base = {
        "matched": False,
        "phone_e164": e164,
        "dnc_blocked": dnc.is_blocked,
        "dnc_reason": dnc.reason,
    }

    phone_hmac = compute_phone_hmac(e164)
    if not phone_hmac:
        return ZaloCopilotContextResponse(**base)

    contact_stmt = (
        select(VerifiedContact)
        .where(
            VerifiedContact.workspace_id == workspace_id,
            VerifiedContact.phone_hmac == phone_hmac,
            VerifiedContact.is_unlocked.is_(True),
            VerifiedContact.is_valid.is_(True),
        )
        .order_by(desc(VerifiedContact.created_at))
        .limit(1)
    )
    contact = (await session.execute(contact_stmt)).scalars().first()
    if contact is None:
        return ZaloCopilotContextResponse(**base)

    lead = await session.get(Lead, (contact.lead_id, workspace_id))
    if lead is None:
        return ZaloCopilotContextResponse(**base)

    signals_stmt = (
        select(SignalEvent)
        .where(
            SignalEvent.workspace_id == workspace_id,
            # Case-insensitive equality — ilike would treat %/_ in the
            # company name as wildcards and leak other companies' signals.
            func.lower(SignalEvent.company_name)
            == func.lower(lead.company_name or "\x00"),
        )
        .order_by(desc(SignalEvent.detected_at))
        .limit(COPILOT_MAX_SIGNALS)
    )
    signal_rows = (await session.execute(signals_stmt)).scalars().all()

    contact_name = _decrypt_contact_field(getattr(contact, "name", None))
    contact_title = _decrypt_contact_field(getattr(contact, "title", None))

    # Portal link is best-effort: drawer still works when pitch infra is
    # down. Skipped entirely when DNC-blocked — insertion is disabled, so
    # generating a portal would be pointless work (AC-4).
    portal_url: str | None = None
    if not dnc.is_blocked:
        try:
            portal = await ensure_pitch_portal(session, redis_client, lead)
            portal_url = portal.get("url")
        except Exception:  # pitch portal build must not fail the whole lookup
            logger.warning(
                "copilot-context: pitch portal build failed for lead %s",
                lead.id,
                exc_info=True,
            )

    pitch_short, pitch_with_link = _build_zalo_pitch_copy(
        lead, contact_name, portal_url
    )

    return ZaloCopilotContextResponse(
        matched=True,
        phone_e164=e164,
        dnc_blocked=dnc.is_blocked,
        dnc_reason=dnc.reason,
        lead=ZaloCopilotLead(
            lead_id=lead.id,
            company_name=lead.company_name,
            contact_name=contact_name,
            contact_title=contact_title,
            industry=lead.industry,
            location=lead.location,
            domain=lead.domain,
            status=lead.status,
            intent_score=lead.intent_score,
        ),
        signals=[
            ZaloCopilotSignal(
                signal_type=s.signal_type,
                confidence=s.confidence,
                detected_at=s.detected_at,
                source_url=s.source_url,
            )
            for s in signal_rows
        ],
        pitch_short=pitch_short,
        pitch_with_link=pitch_with_link,
        pitch_portal_url=portal_url,
    )

