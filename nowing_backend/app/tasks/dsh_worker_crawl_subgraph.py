"""Wide-research crawl subgraph for DSH missions (Story 26.9a)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.tasks.dsh_worker import DshRestClient

logger = logging.getLogger(__name__)

# Allowed fields on a wide-research source row. Extra fields (e.g. raw content,
# emails, phones) are stripped to keep the checkpoint free of PII bloat.
_SOURCE_WHITELIST = frozenset({"title", "url", "source_type", "domain"})

_DEFAULT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Research topics / attributes compared across sources.",
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "source_type": {"type": "string"},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        },
        "matrix": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "boolean"},
            },
        },
    },
    "required": ["topics", "sources", "matrix"],
    "additionalProperties": False,
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


def _is_valid_matrix(matrix: Any) -> bool:
    """Validate the wide-research matrix shape and dimensions.

    Accepts booleans or numeric 0/1 values and normalises them so downstream
    consumers always see a clean boolean matrix.
    """
    if not isinstance(matrix, dict):
        return False
    if not all(k in matrix for k in ("topics", "sources", "matrix")):
        return False
    topics = matrix.get("topics")
    sources = matrix.get("sources")
    grid = matrix.get("matrix")
    if not isinstance(topics, list) or not isinstance(sources, list) or not isinstance(grid, list):
        return False
    n_topics = len(topics)
    n_sources = len(sources)
    if n_topics == 0 or n_sources == 0:
        return False
    if len(grid) != n_sources:
        return False
    for row in grid:
        if not isinstance(row, list) or len(row) != n_topics:
            return False
        for cell in row:
            if not isinstance(cell, (bool, int, float)):
                return False
    for src in sources:
        if not isinstance(src, dict) or not isinstance(src.get("url"), str):
            return False
    return True


class WideResearchCrawlSubgraph:
    """Crawl subgraph for ``research_mode=wide`` DSH missions.

    The subgraph is intentionally a single ``ainvoke`` entry point. Resumption
    and checkpointing are handled at the ``LangGraphMissionExecutor`` level;
    splitting this into LangGraph nodes would add edges without adding real
    resumability because the ChainLens call itself is the only I/O boundary.
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
        if _is_valid_matrix(existing_matrix) and any(
            s.get("id") == "crawl" and s.get("status") == "success" for s in subtasks
        ):
            logger.info("Crawl already completed for this mission; rehydrating matrix.")
            sources = existing_matrix.get("sources", []) if isinstance(existing_matrix, dict) else []
            checkpoint["sources"] = sources
            return {
                **state,
                "subtasks": subtasks,
                "sources": sources,
                "checkpoint": _checkpoint_update(**checkpoint),
                "phase": "reasoning",
            }

        # AC-2: wide research always asks ChainLens for a structured table.
        output = "table"
        output_schema: dict[str, Any] = _DEFAULT_OUTPUT_SCHEMA
        mode = extras.get("mode", "balanced") if isinstance(extras, dict) else "balanced"
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
            subtasks = [s for s in subtasks if s.get("id") != "crawl"]
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
                "subtasks": subtasks,
                "sources": [],
                "checkpoint": _checkpoint_update(**checkpoint),
            }

        if not isinstance(research_output, dict):
            research_output = {}

        structured = research_output.get("structured_output")
        answer = research_output.get("answer", "")
        sources = research_output.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        cost_micros = research_output.get("cost_micros")
        status = research_output.get("status") or "complete"

        wide_matrix = _build_wide_research_matrix(structured, sources, answer, query)

        # The matrix sources are authoritative for downstream extraction.
        matrix_sources = wide_matrix.get("sources", [])
        subtasks = [s for s in subtasks if s.get("id") != "crawl"]
        subtasks.append(
            {
                "id": "crawl",
                "status": "success",
                "sources_count": len(matrix_sources),
            }
        )
        checkpoint["subtasks"] = subtasks
        checkpoint["sources"] = matrix_sources
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
            "sources": matrix_sources,
            "checkpoint": _checkpoint_update(**checkpoint),
        }


def _build_wide_research_matrix(
    structured: dict[str, Any] | None,
    sources: list[dict[str, Any]],
    answer: str,
    query: str,
) -> dict[str, Any]:
    """Validate or synthesise the wide-research source matrix."""
    if isinstance(structured, dict):
        if _is_valid_matrix(structured):
            return _redact_matrix_sources(structured)
        # Some ChainLens outputSchema variants may return rows.
        rows = structured.get("rows")
        if isinstance(rows, list):
            return _rows_to_matrix(rows, sources)

    # Fallback: parse a markdown table from the narrative answer.
    parsed = _parse_markdown_table(answer)
    if parsed is not None:
        return parsed

    # Last-resort fallback: one topic = the query, all sources True.
    topics = [query]
    normalized_sources = [_normalize_source(s) for s in sources]
    matrix = [[True] for _ in normalized_sources]
    return {
        "topics": topics,
        "sources": normalized_sources,
        "matrix": matrix,
    }


