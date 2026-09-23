"""Pitch-portal engagement beacon processing (Story 37.6 / AD-120).

Cookieless ``navigator.sendBeacon`` telemetry from ``pitch.nowing.ai`` lands on
``POST /public/pitch/{workspace_ref}/{lead_id}/beacon``.  Every eligible view is
appended to ``LeadActivityLog`` (the CRM timeline); Telegram push alerts to the
assigned sales rep are capped at one per 30 minutes per lead via the Redis lock
``lock:pitch_beacon:{lead_id}``.  Crawler user-agents and sub-3-second dwell
sessions are discarded as preview pings.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.observability.metrics import record_gateway_outbound

logger = logging.getLogger(__name__)

# AD-120: at most one Telegram push alert per 30 minutes per lead.
PITCH_BEACON_LOCK_TTL_SECONDS = 30 * 60
PITCH_BEACON_LOCK_PREFIX = "lock:pitch_beacon"

# AC-3: sessions shorter than this are link-preview pings, not real views.
MIN_DWELL_SECONDS = 3.0

# Crawler / link-preview user-agent markers.  Matched case-insensitively as
# substrings; keep specific markers (facebookexternalhit, ZaloPC-crawler)
# alongside the generic bot/preview family.  NOTE: no bare "zalo"/"whatsapp"
# here — the Zalo/WhatsApp in-app browsers keep those tokens in the UA, and
# Zalo is the product's primary outbound channel.
CRAWLER_UA_MARKERS: tuple[str, ...] = (
    "facebookexternalhit",
    "zalopc-crawler",
    "bot",
    "crawler",
    "spider",
    "preview",
    "slackbot",
    "telegrambot",
    "discordbot",
    "twitterbot",
    "linkedinbot",
    "headless",
    "lighthouse",
    "pingdom",
    "uptime",
)

# Link-preview fetchers whose UA is the bare product token (e.g.
# "WhatsApp/2.24.x"), unlike the in-app browser which keeps a full
# "Mozilla/5.0 …" UA.  Matched as a prefix on the lowercased UA.
CRAWLER_UA_PREFIXES: tuple[str, ...] = ("whatsapp/",)

_UA_MAX_LEN = 300
_SECTION_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
_NON_DIGIT_RE = re.compile(r"\D+")


def pitch_beacon_lock_key(lead_id: UUID | str) -> str:
    return f"{PITCH_BEACON_LOCK_PREFIX}:{lead_id}"


def is_crawler_user_agent(user_agent: str | None) -> bool:
    """AC-3: True when the UA looks like a link-preview crawler, not a human."""
    if not user_agent:
        return False
    ua = user_agent.lower()
    if any(ua.startswith(prefix) for prefix in CRAWLER_UA_PREFIXES):
        return True
    return any(marker in ua for marker in CRAWLER_UA_MARKERS)


def classify_device_type(user_agent: str | None) -> str:
    """Coarse device bucket derived from the UA (mobile / tablet / desktop)."""
    ua = (user_agent or "").lower()
    if any(m in ua for m in ("ipad", "tablet")):
        return "tablet"
    if any(m in ua for m in ("mobile", "iphone", "android")):
        return "mobile"
    return "desktop"


def sanitize_sections_viewed(sections: Any) -> list[str]:
    """Keep only well-formed section ids; beacon payloads are untrusted input."""
    if not isinstance(sections, list):
        return []
    clean: list[str] = []
    for item in sections[:20]:
        if isinstance(item, str) and _SECTION_ID_RE.match(item):
            clean.append(item)
    return clean


def build_zalo_deep_link(phone: str | None) -> str | None:
    """Normalize a VN phone into a ``https://zalo.me/{phone}`` chat deep-link."""
    if not phone:
        return None
    digits = _NON_DIGIT_RE.sub("", phone)
    if not digits:
        return None
    if digits.startswith("84"):
        normalized = digits
    elif digits.startswith("0"):
        normalized = f"84{digits[1:]}"
    else:
        normalized = digits
    return f"https://zalo.me/{normalized}"


async def resolve_pitch_workspace_id(
    session: AsyncSession, workspace_ref: str
) -> int | None:
    """Resolve the ``[workspace_slug]`` URL segment to a workspace id.

    Numeric refs map to ``workspaces.id`` directly (same convention as the
    public booking links).  Non-numeric slugs resolve through a published
    ``WorkspaceApp.slug`` so branded portal URLs stay stable per AD-119.
    """
    if workspace_ref.isdigit():
        return int(workspace_ref)

    from app.db import WorkspaceApp

    result = await session.execute(
        select(WorkspaceApp.workspace_id).where(
            WorkspaceApp.slug == workspace_ref,
            WorkspaceApp.status == "published",
        )
    )
    return result.scalar_one_or_none()


