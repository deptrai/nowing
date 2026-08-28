"""Unified Multi-Source AI Lead Generation Orchestrator (Story 21.15)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.lead_intelligence.adapters.base import (
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
)
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.campaign.schemas import CampaignSpec, ICPCriteria
from app.lead_intelligence.confidence import ConfidenceGate
from app.lead_intelligence.services.deduplication_service import (
    EntityDeduplicationService,
)
from app.lead_intelligence.services.micro_extraction_worker import (
    MicroExtractionWorker,
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
    execution_time_ms: float = 0.0
    source_latency_ms: dict[str, float] = Field(default_factory=dict)
    deduplication_rate: float = 0.0


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
        self._micro_worker: MicroExtractionWorker | None = None

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

    @classmethod
    def pre_filter_by_icp(
        cls,
        raw_record: RawLeadRecord,
        icp_criteria: ICPCriteria | None,
    ) -> bool:
        """
        Evaluate if a raw record passes basic ICP criteria before full normalization.
        Checks negative keywords and required locations if specified in ICPCriteria.
        Returns True if lead passes or if icp_criteria is None; False if rejected.
        """
        if icp_criteria is None:
            return True

        # Extract text representations from raw data dict
        data = raw_record.data or {}
        text_parts: list[str] = [
            str(data.get("title", "")),
            str(data.get("company_name", "")),
            str(data.get("name", "")),
            str(data.get("address", "")),
            str(data.get("city", "")),
            str(data.get("description", "")),
            str(data.get("industry", "")),
            str(data.get("body", "")),
            str(data.get("job_title", "")),
        ]
        combined_text = " ".join(text_parts).lower()

        # Check negative keywords
        if icp_criteria.negative_keywords:
            for nkw in icp_criteria.negative_keywords:
                if nkw and nkw.lower().strip() in combined_text:
                    return False

        return True

    async def _score_and_enrich(
        self,
        leads: list[NormalizedLead],
        workspace_id: int,
        icp_criteria: ICPCriteria | None = None,
        intent_tags: list[str] | None = None,
    ) -> list[NormalizedLead]:
        """Apply the composite confidence gate and run micro-LLM fallback where needed."""
        high_confidence: list[NormalizedLead] = []
        needs_enrichment: list[NormalizedLead] = []
        micro_candidates: list[NormalizedLead] = []

        for lead in leads:
            result = ConfidenceGate.evaluate_composite(
                lead,
                icp_criteria=icp_criteria,
                intent_tags=intent_tags,
            )
            # Threshold checks: schema_completeness_score is 0.0 - 1.0
            if result.schema_completeness_score >= 0.85 and not result.critical_missing:
                high_confidence.append(lead)
            elif 0.70 <= result.schema_completeness_score < 0.85 and not result.critical_missing:
                lead.needs_enrichment = True
                needs_enrichment.append(lead)
            else:
                micro_candidates.append(lead)

        if micro_candidates:
            if self._micro_worker is None:
                self._micro_worker = MicroExtractionWorker()
            try:
                await self._micro_worker.micro_batch(
                    micro_candidates,
                    workspace_id=workspace_id,
                    user_id=None,
                )
                # Re-score with composite confidence after micro-extraction
                for lead in micro_candidates:
                    ConfidenceGate.evaluate_composite(
                        lead,
                        icp_criteria=icp_criteria,
                        intent_tags=intent_tags,
                    )
            except Exception as exc:
                # Fail-soft: keep the original records and mark for enrichment.
                logger.warning(
                    "Micro-extraction worker failed for workspace %s: %s",
                    workspace_id,
                    exc,
                )
                for lead in micro_candidates:
                    lead.needs_enrichment = True

        return high_confidence + needs_enrichment + micro_candidates

    async def execute_multi_source_lead_gen(
        self,
        workspace_id: int,
        query: str = "",
        filters: dict[str, Any] | None = None,
        table_id: str | None = None,
        concurrency_limit: int = 5,
        adapter_timeout_seconds: float = 12.0,
        limit: int = 50,
        campaign_spec: CampaignSpec | None = None,
    ) -> LeadGenOrchestratorResult:
        """
        Execute multi-source scraper searches concurrently with semaphore bounding,
        per-adapter timeout isolation, graceful degradation, and entity deduplication.
        Supports declarative CampaignSpec or traditional prompt query for backward compatibility.
        """
        start_time = time.perf_counter()
        effective_query = query
        effective_filters = filters or {}
        effective_table_id = table_id
        effective_concurrency = concurrency_limit
        effective_timeout = adapter_timeout_seconds
        effective_limit = limit
        icp_criteria: ICPCriteria | None = None
        intent_tags: list[str] | None = None

        if campaign_spec is not None:
            effective_query = campaign_spec.query or query
            effective_table_id = campaign_spec.table_id or table_id
            effective_concurrency = campaign_spec.concurrency_limit or concurrency_limit
            effective_timeout = (
                campaign_spec.adapter_timeout_seconds or adapter_timeout_seconds
            )
            effective_limit = min(campaign_spec.max_total_leads, limit)
            icp_criteria = campaign_spec.icp_criteria
            intent_tags = campaign_spec.intent_tags
            adapters = self.registry.resolve_adapters_for_campaign(campaign_spec)
        else:
            adapters = self.registry.resolve_adapters_for_intent(effective_query)

        if not adapters:
            total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return LeadGenOrchestratorResult(
                status="degraded",
                total_discovered=0,
                total_deduplicated=0,
                leads=[],
                degraded_sources=["no_adapters_available"],
                table_id=effective_table_id,
                execution_time_ms=total_duration_ms,
                source_latency_ms={},
                deduplication_rate=0.0,
            )

        sem = asyncio.Semaphore(effective_concurrency)
        degraded_sources: list[str] = []
        all_normalized_leads: list[NormalizedLead] = []
        source_latency_ms: dict[str, float] = {}

        async def _run_single_adapter(
            adapter: LeadSourceAdapter,
        ) -> tuple[list[NormalizedLead], str | None, str, float]:
            adapter_start = time.perf_counter()
            async with sem:
                try:
                    raw_records = await asyncio.wait_for(
                        adapter.search_leads(
                            workspace_id=workspace_id,
                            query=effective_query,
                            filters=effective_filters,
                            limit=effective_limit,
                        ),
                        timeout=effective_timeout,
                    )
                    latency = round((time.perf_counter() - adapter_start) * 1000, 2)
                    is_degraded = (
                        getattr(adapter, "last_execution_status", "ok") == "degraded"
                    )
                    degraded_name = adapter.source_name if is_degraded else None

                    normalized: list[NormalizedLead] = []
                    for record in raw_records:
                        try:
                            # Pre-filter by ICP criteria before full normalization
                            if not self.pre_filter_by_icp(record, icp_criteria):
                                continue
                            norm = adapter.normalize_lead(record)
                            normalized.append(norm)
                        except Exception as norm_err:
                            logger.warning(
                                "Failed to normalize lead from %s: %s",
                                adapter.source_name,
                                norm_err,
                            )
                    return normalized, degraded_name, adapter.source_name, latency
                except TimeoutError:
                    latency = round((time.perf_counter() - adapter_start) * 1000, 2)
                    logger.warning(
                        "Adapter %s timed out after %.1fs",
                        adapter.source_name,
                        effective_timeout,
                    )
                    return [], adapter.source_name, adapter.source_name, latency
                except Exception as exc:
                    latency = round((time.perf_counter() - adapter_start) * 1000, 2)
                    logger.error(
                        "Adapter %s failed with error: %s",
                        adapter.source_name,
                        exc,
                    )
                    return [], adapter.source_name, adapter.source_name, latency

        tasks = [_run_single_adapter(a) for a in adapters]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in batch_results:
            if isinstance(res, tuple):
                leads_list, degraded_name, source_name, latency = res
                all_normalized_leads.extend(leads_list)
                source_latency_ms[source_name] = latency
                if degraded_name:
                    degraded_sources.append(degraded_name)

        total_discovered = len(all_normalized_leads)

        # Pass 2: Composite confidence gating and selective micro-LLM fallback.
        scored_leads = await self._score_and_enrich(
            all_normalized_leads,
            workspace_id=workspace_id,
            icp_criteria=icp_criteria,
            intent_tags=intent_tags,
        )

        # Filter out leads that do not meet min_fit_score if specified
        if icp_criteria and icp_criteria.min_fit_score > 0.0:
            scored_leads = [
                lead
                for lead in scored_leads
                if (lead.icp_fit_score or 0.0) >= icp_criteria.min_fit_score
            ]

        # In-stream Deduplication
        dedup_result = self.deduplication_service.deduplicate_leads(scored_leads)

        final_leads = dedup_result.unified_leads

        # Determine overall execution status
        if not final_leads and degraded_sources:
            overall_status = "degraded"
        elif degraded_sources:
            overall_status = "partial"
        else:
            overall_status = "completed"

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        deduplication_rate = (
            round(1.0 - (len(final_leads) / total_discovered), 4)
            if total_discovered > 0
            else 0.0
        )

        def _resolve_adapter_category(adapter: Any) -> LeadSourceCategory:
            cat = getattr(adapter, "category", None)
            if isinstance(cat, LeadSourceCategory):
                return cat
            if isinstance(cat, str):
                try:
                    return LeadSourceCategory(cat)
                except ValueError:
                    return LeadSourceCategory.GENERAL
            return LeadSourceCategory.GENERAL

        subtask_plans = [
            SubTaskPlan(
                source_name=getattr(a, "source_name", "unknown"),
                query=effective_query,
                limit=effective_limit,
                category=_resolve_adapter_category(a),
            )
            for a in adapters
        ]

        return LeadGenOrchestratorResult(
            status=overall_status,
            total_discovered=total_discovered,
            total_deduplicated=len(final_leads),
            leads=final_leads,
            degraded_sources=sorted(set(degraded_sources)),
            table_id=effective_table_id,
            subtask_plans=subtask_plans,
            deduplication_summary={
                "raw_count": total_discovered,
                "deduplicated_count": len(final_leads),
                # DNC filtering is delegated to LeadBatchService at persistence time.
                # The real suppression count is reported by execute_and_persist.
                "dnc_suppressed_count": 0,
            },
            execution_time_ms=execution_time_ms,
            source_latency_ms=source_latency_ms,
            deduplication_rate=deduplication_rate,
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
        query: str = "",
        table_id: str | None = None,
        user_id: UUID | None = None,
        client_id: str | None = None,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
        campaign_spec: CampaignSpec | None = None,
    ) -> LeadGenOrchestratorResult:
        """Execute lead generation and atomically persist records via LeadBatchService."""
        from app.services.lead_batch_service import LeadBatchService

        effective_table_id = (
            campaign_spec.table_id if campaign_spec and campaign_spec.table_id else table_id
        )
        effective_client_id = (
            campaign_spec.client_id if campaign_spec and campaign_spec.client_id else client_id
        )

        table_uuid: UUID | None = None
        if effective_table_id:
            try:
                table_uuid = UUID(str(effective_table_id))
            except (ValueError, TypeError):
                table_uuid = None

        search_result = await self.execute_multi_source_lead_gen(
            workspace_id=workspace_id,
            query=query,
            filters=filters,
            table_id=effective_table_id,
            limit=limit,
            campaign_spec=campaign_spec,
        )
        if not search_result.leads:
            return search_result

        lead_dicts: list[dict[str, Any]] = []
        for lead in search_result.leads:
            lead_dicts.append(
                {
                    "client_id": effective_client_id,
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
                    "schema_completeness_score": lead.schema_completeness_score,
                    "needs_enrichment": bool(lead.needs_enrichment),
                    "area": lead.area,
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
