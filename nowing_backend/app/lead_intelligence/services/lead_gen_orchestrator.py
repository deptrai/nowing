"""Unified Multi-Source AI Lead Generation Orchestrator (Story 21.15)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lead_intelligence.adapters.base import (
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
)
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.services.deduplication_service import (
    EntityDeduplicationService,
)

logger = logging.getLogger(__name__)


class SubTaskPlan(BaseModel):
    """Sub-task plan targeting a specific platform adapter."""

    model_config = ConfigDict(from_attributes=True)

    source_name: str
    query: str
    limit: int = 50
    filters: dict[str, Any] = Field(default_factory=dict)
    category: LeadSourceCategory = LeadSourceCategory.GENERAL


class DispatchedScrapeJobResponse(BaseModel):
    """Response of asynchronous non-blocking scraper job dispatch."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str
    workspace_id: int
    status: str = "dispatched"
    dispatched_tasks: list[dict[str, Any]] = Field(default_factory=list)


class LeadGenOrchestratorResult(BaseModel):
    """Execution outcome of multi-source lead generation orchestrator."""

    model_config = ConfigDict(from_attributes=True)

    status: str = "completed"  # "completed" | "partial" | "degraded"
    total_discovered: int = 0
    total_deduplicated: int = 0
    leads: list[NormalizedLead] = Field(default_factory=list)
    degraded_sources: list[str] = Field(default_factory=list)
    table_id: str | None = None
    subtask_plans: list[SubTaskPlan] = Field(default_factory=list)
    deduplication_summary: dict[str, Any] = Field(default_factory=dict)


