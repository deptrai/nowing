"""``Capability`` registry contracts shared by every verb."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pydantic import BaseModel
    from sqlalchemy.ext.asyncio import AsyncSession


class BillingUnit(StrEnum):
    """The meter a verb charges on (priced by the billing service, 03c). ``None`` = free.

    Each value doubles as the ``TokenUsage.usage_type`` audit string for that meter.
    """

    WEB_CRAWL = "web_crawl"
    REDDIT_ITEM = "reddit_item"
    GOOGLE_SEARCH_SERP = "google_search_serp"
    GOOGLE_MAPS_PLACE = "google_maps_place"
    GOOGLE_MAPS_REVIEW = "google_maps_review"
    AMAZON_PRODUCT = "amazon_product"
    YOUTUBE_VIDEO = "youtube_video"
    YOUTUBE_COMMENT = "youtube_comment"
    INSTAGRAM_ITEM = "instagram_item"
    INSTAGRAM_COMMENT = "instagram_comment"
    TIKTOK_VIDEO = "tiktok_video"
    TIKTOK_USER = "tiktok_user"
    TIKTOK_COMMENT = "tiktok_comment"
    CHAINLENS_QUERY = "chainlens_query"
    BATDONGSAN_ITEM = "batdongsan_item"
    CHOTOT_BDS_ITEM = "chotot_bds_item"
    CHOTOT_ITEM = "chotot_item"
    MUABAN_BDS_ITEM = "muaban_bds_item"
    VN_BDS_AGGREGATE_QUERY = "vn_bds_aggregate_query"
    VIETNAMWORKS_JOB = "vietnamworks_job"
    TOPCV_JOB = "topcv_job"
    ITVIEC_JOB = "itviec_job"
    INDEED_JOB = "indeed_job"
    VN_JOBS_AGGREGATE_QUERY = "vn_jobs_aggregate_query"
    WALMART_PRODUCT = "walmart_product"
    WALMART_REVIEW = "walmart_review"
    CAFEF_DATA = "cafef_data"
    VIETSTOCK_DATA = "vietstock_data"
    MASOTHUE_COMPANY = "masothue_company"
    LEAD_SCORE = "lead_score"
    PROCUREMENT_QUERY = "procurement_query"
    PROCUREMENT_HSMT = "procurement_hsmt"
    SOCIAL_LEAD_ITEM = "social_lead_item"
    TELEGRAM_MESSAGE = "telegram_message"
    ECOMMERCE_PRODUCT = "ecommerce_product"


class BillableInput(Protocol):
    """A billed verb's input that reports its worst-case unit count for pre-flight."""

    @property
    def estimated_units(self) -> int: ...


class BillableOutput(Protocol):
    """A capability output that reports its own billable count."""

    @property
    def billable_units(self) -> int: ...


@dataclass(frozen=True)
class CapabilityContext:
    """Request-scoped deps a capability call needs beyond its typed input."""

    session: AsyncSession
    workspace_id: int
    run_id: str | None = None
    user_id: str | None = None
    auth: Any | None = None


Executor = Callable[[Any], Awaitable[Any]]


@dataclass(frozen=True)
class Capability:
    """One typed verb; the source of truth the doors (05) and agent (07) read."""

    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    executor: Executor
    billing_unit: BillingUnit | None
    docs_url: str | None = None
    context_aware: bool = False
    namespace: str | None = None
    metadata: dict[str, Any] | None = None
