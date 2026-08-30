"""DSH mission executors."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from urllib.parse import urlparse

from app.lead_intelligence.dnc.normalizer import normalize_domain
from app.services.dsh_telegram_checkpoint_service import DshTelegramCheckpointService
from app.services.lead_batch_service import generate_lead_hmac
from app.tasks.dsh_worker.helpers import _checkpoint_update
from app.tasks.dsh_worker.rest_client import DshRestClient

logger = logging.getLogger(__name__)


class DeepLeadResearchExecutor:
    """Default deterministic sequential executor for deep-lead-research missions."""

    def __init__(self, rest_client: DshRestClient) -> None:
        self.rest_client = rest_client

    @staticmethod
    def _extract_domain(url: str | None) -> str | None:
        if not url:
            return None
        try:
            parsed = urlparse(url)
            return parsed.netloc if parsed.netloc else None
        except Exception:
            return None

    async def _patch_checkpoint(
        self,
        mission_id: uuid.UUID,
        checkpoint: dict[str, Any],
        phase: str,
        progress_percent: int,
        current_subtask_id: str | None = None,
        status: str | None = None,
        error: dict[str, Any] | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict[str, Any]:
        update = _checkpoint_update(
            checkpoint=checkpoint,
            phase=phase,
            progress_percent=progress_percent,
            current_subtask_id=current_subtask_id,
            status=status,
            error=error,
            started_at=started_at,
            completed_at=completed_at,
        )
        response = await self.rest_client.patch_checkpoint(mission_id, update)
        # Merge the server's checkpoint back so the next patch does not fail on
        # a stale version. The checkpoint dict is mutated in place so callers
        # that hold references to it see the updated subtasks/sources/leads.
        response_checkpoint = response.get("checkpoint") if isinstance(response, dict) else None
        if response_checkpoint:
            checkpoint.clear()
            checkpoint.update(response_checkpoint)
        return response

    def _mission_id(self, mission: dict[str, Any] | Any) -> uuid.UUID:
        raw = mission["id"] if isinstance(mission, dict) else mission.id
        return uuid.UUID(raw) if isinstance(raw, str) else raw

    def _mission_workspace_id(self, mission: dict[str, Any] | Any) -> int:
        return (
            mission["workspace_id"]
            if isinstance(mission, dict)
            else mission.workspace_id
        )

    def _mission_payload(self, mission: dict[str, Any] | Any) -> dict[str, Any]:
        payload = mission["payload"] if isinstance(mission, dict) else mission.payload
        return payload or {}

    def _mission_checkpoint(self, mission: dict[str, Any] | Any) -> dict[str, Any]:
        checkpoint = (
            mission["checkpoint"] if isinstance(mission, dict) else mission.checkpoint
        )
        if not checkpoint:
            checkpoint = {"version": 1, "phase": "crawl", "subtasks": []}
        return checkpoint

    async def run(self, mission: dict[str, Any] | Any) -> None:
        """Run the four phases sequentially, updating checkpoint after each."""
        mission_id = self._mission_id(mission)
        workspace_id = self._mission_workspace_id(mission)
        payload = self._mission_payload(mission)
        query = payload.get("query", "") if isinstance(payload, dict) else ""

        checkpoint = self._mission_checkpoint(mission)
        subtasks = checkpoint.get("subtasks", [])

        # Phase: crawl -> reasoning -> extraction -> ingestion
        # 1. Crawl (ChainLens research)
        if not any(
            s.get("id") == "crawl" and s.get("status") == "success" for s in subtasks
        ):
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="crawl",
                progress_percent=10,
                current_subtask_id="crawl",
                status="running",
            )
            try:
                research_output = await self.rest_client.chainlens_research(
                    workspace_id, query
                )
                sources = research_output.get("sources", [])
                subtasks.append(
                    {
                        "id": "crawl",
                        "status": "success",
                        "run_id": research_output.get("run_id"),
                        "sources_count": len(sources),
                    }
                )
                checkpoint["subtasks"] = subtasks
                checkpoint["sources"] = sources
                await self._patch_checkpoint(
                    mission_id,
                    checkpoint,
                    phase="reasoning",
                    progress_percent=35,
                    current_subtask_id="reasoning",
                )
            except Exception as exc:
                subtasks.append(
                    {
                        "id": "crawl",
                        "status": "failed",
                        "error": str(exc),
                    }
                )
                checkpoint["subtasks"] = subtasks
                await self._patch_checkpoint(
                    mission_id,
                    checkpoint,
                    phase="crawl",
                    progress_percent=0,
                    current_subtask_id="crawl",
                    status="error",
                    error={"phase": "crawl", "message": str(exc)},
                )
                raise

        # 2. Reasoning
        if not any(
            s.get("id") == "reasoning" and s.get("status") == "success"
            for s in subtasks
        ):
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="reasoning",
                progress_percent=45,
                current_subtask_id="reasoning",
            )
            # Deterministic reasoning can be a no-op for 26.2.
            subtasks.append({"id": "reasoning", "status": "success"})
            checkpoint["subtasks"] = subtasks
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="extraction",
                progress_percent=60,
                current_subtask_id="extraction",
            )

        # 3. Extraction
        if not any(
            s.get("id") == "extraction" and s.get("status") == "success"
            for s in subtasks
        ):
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="extraction",
                progress_percent=70,
                current_subtask_id="extraction",
            )
            sources = checkpoint.get("sources", [])
            extracted_leads = [
                self._source_to_lead(source, workspace_id) for source in sources
            ]
            # Filter degenerate leads that would fail the batch-ingest validator.
            extracted_leads = [lead for lead in extracted_leads if lead is not None]
            subtasks.append(
                {
                    "id": "extraction",
                    "status": "success",
                    "leads_count": len(extracted_leads),
                }
            )
            checkpoint["subtasks"] = subtasks
            checkpoint["leads"] = extracted_leads
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="ingestion",
                progress_percent=85,
                current_subtask_id="ingestion",
            )

        # 4. Ingestion
        if not any(
            s.get("id") == "ingestion" and s.get("status") == "success"
            for s in subtasks
        ):
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="ingestion",
                progress_percent=90,
                current_subtask_id="ingestion",
            )
            leads = checkpoint.get("leads", [])
            if leads:
                try:
                    ingest_res = await self.rest_client.batch_ingest_leads(
                        workspace_id, leads
                    )
                    try:
                        # Trigger Telegram notification for top high-fit lead if any (Story 26.6)
                        checkpoint_svc = DshTelegramCheckpointService()
                        high_fit_candidate = checkpoint_svc.select_high_fit_lead(leads)
                        if high_fit_candidate:
                            lead_id = None
                            if isinstance(high_fit_candidate, dict):
                                cand_company = (
                                    high_fit_candidate.get("company_name")
                                    or high_fit_candidate.get("title")
                                    or "Doanh nghiệp"
                                )
                                cand_domain = normalize_domain(
                                    high_fit_candidate.get("domain")
                                )
                                cand_hmac = high_fit_candidate.get(
                                    "value_hmac"
                                ) or generate_lead_hmac(
                                    workspace_id, cand_company, cand_domain
                                )
                                mapping = ingest_res.get("lead_id_mapping") or {}
                                lead_id = mapping.get(cand_hmac)
                                if not lead_id:
                                    logger.info(
                                        "High-fit lead mapping missing for mission %s; skipping notification",
                                        mission_id,
                                    )
                            elif hasattr(high_fit_candidate, "id"):
                                lead_id = high_fit_candidate.id

                            if lead_id:
                                try:
                                    await self.rest_client.notify_high_fit_lead(
                                        mission_id, lead_id
                                    )
                                except Exception as notify_exc:
                                    logger.warning(
                                        "Failed to notify high fit lead for mission %s: %s",
                                        mission_id,
                                        notify_exc,
                                    )
                    except Exception as notify_exc:
                        logger.warning(
                            "Failed to process high fit lead notification for mission %s: %s",
                            mission_id,
                            notify_exc,
                        )
                except Exception as exc:
                    subtasks.append(
                        {
                            "id": "ingestion",
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
                    checkpoint["subtasks"] = subtasks
                    await self._patch_checkpoint(
                        mission_id,
                        checkpoint,
                        phase="ingestion",
                        progress_percent=85,
                        current_subtask_id="ingestion",
                        status="error",
                        error={"phase": "ingestion", "message": str(exc)},
                    )
                    raise
            subtasks.append({"id": "ingestion", "status": "success"})
            checkpoint["subtasks"] = subtasks
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="terminal",
                progress_percent=100,
                current_subtask_id=None,
                status="success",
            )

    def _source_to_lead(
        self, source: dict[str, Any], workspace_id: int
    ) -> dict[str, Any] | None:
        """Convert a ChainLens source into a LeadItem-shaped dict.

        Returns None for degenerate leads that would fail batch validation.
        """
        url = source.get("url")
        domain = source.get("domain") or self._extract_domain(url)
        lead = {
            "source": "dsh_research",
            "source_url": url,
            "client_id": source.get("client_id"),
            "company_name": source.get("company_name"),
            "domain": domain,
            "phone": source.get("phone"),
            "email": source.get("email"),
            "title": source.get("title"),
            "industry": source.get("industry"),
            "location": source.get("location"),
            "fit_score": source.get("fit_score", 0.0),
            "intent_score": source.get("intent_score", 0.0),
            "composite_score": source.get("composite_score"),
        }
        if not any([lead["phone"], lead["email"], lead["domain"]]):
            logger.warning("Skipping degenerate lead from source %s", url)
            return None
        return lead
