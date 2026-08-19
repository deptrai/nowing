"""LangGraph-based executor for DSH missions.

This is an experimental executor behind the ``DSH_EXECUTOR_ENGINE`` feature flag.
It re-implements the ``deep_lead_research`` pipeline as a LangGraph ``StateGraph``
while keeping the Redis Stream consumer, REST client, and checkpoint persistence
unchanged.

Design notes:
- No LangGraph checkpointer is used. The worker relies on the existing
  ``dsh_missions`` checkpoint and on idempotent nodes that skip already-completed
  subtasks when a mission is reclaimed after a crash.
- The graph state does NOT contain the REST client. We pass it through
  ``configurable`` so the state remains serialisable if we later enable a
  LangGraph checkpointer.
- PII (phone/email in leads) is stored in the checkpoint JSONB the same way
  the legacy executor does. The checkpoint column is private and not published
  to Zero, consistent with AD-108.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict
from urllib.parse import urlparse
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig

if TYPE_CHECKING:
    from app.tasks.dsh_worker import DshRestClient

logger = logging.getLogger(__name__)


class _Subtask(TypedDict, total=False):
    id: str
    status: str
    run_id: str | None
    sources_count: int | None
    leads_count: int | None
    error: dict[str, Any] | None


class MissionState(TypedDict, total=False):
    """In-memory state for the LangGraph mission graph."""

    mission_id: str
    workspace_id: int
    query: str
    payload: dict[str, Any]
    checkpoint: dict[str, Any]
    subtasks: list[_Subtask]
    sources: list[dict[str, Any]]
    leads: list[dict[str, Any]]
    progress_percent: int
    phase: str
    current_subtask_id: str | None
    status: str
    error: dict[str, Any] | None
    completed_at: str | None


class LangGraphMissionExecutor:
    """LangGraph-backed executor for ``deep_lead_research`` missions."""

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

    @staticmethod
    def _subtask_success(state: MissionState, subtask_id: str) -> bool:
        return any(
            s.get("id") == subtask_id and s.get("status") == "success"
            for s in state.get("subtasks", [])
        )

    def _source_to_lead(
        self, source: dict[str, Any], workspace_id: int
    ) -> dict[str, Any] | None:
        """Convert a ChainLens source into a LeadItem-shaped dict."""
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

    async def _patch_checkpoint(
        self,
        state: MissionState,
        **update: Any,
    ) -> MissionState:
        """Persist a checkpoint update and merge the server's response back."""
        from app.tasks.dsh_worker import _checkpoint_update as build_update

        mission_id = state["mission_id"]
        current_checkpoint = update.get("checkpoint") or state.get("checkpoint") or {}

        # Merge the scalar state fields into the checkpoint JSONB so that crash
        # resumption has an authoritative view of the last persisted phase,
        # progress, and current subtask id.
        for key in ("phase", "progress_percent", "current_subtask_id", "status", "error"):
            value = update.get(key) if key in update else state.get(key)
            if value is not None or key == "current_subtask_id":
                current_checkpoint[key] = value

        payload = build_update(
            checkpoint=current_checkpoint,
            phase=update.get("phase", state.get("phase")),
            progress_percent=update.get("progress_percent", state.get("progress_percent")),
            current_subtask_id=update.get(
                "current_subtask_id", state.get("current_subtask_id")
            ),
            status=update.get("status", state.get("status")),
            error=update.get("error", state.get("error")),
            completed_at=update.get("completed_at", state.get("completed_at")),
        )

        response = await self.rest_client.patch_checkpoint(
            UUID(str(mission_id)), payload
        )

        if isinstance(response, dict) and response.get("checkpoint"):
            checkpoint = response["checkpoint"]
        else:
            checkpoint = current_checkpoint



        return {
            **state,
            **{k: v for k, v in payload.items() if k != "checkpoint"},
            "checkpoint": checkpoint,
        }

    async def _crawl_node(
        self, state: MissionState, config: RunnableConfig
    ) -> MissionState:
        if self._subtask_success(state, "crawl"):
            return state

        rest_client: DshRestClient = config["configurable"]["rest_client"]
        workspace_id = state["workspace_id"]
        query = state["query"]

        state = await self._patch_checkpoint(
            state,
            phase="crawl",
            progress_percent=10,
            current_subtask_id="crawl",
            status="running",
        )

        try:
            research_output = await rest_client.chainlens_research(workspace_id, query)
            sources = research_output.get("sources", [])
            subtasks = list(state.get("subtasks", []))
            subtasks.append(
                {
                    "id": "crawl",
                    "status": "success",
                    "run_id": research_output.get("run_id"),
                    "sources_count": len(sources),
                }
            )
            checkpoint = dict(state.get("checkpoint") or {})
            checkpoint["subtasks"] = subtasks
            checkpoint["sources"] = sources

            return await self._patch_checkpoint(
                {**state, "subtasks": subtasks, "sources": sources, "checkpoint": checkpoint},
                checkpoint=checkpoint,
                phase="reasoning",
                progress_percent=35,
                current_subtask_id="reasoning",
            )
        except Exception as exc:
            subtasks = list(state.get("subtasks", []))
            subtasks.append({"id": "crawl", "status": "failed", "error": str(exc)})
            checkpoint = dict(state.get("checkpoint") or {})
            checkpoint["subtasks"] = subtasks
            state = await self._patch_checkpoint(
                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
                checkpoint=checkpoint,
                phase="crawl",
                progress_percent=0,
                current_subtask_id="crawl",
                status="error",
                error={"phase": "crawl", "message": str(exc)},
            )
            raise

    async def _reasoning_node(
        self, state: MissionState, config: RunnableConfig
    ) -> MissionState:
        _ = config
        if self._subtask_success(state, "reasoning"):
            return state

        subtasks = list(state.get("subtasks", []))
        subtasks.append({"id": "reasoning", "status": "success"})
        checkpoint = dict(state.get("checkpoint") or {})
        checkpoint["subtasks"] = subtasks

        return await self._patch_checkpoint(
            {**state, "subtasks": subtasks, "checkpoint": checkpoint},
            checkpoint=checkpoint,
            phase="extraction",
            progress_percent=60,
            current_subtask_id="extraction",
        )

    async def _extraction_node(
        self, state: MissionState, config: RunnableConfig
    ) -> MissionState:
        _ = config
        if self._subtask_success(state, "extraction"):
            return state

        state = await self._patch_checkpoint(
            state,
            phase="extraction",
            progress_percent=70,
            current_subtask_id="extraction",
        )

        sources = state.get("sources", [])
        workspace_id = state["workspace_id"]
        extracted_leads = [
            self._source_to_lead(source, workspace_id) for source in sources
        ]
        extracted_leads = [lead for lead in extracted_leads if lead is not None]

        subtasks = list(state.get("subtasks", []))
        subtasks.append(
            {"id": "extraction", "status": "success", "leads_count": len(extracted_leads)}
        )
        checkpoint = dict(state.get("checkpoint") or {})
        checkpoint["subtasks"] = subtasks
        checkpoint["leads"] = extracted_leads

        return await self._patch_checkpoint(
            {
                **state,
                "subtasks": subtasks,
                "leads": extracted_leads,
                "checkpoint": checkpoint,
            },
            checkpoint=checkpoint,
            phase="ingestion",
            progress_percent=85,
            current_subtask_id="ingestion",
        )

    async def _ingestion_node(
        self, state: MissionState, config: RunnableConfig
    ) -> MissionState:
        if self._subtask_success(state, "ingestion"):
            return state

        rest_client: DshRestClient = config["configurable"]["rest_client"]
        workspace_id = state["workspace_id"]

        state = await self._patch_checkpoint(
            state,
            phase="ingestion",
            progress_percent=90,
            current_subtask_id="ingestion",
        )

        leads = state.get("leads", [])
        if not leads:
            subtasks = list(state.get("subtasks", []))
            subtasks.append({"id": "ingestion", "status": "success"})
            checkpoint = dict(state.get("checkpoint") or {})
            checkpoint["subtasks"] = subtasks
            return await self._patch_checkpoint(
                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
                checkpoint=checkpoint,
                phase="terminal",
                progress_percent=100,
                current_subtask_id=None,
                status="success",
                completed_at=datetime.now(UTC).isoformat(),
            )

        try:
            ingest_res = await rest_client.batch_ingest_leads(workspace_id, leads)
            await self._maybe_notify_high_fit(state, ingest_res)
        except Exception as exc:
            subtasks = list(state.get("subtasks", []))
            subtasks.append({"id": "ingestion", "status": "failed", "error": str(exc)})
            checkpoint = dict(state.get("checkpoint") or {})
            checkpoint["subtasks"] = subtasks
            state = await self._patch_checkpoint(
                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
                checkpoint=checkpoint,
                phase="ingestion",
                progress_percent=85,
                current_subtask_id="ingestion",
                status="error",
                error={"phase": "ingestion", "message": str(exc)},
            )
            raise

        subtasks = list(state.get("subtasks", []))
        subtasks.append({"id": "ingestion", "status": "success"})
        checkpoint = dict(state.get("checkpoint") or {})
        checkpoint["subtasks"] = subtasks

        return await self._patch_checkpoint(
            {**state, "subtasks": subtasks, "checkpoint": checkpoint},
            checkpoint=checkpoint,
            phase="terminal",
            progress_percent=100,
            current_subtask_id=None,
            status="success",
            completed_at=datetime.now(UTC).isoformat(),
        )

    async def _maybe_notify_high_fit(
        self, state: MissionState, ingest_res: dict[str, Any]
    ) -> None:
        """Mirror the legacy high-fit lead notification logic."""
        mission_id = UUID(str(state["mission_id"]))
        workspace_id = state["workspace_id"]
        leads = state.get("leads", [])
        try:
            from app.lead_intelligence.dnc.normalizer import normalize_domain
            from app.services.dsh_telegram_checkpoint_service import (
                DshTelegramCheckpointService,
            )
            from app.services.lead_batch_service import generate_lead_hmac

            checkpoint_svc = DshTelegramCheckpointService()
            high_fit_candidate = checkpoint_svc.select_high_fit_lead(leads)
            if not high_fit_candidate:
                return

            lead_id = None
            if isinstance(high_fit_candidate, dict):
                cand_company = (
                    high_fit_candidate.get("company_name")
                    or high_fit_candidate.get("title")
                    or "Doanh nghiệp"
                )
                cand_domain = normalize_domain(high_fit_candidate.get("domain"))
                cand_hmac = high_fit_candidate.get("value_hmac") or generate_lead_hmac(
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
                await self.rest_client.notify_high_fit_lead(mission_id, lead_id)
        except Exception as notify_exc:
            logger.warning(
                "Failed to process high fit lead notification for mission %s: %s",
                mission_id,
                notify_exc,
            )

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(MissionState)
        graph.add_node("crawl", self._crawl_node)
        graph.add_node("reasoning", self._reasoning_node)
        graph.add_node("extraction", self._extraction_node)
        graph.add_node("ingestion", self._ingestion_node)

        graph.add_edge(START, "crawl")
        graph.add_edge("crawl", "reasoning")
        graph.add_edge("reasoning", "extraction")
        graph.add_edge("extraction", "ingestion")
        graph.add_edge("ingestion", END)

        return graph

    async def run(self, mission: dict[str, Any] | Any) -> None:
        """Run the mission through the LangGraph state graph."""
        if isinstance(mission, dict):
            mission_id = str(mission["id"])
            workspace_id = mission["workspace_id"]
            payload = mission.get("payload") or {}
            checkpoint = mission.get("checkpoint") or {}
        else:
            mission_id = str(mission.id)
            workspace_id = mission.workspace_id
            payload = mission.payload or {}
            checkpoint = mission.checkpoint or {}

        # Re-fetch the mission from the sidecar's view. This is important when the
        # worker has already bumped the checkpoint (e.g. setting status=running)
        # before invoking the executor, because the ``DshMissionService``
        # increments ``checkpoint.version`` on every write and rejects stale
        # checkpoints.
        refreshed = await self.rest_client.get_mission(UUID(mission_id))
        if refreshed:
            workspace_id = refreshed.get("workspace_id", workspace_id)
            payload = refreshed.get("payload") or payload
            checkpoint = refreshed.get("checkpoint") or checkpoint

        query = payload.get("query", "") if isinstance(payload, dict) else ""
        subtasks = checkpoint.get("subtasks", [])
        if not subtasks:
            subtasks = []
        sources = checkpoint.get("sources", [])
        leads = checkpoint.get("leads", [])

        initial_state: MissionState = {
            "mission_id": mission_id,
            "workspace_id": workspace_id,
            "query": query,
            "payload": payload,
            "checkpoint": checkpoint,
            "subtasks": subtasks,
            "sources": sources,
            "leads": leads,
            "progress_percent": checkpoint.get("progress_percent", 0),
            "phase": checkpoint.get("phase", "crawl"),
            "current_subtask_id": checkpoint.get("current_subtask_id"),
            "status": "running",
        }

        graph = self._build_graph().compile()
        config: RunnableConfig = {"configurable": {"rest_client": self.rest_client}}
        await graph.ainvoke(initial_state, config=config)
