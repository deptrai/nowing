"""Redis Stream Worker & Celery Processor for Ingested Social Posts (Story 21.8 / AD-SOC-4 / AD-SOC-6).

Reads raw social posts from Redis Stream 'stream:social:raw_posts', validates the
payload, extracts contact numbers, prices, emails, locations, computes intent &
fit score, performs idempotent UPSERT into PostgreSQL `social_posts`, and creates
CRM `Lead` records + evaluates `AlertRule` matches for high-intent posts.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import socket
import time
from datetime import UTC, datetime
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from redis.exceptions import ResponseError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.engine.execute import execute_alert_rule
from app.alerts.persistence.models.alert_rule import AlertRule
from app.config import config
from app.db import (
    Lead,
    SocialMonitoredTarget,
    SocialPost,
    Workspace,
    async_session_maker,
)
from app.proprietary.platforms.xactions.constants import (
    STREAM_SOCIAL_DEAD_LETTER,
    STREAM_SOCIAL_RAW_POSTS,
)
from app.proprietary.platforms.xactions.phone_extractor import SocialEntityExtractor
from app.tasks.jev_guardrails import sanitize_pii_content

logger = logging.getLogger(__name__)

CONSUMER_GROUP_NAME = "social_processors"
MAX_MESSAGES_PER_BATCH = 100
AUTOCLAIM_MIN_IDLE_TIME_MS = 60_000  # Reclaim messages stuck in PEL > 60s (Story 35.1)
BATCH_SLEEP_SECONDS = 0.01

SUPPORTED_SCHEMA_VERSION_MAX = 1
SOCIAL_STREAM_LAG_WARN_THRESHOLD = 1000
LAG_CHECK_INTERVAL_SECONDS = 30.0
DLQ_MAXLEN = 50000
_LAG_STATE: dict[str, float] = {"last_check": float("-inf")}

DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
DLQ_REASON_INVALID_SCHEMA_VERSION = "INVALID_SCHEMA_VERSION"
DLQ_REASON_MISSING_WORKSPACE_ID = "MISSING_WORKSPACE_ID"
DLQ_REASON_MISSING_TARGET_ID = "MISSING_TARGET_ID"
DLQ_REASON_MISSING_CONTENT = "MISSING_CONTENT"
DLQ_REASON_SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
DLQ_REASON_RUNTIME_FAILURE = "RUNTIME_FAILURE"

SOCIAL_LEAD_CAPABILITY_ID = "social.search_leads"
SOCIAL_LEAD_INTENTS = {"sell", "buy", "hiring", "seeking"}


class SocialPostEvent(BaseModel):
    """Validated payload from ``stream:social:raw_posts``.

    Extra keys (e.g. ``created_at`` pushed by the adapter) are ignored so
    upstream additions do not break the consumer.
    """

    model_config = ConfigDict(extra="ignore")

    platform: str
    external_post_id: str
    content: str = Field(
        default="",
        validation_alias=AliasChoices("content", "content_snippet"),
    )
    schema_version: int = 1
    author_id: str | None = None
    author_name: str | None = None
    author_url: str | None = None
    post_url: str | None = None
    target_id: int | str | None = None
    workspace_id: int | None = None
    client_id: str | None = None
    reactions_count: int | str | None = 0
    comments_count: int | str | None = 0
    shares_count: int | str | None = 0
    media_urls: list[str] | str | None = Field(default_factory=list)
    published_at: datetime | str | None = None
    category: str | None = None
    storage_ref: str | None = None
    scraper_id: str | None = None
    benchmark_health: str | None = None
    benchmark_alert: bool | str | None = False

    @model_validator(mode="before")
    @classmethod
    def _coalesce_content_alias(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data_copy = dict(data)
        content = data_copy.get("content")
        snippet = data_copy.get("content_snippet")

        has_content = content is not None and bool(str(content).strip())
        has_snippet = snippet is not None and bool(str(snippet).strip())

        if not has_content and has_snippet:
            data_copy["content"] = snippet
        return data_copy

    @field_validator("benchmark_alert", mode="before")
    @classmethod
    def _bool_like(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    @field_validator("platform", "external_post_id", mode="after")
    @classmethod
    def _non_empty_string(cls, value: str) -> str:
        value = value.strip()
        if not value or value.lower() == "none":
            raise ValueError("must be a non-empty string")
        return value

    @field_validator("reactions_count", "comments_count", "shares_count", mode="before")
    @classmethod
    def _coerce_int_counts(cls, value: Any) -> int:
        try:
            return int(value or 0)
        except (ValueError, TypeError):
            return 0

    @field_validator("media_urls", mode="before")
    @classmethod
    def _parse_media_urls(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                logger.warning("Malformed media_urls JSON: %r", value)
            return []
        return []

    @field_validator("published_at", mode="before")
    @classmethod
    def _parse_published_at(cls, value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            # Handle lowercase 'z' and RFC-2822 style dates
            if normalized.endswith(("z", "Z")):
                normalized = normalized[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(normalized)
            except (ValueError, TypeError):
                try:
                    # RFC-2822 fallback (e.g., "Mon, 01 Jan 2024 00:00:00 GMT")
                    from email.utils import parsedate_to_datetime

                    return parsedate_to_datetime(normalized)
                except (ValueError, TypeError):
                    logger.warning("Malformed published_at %r; using None", value)
        return None


def compute_fit_score(
    raw_entities: dict[str, Any], intent_tag: str, reactions: int = 0, comments: int = 0
) -> float:
    """Compute lead quality score (0.0 to 1.0) based on extracted signals."""
    score = 0.0

    # Phone numbers present is a major quality signal
    phones = raw_entities.get("phones", [])
    if phones:
        score += 0.45

    # Intent is commercial (sell/buy/hiring)
    if intent_tag in ("sell", "buy", "hiring"):
        score += 0.25
    elif intent_tag == "seeking":
        score += 0.15

    # Price or email specified
    if raw_entities.get("prices") or raw_entities.get("emails"):
        score += 0.15

    # Location specified
    if raw_entities.get("locations"):
        score += 0.10

    # Social engagement bonus
    if reactions >= 10 or comments >= 5:
        score += 0.05

    return min(1.0, round(score, 2))


async def _create_lead_from_social_post(
    session: AsyncSession,
    event: SocialPostEvent,
    raw_entities: dict[str, Any],
    fit_score: float,
    redis_client: Any | None = None,
) -> Lead | None:
    """Create a CRM ``Lead`` for high-intent social posts (AD-SOC-7).

    ``workspace_id`` must be present on the event (or discoverable from the
    monitored target). Without it we cannot satisfy the ``leads.workspace_id``
    NOT NULL constraint, so we log and skip.
    """
    workspace_id = event.workspace_id
    target: SocialMonitoredTarget | None = None

    if event.target_id is not None:
        try:
            target_id = int(event.target_id)
            target = await session.get(SocialMonitoredTarget, target_id)
            if isinstance(target, SocialMonitoredTarget) and isinstance(
                target.workspace_id, int
            ):
                workspace_id = target.workspace_id
        except (ValueError, TypeError):
            logger.warning("Invalid target_id %r; ignoring", event.target_id)

    if not isinstance(workspace_id, int) or workspace_id <= 0:
        logger.warning(
            "Cannot create Lead for %s/%s: workspace_id is missing",
            event.platform,
            event.external_post_id,
        )
        return None

    # Workspace-level privacy overrides for scraped social leads.
    workspace = await session.get(Workspace, workspace_id)
    workspace_settings = (
        workspace.icp_criteria if isinstance(workspace, Workspace) and workspace.icp_criteria else {}
    )
    consent_status = workspace_settings.get("social_lead_consent_status", "public")
    legal_basis = workspace_settings.get("social_lead_legal_basis", "legitimate_interest")

    company_name = (
        event.author_name
        or (target.target_name if isinstance(target, SocialMonitoredTarget) else None)
        or "Unknown social author"
    )[:200]
    source_url = event.post_url or event.author_url

    locations = raw_entities.get("locations", [])
    location = locations[0][:100] if locations else None

    emails = raw_entities.get("emails", [])
    domain = None
    if emails:
        domain = emails[0].split("@")[-1][:255] if "@" in emails[0] else None

    # ponytail: Lead model does not have a phone/content_snippet column.
    # Store phones in the raw_entities JSON on the social post; a follow-up
    # migration can add a lead-level phone/notes column when needed.
    intent_tag = raw_entities.get("intent", "other")
    intent_score = 0.8 if intent_tag in SOCIAL_LEAD_INTENTS else fit_score

    # leads.value_hmac is NOT NULL + UNIQUE(workspace_id, value_hmac)
    # (migration 224). Reuse the canonical stream HMAC so social leads dedupe
    # against batch/stream-ingested leads on the same company+domain.
    from app.lead_intelligence.services.lead_stream_service import generate_lead_hmac

    value_hmac = generate_lead_hmac(workspace_id, company_name, domain)

    # Avoid duplicate leads: value_hmac is the canonical identity
    # (workspace+domain+company). A repeat author posting again, or the same
    # post re-scraped, maps to the same key — skip rather than violate the
    # uq_leads_workspace_value_hmac constraint.
    existing_id = await session.scalar(
        select(Lead.id).where(
            Lead.workspace_id == workspace_id,
            Lead.value_hmac == value_hmac,
        )
    )
    if existing_id is not None:
        logger.debug(
            "Lead already exists for %s/%s (id=%s)",
            event.platform,
            event.external_post_id,
            existing_id,
        )
        return None

    lead = Lead(
        workspace_id=workspace_id,
        client_id=event.client_id,
        source="social",
        source_url=source_url,
        company_name=company_name,
        domain=domain,
        value_hmac=value_hmac,
        industry=intent_tag,
        location=location,
        tech_stack=[],
        fit_score=fit_score,
        intent_score=intent_score,
        composite_score=fit_score,
        status="new",
        enriched=False,
        consent_status=consent_status,
        legal_basis=legal_basis,
    )

    session.add(lead)

    # Trigger round-robin assignment for the social lead.
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
    except Exception:  # best-effort lead assignment; log exception and continue
        logger.exception("Failed to auto-assign social lead in workspace %s", workspace_id)

    try:
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.exception(
            "Failed to create Lead for %s/%s: %s",
            event.platform,
            event.external_post_id,
            exc,
        )
        return None

    return lead


async def _evaluate_alerts_for_social_post(
    session: AsyncSession,
    event: SocialPostEvent,
    raw_entities: dict[str, Any],
    fit_score: float,
) -> None:
    """Evaluate active ``AlertRule`` saved searches against this social post.

    Without ``workspace_id`` we cannot scope the rule lookup, so we skip.
    """
    workspace_id = event.workspace_id
    if not isinstance(workspace_id, int) or workspace_id <= 0:
        logger.debug(
            "Skipping alert evaluation for %s/%s: workspace_id missing",
            event.platform,
            event.external_post_id,
        )
        return

    try:
        stmt = (
            select(AlertRule)
            .where(
                AlertRule.workspace_id == workspace_id,
                AlertRule.enabled.is_(True),
                AlertRule.capability_id == SOCIAL_LEAD_CAPABILITY_ID,
            )
            .limit(1000)
        )
        result = await session.execute(stmt)
        rules = result.scalars().all()

        intent_tag = raw_entities.get("intent", "other")
        content_lower = (event.content or "").lower()
        author_lower = (event.author_name or "").lower()
        haystack = f"{content_lower} {author_lower}"

        for rule in rules:
            query = rule.query or {}

            if query.get("platform") and query["platform"] != event.platform:
                continue
            if query.get("intent") and query["intent"] != intent_tag:
                continue
            if query.get("min_fit_score", 0) > fit_score:
                continue

            keyword = query.get("keyword")
            if keyword:
                pattern = re.compile(
                    r"(?<!\w)" + re.escape(keyword.lower()) + r"(?!\w)"
                )
                if not pattern.search(haystack):
                    continue

            logger.info(
                "Matched alert rule %s for social post %s/%s",
                rule.id,
                event.platform,
                event.external_post_id,
            )
            await execute_alert_rule(
                session=session,
                alert_rule=rule,
                fired_at=datetime.now(UTC),
            )
    except Exception as exc:  # alert rule execution failure; log exception
        logger.exception(
            "Alert evaluation failed for %s/%s: %s",
            event.platform,
            event.external_post_id,
            exc,
        )


async def process_social_post_event(
    payload: dict[str, Any] | None = None,
    session: AsyncSession | None = None,
    redis_client: Any | None = None,
    event: SocialPostEvent | None = None,
) -> dict[str, Any] | None:
    """Validate, extract entities, calculate fit score, and UPSERT into social_posts.

    Returns ``result_data`` dict on success, ``None`` when the event cannot be
    persisted (e.g. workspace_id cannot be resolved). Raises on transient DB
    errors so the caller can route to DLQ.
    """
    if event is None:
        if payload is None:
            return None
        try:
            event = SocialPostEvent.model_validate(payload)
        except ValidationError as exc:
            logger.warning("Invalid social post event: %s", exc)
            return None

    sanitized_content = sanitize_pii_content(event.content)
    extractor = SocialEntityExtractor()
    extracted = extractor.extract_all(sanitized_content)
    intent_tag = extracted["intent"]
    fit_score = compute_fit_score(
        extracted, intent_tag, event.reactions_count, event.comments_count
    )

    target_id: int | None = None
    if event.target_id is not None:
        try:
            target_id = int(event.target_id)
        except (ValueError, TypeError):
            logger.warning("Invalid target_id %r; ignoring", event.target_id)

    result_data = {
        "platform": event.platform,
        "external_post_id": event.external_post_id,
        "target_id": target_id,
        "author_id": event.author_id,
        "author_name": event.author_name,
        "author_url": event.author_url,
        "post_url": event.post_url,
        "content": sanitized_content,
        "intent_tag": intent_tag,
        "fit_score": fit_score,
        "reactions_count": event.reactions_count,
        "comments_count": event.comments_count,
        "shares_count": event.shares_count,
        "media_urls": event.media_urls,
        "raw_entities": extracted,
        "published_at": event.published_at,
        "category": event.category,
        "storage_ref": event.storage_ref,
        "scraper_id": event.scraper_id,
        "benchmark_health": event.benchmark_health,
        "benchmark_alert": event.benchmark_alert,
    }

    if session is not None:
        # Resolve workspace context from explicit event or the monitored target.
        workspace_id = event.workspace_id
        if workspace_id is None and target_id is not None:
            target = await session.get(SocialMonitoredTarget, target_id)
            if isinstance(target, SocialMonitoredTarget) and target.workspace_id:
                workspace_id = target.workspace_id

        if workspace_id is None:
            logger.warning(
                "Cannot persist social post %s/%s: workspace_id is missing",
                event.platform,
                event.external_post_id,
            )
            return None

        if target_id is None:
            logger.warning(
                "Cannot persist social post %s/%s: target_id is missing",
                event.platform,
                event.external_post_id,
            )
            return None

        event.workspace_id = workspace_id
        result_data["workspace_id"] = workspace_id

        stmt = pg_insert(SocialPost).values(**result_data)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["workspace_id", "platform", "external_post_id"],
            set_={
                "target_id": stmt.excluded.target_id,
                "workspace_id": stmt.excluded.workspace_id,
                "author_id": stmt.excluded.author_id,
                "author_name": stmt.excluded.author_name,
                "author_url": stmt.excluded.author_url,
                "post_url": stmt.excluded.post_url,
                "content": stmt.excluded.content,
                "reactions_count": stmt.excluded.reactions_count,
                "comments_count": stmt.excluded.comments_count,
                "shares_count": stmt.excluded.shares_count,
                "raw_entities": stmt.excluded.raw_entities,
                "intent_tag": stmt.excluded.intent_tag,
                "fit_score": stmt.excluded.fit_score,
                "published_at": stmt.excluded.published_at,
                "media_urls": stmt.excluded.media_urls,
                "category": stmt.excluded.category,
                "storage_ref": stmt.excluded.storage_ref,
                "scraper_id": stmt.excluded.scraper_id,
                "benchmark_health": stmt.excluded.benchmark_health,
                "benchmark_alert": stmt.excluded.benchmark_alert,
                "updated_at": datetime.now(UTC),
            },
        )

        try:
            await session.execute(upsert_stmt)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.exception(
                "Social post UPSERT failed for %s/%s: %s",
                event.platform,
                event.external_post_id,
                exc,
            )
            raise

        if intent_tag in SOCIAL_LEAD_INTENTS:
            await _create_lead_from_social_post(
                session=session,
                event=event,
                raw_entities=extracted,
                fit_score=fit_score,
                redis_client=redis_client,
            )

        await _evaluate_alerts_for_social_post(
            session=session,
            event=event,
            raw_entities=extracted,
            fit_score=fit_score,
        )

    return result_data


async def get_async_session():
    """Helper factory for async DB sessions."""
    async with async_session_maker() as session:
        yield session


class ValidationResult(tuple):
    """2-tuple (ok, dlq_reason) with optional errors and event attributes."""

    def __new__(
        cls,
        ok: bool,
        dlq_reason: str | None = None,
        errors: str | None = None,
        event: SocialPostEvent | None = None,
    ):
        obj = super().__new__(cls, (ok, dlq_reason))
        obj.ok = ok
        obj.dlq_reason = dlq_reason
        obj.errors = errors
        obj.event = event
        return obj

    def __bool__(self) -> bool:
        return self.ok


def _validate_event_schema(payload: Any) -> ValidationResult:
    """Validate incoming social stream event schema before processing.

    Returns a 2-tuple (ok, dlq_reason) where ok is True if valid, or False
    with a specific DLQ reason string if invalid.
    """
    if not isinstance(payload, dict):
        return ValidationResult(
            False,
            DLQ_REASON_SCHEMA_VALIDATION_ERROR,
            "Payload must be a dictionary",
            None,
        )

    # 1. Schema version check
    if "schema_version" in payload:
        raw_version = payload["schema_version"]
        if raw_version is None:
            logger.warning("Invalid schema_version None")
            return ValidationResult(
                False,
                DLQ_REASON_INVALID_SCHEMA_VERSION,
                "Invalid schema_version: None",
                None,
            )
        if isinstance(raw_version, bool):
            logger.warning("Invalid schema_version %r (boolean not allowed)", raw_version)
            return ValidationResult(
                False,
                DLQ_REASON_INVALID_SCHEMA_VERSION,
                f"Invalid schema_version: {raw_version!r}",
                None,
            )
        if isinstance(raw_version, float) and not raw_version.is_integer():
            logger.warning("Invalid schema_version %r (non-integer float not allowed)", raw_version)
            return ValidationResult(
                False,
                DLQ_REASON_INVALID_SCHEMA_VERSION,
                f"Invalid schema_version: {raw_version!r}",
                None,
            )
        try:
            version = int(raw_version)
        except (ValueError, TypeError):
            logger.warning("Invalid schema_version %r; cannot parse integer", raw_version)
            return ValidationResult(
                False,
                DLQ_REASON_INVALID_SCHEMA_VERSION,
                f"Invalid schema_version: {raw_version!r}",
                None,
            )
        if version < 1:
            logger.warning("Invalid schema_version %d (must be >= 1)", version)
            return ValidationResult(
                False,
                DLQ_REASON_INVALID_SCHEMA_VERSION,
                f"Invalid schema_version: {version}",
                None,
            )
        if version > SUPPORTED_SCHEMA_VERSION_MAX:
            logger.warning(
                "Unsupported schema_version %d (max supported is %d)",
                version,
                SUPPORTED_SCHEMA_VERSION_MAX,
            )
            return ValidationResult(
                False,
                DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION,
                f"Unsupported schema_version: {version}",
                None,
            )

    # 2. Content check (content or content_snippet must have non-empty text)
    content = payload.get("content")
    content_snippet = payload.get("content_snippet")
    has_content = bool(
        (isinstance(content, str) and content.strip())
        or (isinstance(content_snippet, str) and content_snippet.strip())
        or (content is not None and not isinstance(content, str) and str(content).strip())
        or (
            content_snippet is not None
            and not isinstance(content_snippet, str)
            and str(content_snippet).strip()
        )
    )

    if not has_content:
        logger.warning(
            "Missing content in social stream event (both content and content_snippet are empty)"
        )
        return ValidationResult(
            False,
            DLQ_REASON_MISSING_CONTENT,
            "Both content and content_snippet are empty or missing",
            None,
        )

    # 3. Workspace / Target check (target_id is required by social_posts database schema)
    raw_ws = payload.get("workspace_id")
    has_workspace = False
    if raw_ws is not None and not isinstance(raw_ws, bool):
        try:
            if int(raw_ws) > 0:
                has_workspace = True
        except (ValueError, TypeError):
            pass

    raw_target = payload.get("target_id")
    has_target = False
    if raw_target is not None and not isinstance(raw_target, bool):
        try:
            if int(raw_target) > 0:
                has_target = True
        except (ValueError, TypeError):
            pass

    if not has_target:
        if not has_workspace:
            logger.warning(
                "Missing workspace_id and target_id is null/invalid in social stream event"
            )
            return ValidationResult(
                False,
                DLQ_REASON_MISSING_WORKSPACE_ID,
                "Missing workspace_id and unresolvable target_id",
                None,
            )
        logger.warning(
            "Missing target_id in social stream event (target_id is required by database schema)"
        )
        return ValidationResult(
            False,
            DLQ_REASON_MISSING_TARGET_ID,
            "Missing target_id: target_id is required by social_posts database schema",
            None,
        )

    # 4. Pydantic validation (field type, platform/external_post_id non-empty, etc.)
    try:
        event = SocialPostEvent.model_validate(payload)
    except ValidationError as exc:
        logger.warning("Pydantic validation error for social post event: %s", exc)
        return ValidationResult(
            False,
            DLQ_REASON_SCHEMA_VALIDATION_ERROR,
            json.dumps(exc.errors(), default=str),
            None,
        )

    return ValidationResult(True, None, None, event)


def _safe_serialize_payload(payload: Any) -> str:
    """Serialize payload to JSON string, falling back to repr() if serialization fails."""
    try:
        return json.dumps(payload, default=str)
    except Exception as exc:
        logger.exception(
            "Failed to JSON-serialize payload for DLQ (%s); falling back to repr()", exc
        )
        return repr(payload)


async def _route_to_dlq(
    redis_client: Any,
    msg_id: str,
    payload: Any,
    dlq_reason: str,
    error: str | None = None,
    errors: Any = None,
) -> None:
    """Send failed message to dead-letter queue with dlq_reason and ACK original message."""
    dlq_payload = _safe_serialize_payload(payload)
    dlq_data: dict[str, str] = {
        "original_id": str(msg_id),
        "payload": dlq_payload,
        "dlq_reason": str(dlq_reason),
        "error": str(errors or error or dlq_reason or ""),
        "errors": str(errors) if errors is not None else "",
        "failed_at": datetime.now(UTC).isoformat(),
    }

    try:
        await redis_client.xadd(
            STREAM_SOCIAL_DEAD_LETTER,
            dlq_data,
            maxlen=DLQ_MAXLEN,
            approximate=True,
        )
    except Exception:
        logger.exception(
            "Failed to move message %s to dead-letter queue %s",
            msg_id,
            STREAM_SOCIAL_DEAD_LETTER,
        )
    finally:
        try:
            await redis_client.xack(
                STREAM_SOCIAL_RAW_POSTS,
                CONSUMER_GROUP_NAME,
                msg_id,
            )
        except Exception:
            logger.exception(
                "Failed to ACK social stream message %s during DLQ routing",
                msg_id,
            )


async def _check_stream_lag(redis_client: Any) -> dict[str, Any] | None:
    """Inspect Redis stream lag and pending messages count, logging warning if threshold exceeded.

    Probe uses XINFO GROUPS and XPENDING (count-only summary).
    Wrapped in try/except so probe failures never crash the consumer.
    """
    try:
        groups_info = await redis_client.xinfo_groups(STREAM_SOCIAL_RAW_POSTS)
        group_meta: dict[str, Any] = {}
        if isinstance(groups_info, list):
            for g in groups_info:
                if isinstance(g, dict):
                    name = g.get("name") if g.get("name") is not None else g.get(b"name")
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="replace")
                    if name == CONSUMER_GROUP_NAME:
                        group_meta = g
                        break

        pending_info = await redis_client.xpending(
            STREAM_SOCIAL_RAW_POSTS,
            CONSUMER_GROUP_NAME,
        )

        pending_count = 0
        if isinstance(pending_info, dict):
            raw_pending = (
                pending_info.get("pending")
                if pending_info.get("pending") is not None
                else pending_info.get(b"pending", 0)
            )
            try:
                pending_count = int(raw_pending or 0)
            except (ValueError, TypeError):
                pending_count = 0
        elif isinstance(pending_info, (int, float)):
            pending_count = int(pending_info)

        lag = (
            group_meta.get("lag")
            if group_meta.get("lag") is not None
            else group_meta.get(b"lag")
        )
        if lag is not None:
            with contextlib.suppress(ValueError, TypeError):
                lag = int(lag)

        consumer_count = (
            group_meta.get("consumers")
            if group_meta.get("consumers") is not None
            else group_meta.get(b"consumers", 0)
        )
        if consumer_count is not None:
            with contextlib.suppress(ValueError, TypeError):
                consumer_count = int(consumer_count)

        metrics = {
            "pending_count": pending_count,
            "lag": lag,
            "consumer_count": consumer_count,
        }

        exceeded = []
        if pending_count > SOCIAL_STREAM_LAG_WARN_THRESHOLD:
            exceeded.append(f"pending={pending_count}")
        if isinstance(lag, int) and lag > SOCIAL_STREAM_LAG_WARN_THRESHOLD:
            exceeded.append(f"lag={lag}")
        if exceeded:
            logger.warning(
                "Social stream lag warning: %s (threshold=%s), consumer_count=%s",
                ", ".join(exceeded),
                SOCIAL_STREAM_LAG_WARN_THRESHOLD,
                consumer_count,
            )

        return metrics
    except ResponseError as exc:
        if "NOGROUP" in str(exc).upper() or "NO SUCH KEY" in str(exc).upper():
            logger.debug("Stream or group not found during lag probe: %s", exc)
        else:
            logger.debug("Redis response error during lag probe: %s", exc)
        return None
    except Exception as exc:
        logger.debug("Failed checking social stream lag: %s", exc)
        return None


def _default_consumer_name() -> str:
    """Return a unique consumer name per process/host for load balancing."""
    return f"{socket.gethostname()}-{os.getpid()}"


async def run_social_stream_consumer(
    redis_client: Any | None = None,
    consumer_name: str | None = None,
    batch_size: int = 10,
    block_ms: int = 2000,
    max_messages_per_batch: int = MAX_MESSAGES_PER_BATCH,
    max_loops: int = 1,
) -> int:
    """Consume events from Redis stream using Consumer Groups (AD-SOC-4)."""
    created_locally = False
    if redis_client is None:
        import redis.asyncio as aioredis

        # The single-writer social raw-posts stream lives on the XActions-side
        # Redis instance, which can differ from the app REDIS_APP_URL
        # (cache/queues). Prefer the dedicated XACTIONS_STREAM_REDIS_URL when
        # set; fall back to REDIS_APP_URL for same-instance deployments.
        stream_url = (
            getattr(config, "XACTIONS_STREAM_REDIS_URL", "") or config.REDIS_APP_URL
        )
        redis_client = aioredis.from_url(stream_url, decode_responses=True)
        created_locally = True

    consumer_name = consumer_name or _default_consumer_name()

    try:
        # Ensure consumer group exists, but only swallow "BUSYGROUP".
        try:
            await redis_client.xgroup_create(
                name=STREAM_SOCIAL_RAW_POSTS,
                groupname=CONSUMER_GROUP_NAME,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc).upper():
                logger.error(
                    "Failed to create Redis consumer group: %s",
                    exc,
                )
                return 0
        except Exception as exc:  # consumer group creation failure; log exception and return 0
            logger.exception("Failed to create Redis consumer group: %s", exc)
            return 0

        count = min(batch_size, max_messages_per_batch)
        total_processed = 0

        for _ in range(max(1, max_loops)):
            entries = None
            # Story 35.1: Reclaim pending messages stuck in PEL from dead workers
            try:
                claim_res = await redis_client.xautoclaim(
                    name=STREAM_SOCIAL_RAW_POSTS,
                    groupname=CONSUMER_GROUP_NAME,
                    consumername=consumer_name,
                    min_idle_time=AUTOCLAIM_MIN_IDLE_TIME_MS,
                    start_id="0-0",
                    count=count,
                )
                if claim_res and len(claim_res) >= 2 and claim_res[1]:
                    logger.info(
                        "XAUTOCLAIM reclaimed %d pending messages from dead workers",
                        len(claim_res[1]),
                    )
                    entries = [(STREAM_SOCIAL_RAW_POSTS, claim_res[1])]
            except Exception as claim_exc:
                logger.debug("XAUTOCLAIM check skipped or failed: %s", claim_exc)

            # Fall back to reading new messages if no pending messages were claimed
            if not entries:
                try:
                    entries = await redis_client.xreadgroup(
                        groupname=CONSUMER_GROUP_NAME,
                        consumername=consumer_name,
                        streams={STREAM_SOCIAL_RAW_POSTS: ">"},
                        count=count,
                        block=block_ms,
                    )
                except Exception as exc:  # stream read failure; log error and break consumer loop
                    logger.error("Error reading from social stream: %s", exc)
                    break

            now = time.monotonic()
            if now - _LAG_STATE["last_check"] >= LAG_CHECK_INTERVAL_SECONDS:
                await _check_stream_lag(redis_client)
                _LAG_STATE["last_check"] = now

            if not entries:
                break

            async with async_session_maker() as session:
                session_broken = False
                for _stream_name, messages in entries:
                    for msg_id, payload in messages:
                        validation = _validate_event_schema(payload)
                        if not validation.ok:
                            dlq_reason = (
                                validation.dlq_reason
                                or DLQ_REASON_SCHEMA_VALIDATION_ERROR
                            )
                            logger.warning(
                                "Social stream event %s schema validation failed (reason=%s); routing to DLQ",
                                msg_id,
                                dlq_reason,
                            )
                            await _route_to_dlq(
                                redis_client=redis_client,
                                msg_id=msg_id,
                                payload=payload,
                                dlq_reason=dlq_reason,
                                errors=validation.errors,
                            )
                            continue

                        try:
                            result = await process_social_post_event(
                                payload,
                                session=session,
                                redis_client=redis_client,
                                event=validation.event,
                            )
                            if result is not None:
                                total_processed += 1
                                try:
                                    await redis_client.xack(
                                        STREAM_SOCIAL_RAW_POSTS,
                                        CONSUMER_GROUP_NAME,
                                        msg_id,
                                    )
                                except Exception:  # best-effort message ACK; log exception
                                    logger.exception(
                                        "Failed to ACK social stream message %s",
                                        msg_id,
                                    )
                            else:
                                logger.warning(
                                    "Social post event %s processing failed (reason=%s); routing to DLQ",
                                    msg_id,
                                    DLQ_REASON_MISSING_WORKSPACE_ID,
                                )
                                await _route_to_dlq(
                                    redis_client=redis_client,
                                    msg_id=msg_id,
                                    payload=payload,
                                    dlq_reason=DLQ_REASON_MISSING_WORKSPACE_ID,
                                    error="workspace_id could not be resolved from target_id",
                                )
                        except Exception as exc:  # per-item message processing failure; rollback, log exception, and move to DLQ
                            session_broken = False
                            try:
                                await session.rollback()
                            except Exception:
                                logger.exception("Session rollback failed — marking session as broken")
                                session_broken = True
                            logger.exception(
                                "Failed processing social stream message %s: %s",
                                msg_id,
                                exc,
                            )
                            await _route_to_dlq(
                                redis_client=redis_client,
                                msg_id=msg_id,
                                payload=payload,
                                dlq_reason=DLQ_REASON_RUNTIME_FAILURE,
                                error=str(exc),
                            )
                            if session_broken:
                                logger.warning(
                                    "Session corrupted — aborting batch early to avoid cascading failures"
                                )
                                break
                    if session_broken:
                        break

            await asyncio.sleep(BATCH_SLEEP_SECONDS)

        return total_processed
    finally:
        if created_locally and redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:  # best-effort redis client close; log exception
                logger.exception("Error closing Redis client")