def _redact_matrix_sources(matrix: dict[str, Any]) -> dict[str, Any]:
    """Return a matrix with source rows limited to the allowed whitelist."""
    sources = matrix.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    grid = matrix.get("matrix", [])
    if not isinstance(grid, list):
        grid = []
    return {
        "topics": list(matrix.get("topics", [])),
        "sources": [_normalize_source(s) for s in sources],
        "matrix": [[_to_bool(cell, default=False) for cell in row] for row in grid],
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
        if not url:
            continue
        source_index[url] = len(normalized_sources)
        normalized_sources.append(src)

    if not normalized_sources:
        # No sources to build a matrix; return an empty but well-shaped matrix.
        return {"topics": [], "sources": [], "matrix": []}

    cells: dict[tuple[int, int], bool] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        entity = row.get("entity") or row.get("source_title")
        attribute = row.get("attribute") or row.get("topic") or entity
        value = row.get("value")
        source_url = row.get("source_url") or row.get("url")
        if not entity or not attribute:
            continue
        if not isinstance(source_url, str) or source_url not in source_index:
            continue
        topic = attribute
        if topic not in topic_index:
            topic_index[topic] = len(topics)
            topics.append(topic)
        topic_i = topic_index[topic]
        src_i = source_index[source_url]
        cells[(src_i, topic_i)] = _to_bool(value, default=True)

    matrix: list[list[bool]] = []
    for src_i in range(len(normalized_sources)):
        row: list[bool] = []
        for topic_i in range(len(topics)):
            row.append(cells.get((src_i, topic_i), False))
        matrix.append(row)

    return {
        "topics": topics,
        "sources": normalized_sources,
        "matrix": matrix,
    }


def _parse_markdown_table(answer: str) -> dict[str, Any] | None:
    """Best-effort parse of a GFM-style table in the ChainLens answer.

    Expects the first table to have a header row and at least one body row.
    The first column is treated as the source title; all remaining columns are
    topics. A cell is considered True if it contains a non-empty, non-'false'
    value.
    """
    if not isinstance(answer, str) or "|" not in answer:
        return None

    lines = [ln.strip() for ln in answer.splitlines() if "|" in ln]
    if len(lines) < 2:
        return None

    def _split_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.split("|")]

    # Skip the header separator (all dashes).
    body_lines: list[str] = []
    header_parsed = False
    header: list[str] = []
    for line in lines:
        cells = _split_row(line)
        cells = [c for c in cells if c or c == ""]
        if not cells:
            continue
        if all(_is_separator_cell(c) for c in cells):
            continue
        if not header_parsed:
            header = cells
            header_parsed = True
            continue
        body_lines.append(line)

    if not header or len(body_lines) < 1:
        return None

    # First column is the source label; remaining columns are topics.
    topics = [h for h in header[1:] if h]
    if not topics:
        return None

    sources: list[dict[str, Any]] = []
    matrix: list[list[bool]] = []
    for line in body_lines:
        cells = _split_row(line)
        if len(cells) < 2:
            continue
        title = cells[0]
        if not title:
            continue
        url = _extract_url(title) or ""
        sources.append({"title": title, "url": url, "source_type": "web"})
        row: list[bool] = []
        for cell in cells[1 : 1 + len(topics)]:
            row.append(_to_bool(cell, default=True))
        # Pad if row is shorter than topics.
        while len(row) < len(topics):
            row.append(False)
        matrix.append(row[: len(topics)])

    if not sources:
        return None
    return {"topics": topics, "sources": sources, "matrix": matrix}


def _is_separator_cell(cell: str) -> bool:
    return bool(cell) and all(c in "-: " for c in cell)


def _extract_url(text: str) -> str | None:
    """Return the first URL in ``text`` if any."""
    if not isinstance(text, str):
        return None
    for token in text.split():
        if token.startswith("http://") or token.startswith("https://"):
            return token.rstrip(")]}>,.;!")
    return None


def _to_bool(value: Any, default: bool = False) -> bool:
    """Coerce a ChainLens cell value to bool without misclassifying ``0``."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "0", "no", "n", "f"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _normalize_source(source: dict[str, Any] | Any) -> dict[str, Any]:
    """Reduce a ChainLens source to the fields kept in the wide matrix."""
    if not isinstance(source, dict):
        return {"title": "", "url": "", "source_type": "web"}
    redacted = {
        k: v for k, v in source.items() if k in _SOURCE_WHITELIST and v is not None
    }
    redacted.setdefault("title", "")
    redacted.setdefault("url", source.get("web_url", ""))
    redacted.setdefault("source_type", "web")
    # Coerce to string so downstream keys stay comparable.
    for key in ("title", "url", "source_type"):
        if key in redacted and not isinstance(redacted[key], str):
            redacted[key] = str(redacted[key]) or ""
    return {
        "title": redacted.get("title", "") or "",
        "url": redacted.get("url", "") or "",
        "source_type": redacted.get("source_type", "web") or "web",
    }
