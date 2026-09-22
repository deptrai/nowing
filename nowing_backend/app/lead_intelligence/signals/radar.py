"""Proactive Intent Signal Radar (Story 37.1 / AD-115).

Two background ingestion paths:

- **Periodic scanner** (``scan_high_intent_companies_periodic`` Celery Beat
  task, every 6h): for each active workspace, detects hiring surges (>=3 new
  job postings in 7 days across TopCV/VietnamWorks) and newly incorporated
  tax codes (masothue.com / dangkykinhdoanh.gov.vn), persisting
  ``SignalEvent`` rows at ``intent_score >= 0.75`` confidence.

- **Telegram stream matcher**: a consumer group on
  ``stream:telegram:raw_events`` runs an in-memory compiled Aho-Corasick
  keyword trie (O(n) per AD-115) to pre-filter purchase-intent messages,
  extracts contact info, and creates a ``Lead`` assigned round-robin via
  ``LeadAssignmentService``. Messages with no extractable phone/email become
  ``status='pending_enrichment'`` leads with zero credit deduction (AC-3).

Budget guardrails (AD-115): max ``MAX_SCANS_PER_WORKSPACE_PER_DAY`` scans per
workspace per day; a workspace pauses automatically when its shared credit
balance (``workspaces.credit_micros_balance``) falls below
``MIN_WORKSPACE_CREDIT_MICROS`` (50 credits).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import socket
import unicodedata
from collections import deque
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from redis.exceptions import ResponseError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Lead,
    LeadActivityLog,
    SignalEvent,
    SignalSubscription,
    SocialMonitoredTarget,
    Workspace,
    WorkspaceMembership,
    async_session_maker,
)
from app.lead_intelligence.services.lead_stream_service import generate_lead_hmac
from app.lead_intelligence.signals.service import SignalDetectionService
from app.proprietary.platforms.telegram.entity_extractor import (
    TelegramEntityExtractor,
)
from app.proprietary.platforms.telegram.stream_daemon import (
    STREAM_TELEGRAM_RAW_EVENTS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AD-115 constants
# ---------------------------------------------------------------------------

# intent_score >= 0.75 on the Lead scale (0-1) == confidence >= 75 on the
# SignalEvent scale (0-100).
RADAR_MIN_INTENT_SCORE = 0.75
RADAR_SIGNAL_CONFIDENCE = 80.0

HIRING_SURGE_MIN_POSTINGS = 3
HIRING_SURGE_LOOKBACK_DAYS = 7
HIRING_WATCHLIST_LOOKBACK_DAYS = 90
HIRING_WATCHLIST_MAX_COMPANIES = 50
HIRING_AGGREGATE_TIMEOUT_S = 30.0

MAX_SCANS_PER_WORKSPACE_PER_DAY = 100
MIN_WORKSPACE_CREDIT_MICROS = 50 * 1_000_000  # 50 credits (1 credit = $1 = 1e6 micros)
SCAN_COUNTER_TTL_SECONDS = 48 * 3600

# Re-alert the same company at most once per day for the same radar signal.
RADAR_SIGNAL_DEDUPE_HOURS = 20

TELEGRAM_INTENT_CONSUMER_GROUP = "telegram_intent_processors"
STREAM_TELEGRAM_INTENT_DLQ = "stream:telegram:intent_dlq"
DLQ_MAXLEN = 10_000
AUTOCLAIM_MIN_IDLE_TIME_MS = 60_000
MAX_MESSAGES_PER_BATCH = 100

TELEGRAM_CHANNEL_PLATFORM = "telegram_channel"

MASOTHUE_NEW_COMPANIES_URL = "https://masothue.com/tra-cuu-ma-so-thue-moi"
DKKD_NEW_BUSINESSES_URL = "https://dangkykinhdoanh.gov.vn/vn/Pages/DoanhNghiepMoi.aspx"
HTTP_TIMEOUT_S = 15.0

# Purchase-intent patterns (AD-115). Matching is accent- and case-insensitive
# so both "báo giá" and "bao gia" hit.
PURCHASE_INTENT_PATTERNS: tuple[str, ...] = (
    "cần tìm nhà cung cấp",
    "tìm nhà cung cấp",
    "cần báo giá",
    "xin báo giá",
    "báo giá",
    "tìm agency",
    "thuê agency",
    "tìm đơn vị",
    "thuê ngoài",
    "cần thuê ngoài",
    "tìm đối tác cung cấp",
    "cần tuyển đơn vị",
)


# ---------------------------------------------------------------------------
# Aho-Corasick keyword automaton (O(n) pre-filter, AD-115)
# ---------------------------------------------------------------------------


def _normalize_match_text(text: str) -> str:
    """Lowercase, strip Vietnamese diacritics, collapse whitespace."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    # đ/Đ is not a combining mark — it survives NFD stripping.
    stripped = stripped.replace("đ", "d")
    return re.sub(r"\s+", " ", stripped)


