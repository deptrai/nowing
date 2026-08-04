"""Nowing arm: per-question fresh thread + ``/api/v1/new_chat`` stream.

For every question:

* Create a fresh ``NewChatThread`` on the suite's pinned SearchSpace.
  This sidesteps the per-thread ``THREAD_BUSY`` 409 (a single thread
  serialises turns, see ``nowing_backend/app/routes/new_chat_routes.py:191-220``).
* POST ``/api/v1/new_chat`` with the prompt and the per-question
  ``mentioned_document_ids`` (``nowing_backend/app/schemas/new_chat.py:241-243``).
* Consume the SSE stream via ``NewChatClient.ask`` which accumulates
  text deltas and returns ``StreamedAnswer``.
* Optionally delete the thread (default ON for ephemeral runs).

Citations are parsed from the streamed assistant text via the
canonical regex port; chunk ids are returned in ``ArmResult.citations``
for the runner to map back to corpus ids.
"""

from __future__ import annotations

import asyncio
import logging

from ..clients import NewChatClient
from ..parse.answer_letter import extract_answer_letter
from .base import Arm, ArmRequest, ArmResult

logger = logging.getLogger(__name__)


class NowingArm(Arm):
    """``Arm`` implementation backed by ``NewChatClient``."""

    name: str = "nowing"

    def __init__(
        self,
        *,
        client: NewChatClient,
        search_space_id: int,
        ephemeral_threads: bool = True,
        thread_title_prefix: str = "eval",
    ) -> None:
        self._client = client
        self._search_space_id = search_space_id
        self._ephemeral = ephemeral_threads
        self._title_prefix = thread_title_prefix

    async def answer(self, request: ArmRequest) -> ArmResult:
        """Answer one turn. Reuse an existing thread when ``options["thread_id"]``
        is provided (caller is then responsible for deletion unless it also sets
        ``options["delete_thread"]=True``).
        """
        reused = request.options.get("thread_id")
        thread_id: int | None = reused
        try:
            if thread_id is None:
                thread_id = await self._client.create_thread(
                    search_space_id=self._search_space_id,
                    title=f"{self._title_prefix}:{request.question_id}",
                )
            answer = await self._client.ask(
                thread_id=thread_id,
                search_space_id=self._search_space_id,
                user_query=request.prompt,
                mentioned_document_ids=request.mentioned_document_ids,
                disabled_tools=request.options.get("disabled_tools"),
            )
        except Exception as exc:  # noqa: BLE001
            return ArmResult(
                arm=self.name,
                question_id=request.question_id,
                raw_text="",
                error=f"{type(exc).__name__}: {exc}",
                extra={"thread_id": thread_id},
            )
        finally:
            should_delete = request.options.get("delete_thread")
            if should_delete is None:
                should_delete = self._ephemeral and reused is None
            if should_delete and thread_id is not None:
                try:
                    # Shield cleanup so an outer asyncio.wait_for timeout
                    # cannot cancel the delete before the backend receives it.
                    await asyncio.shield(self._client.delete_thread(thread_id))
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to delete thread %s: %s", thread_id, exc)

        letter = extract_answer_letter(answer.text)
        return ArmResult(
            arm=self.name,
            question_id=request.question_id,
            raw_text=answer.text,
            error=answer.error,
            answer_letter=letter.letter,
            citations=answer.citations,
            input_tokens=answer.prompt_tokens,
            output_tokens=answer.completion_tokens,
            cost_micros=answer.cost_micros or 0,
            latency_ms=answer.latency_ms,
            extra={
                "thread_id": thread_id,
                "search_space_id": self._search_space_id,
                "answer_letter_strategy": letter.strategy,
                "user_message_id": answer.user_message_id,
                "assistant_message_id": answer.assistant_message_id,
                "turn_id": answer.turn_id,
                "ttfb_ms": answer.ttfb_ms,
                "finished_normally": answer.finished_normally and answer.error is None,
                "n_raw_events": len(answer.raw_events),
                "n_mentioned_documents": len(request.mentioned_document_ids or []),
                "model_breakdown": answer.model_breakdown,
                "call_details": answer.call_details,
                "raw_events": answer.raw_events,
                "error_code": answer.error_code,
            },
        )

    async def delete_thread(self, thread_id: int) -> None:
        """Explicit cleanup helper for multi-turn runners."""
        try:
            await asyncio.shield(self._client.delete_thread(thread_id))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to delete thread %s: %s", thread_id, exc)


__all__ = ["NowingArm"]
