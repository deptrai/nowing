"""Minimal SSE consumer compatible with Nowing's wire format.

Port of the evals client's parser (``nowing_evals/core/parse/sse.py``) so the
MCP server can stream ``POST /new_chat`` without depending on the evals
package. The backend frames events as ``data: <json-or-text>\\n\\n`` with a
literal ``data: [DONE]`` terminator and no ``event:``/``id:``/``retry:`` lines.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class SseEvent:
    """A parsed SSE event. Only the ``data`` field is populated."""

    data: str


async def iter_sse_events(lines: AsyncIterator[str]) -> AsyncIterator[SseEvent]:
    """Yield one ``SseEvent`` per blank-line-terminated frame.

    Empty/whitespace lines flush the buffer; ``data:`` lines accumulate into
    it; everything else is ignored (lenient browser EventSource behaviour).
    Multi-line payloads are joined with ``\\n``.
    """

    buffer: list[str] = []
    async for raw in lines:
        if raw is None:
            continue
        line = raw.rstrip("\r")
        if line == "" or line.strip() == "":
            if buffer:
                yield SseEvent(data="\n".join(buffer))
                buffer.clear()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            payload = line[5:]
            if payload.startswith(" "):
                payload = payload[1:]
            buffer.append(payload)
            continue
        continue

    if buffer:
        yield SseEvent(data="\n".join(buffer))


__all__ = ["SseEvent", "iter_sse_events"]
