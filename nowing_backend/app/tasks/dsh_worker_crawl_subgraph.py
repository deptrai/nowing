"""Wide-research crawl subgraph for DSH missions (Story 26.9a)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.tasks.dsh_worker import DshRestClient

logger = logging.getLogger(__name__)

_DEFAULT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topics": {"type": "array", "items": {"type": "string"}},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "source_type": {"type": "string"},
                },
            },
        },
        "matrix": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "boolean"}},
        },
    },
}


def _checkpoint_update(**kwargs: Any) -> dict[str, Any]:
    """Build a JSON-serialisable checkpoint update with None values omitted.

    Mirrors ``app.tasks.dsh_worker._checkpoint_update`` without importing the
    circular ``dsh_worker`` module at the top level.
    """
    from datetime import datetime

    result: dict[str, Any] = {}
    for k, v in kwargs.items():
        if v is None and k != "current_subtask_id":
            continue
        if k in ("started_at", "completed_at") and isinstance(v, datetime):
            v = v.isoformat()
        result[k] = v
    return result


class WideResearchCrawlSubgraph:
    """Crawl subgraph for ``research_mode=wide`` DSH missions.

    The subgraph is intentionally simple (a single ``ainvoke`` entry point) so
    it can be used directly inside ``LangGraphMissionExecutor._crawl_node`` or
    tested in isolation.
    """

    def __init__(self, rest_client: DshRestClient) -> None:
        self._rest_client = rest_client

    @classmethod
    def build(cls, rest_client: DshRestClient) -> WideResearchCrawlSubgraph:
        """Build a compiled subgraph instance bound to ``rest_client``."""
        return cls(rest_client)

    async def ainvoke(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the wide-research crawl phase.

        The entry point name follows ``CompiledStateGraph.ainvoke`` so the same
        object can be swapped in for a LangGraph graph later.
        """
        _ = config  # reserved for RunnableConfig / graph metadata
        payload = state.get("payload") or {}
        extras = payload.get("extras", {}) if isinstance(payload, dict) else {}
        checkpoint = dict(state.get("checkpoint") or {})
        subtasks = list(
            state.get("subtasks") or checkpoint.get("subtasks") or []
        )

        # AC-7: resumption
        existing_matrix = checkpoint.get("wide_research_matrix")
        if existing_matrix and any(
            s.get("id") == "crawl" and s.get("status") == "success" for s in subtasks
        ):
            logger.info("Crawl already completed for this mission; rehydrating matrix.")
            return {**state, "checkpoint": _checkpoint_update(**checkpoint), "phase": "reasoning"}

        output = extras.get("output", "table")
        output_schema = extras.get("output_schema") or _DEFAULT_OUTPUT_SCHEMA
        mode = extras.get("mode", "balanced")
        workspace_id = state.get("workspace_id", 0)
        query = state.get("query", "")

        try:
            research_output = await self._rest_client.chainlens_research(
                workspace_id=workspace_id,
                query=query,
                output=output,
                output_schema=output_schema,
                mode=mode,
            )
        except Exception as exc:  # pragma: no cover - only on network faults
            logger.exception("Wide research chainlens call failed: %s", exc)
            subtasks.append(
                {
                    "id": "crawl",
                    "status": "degraded",
                    "error": {"message": str(exc)},
                }
            )
            checkpoint["subtasks"] = subtasks
            checkpoint["degraded"] = True
            checkpoint["degradation_reason"] = "chainlens_unavailable"
            return {
                **state,
                "phase": "reasoning",
                "checkpoint": _checkpoint_update(**checkpoint),
            }

        structured = (
            research_output.get("structured_output")
            if isinstance(research_output, dict)
            else None
        )
        sources = (
            research_output.get("sources", [])
            if isinstance(research_output, dict)
            else []
        )
        if not isinstance(sources, list):
            sources = []
        cost_micros = (
            research_output.get("cost_micros")
            if isinstance(research_output, dict)
            else None
        )
        status = (
            research_output.get("status")
            if isinstance(research_output, dict)
            else "complete"
        )

        wide_matrix = _build_wide_research_matrix(structured, sources, query)

        subtasks = [s for s in subtasks if s.get("id") != "crawl"]
        subtasks.append(
            {
                "id": "crawl",
                "status": "success",
                "sources_count": len(sources),
            }
        )
        checkpoint["subtasks"] = subtasks
        checkpoint["sources"] = sources
        checkpoint["wide_research_matrix"] = wide_matrix
        if cost_micros is not None:
            checkpoint["cost_micros"] = cost_micros

        degraded = status != "complete" or research_output.get("degraded") is True
        if degraded:
            checkpoint["degraded"] = True
            checkpoint["degradation_reason"] = (
                research_output.get("degradation_reason")
                or research_output.get("engine_reason")
                or status
            )

        return {
            **state,
            "phase": "reasoning",
            "subtasks": subtasks,
            "sources": sources,
            "checkpoint": _checkpoint_update(**checkpoint),
        }


def _build_wide_research_matrix(
    structured: dict[str, Any] | None,
    sources: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    """Validate or synthesise the wide-research source matrix."""
    if isinstance(structured, dict):
        if (
            "topics" in structured
            and "sources" in structured
            and "matrix" in structured
        ):
            return structured
        # Some ChainLens outputSchema variants may return rows.
        rows = structured.get("rows")
        if isinstance(rows, list):
            return _rows_to_matrix(rows, sources)

    # Fallback: one topic = the query, all sources True.
    topics = [query]
    normalized_sources = [_normalize_source(s) for s in sources]
    matrix = [[True] for _ in normalized_sources]
    return {
        "topics": topics,
        "sources": normalized_sources,
        "matrix": matrix,
    }


def _rows_to_matrix(
    rows: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Convert a row-based outputSchema result into a topicxsource matrix."""
    topics: list[str] = []
    topic_index: dict[str, int] = {}
    normalized_sources: list[dict[str, Any]] = []
    source_index: dict[str, int] = {}
    for s in sources:
        src = _normalize_source(s)
        url = src["url"]
        source_index[url] = len(normalized_sources)
        normalized_sources.append(src)

    cells: dict[tuple[int, int], Any] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        entity = row.get("entity") or row.get("source_title")
        attribute = row.get("attribute") or row.get("topic") or entity
        value = row.get("value")
        source_url = row.get("source_url") or row.get("url")
        if not entity or not attribute:
            continue
        topic = attribute
        if topic not in topic_index:
            topic_index[topic] = len(topics)
            topics.append(topic)
        topic_i = topic_index[topic]
        src_i = source_index.get(source_url, 0) if source_url else 0
        cells[(src_i, topic_i)] = value if value is not None else True

    matrix: list[list[bool]] = []
    for src_i in range(len(normalized_sources)):
        row: list[bool] = []
        for topic_i in range(len(topics)):
            row.append(cells.get((src_i, topic_i), False) is not False)
        matrix.append(row)

    return {
        "topics": topics,
        "sources": normalized_sources,
        "matrix": matrix,
    }


def _normalize_source(source: dict[str, Any] | Any) -> dict[str, Any]:
    """Reduce a ChainLens source to the fields kept in the wide matrix."""
    if not isinstance(source, dict):
        return {"title": "", "url": "", "source_type": "web"}
    return {
        "title": source.get("title", "") or "",
        "url": source.get("url", "") or source.get("web_url", "") or "",
        "source_type": source.get("source_type", "web") or "web",
    }
