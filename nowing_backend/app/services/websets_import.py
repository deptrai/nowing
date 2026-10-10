"""Websets import service and entity mapping seam (Story 41.1)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.db import async_session_maker
from app.models.webset_campaign import WebsetCampaign
from app.services.chainlens.websets import WebsetsService
from app.services.lead_batch_service import LeadBatchService

logger = logging.getLogger(__name__)


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

    data = entity.get("data")
    if not isinstance(data, dict):
        data = entity.get("properties") or entity.get("fields") or entity
    if not isinstance(data, dict):
        return None

    entity_id = str(
        entity.get("id") or entity.get("entity_id") or entity.get("entityId") or ""
    )
    source_url = (
        data.get("source_url")
        or data.get("sourceUrl")
        or data.get("url")
        or entity.get("source_url")
        or entity.get("sourceUrl")
        or entity.get("url")
    )
    company_name = (
        data.get("company_name")
        or data.get("companyName")
        or data.get("company")
        or data.get("name")
    )
    title = data.get("title") or data.get("job_title") or data.get("position")
    phone = data.get("phone") or data.get("phone_number") or data.get("phoneNumber")
    email = data.get("email")
    domain = data.get("domain") or data.get("website")

    if not any([company_name, title, phone, email, domain, source_url]):
        return None

    if not company_name:
        # Fallback phải unique theo entity để không va value_hmac
        # (hash workspace+domain+company_name) khi nhiều entity cùng thiếu tên
        fragment = entity_id or phone or email or title or "unknown"
        company_name = f"Webset Lead {fragment}"

    return {
        "company_name": company_name,
        "title": title,
        "phone": phone,
        "email": email,
        "domain": domain,
        "source": "websets",
        "source_url": source_url,
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

        # Drain theo stream + flush ingest mỗi 100 leads — không buffer toàn bộ,
        # và mọi lỗi (drain lẫn ingest) đều đánh dấu campaign failed.
        imported_count = 0
        drained_count = 0  # mapped leads (đã qua map_webset_entity)
        raw_count = 0  # raw items ChainLens trả về (kể cả bị mapper loại)
        try:
            async with maker() as session:
                buffer: list[dict[str, Any]] = []

                async def flush() -> None:
                    nonlocal imported_count
                    if not buffer:
                        return
                    ingest_res = await self._batch_service.ingest_batch(
                        session=session,
                        workspace_id=workspace_id,
                        leads=list(buffer),
                    )
                    imported_count += ingest_res.get("ingested_count", len(buffer))
                    buffer.clear()
                    await session.commit()

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
                await flush()
        except Exception as exc:
            logger.exception(
                "Error importing items for webset_id=%s: %s", webset_id, exc
            )
            async with maker() as session:
                stmt = select(WebsetCampaign).where(
                    WebsetCampaign.webset_id == str(webset_id)
                )
                res = await session.execute(stmt)
                campaign = res.scalar_one_or_none()
                if campaign:
                    campaign.status = "failed"
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
