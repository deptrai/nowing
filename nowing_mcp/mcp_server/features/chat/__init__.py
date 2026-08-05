"""Chat tool: stream a turn over ``POST /new_chat`` SSE and return the answer.

Buffers the whole SSE stream (Hướng A) so the model gets one complete answer,
not a firehose of raw events. Optionally creates a thread first when no
``chat_id`` is supplied, and threads ``mode`` through to the backend
(``speed|balanced|quality|auto``).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.errors import ThreadBusyError, ToolError
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.sse import SseEvent
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import WRITE

logger = logging.getLogger(__name__)

ChatMode = Literal["speed", "balanced", "quality", "auto"]

_MAX_BUSY_RETRIES = 4
_BUSY_CAP_SECONDS = 30.0


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the ``nowing_chat`` tool on the MCP server."""

    @mcp.tool(
        name="nowing_chat",
        title="Ask the Nowing deep agent and get a full answer",
        annotations=WRITE,
        structured_output=False,
    )
    async def nowing_chat(
        user_query: Annotated[
            str,
            Field(description="The question or instruction for the agent."),
        ],
        chat_id: Annotated[
            int | None,
            Field(
                description="Optional existing chat thread id to continue. "
                "Omit to create a fresh thread for this turn."
            ),
        ] = None,
        mode: Annotated[
            ChatMode | None,
            Field(
                description="Research depth hint: speed, balanced, quality, or auto."
            ),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Ask the Nowing deep agent a question and stream back the full answer.

        Use this for open-ended questions that benefit from the agent's
        research and tool use. The tool waits for the whole answer, so long
        research questions may take a while. Returns the complete text.
        Example: user_query="Summarize the state of RAG in 2026".
        """
        query = user_query.strip() if user_query else ""
        if not query:
            raise ToolError(
                "user_query is empty. Provide a question or instruction to chat about."
            )

        resolved = await context.resolve(workspace)

        # Create a fresh thread when the caller didn't pin one.
        if chat_id is None:
            thread = await client.request(
                "POST",
                "/threads",
                json={
                    "workspace_id": resolved.id,
                    "title": clip(query, 80),
                    "visibility": "PRIVATE",
                },
            )
            chat_id = _thread_id(thread)

        answer = await _ask_turn(
            client=client,
            chat_id=chat_id,
            workspace_id=resolved.id,
            user_query=query,
            mode=mode,
        )

        if response_format == "json":
            return to_json({"chat_id": chat_id, "text": answer})
        return answer


async def _ask_turn(
    *,
    client: NowingClient,
    chat_id: int,
    workspace_id: int,
    user_query: str,
    mode: ChatMode | None,
) -> str:
    body: dict[str, Any] = {
        "chat_id": chat_id,
        "workspace_id": workspace_id,
        "user_query": user_query,
    }
    if mode is not None:
        body["mode"] = mode

    attempt = 0
    while True:
        try:
            text, turn_id = await _consume_once(client=client, body=body)
        except ThreadBusyError as exc:
            if exc.error_code == "TURN_CANCELLING":
                raise ToolError(
                    "The turn on this thread is being cancelled by another "
                    "request; wait for it to settle, then try again."
                ) from exc
            attempt += 1
            if attempt > _MAX_BUSY_RETRIES:
                raise ToolError(
                    f"Thread {chat_id} stayed busy after {_MAX_BUSY_RETRIES} "
                    "retries. Wait a moment, then try again."
                ) from exc
            await asyncio.sleep(min(_BUSY_CAP_SECONDS, 0.5 * (2**attempt)))
            continue
        break

    if not text.strip():
        return "No content returned by the agent for this turn."
    if turn_id:
        return f"{text}\n\n_(chat_turn: {turn_id})_"
    return text


async def _consume_once(
    *, client: NowingClient, body: dict[str, Any]
) -> tuple[str, str | None]:
    ordered_ids: list[str] = []
    buffers: dict[str, list[str]] = {}
    turn_id: str | None = None
    async for event in client.stream_sse("POST", "/new_chat", json=body):
        if event.data == "[DONE]":
            continue
        payload = _parse_event(event)
        if not isinstance(payload, dict):
            continue
        ev_type = payload.get("type")
        if ev_type == "text-delta":
            delta = payload.get("delta")
            if not isinstance(delta, str):
                continue
            tid = str(payload.get("id", ""))
            if tid not in buffers:
                buffers[tid] = []
                ordered_ids.append(tid)
            buffers[tid].append(delta)
        elif ev_type == "data-turn-info":
            data = payload.get("data")
            if isinstance(data, dict) and data.get("chat_turn_id"):
                turn_id = str(data["chat_turn_id"])
        elif ev_type == "error":
            message = payload.get("message") or payload.get("detail") or "agent error"
            raise ToolError(f"The agent reported an error: {message}")

    parts = ["".join(buffers[tid]) for tid in ordered_ids]
    return "".join(parts), turn_id


def _parse_event(event: SseEvent) -> Any:
    if event.data == "[DONE]":
        return "[DONE]"
    try:
        return json.loads(event.data)
    except (json.JSONDecodeError, ValueError):
        logger.debug("Skipping non-JSON SSE payload: %r", event.data[:120])
        return None


def _thread_id(thread: Any) -> int:
    if isinstance(thread, dict):
        value = thread.get("id")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    raise ToolError("Could not create the chat thread: no thread id returned.")
