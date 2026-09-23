"""MicroClauseStreamer — cuts LLM token streams into TTS-ready clauses.

Implements the micro-clause streaming pattern from Story 38.2:
- Flush a clause at any Vietnamese sentence punctuation (`.`, `,`, `?`, `!`,
  `:`, `;`, newline) — preserving natural prosody.
- Force-cut after ``max_tokens`` tokens (default 5) when no punctuation arrives,
  preventing TTS delay on long unpunctuated runs.
- Track first-token arrival via ``first_token_event`` so the worker can decide
  whether to inject filler audio before the first TTS clause.

Vietnamese punctuation rationale:
  Tiếng Việt uses the same core punctuation set as English (``.``, ``,``, ``?``,
  ``!``, ``:``, ``;``) plus line breaks for clause boundaries. We deliberately
  exclude ``…`` (U+2026) because it is ambiguous — it can appear mid-word in
  informal text — and ``,`` is included despite being a clause-internal pause
  because it produces natural TTS phrasing at minimal latency cost.

Story 38.2 / Invariant: sub-800ms perceived latency; first TTS audio must
start within ~300ms of end-of-utterance detection.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

# Punctuation characters that trigger a clause flush.
# Covers Vietnamese + English sentence-internal pauses.
_CLAUSE_BREAK_RE = re.compile(r'[.,?!:;\n]')

# Default maximum tokens to buffer before force-cutting a clause.
_DEFAULT_MAX_TOKENS = 5


class MicroClauseStreamer:
    """Buffers an LLM token stream and yields TTS-ready text clauses.

    Usage::

        streamer = MicroClauseStreamer(max_tokens=5)
        async for clause in streamer.stream_clauses(llm_token_stream()):
            await tts.synthesize(clause)

    Attributes:
        first_token_event: Set the first time any token arrives. Workers use
            ``asyncio.wait_for(streamer.first_token_event.wait(), 0.08)`` to
            decide whether to inject filler audio.
    """

    def __init__(self, max_tokens: int = _DEFAULT_MAX_TOKENS) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        self.max_tokens = max_tokens
        self.first_token_event: asyncio.Event = asyncio.Event()
        self._total_clauses: int = 0
        self._total_tokens: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def stream_clauses(
        self,
        token_stream: AsyncIterator[str],
    ) -> AsyncIterator[str]:
        """Yield clauses from *token_stream*, cutting at punctuation or token cap.

        Args:
            token_stream: Async iterator yielding string tokens from the LLM.

        Yields:
            Non-empty clause strings ready for TTS synthesis.
        """
        buffer: list[str] = []

        async for token in token_stream:
            if not self.first_token_event.is_set():
                self.first_token_event.set()
                logger.debug("MicroClauseStreamer: first token received")

            self._total_tokens += 1
            buffer.append(token)

            # Flush on punctuation — last char of token is a clause break
            if token and _CLAUSE_BREAK_RE.search(token[-1]):
                clause = self._flush(buffer)
                if clause:
                    yield clause
                continue

            # Force-cut when buffer reaches max_tokens without punctuation
            if len(buffer) >= self.max_tokens:
                clause = self._flush(buffer)
                if clause:
                    yield clause

        # Flush any residual tokens at stream end
        clause = self._flush(buffer)
        if clause:
            yield clause

        logger.debug(
            "MicroClauseStreamer done: %d tokens → %d clauses",
            self._total_tokens,
            self._total_clauses,
        )

    async def wait_first_token(self, timeout: float = 0.08) -> bool:
        """Wait for the first token with a timeout.

        Args:
            timeout: Seconds to wait (default 80ms per spec).

        Returns:
            True if a token arrived within *timeout*, False otherwise.
        """
        try:
            await asyncio.wait_for(self.first_token_event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    @property
    def stats(self) -> dict[str, Any]:
        """Return streaming statistics for observability."""
        return {
            "total_tokens": self._total_tokens,
            "total_clauses": self._total_clauses,
            "first_token_received": self.first_token_event.is_set(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush(self, buffer: list[str]) -> str:
        """Join buffer into a clause string and clear it.

        Args:
            buffer: Mutable token buffer — cleared in place after join.

        Returns:
            Clause string, or empty string if buffer contained only whitespace.
        """
        if not buffer:
            return ""
        clause = "".join(buffer).strip()
        buffer.clear()
        if clause:
            self._total_clauses += 1
        return clause
