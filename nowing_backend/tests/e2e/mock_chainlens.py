"""Minimal local ChainLens mock for happy-path smoke tests.

Serves ``POST /api/v1/search`` and streams SSE events matching the contract
expected by ``app.capabilities.chainlens.research.executor``.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


async def _event_stream(query: str, mode: str) -> None:
    # Accept / first progress / factual chunk timestamps
    now = time.time()
    request_accepted_at = int((now - 2) * 1000)
    first_progress_at = int((now - 1.5) * 1000)
    evidence_ready_at = int((now - 1) * 1000)
    first_factual_chunk_at = int((now - 0.5) * 1000)

    events = [
        {"type": "heartbeat"},
        {
            "type": "progress",
            "phase": "starting",
            "message": "Researching...",
            "requestAcceptedAt": request_accepted_at,
            "firstProgressAt": first_progress_at,
            "evidenceReadyAt": evidence_ready_at,
            "firstFactualChunkAt": first_factual_chunk_at,
        },
        {"type": "evidence_ready", "message": "Evidence ready"},
        {"type": "synthesizing", "message": "Synthesizing answer"},
        {
            "type": "block",
            "block": {
                "id": "answer",
                "type": "text",
                "data": f"A concise answer to: {query}",
            },
        },
        {
            "type": "block",
            "block": {
                "id": "sources",
                "type": "source",
                "data": [
                    {
                        "title": "Mock source",
                        "url": "https://example.com/mock",
                        "content": "Mock source content for testing.",
                    }
                ],
            },
        },
        {"type": "researchComplete", "message": "Research complete"},
        {
            "type": "done",
            "costDollars": 0.0123,
            "resolvedMode": "balanced",
            "chatId": "chat-mock-123",
            "tokens": {"total": 1280},
        },
    ]

    for event in events:
        yield f"data: {json.dumps(event)}\n\n"
        await asyncio.sleep(0.05)
    # Some engines emit a trailing [DONE] marker; the parser ignores it.
    yield "data: [DONE]\n\n"


@app.post("/api/v1/search")
async def search(request: Request) -> StreamingResponse:
    body = await request.json()
    query = body.get("query", "")
    mode = body.get("mode", "balanced")
    return StreamingResponse(
        _event_stream(query, mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3001, log_level="info")
