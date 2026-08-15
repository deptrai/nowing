"""Redis Stream Worker & Celery Processor for Ingested Social Posts (Story 21.8 / AD-SOC-4 / AD-SOC-6).

Reads raw social posts from Redis Stream 'stream:social:raw_posts', validates the
payload, extracts contact numbers, prices, emails, locations, computes intent &
fit score, performs idempotent UPSERT into PostgreSQL `social_posts`, and creates
CRM `Lead` records + evaluates `AlertRule` matches for high-intent posts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import socket
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
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
from app.proprietary.platforms.xactions.adapter import STREAM_SOCIAL_RAW_POSTS
from app.proprietary.platforms.xactions.phone_extractor import SocialEntityExtractor

logger = logging.getLogger(__name__)

CONSUMER_GROUP_NAME = "social_processors"
MAX_MESSAGES_PER_BATCH = 100
BATCH_SLEEP_SECONDS = 0.01
STREAM_SOCIAL_DEAD_LETTER = "stream:social:failed"

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
    content: str = ""
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
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
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
    if reactions > 10 or comments > 5:
        score += 0.05

    return min(1.0, round(score, 2))


async def _create_lead_from_social_post(
    session: AsyncSession,
    event: SocialPostEvent,
    raw_entities: dict[str, Any],
    fit_score: float,
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

    # Avoid duplicate leads for the same social post/source.
    existing_id = await session.scalar(
        select(Lead.id).where(
            Lead.workspace_id == workspace_id,
            Lead.source == "social",
            Lead.source_url == source_url,
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

    lead = Lead(
        workspace_id=workspace_id,
        client_id=event.client_id,
        source="social",
        source_url=source_url,
        company_name=company_name,
        domain=domain,
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
    except Exception as exc:
        logger.exception(
            "Alert evaluation failed for %s/%s: %s",
            event.platform,
            event.external_post_id,
            exc,
        )


async def process_social_post_event(
    payload: dict[str, Any],
    session: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Validate, extract entities, calculate fit score, and UPSERT into social_posts."""
    try:
        event = SocialPostEvent.model_validate(payload)
    except ValidationError as exc:
        logger.warning("Invalid social post event: %s", exc)
        return None

    extractor = SocialEntityExtractor()
    extracted = extractor.extract_all(event.content)
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
        "content": event.content,
        "intent_tag": intent_tag,
        "fit_score": fit_score,
        "reactions_count": event.reactions_count,
        "comments_count": event.comments_count,
        "shares_count": event.shares_count,
        "media_urls": event.media_urls,
        "raw_entities": extracted,
        "published_at": event.published_at,
    }

    if session is not None:
        # Resolve workspace context from explicit event or the monitored target.
        workspace_id = event.workspace_id
        if target_id is None:
            logger.warning(
                "Cannot persist social post %s/%s: target_id is missing",
                event.platform,
                event.external_post_id,
            )
            return None

        if workspace_id is None:
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

        event.workspace_id = workspace_id
        result_data["workspace_id"] = workspace_id

        stmt = pg_insert(SocialPost).values(**result_data)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["platform", "external_post_id"],
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
            return None

        if intent_tag in SOCIAL_LEAD_INTENTS:
            await _create_lead_from_social_post(
                session=session,
                event=event,
                raw_entities=extracted,
                fit_score=fit_score,
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


def _default_consumer_name() -> str:
    """Return a unique consumer name per process/host for load balancing."""
    return f"{socket.gethostname()}-{os.getpid()}"


async def run_social_stream_consumer(
    redis_client: Any | None = None,
    consumer_name: str | None = None,
    batch_size: int = 10,
    block_ms: int = 2000,
    max_messages_per_batch: int = MAX_MESSAGES_PER_BATCH,
) -> int:
    """Consume events from Redis stream using Consumer Groups (AD-SOC-4)."""
    created_locally = False
    if redis_client is None:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(
            config.REDIS_APP_URL, decode_responses=True
        )
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
        except Exception as exc:
            logger.exception("Failed to create Redis consumer group: %s", exc)
            return 0

        count = min(batch_size, max_messages_per_batch)
        try:
            entries = await redis_client.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=consumer_name,
                streams={STREAM_SOCIAL_RAW_POSTS: ">"},
                count=count,
                block=block_ms,
            )
        except Exception as exc:
            logger.error("Error reading from social stream: %s", exc)
            return 0

        if not entries:
            return 0

        processed_count = 0
        async with async_session_maker() as session:
            for _stream_name, messages in entries:
                for msg_id, payload in messages:
                    try:
                        result = await process_social_post_event(
                            payload, session=session
                        )
                        if result is not None:
                            processed_count += 1
                            try:
                                await redis_client.xack(
                                    STREAM_SOCIAL_RAW_POSTS,
                                    CONSUMER_GROUP_NAME,
                                    msg_id,
                                )
                            except Exception:
                                logger.exception(
                                    "Failed to ACK social stream message %s",
                                    msg_id,
                                )
                    except Exception as exc:
                        await session.rollback()
                        logger.exception(
                            "Failed processing social stream message %s: %s",
                            msg_id,
                            exc,
                        )
                        try:
                            await redis_client.xadd(
                                STREAM_SOCIAL_DEAD_LETTER,
                                {
                                    "original_id": msg_id,
                                    "payload": json.dumps(payload),
                                    "error": str(exc),
                                    "failed_at": datetime.now(UTC).isoformat(),
                                },
                            )
                            await redis_client.xack(
                                STREAM_SOCIAL_RAW_POSTS,
                                CONSUMER_GROUP_NAME,
                                msg_id,
                            )
                        except Exception:
                            logger.exception(
                                "Failed to move message %s to dead-letter queue",
                                msg_id,
                            )

                    await asyncio.sleep(BATCH_SLEEP_SECONDS)

        return processed_count
    finally:
        if created_locally and redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:
                logger.exception("Error closing Redis client")
