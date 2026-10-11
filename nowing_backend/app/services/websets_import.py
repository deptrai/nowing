"""Websets import service and entity mapping seam (Story 41.1, Story 41.2)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.core.billing import _resolve_workspace_owner
from app.db import async_session_maker
from app.lead_intelligence.dnc.normalizer import (
    normalize_domain,
    normalize_email,
    normalize_phone_e164,
)
from app.models.billing import BillingEvent
from app.models.webset_campaign import WebsetCampaign
from app.models.workspaces import VerticalClient
from app.services import wallet_credit
from app.services.chainlens.websets import WebsetsService
from app.services.etl_credit_service import InsufficientCreditsError
from app.services.lead_batch_service import LeadBatchService

logger = logging.getLogger(__name__)

WEBSET_LEAD_IMPORT_COST_MICROS = 1_500_000  # 1.5 credits = 1,500,000 micros


class _QuotaExceededError(Exception):
    """Internal sentinel raised when wallet reservation fails with InsufficientCreditsError."""


def map_webset_entity(
    entity: dict[str, Any],
    webset_id: str | None = None,
) -> dict[str, Any] | None:
    """Map a ChainLens webset item/entity to the LeadBatchService lead dict shape.

    Extension seam for Story 41.2 (custom mapper, schema transformation, billing).
    Returns None if entity is invalid or status is not ready/verified.
    """
    if not isinstance(entity, dict):
        return None

    status = entity.get("status")
    if status is not None and status not in ("ready", "verified"):
        return None

    entity_id = str(
        entity.get("id") or entity.get("entity_id") or entity.get("entityId") or ""
    )
    source_url = (
        entity.get("canonical_url")
        or entity.get("canonicalUrl")
        or entity.get("url")
        or entity.get("source_url")
        or entity.get("sourceUrl")
    )

    enrichments = entity.get("enrichments")
    unmapped_enrichments: dict[str, Any] = {}
    company_name = None
    title = None
    phone = None
    email = None
    domain = None
    first_grounding_url = None

    if isinstance(enrichments, dict):
        for col_key, val_obj in enrichments.items():
            val = val_obj.get("value") if isinstance(val_obj, dict) else val_obj
            g_url = (
                val_obj.get("groundingUrl") or val_obj.get("grounding_url")
                if isinstance(val_obj, dict)
                else None
            )
            if not first_grounding_url and g_url:
                first_grounding_url = g_url

            if col_key == "company_name":
                company_name = val
            elif col_key == "phone":
                phone = val
            elif col_key == "email":
                email = val
            elif col_key == "title":
                title = val
            elif col_key in ("website", "domain"):
                domain = val
            else:
                unmapped_enrichments[col_key] = val_obj

    if not source_url and first_grounding_url:
        source_url = first_grounding_url

    data = entity.get("data")
    if not isinstance(data, dict):
        data = entity.get("properties") or entity.get("fields")
    if isinstance(data, dict):
        if not company_name:
            company_name = (
                data.get("company_name")
                or data.get("companyName")
                or data.get("company")
                or data.get("name")
            )
        if not title:
            title = data.get("title") or data.get("job_title") or data.get("position")
        if not phone:
            phone = (
                data.get("phone") or data.get("phone_number") or data.get("phoneNumber")
            )
        if not email:
            email = data.get("email")
        if not domain:
            domain = data.get("domain") or data.get("website")
        if not source_url:
            source_url = (
                data.get("source_url") or data.get("sourceUrl") or data.get("url")
            )

    if not any([company_name, title, phone, email, domain, source_url]):
        return None

    if not company_name:
        fragment = entity_id or phone or email or title or "unknown"
        company_name = f"Webset Lead {fragment}"

    extra_metadata = {"websets": unmapped_enrichments}

    # Reuse the DNC normalizers so stored values match the canonical form used
    # for value_hmac dedup and DNC checks. Fall back to the raw value when it
    # cannot be normalized — losing displayable data is worse than a hmac miss.
    if phone:
        phone = normalize_phone_e164(str(phone)) or phone
    if email:
        email = normalize_email(str(email)) or email
    if domain:
        domain = normalize_domain(str(domain)) or domain

    # Truncate to Lead VARCHAR bounds — a longer value would raise
    # StringDataRightTruncationError and abort the whole 100-lead batch.
    return {
        "company_name": str(company_name)[:200],
        "title": title,
        "phone": phone,
        "email": email,
        "domain": str(domain)[:255] if domain else domain,
        "source": "websets",
        "source_url": source_url,
        "extra_metadata": extra_metadata,
        "_entity_id": entity_id,
        "raw": {
            "entity_id": entity_id,
            "webset_id": webset_id or entity.get("webset_id") or entity.get("websetId"),
        },
    }


class WebsetsImportService:
    """Coordinates draining items from ChainLens Websets and batch ingesting them into Nowing."""

    def __init__(
        self,
        websets_service: WebsetsService | None = None,
        batch_service: LeadBatchService | None = None,
    ) -> None:
        self._websets_service = websets_service or WebsetsService()
        self._batch_service = batch_service or LeadBatchService()

    async def import_webset(
        self,
        webset_id: str,
        session_factory: Any = None,
    ) -> dict[str, Any]:
        """Fetch all ready/verified items from ChainLens webset and ingest into Nowing."""
        maker = session_factory or async_session_maker
        async with maker() as session:
            stmt = select(WebsetCampaign).where(
                WebsetCampaign.webset_id == str(webset_id)
            )
            res = await session.execute(stmt)
            campaign = res.scalar_one_or_none()
            if not campaign:
                logger.error("WebsetCampaign not found for webset_id=%s", webset_id)
                return {
                    "status": "not_found",
                    "webset_id": webset_id,
                    "imported_count": 0,
                }

            if campaign.status == "completed":
                logger.info(
                    "Webset %s already imported (status=completed); skipping",
                    webset_id,
                )
                return {
                    "status": "skipped",
                    "webset_id": webset_id,
                    "imported_count": campaign.imported_count or 0,
                }

            workspace_id = campaign.workspace_id
            campaign_id = campaign.campaign_id

            # Only propagate campaign_id into lead.client_id when it points at a
            # real vertical client — verified_contacts enforces an FK on
            # client_id, so a synthetic id would abort the whole ingest batch.
            if campaign_id is not None:
                client_exists = await session.scalar(
                    select(func.count(VerticalClient.id)).where(
                        VerticalClient.client_id == campaign_id
                    )
                )
                if not client_exists:
                    logger.warning(
                        "campaign_id %s is not a vertical client; leads import "
                        "without client_id propagation",
                        campaign_id,
                    )
                    campaign_id = None

            raw_owner = await _resolve_workspace_owner(session, workspace_id)
            owner_user_id: UUID | None = None
            if raw_owner is not None:
                if isinstance(raw_owner, UUID):
                    owner_user_id = raw_owner
                else:
                    try:
                        owner_user_id = UUID(str(raw_owner))
                    except (ValueError, TypeError, AttributeError):
                        owner_user_id = None

            if owner_user_id is None:
                # Fail-closed (retro AI-41.5, decided): importing without an owner
                # means free leads — fail instead of silently skipping billing.
                logger.warning(
                    "No owner found for workspace_id=%s; failing webset import "
                    "(billing requires a workspace owner)",
                    workspace_id,
                )
                campaign.status = "failed"
                current_stats = dict(campaign.stats or {})
                current_stats["failure_reason"] = "no_workspace_owner"
                campaign.stats = current_stats
                await session.commit()
                return {
                    "status": "failed",
                    "webset_id": webset_id,
                    "imported_count": campaign.imported_count or 0,
                }

        # Drain theo stream + flush ingest mỗi 100 leads — không buffer toàn bộ,
        # và mọi lỗi (drain lẫn ingest) đều đánh dấu campaign failed.
        imported_count = 0
        drained_count = 0  # mapped leads (đã qua map_webset_entity)
        raw_count = 0  # raw items ChainLens trả về (kể cả bị mapper loại)
        skipped_count = 0  # raw items bị mapper drop (None)
        try:
            async with maker() as session:
                buffer: list[dict[str, Any]] = []

                async def flush() -> None:
                    nonlocal imported_count
                    if not buffer:
                        return
                    batch = list(buffer)
                    buffer.clear()
                    imported_count += await self._flush_batch(
                        session=session,
                        batch=batch,
                        webset_id=webset_id,
                        workspace_id=workspace_id,
                        campaign_id=campaign_id,
                        owner_user_id=owner_user_id,
                        stats_counts={
                            "raw_items_count": raw_count,
                            "drained_count": drained_count,
                            "skipped_count": skipped_count,
                            "imported_count": imported_count,
                        },
                    )

                async for item in self._websets_service.iter_ready_items(
                    webset_id=webset_id,
                    workspace_id=workspace_id,
                ):
                    raw_count += 1
                    mapped = map_webset_entity(item, webset_id=webset_id)
                    if mapped:
                        if campaign_id and "client_id" not in mapped:
                            mapped["client_id"] = campaign_id
                        buffer.append(mapped)
                        drained_count += 1
                        if len(buffer) >= 100:
                            await flush()
                    else:
                        skipped_count += 1
                await flush()
        except _QuotaExceededError:
            logger.info(
                "Webset import stopped due to quota exceeded for webset_id=%s; imported=%d",
                webset_id,
                imported_count,
            )
            return {
                "status": "quota_exceeded",
                "webset_id": webset_id,
                "imported_count": imported_count,
            }
        except Exception as exc:
            logger.exception(
                "Error importing items for webset_id=%s: %s", webset_id, exc
            )
            async with maker() as session:
                # Skip the write if a concurrent import already completed — a
                # late failure must not clobber a terminal success status.
                stmt = select(WebsetCampaign).where(
                    WebsetCampaign.webset_id == str(webset_id),
                    WebsetCampaign.status != "completed",
                )
                res = await session.execute(stmt)
                campaign = res.scalar_one_or_none()
                if campaign:
                    campaign.status = "failed"
                    campaign.imported_count = imported_count
                    current_stats = dict(campaign.stats or {})
                    current_stats["raw_items_count"] = raw_count
                    current_stats["drained_count"] = drained_count
                    current_stats["skipped_count"] = skipped_count
                    current_stats["imported_count"] = imported_count
                    campaign.stats = current_stats
                    await session.commit()
            raise

        async with maker() as session:
            stmt = select(WebsetCampaign).where(
                WebsetCampaign.webset_id == str(webset_id)
            )
            res = await session.execute(stmt)
            campaign = res.scalar_one_or_none()
            if campaign:
                campaign.imported_count = imported_count
                campaign.status = "completed"
                current_stats = dict(campaign.stats or {})
                current_stats["raw_items_count"] = raw_count
                current_stats["drained_count"] = drained_count
                current_stats["skipped_count"] = skipped_count
                current_stats["imported_count"] = imported_count
                campaign.stats = current_stats
                await session.commit()

        logger.info(
            "Completed webset import for webset_id=%s: imported=%s leads",
            webset_id,
            imported_count,
        )
        return {
            "status": "completed",
            "webset_id": webset_id,
            "imported_count": imported_count,
        }

    async def _flush_batch(
        self,
        *,
        session: AsyncSession,
        batch: list[dict[str, Any]],
        webset_id: str,
        workspace_id: int,
        campaign_id: str | None,
        owner_user_id: str | None,
        stats_counts: dict[str, int],
    ) -> int:
        """Ingest one mapped-lead batch and settle its billing.

        Reserves 1.5 credits/lead up front; on success commits credits for new
        BillingEvent rows and releases dupes/rejects; on any failure rolls the
        session back then releases the uncommitted remainder so reserved
        credits are never stranded. Returns the ingested lead count.
        """
        batch_size = len(batch)
        credit_reserved = False
        reserve_micros = batch_size * WEBSET_LEAD_IMPORT_COST_MICROS
        if owner_user_id is not None:
            try:
                await wallet_credit.reserve_credit(
                    session, owner_user_id, reserve_micros
                )
                credit_reserved = True
            except InsufficientCreditsError as ice:
                logger.warning("Insufficient credits to import webset batch: %s", ice)
                stmt = select(WebsetCampaign).where(
                    WebsetCampaign.webset_id == str(webset_id),
                    WebsetCampaign.status != "completed",
                )
                res = await session.execute(stmt)
                camp = res.scalar_one_or_none()
                if camp:
                    camp.status = "quota_exceeded"
                    current_stats = dict(camp.stats or {})
                    current_stats.update(stats_counts)
                    camp.stats = current_stats
                    camp.imported_count = stats_counts.get("imported_count", 0)
                    await session.commit()
                raise _QuotaExceededError() from ice

        committed_micros = 0
        try:
            ingest_res = await self._batch_service.ingest_batch(
                session=session,
                workspace_id=workspace_id,
                leads=batch,
            )
            batch_imported = ingest_res.get("ingested_count", batch_size)

            if owner_user_id is not None and credit_reserved:
                accepted = ingest_res.get("accepted", [True] * batch_size)
                committed_micros = await self._settle_batch_credits(
                    session,
                    batch=batch,
                    accepted=accepted,
                    owner_user_id=owner_user_id,
                    webset_id=webset_id,
                    campaign_id=campaign_id,
                    workspace_id=workspace_id,
                )

            # Commit inside the guarded block: a commit failure must also
            # release the reservation instead of stranding it.
            await session.commit()
            # Count only after commit: a rolled-back batch left no leads.
            return batch_imported
        except Exception:
            # Release whatever reservation is left so a mid-flush failure never
            # strands locked credits. Roll back first: the session is in a
            # failed transaction, so release_credit would raise
            # InFailedSqlTransactionError and the credits would stay locked.
            if owner_user_id is not None and credit_reserved:
                try:
                    await session.rollback()
                    await wallet_credit.release_credit(
                        session,
                        owner_user_id,
                        reserve_micros - committed_micros,
                    )
                except Exception:
                    logger.warning(
                        "Failed to release reserved webset import credits",
                        exc_info=True,
                    )
            raise

    async def _settle_batch_credits(
        self,
        session: AsyncSession,
        *,
        batch: list[dict[str, Any]],
        accepted: list[Any],
        owner_user_id: str,
        webset_id: str,
        campaign_id: str | None,
        workspace_id: int,
    ) -> int:
        """Bill each accepted lead exactly once.

        Dedup key per lead: entity id / source_url, else a content-derived
        fallback — a per-batch index would collide across flushes while
        identical entities must dedup to the same event id. Commits reserved
        credits for new (webset_id, entity) BillingEvent rows and releases
        credits for duplicates/rejects. Returns committed micros.
        """
        accepted_flags: list[bool] = []
        event_ids: list[Any] = []
        for idx, lead in enumerate(batch):
            accepted_flags.append(accepted[idx] if idx < len(accepted) else True)
            entity_id = (
                lead.get("_entity_id")
                or (lead.get("raw") or {}).get("entity_id")
                or lead.get("source_url")
                or f"lead:{lead.get('company_name')}|{lead.get('domain')}|{lead.get('phone')}|{lead.get('email')}"
            )
            event_ids.append(uuid5(NAMESPACE_URL, f"{webset_id}:{entity_id}"))

        candidates = [
            eid for eid, ok in zip(event_ids, accepted_flags, strict=True) if ok
        ]
        existing_ids: set[Any] = set()
        if candidates:
            rows = (
                (
                    await session.execute(
                        select(BillingEvent.event_id).where(
                            BillingEvent.event_entity_type == "webset",
                            BillingEvent.event_type == "lead_import",
                            BillingEvent.event_id.in_(candidates),
                        )
                    )
                )
                .scalars()
                .all()
            )
            existing_ids = set(rows)

        to_commit_count = 0
        to_release_count = 0
        seen: set[Any] = set()
        for idx, _lead in enumerate(batch):
            event_id = event_ids[idx]
            if not accepted_flags[idx] or event_id in existing_ids or event_id in seen:
                to_release_count += 1
                continue
            seen.add(event_id)
            session.add(
                BillingEvent(
                    workspace_id=workspace_id,
                    client_id=campaign_id,
                    user_id=owner_user_id,
                    event_entity_type="webset",
                    event_type="lead_import",
                    event_id=event_id,
                    cost_micros=WEBSET_LEAD_IMPORT_COST_MICROS,
                    currency="USD",
                    cost_basis="actual",
                )
            )
            to_commit_count += 1

        to_commit_micros = to_commit_count * WEBSET_LEAD_IMPORT_COST_MICROS
        to_release_micros = to_release_count * WEBSET_LEAD_IMPORT_COST_MICROS

        if to_commit_micros > 0:
            await wallet_credit.commit_reserved_credit(
                session, owner_user_id, to_commit_micros
            )
        if to_release_micros > 0:
            await wallet_credit.release_credit(
                session, owner_user_id, to_release_micros
            )
        return to_commit_micros
