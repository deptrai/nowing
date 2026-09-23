"""Mini-pitch portal generation + self-serve opt-out (Story 37.5 / AD-119).

The sequencer's ``generate_pitch_portal`` step (or a send step whose template
references ``{pitch_portal_url}``) triggers a 1-click portal build: sanitized,
deterministic per-lead metadata cached in Redis under
``pitch_portal:{lead_id}`` and rendered by the single multi-tenant SSR route
``pitch.nowing.ai/{workspace_ref}/{lead_id}`` — no per-lead containers.

Generation is intentionally template-based, not LLM-based: the artifact must be
reproducible so a cache miss rebuilds the exact same portal (idempotent).  The
portal URL itself is deterministic (``{base}/{workspace_ref}/{lead_uuid}``), so
re-enrollment or repeat sends always produce the same link.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config

logger = logging.getLogger(__name__)

PITCH_PORTAL_CACHE_PREFIX = "pitch_portal"
PITCH_PORTAL_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 days — outlives any cadence
PITCH_PORTAL_CONTENT_VERSION = 1

_DEFAULT_PITCH_BASE = "https://pitch.nowing.ai"

# Matches {pitch_portal_url} and {{pitch_portal_url}} in cadence copy.
_PITCH_TOKEN_RE = re.compile(r"\{+\s*pitch_portal_url\s*\}+")

_TAG_RE = re.compile(r"<[^>]*>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$", re.IGNORECASE)


def sanitize_text(value: Any, max_len: int = 200) -> str:
    """Strip HTML tags/control chars from untrusted prospect fields (AC-3).

    React escaping on the SSR page is the primary XSS barrier; this is the
    defense-in-depth layer so cached content never carries markup.
    """
    if not isinstance(value, str) or not value:
        return ""
    text = _CONTROL_RE.sub("", value)
    text = _TAG_RE.sub("", text)
    text = text.replace("<", "").replace(">", "")  # stray brackets
    return text.strip()[:max_len]


def template_requests_pitch_portal(template_data: Any) -> bool:
    """True when any string in the step template references the portal URL."""
    if isinstance(template_data, str):
        return bool(_PITCH_TOKEN_RE.search(template_data))
    if isinstance(template_data, dict):
        return any(
            template_requests_pitch_portal(v) for v in template_data.values()
        )
    if isinstance(template_data, (list, tuple)):
        return any(template_requests_pitch_portal(v) for v in template_data)
    return False


def pitch_portal_cache_key(lead_id: UUID | str) -> str:
    return f"{PITCH_PORTAL_CACHE_PREFIX}:{lead_id}"


def build_pitch_portal_url(workspace_ref: str | int, lead_id: UUID | str) -> str:
    base = (
        getattr(config, "PITCH_PORTAL_BASE_URL", None) or _DEFAULT_PITCH_BASE
    ).rstrip("/")
    return f"{base}/{workspace_ref}/{lead_id}"


async def resolve_workspace_portal_ref(
    session: AsyncSession, workspace_id: int
) -> str:
    """Public URL segment for the workspace: published app slug (branded) or
    the numeric id — both resolve through ``resolve_pitch_workspace_id``."""
    from app.db import WorkspaceApp

    result = await session.execute(
        select(WorkspaceApp.slug)
        .where(
            WorkspaceApp.workspace_id == workspace_id,
            WorkspaceApp.status == "published",
        )
        .order_by(WorkspaceApp.updated_at.desc())
        .limit(1)
    )
    slug = result.scalar_one_or_none()
    return slug or str(workspace_id)


def _prospect_logo_url(domain: Any) -> str | None:
    """Prospect logo from its public domain favicon; None when no clean domain."""
    d = sanitize_text(domain, 255).lower()
    if not d or not _DOMAIN_RE.match(d):
        return None
    return f"https://www.google.com/s2/favicons?domain={d}&sz=128"


def build_portal_content(lead: Any) -> dict[str, Any]:
    """Deterministic sanitized portal content for one lead (AC-2/AC-3).

    ponytail: copy is template-generated, not LLM-generated — deterministic
    output is what makes the Redis cache idempotent. Upgrade path: swap this
    for an LLM call keyed on a content hash if personalization quality needs it.
    """
    company = sanitize_text(getattr(lead, "company_name", None), 200) or (
        "Doanh nghiệp"
    )
    industry = sanitize_text(getattr(lead, "industry", None), 100)
    location = sanitize_text(getattr(lead, "location", None), 100)
    ind_label = industry or "B2B"
    where = f" tại {location}" if location else ""

    return {
        "version": PITCH_PORTAL_CONTENT_VERSION,
        "headline": f"3 đòn bẩy tối ưu tỷ lệ chốt hợp đồng B2B cho {company}",
        "exec_summary": (
            f"{company} đang hoạt động trong lĩnh vực {ind_label}{where}. "
            "Nowing gom lead enrichment, sequencing đa kênh (Email/Zalo/"
            "Telegram) và cảnh báo realtime vào một workstation duy nhất — "
            "giúp đội sales chạm đúng khách đúng lúc thay vì gửi tin lạnh "
            "hàng loạt."
        ),
        "exec_cards": [
            {
                "tone": "red",
                "title": "Thực trạng",
                "body": (
                    f"Tỷ lệ phản hồi email lạnh ngành {ind_label} "
                    "đang rơi xuống dưới 4%."
                ),
            },
            {
                "tone": "yellow",
                "title": "Khoảng trống",
                "body": (
                    "Đối thủ cùng ngành đang tiếp cận khách hàng trực tiếp "
                    "qua Zalo và các tín hiệu intent realtime."
                ),
            },
            {
                "tone": "green",
                "title": "Giải pháp Nowing",
                "body": (
                    "Kịch bản tiếp cận theo tín hiệu mở rộng doanh nghiệp, "
                    "tự động hoá cadence và bắn cảnh báo Telegram khi "
                    "prospect mở portal này."
                ),
            },
        ],
        "logo_url": _prospect_logo_url(getattr(lead, "domain", None)),
        # ROI slider seeds; the interactive calculator lives in the SSR page.
        "roi": {
            "default_sales_reps": 3,
            "min_sales_reps": 1,
            "max_sales_reps": 20,
            "meetings_per_rep_per_month": 5,
            "data_saving_per_rep_vnd": 8_000_000,
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _cached_fields_valid(content: dict[str, Any]) -> bool:
    """Shape-check the fields the /meta route serializes so a poisoned cache
    blob (e.g. ``exec_cards`` as a string, ``roi`` out of bounds) is treated as
    a miss instead of surfacing a Pydantic error at response time."""
    from pydantic import ValidationError

    from app.schemas.pitch import PitchExecCard, PitchRoiDefaults

    try:
        for card in content.get("exec_cards") or []:
            PitchExecCard.model_validate(card)
        if content.get("roi") is not None:
            PitchRoiDefaults.model_validate(content["roi"])
    except (ValidationError, TypeError):
        return False
    return True


async def _get_or_build_content(
    session: AsyncSession,
    redis_client: Any,
    lead: Any,
) -> tuple[dict[str, Any], bool]:
    """Return ``(content, cache_hit)``.  Cache miss rebuilds deterministically
    and repopulates Redis — a flushed cache therefore never changes the portal.

    Cached blobs must be a dict at the current content version; anything else
    (legacy shape, malformed JSON decoded to a scalar) is treated as a miss and
    overwritten so a poisoned entry cannot serve for the full TTL.
    """
    content: dict[str, Any] | None = None
    key = pitch_portal_cache_key(lead.id)
    if redis_client is not None:
        try:
            raw = await redis_client.get(key)
            if raw:
                cached = json.loads(raw)
                if (
                    isinstance(cached, dict)
                    and cached.get("version") == PITCH_PORTAL_CONTENT_VERSION
                    and _cached_fields_valid(cached)
                ):
                    content = cached
        except Exception:  # degraded cache → rebuild; never block the portal
            logger.warning(
                "pitch portal: cache read failed for lead %s", lead.id
            )
    if content is not None:
        return content, True

    content = build_portal_content(lead)
    # Pin the workspace ref inside the artifact so the emitted URL never
    # changes when the workspace republishes a different app later.
    content["workspace_ref"] = await resolve_workspace_portal_ref(
        session, lead.workspace_id
    )
    if redis_client is not None:
        try:
            await redis_client.set(
                key,
                json.dumps(content, ensure_ascii=False),
                ex=PITCH_PORTAL_CACHE_TTL_SECONDS,
            )
        except Exception:  # cache write failure is non-fatal
            logger.warning(
                "pitch portal: cache write failed for lead %s", lead.id
            )
    return content, False


async def ensure_pitch_portal(
    session: AsyncSession,
    redis_client: Any,
    lead: Any,
) -> dict[str, Any]:
    """Idempotent portal build (AC-5).  Returns ``{url, content, cache_hit}``."""
    content, cache_hit = await _get_or_build_content(
        session, redis_client, lead
    )
    workspace_ref = content.get("workspace_ref")
    if not workspace_ref:
        # Pre-version-1 blobs (or a hand-seeded cache) may lack the pinned ref.
        workspace_ref = await resolve_workspace_portal_ref(
            session, lead.workspace_id
        )
    return {
        "url": build_pitch_portal_url(workspace_ref, lead.id),
        "content": content,
        "cache_hit": cache_hit,
    }


async def get_portal_content(
    session: AsyncSession,
    redis_client: Any,
    lead: Any,
) -> dict[str, Any]:
    """Read path for ``GET .../meta`` — lazily builds on first view so a link
    rendered before the generate step ran still produces a full portal."""
    content, _ = await _get_or_build_content(session, redis_client, lead)
    return content


async def _dnc_record_from_stored_hmac(
    opt_out_service: Any,
    contact: Any,
    record_type: str,
    *,
    workspace_id: int,
    reason: str,
) -> bool:
    """Fallback DNC write when a contact value can't be decrypted: reuse the
    stored blind ``phone_hmac``/``email_hmac`` (the same index ``is_blocked``
    recomputes) so undecryptable PII still blocks future sends."""
    stored_hmac = getattr(contact, f"{record_type}_hmac", None)
    if not stored_hmac:
        return False
    await opt_out_service._ensure_dnc_record(
        workspace_id=workspace_id,
        record_type=record_type,
        value="(encrypted)",  # value column is a display field; hmac is the key
        value_hmac=stored_hmac,
        reason=reason,
        global_scope=False,
    )
    return True


async def process_pitch_opt_out(
    session: AsyncSession,
    redis_client: Any = None,
    *,
    lead: Any,
    ip_address: str | None = None,
) -> int:
    """Decree 13 self-serve opt-out from the portal footer (AC-4).

    Delegates per-value purging to ``OptOutService.process_opt_out`` so this
    path keeps the established semantics: workspace row lock, normalized-value
    DNC record, purge of ALL hmac-matching contacts (including ``is_valid=
    False`` rows), unlock refund, and audit log.  When a stored value can't be
    decrypted, a DNC record is written from the stored blind HMAC so sends are
    still blocked.  Every contact row is anonymized regardless (idempotent).

    Also marks the lead ``withdrawn``, cancels pending enrollments (with a
    version bump so the OCC guard catches in-flight sends), evicts the cached
    portal so the personalized page stops rendering, and logs the timeline.
    """
    from app.db import (
        LeadActivityLog,
        SequenceEnrollment,
        VerifiedContact,
        Workspace,
    )
    from app.lead_intelligence.dnc.service import DncComplianceService
    from app.services.pii.opt_out_service import (
        OptOutService,
        OptOutValidationError,
        _anonymize_contact,
        _append_opt_out_audit_log,
    )

    workspace = await session.get(Workspace, lead.workspace_id)
    actor = getattr(lead, "assigned_to_user_id", None) or getattr(
        workspace, "user_id", None
    )
    reason = "Self-serve opt-out via pitch portal (Decree 13/2023/NĐ-CP)"
    opt_out_service = OptOutService(session)
    try:
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )

        encryption = VerifiedContactEncryption()
    except Exception:  # no key configured → purge still proceeds via HMAC path
        encryption = None

    contacts = (
        (
            await session.execute(
                select(VerifiedContact)
                .where(
                    VerifiedContact.lead_id == lead.id,
                    VerifiedContact.workspace_id == lead.workspace_id,
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )

    purged = 0
    seen: set[tuple[str, str]] = set()
    dnc_fallback_written = False
    for contact in contacts:
        for record_type, raw in (
            ("phone", contact.phone),
            ("email", contact.email),
        ):
            decrypted = None
            if raw:
                try:
                    decrypted = (
                        encryption.decrypt(raw)
                        if encryption is not None
                        and encryption.is_encrypted(raw)
                        else raw
                    )
                except Exception:  # decrypt failure → HMAC fallback below
                    decrypted = None

            if decrypted:
                key = (record_type, decrypted)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    await opt_out_service.process_opt_out(
                        workspace_id=lead.workspace_id,
                        record_type=record_type,
                        value=decrypted,
                        actor_user_id=actor,
                        ip_address=ip_address,
                        global_scope=False,
                        reason=reason,
                    )
                    continue
                except OptOutValidationError:
                    pass  # un-normalizable value → HMAC fallback below
                except Exception:  # keep purging remaining contacts
                    logger.exception(
                        "pitch opt-out: process_opt_out failed for lead %s",
                        lead.id,
                    )
            dnc_fallback_written = (
                await _dnc_record_from_stored_hmac(
                    opt_out_service,
                    contact,
                    record_type,
                    workspace_id=lead.workspace_id,
                    reason=reason,
                )
                or dnc_fallback_written
            )

        _anonymize_contact(contact)
        _append_opt_out_audit_log(
            contact,
            actor_id=actor or "pitch_portal_self_serve",
            ip_address=ip_address,
            reason=reason,
        )
        purged += 1

    # Mark the lead withdrawn and stop any pending cadence sends. The version
    # bump lets the OCC/CAS guard in execute_enrollment_step detect the
    # withdrawal instead of overwriting it for an in-flight enrollment.
    lead.consent_status = "withdrawn"
    await session.execute(
        update(SequenceEnrollment)
        .where(
            SequenceEnrollment.lead_id == lead.id,
            SequenceEnrollment.workspace_id == lead.workspace_id,
            SequenceEnrollment.status.in_(
                ["scheduled", "executing", "paused"]
            ),
        )
        .values(
            status="unsubscribed",
            scheduled_at=None,
            version=SequenceEnrollment.version + 1,
            updated_at=datetime.now(UTC),
        )
    )

    # Evict the cached portal artifact — a withdrawn lead's personalized page
    # must stop rendering (the /meta route also 404s on withdrawn consent).
    if redis_client is not None:
        try:
            await redis_client.delete(pitch_portal_cache_key(lead.id))
        except Exception:
            logger.warning(
                "pitch opt-out: portal cache delete failed lead=%s", lead.id
            )

    session.add(
        LeadActivityLog(
            workspace_id=lead.workspace_id,
            lead_id=lead.id,
            actor_user_id=None,
            activity_type="pitch_portal_opt_out",
            title="Yêu cầu xóa thông tin qua pitch portal",
            details={
                "purged_contacts": purged,
                "ip_address": ip_address,
                "reason": reason,
            },
        )
    )

    # process_opt_out invalidates the workspace DNC cache itself; only needed
    # here when fallback rows were written without going through it.
    if dnc_fallback_written:
        try:
            await DncComplianceService().invalidate_workspace_cache(
                lead.workspace_id
            )
        except Exception:  # rows persisted; cache expiry is best-effort
            logger.warning(
                "pitch opt-out: DNC cache invalidation failed ws=%s",
                lead.workspace_id,
            )
    return purged
