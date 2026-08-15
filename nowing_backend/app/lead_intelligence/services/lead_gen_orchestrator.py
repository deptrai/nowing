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
    ) -> None:
        self.registry = registry or LeadSourceAdapterRegistry.get_default()
        self.deduplication_service = (
            deduplication_service or EntityDeduplicationService()
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
        ) -> list[NormalizedLead]:
            async with sem:
                retries = 1
                attempt = 0
                while attempt <= retries:
                    attempt += 1
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
                        if (
                            getattr(adapter, "last_execution_status", "ok")
                            == "degraded"
                        ):
                            degraded_sources.append(adapter.source_name)

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
                        return normalized
                    except TimeoutError:
                        logger.warning(
                            "Adapter %s timed out after %.1fs on attempt %d",
                            adapter.source_name,
                            adapter_timeout_seconds,
                            attempt,
                        )
                        if attempt > retries:
                            degraded_sources.append(adapter.source_name)
                            return []
                    except Exception as exc:
                        logger.error(
                            "Adapter %s failed attempt %d: %s",
                            adapter.source_name,
                            attempt,
                            exc,
                        )
                        if attempt > retries:
                            degraded_sources.append(adapter.source_name)
                            return []
                return []

        tasks = [_run_single_adapter(a) for a in adapters]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in batch_results:
            if isinstance(res, list):
                all_normalized_leads.extend(res)

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

    async def _execute_adapter_searches(
        self, workspace_id: int, query: str
    ) -> list[NormalizedLead]:
        """Test stub override for adapter execution."""
        res = await self.execute_multi_source_lead_gen(
            workspace_id=workspace_id, query=query
        )
        return res.leads

    async def execute_and_persist(
        self,
        session: AsyncSession,
        workspace_id: int,
        query: str,
        table_id: str,
        user_id: UUID | None = None,
        client_id: str | None = None,
    ) -> LeadGenOrchestratorResult:
        """Execute lead generation and atomically upsert records to PostgreSQL database."""
        from app.db import Lead

        # Call adapter search routine
        leads = await self._execute_adapter_searches(
            workspace_id=workspace_id, query=query
        )

        # Deduplicate before DB write
        dedup_result = self.deduplication_service.deduplicate_leads(leads)
        unified_leads = dedup_result.unified_leads

        # Atomic upsert in PostgreSQL
        for lead in unified_leads:
            existing_lead = None
            if lead.primary_phone:
                stmt = select(Lead).where(
                    Lead.workspace_id == workspace_id,
                    Lead.phone == lead.primary_phone,
                )
                existing_lead = (await session.execute(stmt)).scalars().first()

            if existing_lead:
                # Update existing row
                if lead.contact_name:
                    existing_lead.contact_name = lead.contact_name
                if lead.title:
                    existing_lead.title = lead.title
                if lead.price:
                    existing_lead.price_estimate = str(lead.price)
                if lead.confidence_score:
                    existing_lead.confidence_score = max(
                        getattr(existing_lead, "confidence_score", 0.0) or 0.0,
                        lead.confidence_score,
                    )
                if table_id:
                    existing_lead.table_id = table_id
            else:
                # Insert new Lead row
                new_row = Lead(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    client_id=client_id,
                    table_id=table_id,
                    source=",".join(lead.sources) if lead.sources else lead.source_name,
                    source_url=lead.raw_data.get("url")
                    or lead.raw_data.get("source_url"),
                    company_name=lead.company_name or "N/A",
                    domain=lead.canonical_domain,
                    phone=lead.primary_phone,
                    author=lead.contact_name,
                    title=lead.title,
                    price_estimate=str(lead.price) if lead.price else None,
                    fit_score=lead.confidence_score,
                    confidence_score=lead.confidence_score,
                    status="new",
                )
                session.add(new_row)

        await session.flush()

        return LeadGenOrchestratorResult(
            status="completed",
            total_discovered=len(leads),
            total_deduplicated=len(unified_leads),
            leads=unified_leads,
            table_id=table_id,
        )