async def _resolve_alert_recipient_id(
    session: AsyncSession, lead: Any
) -> Any:
    """Assigned sales rep for the alert: lead owner → latest assignment →
    workspace owner."""
    if lead.assigned_to_user_id is not None:
        return lead.assigned_to_user_id

    from app.db import LeadAssignment, Workspace

    result = await session.execute(
        select(LeadAssignment.assigned_to_user_id)
        .where(
            LeadAssignment.lead_id == lead.id,
            LeadAssignment.workspace_id == lead.workspace_id,
            LeadAssignment.status == "assigned",
            LeadAssignment.assigned_to_user_id.is_not(None),
        )
        .order_by(LeadAssignment.created_at.desc())
        .limit(1)
    )
    assigned = result.scalar_one_or_none()
    if assigned is not None:
        return assigned

    workspace = await session.get(Workspace, lead.workspace_id)
    return workspace.user_id if workspace is not None else None


async def _resolve_zalo_deep_link(
    session: AsyncSession, lead: Any
) -> str | None:
    """Best verified phone for the lead → 1-click Zalo chat link (AC-4)."""
    from app.db import VerifiedContact

    result = await session.execute(
        select(VerifiedContact.phone)
        .where(
            VerifiedContact.lead_id == lead.id,
            VerifiedContact.workspace_id == lead.workspace_id,
            VerifiedContact.is_valid.is_(True),
            VerifiedContact.is_unlocked.is_(True),
            VerifiedContact.phone.is_not(None),
        )
        .order_by(VerifiedContact.confidence.desc())
        .limit(1)
    )
    phone = result.scalar_one_or_none()
    if phone:
        # PII is Fernet-encrypted at rest (AD-42/49); decrypt before linking —
        # same pattern as sequencer dispatch.
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )

        encryption = VerifiedContactEncryption()
        try:
            if encryption.is_encrypted(phone):
                phone = encryption.decrypt(phone)
        except Exception:  # decrypt failure → no link beats a garbage link
            logger.warning(
                "pitch beacon: phone decrypt failed for lead %s", lead.id
            )
            return None
    return build_zalo_deep_link(phone)


def _format_alert_message(
    *,
    lead: Any,
    dwell_seconds: float,
    sections_viewed: list[str],
    device_type: str,
    zalo_link: str | None,
) -> str:
    """MarkdownV2 Telegram alert with dwell, section read, and Zalo deep-link."""
    from app.gateway.telegram.formatting import escape_markdown_v2

    company = escape_markdown_v2(lead.company_name or "Prospect")
    lines = [
        f"🔥 *{company}* {escape_markdown_v2('đang xem mini-pitch portal!')}",
        "",
        escape_markdown_v2(
            f"⏱ Dwell: {int(dwell_seconds)}s · 📱 {device_type}"
        ),
    ]
    if sections_viewed:
        lines.append(
            escape_markdown_v2(f"📖 Sections: {', '.join(sections_viewed)}")
        )

    base_url = (config.NEXT_FRONTEND_URL or "").rstrip("/")
    if base_url:
        crm_link = f"{base_url}/dashboard/{lead.workspace_id}/leads/pipeline"
        lines.append(f"[Mở CRM pipeline]({crm_link})")
    if zalo_link:
        lines.append(f"[💬 Chat Zalo ngay]({zalo_link})")
    return "\n".join(lines)


async def _dispatch_telegram_alert(
    session: AsyncSession,
    lead: Any,
    *,
    dwell_seconds: float,
    sections_viewed: list[str],
    device_type: str,
) -> bool:
    """Send the instant Telegram push to the assigned sales rep (AC-4)."""
    from app.automations.services.telegram_notifications import (
        resolve_telegram_binding_for_run,
    )
    from app.gateway.accounts import account_token
    from app.gateway.telegram.adapter import TelegramAdapter

    user_id = await _resolve_alert_recipient_id(session, lead)
    if user_id is None:
        logger.info(
            "pitch beacon: no recipient for lead %s ws %s",
            lead.id,
            lead.workspace_id,
        )
        return False

    binding = await resolve_telegram_binding_for_run(
        session, user_id, lead.workspace_id
    )
    if binding is None or not binding.external_peer_id:
        logger.info(
            "pitch beacon: no Telegram binding for user %s ws %s",
            user_id,
            lead.workspace_id,
        )
        return False

    token = account_token(binding.account)
    if not token:
        logger.warning(
            "pitch beacon: no token for Telegram account %s", binding.account_id
        )
        return False

    zalo_link = await _resolve_zalo_deep_link(session, lead)
    text = _format_alert_message(
        lead=lead,
        dwell_seconds=dwell_seconds,
        sections_viewed=sections_viewed,
        device_type=device_type,
        zalo_link=zalo_link,
    )
    try:
        adapter = TelegramAdapter(token)
        await adapter.send_message(
            external_peer_id=binding.external_peer_id,
            text=text,
            parse_mode="MarkdownV2",
        )
        record_gateway_outbound(platform="telegram", kind="send", status="sent")
        return True
    except Exception:  # delivery is best-effort; the timeline row still stands
        logger.exception(
            "pitch beacon: Telegram alert failed for lead %s", lead.id
        )
        record_gateway_outbound(platform="telegram", kind="send", status="failed")
        return False