class _TrieNode:
    __slots__ = ("children", "fail", "outputs")

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.fail: _TrieNode | None = None
        self.outputs: list[str] = []


class IntentKeywordMatcher:
    """In-memory compiled Aho-Corasick keyword trie (O(n) search per AD-115)."""

    def __init__(self, patterns: list[str] | tuple[str, ...]) -> None:
        self._root = _TrieNode()
        for pattern in patterns:
            normalized = _normalize_match_text(pattern).strip()
            if not normalized:
                continue
            node = self._root
            for ch in normalized:
                node = node.children.setdefault(ch, _TrieNode())
            node.outputs.append(pattern)

        # Build failure links via BFS.
        queue: deque[_TrieNode] = deque()
        for child in self._root.children.values():
            child.fail = self._root
            queue.append(child)

        while queue:
            current = queue.popleft()
            for ch, child in current.children.items():
                queue.append(child)
                fail = current.fail
                while fail is not None and ch not in fail.children:
                    fail = fail.fail
                child.fail = (
                    fail.children[ch]
                    if fail is not None and ch in fail.children
                    else self._root
                )
                # Always inherit suffix-pattern outputs; duplicates are
                # filtered by ``seen`` in find_matches.
                child.outputs.extend(child.fail.outputs)

    def find_matches(self, text: str) -> list[str]:
        """Return the canonical patterns found in ``text`` (accent-insensitive)."""
        if not text:
            return []
        normalized = _normalize_match_text(text)
        node = self._root
        seen: set[str] = set()
        ordered: list[str] = []
        for ch in normalized:
            while node is not self._root and ch not in node.children:
                node = node.fail or self._root
            node = node.children.get(ch, self._root)
            for pattern in node.outputs:
                if pattern not in seen:
                    seen.add(pattern)
                    ordered.append(pattern)
        return ordered

    def has_match(self, text: str) -> bool:
        """Short-circuit variant of :meth:`find_matches`."""
        if not text:
            return False
        normalized = _normalize_match_text(text)
        node = self._root
        for ch in normalized:
            while node is not self._root and ch not in node.children:
                node = node.fail or self._root
            node = node.children.get(ch, self._root)
            if node.outputs:
                return True
        return False