class LeadGenOrchestrator:
    """Orchestrator planning, parallelizing, and aggregating multi-source lead generation."""

    def __init__(
        self,
        registry: LeadSourceAdapterRegistry | None = None,
        deduplication_service: EntityDeduplicationService | None = None,
        db: Any = None,
        redis: Any = None,
    ) -> None:
        self.registry = registry or LeadSourceAdapterRegistry.get_default()
        self.deduplication_service = (
            deduplication_service or EntityDeduplicationService()
        )
        self.db = db
        self.redis = redis

    async def dispatch_scrape_job(
        self,
        workspace_id: int,
        query: str,
        sources: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> DispatchedScrapeJobResponse:
        """
        Non-blocking dispatch of multi-platform scraper tasks to dedicated Celery pool (AC-1).
        Returns job_id and task descriptors in < 100ms without blocking on HTTP calls.
        """
        from app.tasks.lead_scrapers import run_platform_scrape_task

        job_id = f"lead-job-{uuid4()}"
        target_sources = (
            sources
            if sources is not None
            else ["batdongsan", "chotot", "topcv", "masothue"]
        )

        dispatched_tasks: list[dict[str, Any]] = []
        for platform in target_sources:
            try:
                task_res = run_platform_scrape_task.apply_async(
                    args=[workspace_id, platform, query],
                    kwargs={"filters": filters, "limit": limit},
                    queue="nowing.lead_scrapers",
                )
                dispatched_tasks.append(
                    {
                        "platform": platform,
                        "task_id": str(getattr(task_res, "id", uuid4())),
                        "queue": "nowing.lead_scrapers",
                    }
                )
            except Exception as exc:
                logger.error("Failed to enqueue scrape task for %s: %s", platform, exc)
                dispatched_tasks.append(
                    {
                        "platform": platform,
                        "error": str(exc),
                    }
                )

        return DispatchedScrapeJobResponse(
            job_id=job_id,
            workspace_id=workspace_id,
            status="dispatched",
            dispatched_tasks=dispatched_tasks,
        )

    async def _plan_subtasks_with_llm(self, prompt: str) -> list[dict[str, Any]]:
        """Optional LLM-based subtask decomposition helper."""
        return []

    async def decompose_query(self, prompt: str) -> list[SubTaskPlan]:
        """Decompose user prompt into structured sub-tasks across scraper categories."""
        try:
            llm_plans = await self._plan_subtasks_with_llm(prompt)
            if llm_plans:
                return [
                    SubTaskPlan(
                        source_name=p.get("source_name", "general"),
                        query=p.get("query", prompt),
                        limit=p.get("limit", 50),
                        category=LeadSourceCategory(p.get("category", "GENERAL")),
                    )
                    for p in llm_plans
                ]
        except Exception as exc:
            logger.debug("LLM subtask decomposition fallback: %s", exc)

        # Heuristic intent matching fallback
        adapters = self.registry.resolve_adapters_for_intent(prompt)
        return [
            SubTaskPlan(
                source_name=a.source_name,
                query=prompt,
                limit=50,
                category=a.category,
            )
            for a in adapters
        ]

    async def execute_multi_source_lead_gen(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        table_id: str | None = None,
        concurrency_limit: int = 5,
        adapter_timeout_seconds: float = 12.0,
    ) -> LeadGenOrchestratorResult:
        """
        Execute multi-source scraper searches concurrently with semaphore bounding,
        per-adapter timeout isolation, graceful degradation, and entity deduplication.
        """
        adapters = self.registry.resolve_adapters_for_intent(query)
        if not adapters:
            return LeadGenOrchestratorResult(
                status="degraded",
                total_discovered=0,
                total_deduplicated=0,
                leads=[],
                degraded_sources=["no_adapters_available"],
                table_id=table_id,
            )

        sem = asyncio.Semaphore(concurrency_limit)
        degraded_sources: list[str] = []
        all_normalized_leads: list[NormalizedLead] = []

        async def _run_single_adapter(
            adapter: LeadSourceAdapter,
        ) -> tuple[list[NormalizedLead], str | None]:
            async with sem:
                try:
                    raw_records = await asyncio.wait_for(
                        adapter.search_leads(
                            workspace_id=workspace_id,
                            query=query,
                            filters=filters,
                            limit=50,
                        ),
                        timeout=adapter_timeout_seconds,
                    )
                    is_degraded = (
                        getattr(adapter, "last_execution_status", "ok") == "degraded"
                    )
                    degraded_name = adapter.source_name if is_degraded else None

                    normalized: list[NormalizedLead] = []
                    for record in raw_records:
                        try:
                            norm = adapter.normalize_lead(record)
                            normalized.append(norm)
                        except Exception as norm_err:
                            logger.warning(
                                "Failed to normalize lead from %s: %s",
                                adapter.source_name,
                                norm_err,
                            )
                    return normalized, degraded_name
                except TimeoutError:
                    logger.warning(
                        "Adapter %s timed out after %.1fs",
                        adapter.source_name,
                        adapter_timeout_seconds,
                    )
                    return [], adapter.source_name
                except Exception as exc:
                    logger.error(
                        "Adapter %s failed with error: %s",
                        adapter.source_name,
                        exc,
                    )
                    return [], adapter.source_name

        tasks = [_run_single_adapter(a) for a in adapters]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in batch_results:
            if isinstance(res, tuple):
                leads_list, degraded_name = res
                all_normalized_leads.extend(leads_list)
                if degraded_name:
                    degraded_sources.append(degraded_name)

        total_discovered = len(all_normalized_leads)

        # In-stream Deduplication
        dedup_result = self.deduplication_service.deduplicate_leads(
            all_normalized_leads
        )

        # In-stream DNC Compliance
        dnc_result = self.deduplication_service.apply_dnc_compliance(
            dedup_result.unified_leads, workspace_id=workspace_id, suppress_dnc=True
        )

        final_leads = dnc_result.compliant_leads

        # Determine overall execution status
        if not final_leads and degraded_sources:
            overall_status = "degraded"
        elif degraded_sources:
            overall_status = "partial"
        else:
            overall_status = "completed"

        return LeadGenOrchestratorResult(
            status=overall_status,
            total_discovered=total_discovered,
            total_deduplicated=len(final_leads),
            leads=final_leads,
            degraded_sources=sorted(set(degraded_sources)),
            table_id=table_id,
            deduplication_summary={
                "raw_count": total_discovered,
                "deduplicated_count": len(final_leads),
                "dnc_suppressed_count": len(dnc_result.dnc_suppressed_leads),
            },
        )

    async def execute_and_persist(
        self,
        session: AsyncSession,
        workspace_id: int,
        query: str,
        table_id: str | None = None,
        user_id: UUID | None = None,
        client_id: str | None = None,
    ) -> LeadGenOrchestratorResult:
        """Execute lead generation and atomically upsert records to PostgreSQL database."""
        from app.db import Lead, VerifiedContact

        # Safely parse table_id to UUID if provided
        table_uuid: UUID | None = None
        if table_id:
            try:
                table_uuid = UUID(str(table_id))
            except (ValueError, TypeError):
                table_uuid = None

        # Execute lead search and in-stream deduplication
        search_result = await self.execute_multi_source_lead_gen(
            workspace_id=workspace_id,
            query=query,
            table_id=table_id,
        )
        unified_leads = search_result.leads

        try:
            for lead in unified_leads:
                company_name = (
                    lead.company_name or lead.title or "Doanh nghiệp tiềm năng"
                )
                domain = lead.canonical_domain

                # Check if Lead entity already exists by domain or company in this workspace
                existing_lead = None
                if domain:
                    stmt = select(Lead).where(
                        Lead.workspace_id == workspace_id,
                        Lead.domain == domain,
                    )
                    existing_lead = (await session.execute(stmt)).scalars().first()

                if not existing_lead and company_name:
                    stmt = select(Lead).where(
                        Lead.workspace_id == workspace_id,
                        Lead.company_name == company_name,
                    )
                    existing_lead = (await session.execute(stmt)).scalars().first()

                lead_row_id: UUID
                if existing_lead:
                    lead_row_id = existing_lead.id
                    if lead.confidence_score:
                        existing_lead.fit_score = max(
                            existing_lead.fit_score or 0.0,
                            lead.confidence_score,
                        )
                    if table_uuid and not existing_lead.table_id:
                        existing_lead.table_id = table_uuid
                else:
                    lead_row_id = uuid4()
                    new_lead = Lead(
                        id=lead_row_id,
                        workspace_id=workspace_id,
                        client_id=client_id,
                        table_id=table_uuid,
                        source=",".join(lead.sources)
                        if lead.sources
                        else lead.source_name,
                        source_url=lead.raw_data.get("url")
                        or lead.raw_data.get("source_url"),
                        company_name=company_name,
                        domain=domain,
                        fit_score=lead.confidence_score,
                        status="new",
                    )
                    session.add(new_lead)

                # Persist discovered contact in VerifiedContact table
                if lead.primary_phone or lead.primary_email or lead.contact_name:
                    contact_stmt = select(VerifiedContact).where(
                        VerifiedContact.workspace_id == workspace_id,
                        VerifiedContact.lead_id == lead_row_id,
                        VerifiedContact.phone == lead.primary_phone,
                    )
                    existing_contact = (
                        (await session.execute(contact_stmt)).scalars().first()
                    )

                    if not existing_contact and (
                        lead.primary_phone or lead.primary_email
                    ):
                        new_contact = VerifiedContact(
                            id=uuid4(),
                            workspace_id=workspace_id,
                            client_id=client_id,
                            lead_id=lead_row_id,
                            name=lead.contact_name or lead.legal_rep,
                            title=lead.title,
                            phone=lead.primary_phone,
                            email=lead.primary_email,
                            confidence=lead.confidence_score / 100.0,
                            source_provider=lead.source_name,
                            verification_status="discovered",
                        )
                        session.add(new_contact)

            await session.flush()

        except Exception as exc:
            logger.error("Failed to persist leads to database: %s", exc)
            await session.rollback()
            return LeadGenOrchestratorResult(
                status="degraded",
                total_discovered=search_result.total_discovered,
                total_deduplicated=0,
                leads=[],
                degraded_sources=[
                    *search_result.degraded_sources,
                    "db_persistence_error",
                ],
                table_id=table_id,
            )

        return search_result