async def record_pitch_beacon(
    session: AsyncSession,
    redis_client: Any,
    *,
    lead: Any,
    dwell_seconds: float,
    sections_viewed: Any,
    device_type: str | None,
    session_id: str | None,
    event: str | None,
    user_agent: str | None,
) -> str:
    """Process one beacon. Returns the outcome for logging/tests.

    Outcomes: ``filtered_crawler``, ``filtered_short_dwell``,
    ``recorded_alerted``, ``recorded_silent``.
    """
    if is_crawler_user_agent(user_agent):
        return "filtered_crawler"
    if dwell_seconds < MIN_DWELL_SECONDS:
        return "filtered_short_dwell"

    sections = sanitize_sections_viewed(sections_viewed)
    device = device_type or classify_device_type(user_agent)

    # AD-120 cooldown: the lock is acquired before writing so concurrent
    # beacons for the same lead cannot both trigger an alert.
    lock_key = pitch_beacon_lock_key(lead.id)
    alert_due = False
    try:
        alert_due = bool(
            await redis_client.set(
                lock_key,
                "1",
                nx=True,
                ex=PITCH_BEACON_LOCK_TTL_SECONDS,
            )
        )
    except Exception:  # fail closed: never spam Telegram when Redis is down
        logger.warning(
            "pitch beacon: redis lock failed for lead %s; alert suppressed",
            lead.id,
            exc_info=True,
        )

    alerted = False
    if alert_due:
        try:
            alerted = await _dispatch_telegram_alert(
                session,
                lead,
                dwell_seconds=dwell_seconds,
                sections_viewed=sections,
                device_type=device,
            )
        except Exception:  # dispatch must never lose the timeline row
            logger.exception(
                "pitch beacon: alert dispatch raised for lead %s", lead.id
            )
        if not alerted:
            # Release the cooldown so a transient failure doesn't suppress
            # retries for the full 30 minutes.
            try:
                await redis_client.delete(lock_key)
            except Exception:
                logger.warning(
                    "pitch beacon: failed to release lock %s", lock_key
                )

    from app.db import LeadActivityLog

    title = f"Xem mini-pitch portal ({int(dwell_seconds)}s)"
    # Dedupe by session_id: heartbeats/close events update the session's
    # existing row instead of stacking duplicates.
    existing = None
    if session_id:
        result = await session.execute(
            select(LeadActivityLog)
            .where(
                LeadActivityLog.workspace_id == lead.workspace_id,
                LeadActivityLog.lead_id == lead.id,
                LeadActivityLog.activity_type == "pitch_portal_view",
                LeadActivityLog.details["session_id"].astext == session_id,
            )
            .order_by(LeadActivityLog.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

    if existing is not None:
        details = dict(existing.details or {})
        merged_sections = list(
            dict.fromkeys((details.get("sections_viewed") or []) + sections)
        )
        details.update(
            {
                "dwell_seconds": dwell_seconds,
                "sections_viewed": merged_sections,
                "device_type": device,
                "session_id": session_id,
                "event": event,
                "telegram_alerted": bool(details.get("telegram_alerted"))
                or alerted,
                "user_agent": (user_agent or "")[:_UA_MAX_LEN],
            }
        )
        existing.details = details
        existing.title = title
    else:
        session.add(
            LeadActivityLog(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                actor_user_id=None,
                activity_type="pitch_portal_view",
                title=title,
                details={
                    "dwell_seconds": dwell_seconds,
                    "sections_viewed": sections,
                    "device_type": device,
                    "session_id": session_id,
                    "event": event,
                    "telegram_alerted": alerted,
                    "user_agent": (user_agent or "")[:_UA_MAX_LEN],
                },
            )
        )
    return "recorded_alerted" if alerted else "recorded_silent"
