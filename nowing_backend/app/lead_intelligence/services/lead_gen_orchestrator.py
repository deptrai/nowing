"""Unified Multi-Source AI Lead Generation Orchestrator (Story 21.15)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
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
        limit: int = 50,
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
                            limit=limit,
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

        final_leads = dedup_result.unified_leads

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
                # DNC filtering is delegated to LeadBatchService at persistence time.
                # The real suppression count is reported by execute_and_persist.
                "dnc_suppressed_count": 0,
            },
        )

    async def _assign_new_leads(
        self,
        session: AsyncSession,
        workspace_id: int,
        new_lead_ids: list[UUID],
    ) -> None:
        """Trigger round-robin assignment for newly persisted leads."""
        if not new_lead_ids:
            return

        from app.services.lead_assignment_service import LeadAssignmentService

        service = LeadAssignmentService(
            session=session,
            redis_client=self.redis,
        )
        try:
            result = await service.assign_leads_batch(
                workspace_id=workspace_id,
                lead_ids=new_lead_ids,
            )
            logger.info(
                "Auto-assigned %s of %s new leads in workspace %s",
                result.total_assigned,
                len(new_lead_ids),
                workspace_id,
            )
        except Exception as exc:
            logger.exception(
                "Failed to auto-assign new leads for workspace %s: %s",
                workspace_id,
                exc,
            )

    async def execute_and_persist(
        self,
        session: AsyncSession,
        workspace_id: int,
        query: str,
        table_id: str | None = None,
        user_id: UUID | None = None,
        client_id: str | None = None,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> LeadGenOrchestratorResult:
        """Execute lead generation and atomically persist records via LeadBatchService."""
        from app.services.lead_batch_service import LeadBatchService

        table_uuid: UUID | None = None
        if table_id:
            try:
                table_uuid = UUID(str(table_id))
            except (ValueError, TypeError):
                table_uuid = None

        search_result = await self.execute_multi_source_lead_gen(
            workspace_id=workspace_id,
            query=query,
            filters=filters,
            table_id=table_id,
            limit=limit,
        )
        if not search_result.leads:
            return search_result

        lead_dicts: list[dict[str, Any]] = []
        for lead in search_result.leads:
            lead_dicts.append(
                {
                    "client_id": client_id,
                    "table_id": table_uuid,
                    "source": ",".join(lead.sources)
                    if lead.sources
                    else lead.source_name,
                    "source_url": (
                        lead.source_url
                        or lead.raw_data.get("url")
                        or lead.raw_data.get("source_url")
                        or lead.raw_data.get("detail_url")
                        or lead.raw_data.get("dossier_url")
                    ),
                    "company_name": lead.company_name or lead.title or "Doanh nghiệp",
                    "domain": lead.canonical_domain,
                    "industry": lead.raw_data.get("industry"),
                    "location": lead.city or lead.address,
                    "fit_score": lead.confidence_score,
                    "phone": lead.primary_phone,
                    "email": lead.primary_email,
                    "tax_id": lead.tax_id,
                    "contact_name": lead.contact_name or lead.legal_rep,
                    "title": lead.title,
                }
            )

        service = LeadBatchService()
        try:
            summary = await service.ingest_batch(session, workspace_id, lead_dicts)
        except Exception as exc:
            logger.error("Failed to persist leads via LeadBatchService: %s", exc)
            return LeadGenOrchestratorResult(
                status="degraded",
                total_discovered=search_result.total_discovered,
                total_deduplicated=0,
                leads=[],
                degraded_sources=[
                    *search_result.degraded_sources,
                    "persistence_error",
                ],
                table_id=table_id,
            )

        # Filter response to only the leads that survived DNC and DB upsert.
        accepted = summary.get("accepted") or [True] * len(search_result.leads)
        search_result.leads = [
            lead for lead, ok in zip(search_result.leads, accepted, strict=True) if ok
        ]
        search_result.total_deduplicated = len(search_result.leads)

        new_lead_ids = summary.get("accepted_lead_ids") or []
        await self._assign_new_leads(session, workspace_id, new_lead_ids)

        # Update the search result with actual persistence counts.
        existing_summary = getattr(search_result, "deduplication_summary", None)
        if not isinstance(existing_summary, dict):
            existing_summary = {}
        search_result.deduplication_summary = {
            **existing_summary,
            "deduplicated_count": len(search_result.leads),
            "dnc_suppressed_count": summary.get("skipped_blacklisted_count", 0),
            "failed_count": summary.get("failed_count", 0),
        }
        return search_result