# Module-level compiled matcher — built once per process (AD-115).
TELEGRAM_INTENT_MATCHER = IntentKeywordMatcher(PURCHASE_INTENT_PATTERNS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _scan_counter_key(workspace_id: int, day: date) -> str:
    return f"signal_radar:scans:{workspace_id}:{day:%Y%m%d}"


async def _scans_used_today(redis_client: Any, workspace_id: int, day: date) -> int:
    try:
        raw = await redis_client.get(_scan_counter_key(workspace_id, day))
        return int(raw or 0)
    except Exception as exc:  # counter read failure; fail closed on the daily budget
        logger.warning(
            "Scan counter read failed for workspace %s; failing closed: %r",
            workspace_id,
            exc,
        )
        return MAX_SCANS_PER_WORKSPACE_PER_DAY


async def _incr_scan_count(
    redis_client: Any, workspace_id: int, day: date
) -> int | None:
    """Bump the workspace scan counter; returns the new value.

    ``SET NX EX`` + ``INCR`` guarantees the TTL is set whenever the key is
    first created (a bare ``INCR``+``EXPIRE`` pair can orphan the key if the
    EXPIRE is lost).
    """
    try:
        key = _scan_counter_key(workspace_id, day)
        await redis_client.set(key, 0, nx=True, ex=SCAN_COUNTER_TTL_SECONDS)
        value = await redis_client.incr(key)
        return int(value)
    except Exception as exc:  # counter increment failure; let the scan proceed
        logger.debug("Suppressed %r", exc)
        return None


async def _recent_signal_exists(
    session: AsyncSession,
    *,
    workspace_id: int,
    company_name: str,
    signal_type: str,
    since: datetime,
) -> bool:
    """Dedupe: True when an equivalent radar signal was persisted recently."""
    stmt = (
        select(SignalEvent.id)
        .where(
            SignalEvent.workspace_id == workspace_id,
            SignalEvent.company_name == company_name,
            SignalEvent.signal_type == signal_type,
            SignalEvent.detected_at >= since,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _resolve_billing_user_id(
    session: AsyncSession, workspace_id: int
) -> Any | None:
    """Pick the workspace user that radar scans bill against.

    Prefers the ``SignalSubscription`` creator, falls back to the workspace
    owner membership. ``None`` means billing is skipped entirely for this
    workspace — no BillingEvent is written and no wallet is debited.
    """
    sub_user = (
        await session.execute(
            select(SignalSubscription.created_by_user_id)
            .where(SignalSubscription.workspace_id == workspace_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if sub_user is not None:
        return sub_user

    return (
        await session.execute(
            select(WorkspaceMembership.user_id)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.is_owner.is_(True),
                WorkspaceMembership.status == "ACTIVE",
            )
            .limit(1)
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# AC-2 / AC-3: Telegram stream intent matcher
# ---------------------------------------------------------------------------


async def _resolve_workspace_id(
    session: AsyncSession, payload: dict[str, Any]
) -> int | None:
    """Resolve the owning workspace for a raw Telegram stream event."""
    explicit = _as_int(payload.get("workspace_id"))
    if explicit is not None:
        # Don't trust a caller-supplied id blindly — confirm the workspace
        # actually exists before attributing the lead to it.
        return explicit if await session.get(Workspace, explicit) is not None else None

    username = str(payload.get("channel_username") or "").lstrip("@").strip()
    channel_id = str(payload.get("channel_id") or "").strip()
    candidates = {c for c in (username, channel_id) if c}
    if not candidates:
        return None

    stmt = (
        select(SocialMonitoredTarget.workspace_id)
        .where(
            SocialMonitoredTarget.platform == TELEGRAM_CHANNEL_PLATFORM,
            SocialMonitoredTarget.is_active.is_(True),
            SocialMonitoredTarget.target_id.in_(sorted(candidates)),
        )
        .order_by(SocialMonitoredTarget.workspace_id)
        .limit(1)
    )
    return _as_int((await session.execute(stmt)).scalar_one_or_none())


def _coerce_str_list(value: Any) -> list[str]:
    """Normalize an entities field to a list of strings.

    Upstream producers sometimes emit a bare scalar or dict for
    phones/emails/locations — wrap those into a one-element list instead of
    iterating garbage (e.g. per-character strings).
    """
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if value:
        return [str(value)]
    return []


def _extract_event_entities(payload: dict[str, Any], text: str) -> dict[str, Any]:
    """Use upstream entities when present, else run the Telegram extractor."""
    for key in ("raw_entities", "entities"):
        entities = payload.get(key)
        if isinstance(entities, str):
            with contextlib.suppress(Exception):
                entities = json.loads(entities)
        if isinstance(entities, dict) and (
            entities.get("phones") or entities.get("emails")
        ):
            return {
                "phones": _coerce_str_list(entities.get("phones")),
                "emails": _coerce_str_list(entities.get("emails")),
                "locations": _coerce_str_list(entities.get("locations")),
            }
    return TelegramEntityExtractor.extract_entities(text)


async def process_telegram_intent_event(
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    redis_client: Any | None = None,
) -> Lead | None:
    """Process one ``stream:telegram:raw_events`` entry (AC-2 / AC-3).

    Returns the created ``Lead``, or ``None`` when the message carries no
    purchase intent or cannot be attributed to a workspace.
    """
    text = str(payload.get("message_text") or payload.get("text") or "").strip()
    if not text:
        return None

    matched_keywords = TELEGRAM_INTENT_MATCHER.find_matches(text)
    if not matched_keywords:
        return None

    if session is None:
        logger.warning("Telegram intent event has no session; skipping")
        return None

    workspace_id = await _resolve_workspace_id(session, payload)
    if workspace_id is None:
        logger.info(
            "Telegram intent event %s: no workspace resolved; skipping",
            payload.get("message_id"),
        )
        return None

    entities = _extract_event_entities(payload, text)
    phones = [str(p) for p in entities.get("phones", []) if p]
    emails = [str(e) for e in entities.get("emails", []) if e]
    has_contact = bool(phones or emails)

    channel_username = str(payload.get("channel_username") or "").lstrip("@")
    message_id = payload.get("message_id")
    source_url = (
        f"https://t.me/{channel_username}/{message_id}"
        if channel_username and message_id
        else payload.get("post_url") or payload.get("source_url")
    )
    if source_url is not None:
        source_url = str(source_url)[:4096]

    sender_name = (
        payload.get("sender_name")
        or payload.get("author_name")
        or payload.get("from_name")
    )
    company_name = (
        sender_name
        or payload.get("channel_title")
        or channel_username
        or "Telegram Intent Lead"
    )[:200]

    domain = None
    if emails and "@" in emails[0]:
        domain = emails[0].split("@")[-1][:255]

    locations = entities.get("locations", [])
    location = str(locations[0])[:100] if locations else None

    # When no per-sender name is present the company_name falls back to the
    # channel — fold a stable per-sender key into the hmac material so
    # distinct buyers in one channel don't collapse into a single lead.
    hmac_name = str(company_name)
    if not sender_name:
        sender_key = (
            payload.get("sender_id")
            or payload.get("from_id")
            or payload.get("user_id")
            or payload.get("sender_username")
            or message_id
        )
        if sender_key is not None:
            hmac_name = f"{hmac_name}#{sender_key}"

    value_hmac = generate_lead_hmac(workspace_id, hmac_name, domain)
    existing_id = await session.scalar(
        select(Lead.id).where(
            Lead.workspace_id == workspace_id,
            Lead.value_hmac == value_hmac,
        )
    )
    if existing_id is not None:
        logger.debug(
            "Telegram intent lead already exists for %s (id=%s)",
            company_name,
            existing_id,
        )
        return None

    # Consent defaults come from workspace settings, same as the social
    # stream worker (icp_criteria keys shared across ingest paths).
    workspace = await session.get(Workspace, workspace_id)
    workspace_settings = (
        workspace.icp_criteria
        if isinstance(workspace, Workspace) and workspace.icp_criteria
        else {}
    )
    consent_status = workspace_settings.get("social_lead_consent_status", "public")
    legal_basis = workspace_settings.get(
        "social_lead_legal_basis", "legitimate_interest"
    )

    # AC-3: no extractable phone/email -> Unqualified Signal Lead with
    # status='pending_enrichment' and NO credit deduction. We never call any
    # billing primitive on this path; deduction happens later when contact
    # enrichment resolves the lead. Extracted contacts land in the activity
    # log only — no VerifiedContact exists, so the lead always stays
    # enriched=False / needs_enrichment=True until the waterfall runs.
    lead = Lead(
        workspace_id=workspace_id,
        client_id=payload.get("client_id") or "default",
        source="telegram_intent",
        source_url=source_url,
        company_name=company_name,
        domain=domain,
        value_hmac=value_hmac,
        industry="purchase_intent",
        location=location,
        tech_stack=[],
        fit_score=0.7 if has_contact else 0.3,
        intent_score=RADAR_SIGNAL_CONFIDENCE / 100.0,
        composite_score=RADAR_MIN_INTENT_SCORE,
        status="new" if has_contact else "pending_enrichment",
        needs_enrichment=True,
        enriched=False,
        consent_status=consent_status,
        legal_basis=legal_basis,
    )
    session.add(lead)
    await session.flush()

    # Audit trail: keep the matched keywords + extracted contacts on the lead
    # timeline (Lead has no phone column; VerifiedContact is reserved for the
    # enrichment waterfall output).
    session.add(
        LeadActivityLog(
            workspace_id=workspace_id,
            client_id=payload.get("client_id") or "default",
            lead_id=lead.id,
            actor_user_id=None,
            activity_type="telegram_intent_detected",
            title="Telegram purchase-intent signal",
            details={
                "matched_keywords": matched_keywords,
                "phones": phones,
                "emails": emails,
                "channel_username": channel_username or None,
                "message_id": message_id,
                "message_excerpt": text[:500],
            },
        )
    )

    if has_contact and redis_client is not None:
        from app.services.lead_assignment_service import LeadAssignmentService

        assignment_service = LeadAssignmentService(
            session=session,
            redis_client=redis_client,
        )
        try:
            await assignment_service.assign_leads_batch(
                workspace_id=workspace_id,
                lead_ids=[lead.id],
            )
        except Exception:  # best-effort round-robin; unassigned lead still valid
            logger.exception(
                "Failed to auto-assign telegram intent lead %s in workspace %s",
                lead.id,
                workspace_id,
            )

    await session.commit()
    return lead


def _default_consumer_name() -> str:
    return f"tg-intent-{socket.gethostname()}-{os.getpid()}"


async def _route_telegram_intent_to_dlq(
    redis_client: Any,
    msg_id: str,
    payload: Any,
    error: str,
) -> None:
    """Push a failed event to the intent DLQ and ACK the original."""
    try:
        await redis_client.xadd(
            STREAM_TELEGRAM_INTENT_DLQ,
            {
                "original_id": str(msg_id),
                "payload": json.dumps(payload, default=str),
                "error": error[:2000],
                "failed_at": datetime.now(UTC).isoformat(),
            },
            maxlen=DLQ_MAXLEN,
            approximate=True,
        )
    except Exception:  # DLQ write failure; still ACK to avoid poison-loop
        logger.exception("Failed to write telegram intent DLQ entry")
    finally:
        with contextlib.suppress(Exception):
            await redis_client.xack(
                STREAM_TELEGRAM_RAW_EVENTS,
                TELEGRAM_INTENT_CONSUMER_GROUP,
                msg_id,
            )


async def run_telegram_intent_consumer(
    redis_client: Any | None = None,
    consumer_name: str | None = None,
    batch_size: int = 10,
    block_ms: int = 2000,
    max_loops: int = 1,
    session_maker: Any | None = None,
) -> int:
    """Consume ``stream:telegram:raw_events`` via a consumer group (AC-2).

    Returns the number of intent-matched events that produced a Lead.
    """
    created_locally = False
    if redis_client is None:
        import redis.asyncio as aioredis

        stream_url = (
            getattr(config, "TELEGRAM_STREAM_REDIS_URL", "") or config.REDIS_APP_URL
        )
        redis_client = aioredis.from_url(stream_url, decode_responses=True)
        created_locally = True

    consumer_name = consumer_name or _default_consumer_name()

    try:
        try:
            await redis_client.xgroup_create(
                name=STREAM_TELEGRAM_RAW_EVENTS,
                groupname=TELEGRAM_INTENT_CONSUMER_GROUP,
                # "$" — start at new messages only; "0" would replay the whole
                # backlog into stale leads on first group creation.
                id="$",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc).upper():
                logger.error("Failed to create telegram intent consumer group: %s", exc)
                return 0
        except Exception as exc:  # group creation failure; abort this run
            logger.exception("Failed to create telegram intent consumer group: %s", exc)
            return 0

        count = max(1, min(batch_size, MAX_MESSAGES_PER_BATCH))
        processed = 0
        session_factory = session_maker or async_session_maker

        for _ in range(max(1, max_loops)):
            entries = None
            try:
                claim_res = await redis_client.xautoclaim(
                    name=STREAM_TELEGRAM_RAW_EVENTS,
                    groupname=TELEGRAM_INTENT_CONSUMER_GROUP,
                    consumername=consumer_name,
                    min_idle_time=AUTOCLAIM_MIN_IDLE_TIME_MS,
                    start_id="0-0",
                    count=count,
                )
                if claim_res and len(claim_res) >= 2 and claim_res[1]:
                    entries = [(STREAM_TELEGRAM_RAW_EVENTS, claim_res[1])]
            except Exception as exc:  # autoclaim unsupported/failed; fall through
                logger.debug("Suppressed %r", exc)

            if not entries:
                try:
                    entries = await redis_client.xreadgroup(
                        groupname=TELEGRAM_INTENT_CONSUMER_GROUP,
                        consumername=consumer_name,
                        streams={STREAM_TELEGRAM_RAW_EVENTS: ">"},
                        count=count,
                        block=block_ms,
                    )
                except Exception as exc:  # stream read failure; stop this run
                    logger.error("Error reading telegram intent stream: %s", exc)
                    break

            if not entries:
                break

            async with session_factory() as session:
                for _stream, messages in entries:
                    for msg_id, payload in messages:
                        try:
                            lead = await process_telegram_intent_event(
                                payload,
                                session=session,
                                redis_client=redis_client,
                            )
                            with contextlib.suppress(Exception):
                                await redis_client.xack(
                                    STREAM_TELEGRAM_RAW_EVENTS,
                                    TELEGRAM_INTENT_CONSUMER_GROUP,
                                    msg_id,
                                )
                            if lead is not None:
                                processed += 1
                        except Exception as exc:  # per-message failure -> DLQ
                            with contextlib.suppress(Exception):
                                await session.rollback()
                            logger.exception(
                                "Telegram intent event %s failed: %s", msg_id, exc
                            )
                            await _route_telegram_intent_to_dlq(
                                redis_client, msg_id, payload, str(exc)
                            )

        return processed
    finally:
        if created_locally:
            with contextlib.suppress(Exception):
                await redis_client.aclose()


# ---------------------------------------------------------------------------
# AC-1: newly incorporated tax codes (masothue.com / dangkykinhdoanh.gov.vn)
# ---------------------------------------------------------------------------

_TAX_CODE_RE = re.compile(r"\b(\d{10,13})(?:-\d{3})?\b")
_DKKD_NAME_RE = re.compile(
    r"(?:Tên\s+(?:doanh nghiệp|công ty)|TÊN\s+(?:DOANH NGHIỆP|CÔNG TY))\s*[:\-]?\s*"
    r"([A-ZÀ-Ỹ][^\n\r<|]{3,150})",
    re.UNICODE,
)


def _parse_dkkd_new_companies(html: str) -> list[dict[str, Any]]:
    """Best-effort parse of dangkykinhdoanh.gov.vn new-registration listings.

    ponytail: the portal markup is unstable ASP.NET; we extract MST tax codes
    plus nearby ``Tên doanh nghiệp`` names and skip what we can't parse.
    """
    names = [m.group(1).strip() for m in _DKKD_NAME_RE.finditer(html)]
    tax_codes = list(dict.fromkeys(_TAX_CODE_RE.findall(html)))
    # Only pair names↔tax codes by index when the counts line up; any stray
    # digit string on the page would otherwise misalign every company.
    pair_by_index = len(names) == len(tax_codes)

    items: list[dict[str, Any]] = []
    for idx, name in enumerate(names):
        items.append(
            {
                "company_name": name[:200],
                "tax_code": tax_codes[idx] if pair_by_index else None,
                "source_url": DKKD_NEW_BUSINESSES_URL,
                "source": "dangkykinhdoanh",
            }
        )
    return items


async def fetch_new_incorporations(
    fetch_page_fn: Any | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch newly incorporated companies from masothue + dangkykinhdoanh.

    Returns ``(items, degradation_reasons)``. Each item is a dict with
    ``company_name``, ``tax_code``, ``source_url``, ``source``.
    """
    items: list[dict[str, Any]] = []
    reasons: list[str] = []

    # --- masothue.com "mã số thuế mới" listing -------------------------------
    try:
        if fetch_page_fn is not None:
            html = await fetch_page_fn(MASOTHUE_NEW_COMPANIES_URL)
        else:
            from app.proprietary.platforms.masothue.fetch import fetch_detail_page

            html = await fetch_detail_page(MASOTHUE_NEW_COMPANIES_URL)

        from app.proprietary.platforms.masothue.parsers import parse_search_results

        parsed = [c for c in parse_search_results(html) if c.name]
        if not parsed:
            # An empty parse on a listing page usually means markup drift, not
            # "zero new companies" — surface it as a degradation.
            reasons.append("masothue_new_listing.empty_parse")
        for company in parsed:
            items.append(
                {
                    "company_name": company.name,
                    "tax_code": company.tax_code,
                    "source_url": company.detail_url or MASOTHUE_NEW_COMPANIES_URL,
                    "source": "masothue",
                }
            )
    except Exception as exc:  # masothue listing failure; degrade and continue
        logger.warning("masothue new-companies listing failed: %s", exc)
        reasons.append(f"masothue_new_listing: {exc}")

    # --- dangkykinhdoanh.gov.vn new-registration announcements ----------------
    try:
        if fetch_page_fn is not None:
            dkkd_html = await fetch_page_fn(DKKD_NEW_BUSINESSES_URL)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
                resp = await client.get(
                    DKKD_NEW_BUSINESSES_URL,
                    # ASP.NET portals commonly UA-block bare httpx clients.
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/126.0 Safari/537.36"
                        )
                    },
                )
            dkkd_html = resp.text if resp.status_code == 200 else ""
            if resp.status_code != 200:
                reasons.append(f"dkkd.http_{resp.status_code}")
        items.extend(_parse_dkkd_new_companies(dkkd_html or ""))
    except Exception as exc:  # dkkd fetch failure; degrade and continue
        logger.warning("dangkykinhdoanh new-business listing failed: %s", exc)
        reasons.append(f"dkkd_new_listing: {exc}")

    # Dedupe by (tax_code | company_name) across sources.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = item.get("tax_code") or str(item.get("company_name") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique, reasons


# ---------------------------------------------------------------------------
# AC-1 / AC-4: periodic high-intent scanner
# ---------------------------------------------------------------------------


async def _hiring_watchlist(
    session: AsyncSession, workspace_id: int, now: datetime
) -> list[str]:
    """Distinct company names the workspace tracks (from recent leads)."""
    cutoff = now - timedelta(days=HIRING_WATCHLIST_LOOKBACK_DAYS)
    stmt = (
        select(Lead.company_name)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.created_at >= cutoff,
        )
        .distinct()
        .limit(HIRING_WATCHLIST_MAX_COMPANIES)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [str(name) for name in rows if name]


def _count_recent_postings(items: list[Any], cutoff_date: date) -> int:
    """Count aggregated listings posted within the lookback window.

    AC-1 requires "new postings in 7 days" — undated or unparseable
    ``posted_at`` values do NOT count toward the surge.
    """
    count = 0
    for listing in items:
        posted_at = (
            listing.get("posted_at")
            if isinstance(listing, dict)
            else getattr(listing, "posted_at", None)
        )
        if isinstance(posted_at, datetime):
            posted = posted_at.date()
        elif isinstance(posted_at, date):
            posted = posted_at
        elif posted_at is not None:
            try:
                posted = datetime.fromisoformat(str(posted_at)).date()
            except ValueError:
                continue
        else:
            continue
        if posted >= cutoff_date:
            count += 1
    return count


async def scan_workspace_high_intent(
    session: AsyncSession,
    redis_client: Any,
    *,
    workspace_id: int,
    client_id: str | None = None,
    new_incorporations: list[dict[str, Any]] | None = None,
    aggregate_fn: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run one radar scan pass for a workspace (AC-1 + AC-4 guardrails)."""
    now = now or datetime.now(UTC)
    day = now.date()
    service = SignalDetectionService()

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        return {"workspace_id": workspace_id, "status": "workspace_not_found"}

    # AD-115: pause when the workspace shared credit pool drops below 50 credits.
    if (workspace.credit_micros_balance or 0) < MIN_WORKSPACE_CREDIT_MICROS:
        logger.info(
            "Signal radar paused for workspace %s: credit balance %s < %s micros",
            workspace_id,
            workspace.credit_micros_balance,
            MIN_WORKSPACE_CREDIT_MICROS,
        )
        return {"workspace_id": workspace_id, "status": "paused_low_credit"}

    used = await _scans_used_today(redis_client, workspace_id, day)
    if used >= MAX_SCANS_PER_WORKSPACE_PER_DAY:
        logger.info(
            "Signal radar daily budget exhausted for workspace %s (%s/%s)",
            workspace_id,
            used,
            MAX_SCANS_PER_WORKSPACE_PER_DAY,
        )
        return {"workspace_id": workspace_id, "status": "budget_exhausted"}
    remaining = MAX_SCANS_PER_WORKSPACE_PER_DAY - used

    cost_per_item = config.SIGNAL_SCAN_MICROS_PER_SIGNAL
    billing_user_id = (
        await _resolve_billing_user_id(session, workspace_id)
        if cost_per_item > 0
        else None
    )

    signals_created = 0
    scans_used = 0
    dedupe_since = now - timedelta(hours=RADAR_SIGNAL_DEDUPE_HOURS)

    async def _persist(
        *, company_name: str, signal_type: str, raw: dict[str, Any]
    ) -> SignalEvent | None:
        signal = await service.persist_signal(
            session,
            workspace_id=workspace_id,
            client_id=client_id,
            company_name=company_name,
            signal_type=signal_type,
            raw=raw,
            confidence_threshold=RADAR_SIGNAL_CONFIDENCE,
        )
        # billing_user_id is None => billing skipped entirely (no BillingEvent
        # is written) — see _resolve_billing_user_id docstring.
        if signal is not None and cost_per_item > 0 and billing_user_id is not None:
            from app.services.billing_event_service import record_signal_scan

            try:
                await record_signal_scan(
                    session,
                    signal_event_id=signal.id,
                    workspace_id=workspace_id,
                    client_id=client_id,
                    user_id=billing_user_id,
                    cost_micros=cost_per_item,
                )
            except Exception:  # billing failure must not lose the signal
                logger.exception("Billing event failed for radar signal %s", signal.id)
        return signal

    # --- Newly incorporated tax codes -----------------------------------------
    # Runs BEFORE the hiring loop so a hiring-heavy watchlist cannot starve
    # incorporation signals of the shared daily budget.
    for item in new_incorporations or []:
        if remaining <= 0:
            break
        # SignalInput.company_name is capped at 200 chars.
        company_name = str(item.get("company_name") or "").strip()[:200]
        if not company_name:
            continue

        if await _recent_signal_exists(
            session,
            workspace_id=workspace_id,
            company_name=company_name,
            signal_type="incorporation",
            since=dedupe_since,
        ):
            continue

        await _incr_scan_count(redis_client, workspace_id, day)
        scans_used += 1
        remaining -= 1

        try:
            signal = await _persist(
                company_name=company_name,
                signal_type="incorporation",
                raw={
                    "company_name": company_name,
                    "tax_code": item.get("tax_code"),
                    "source_url": item.get("source_url"),
                    "confidence": RADAR_SIGNAL_CONFIDENCE,
                    "detected_at": now,
                    "registry_source": item.get("source"),
                },
            )
        except Exception as exc:  # one bad item must not abort the workspace run
            logger.warning(
                "Incorporation signal persist failed for %r in workspace %s: %s",
                company_name,
                workspace_id,
                exc,
            )
            continue
        if signal is not None:
            signals_created += 1

    # --- Hiring surges (TopCV / VietnamWorks) ---------------------------------
    if aggregate_fn is None:
        from app.services.jobs_aggregator import aggregate_jobs

        aggregate_fn = aggregate_jobs

    companies = await _hiring_watchlist(session, workspace_id, now)
    cutoff_date = (now - timedelta(days=HIRING_SURGE_LOOKBACK_DAYS)).date()

    for company_name in companies:
        if remaining <= 0:
            break
        # Dedupe BEFORE spending scan budget + scraping job boards.
        if await _recent_signal_exists(
            session,
            workspace_id=workspace_id,
            company_name=company_name,
            signal_type="hiring",
            since=dedupe_since,
        ):
            continue

        await _incr_scan_count(redis_client, workspace_id, day)
        scans_used += 1
        remaining -= 1

        try:
            from app.services.jobs_aggregator.schemas import VnJobAggregateInput

            output = await asyncio.wait_for(
                aggregate_fn(
                    VnJobAggregateInput(
                        keyword=company_name,
                        sources=["topcv", "vietnamworks"],
                        max_pages=2,
                        max_items_per_source=25,
                    ),
                    None,
                ),
                timeout=HIRING_AGGREGATE_TIMEOUT_S,
            )
        except Exception as exc:  # aggregator failure for one company; continue
            logger.warning(
                "Hiring surge scan failed for %r in workspace %s: %s",
                company_name,
                workspace_id,
                exc,
            )
            continue

        items = (
            output.get("items", [])
            if isinstance(output, dict)
            else getattr(output, "items", []) or []
        )
        recent_count = _count_recent_postings(items, cutoff_date)
        if recent_count < HIRING_SURGE_MIN_POSTINGS:
            continue

        first_url = None
        for listing in items:
            if isinstance(listing, dict):
                url = listing.get("source_url") or listing.get("url")
                urls = listing.get("source_urls") or []
            else:
                url = getattr(listing, "source_url", None)
                urls = getattr(listing, "source_urls", None) or []
            first_url = url or (urls[0] if urls else None)
            if first_url:
                break

        try:
            signal = await _persist(
                company_name=company_name,
                signal_type="hiring",
                raw={
                    "company_name": company_name,
                    "job_count": recent_count,
                    "source_url": first_url,
                    "confidence": RADAR_SIGNAL_CONFIDENCE,
                    "detected_at": now,
                },
            )
        except Exception as exc:  # one bad item must not abort the workspace run
            logger.warning(
                "Hiring signal persist failed for %r in workspace %s: %s",
                company_name,
                workspace_id,
                exc,
            )
            continue
        if signal is not None:
            signals_created += 1

    try:
        await session.commit()
    except Exception:  # commit failure; rollback and report
        await session.rollback()
        raise

    return {
        "workspace_id": workspace_id,
        "status": "ok",
        "scans_used": scans_used,
        "signals_created": signals_created,
    }


async def run_periodic_signal_scan(
    redis_client: Any | None = None,
    session_maker: Any | None = None,
) -> dict[str, Any]:
    """Entry point for ``scan_high_intent_companies_periodic`` (AC-1)."""
    created_locally = False
    if redis_client is None:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
        created_locally = True

    if session_maker is None:
        session_maker = async_session_maker

    try:
        # Fetch the shared incorporation listing once per run — it is global
        # data, not per-workspace.
        new_incorporations, fetch_reasons = await fetch_new_incorporations()
        for reason in fetch_reasons:
            logger.warning("incorporation source degraded: %s", reason)

        async with session_maker() as session:
            lead_ws = (
                (await session.execute(select(Lead.workspace_id).distinct()))
                .scalars()
                .all()
            )
            sub_ws = (
                (await session.execute(select(SignalSubscription.workspace_id)))
                .scalars()
                .all()
            )
            candidate_ids = {int(w) for w in (*lead_ws, *sub_ws) if w}
            # Skip archived / governance-paused workspaces.
            active_ws = (
                await session.execute(
                    select(Workspace.id).where(
                        Workspace.id.in_(candidate_ids or {-1}),
                        Workspace.archived_at.is_(None),
                        Workspace.scrape_paused_at.is_(None),
                    )
                )
            ).scalars()
            workspace_ids = sorted(int(w) for w in active_ws.all())

        results: list[dict[str, Any]] = []
        for workspace_id in workspace_ids:
            try:
                async with session_maker() as session:
                    results.append(
                        await scan_workspace_high_intent(
                            session,
                            redis_client,
                            workspace_id=workspace_id,
                            new_incorporations=new_incorporations,
                        )
                    )
            except Exception as exc:  # one workspace failure; continue others
                logger.exception(
                    "Signal radar scan failed for workspace %s: %s",
                    workspace_id,
                    exc,
                )
                results.append(
                    {"workspace_id": workspace_id, "status": "error", "error": str(exc)}
                )

        return {
            "workspaces": len(workspace_ids),
            "signals_created": sum(r.get("signals_created", 0) for r in results),
            "incorporation_candidates": len(new_incorporations),
            "degradation_reasons": fetch_reasons or None,
            "results": results,
        }
    finally:
        if created_locally:
            with contextlib.suppress(Exception):
                await redis_client.aclose()
