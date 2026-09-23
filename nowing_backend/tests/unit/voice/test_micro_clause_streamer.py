"""Unit tests for MicroClauseStreamer (Story 38.2).

Hermetic tests covering:
- Clause boundary detection at Vietnamese punctuation
- Token-count force-cut when no punctuation arrives
- first_token_event timing for filler injection trigger
- Edge cases: empty stream, single token, whitespace-only tokens
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from app.services.voice.micro_clause_streamer import MicroClauseStreamer


async def _tokens(*items: str) -> AsyncIterator[str]:
    """Helper: yield tokens as an async iterator."""
    for item in items:
        yield item


async def _collect(streamer: MicroClauseStreamer, tokens: AsyncIterator[str]) -> list[str]:
    """Collect all clauses yielded by streamer."""
    return [clause async for clause in streamer.stream_clauses(tokens)]


@pytest.mark.unit
class TestClauseBoundaryDetection:
    """Clauses must flush at Vietnamese/English punctuation marks."""

    @pytest.mark.asyncio
    async def test_period_triggers_flush(self):
        """A token ending with '.' flushes the clause immediately."""
        streamer = MicroClauseStreamer()
        clauses = await _collect(streamer, _tokens("Xin chào.", "Em là AI."))
        assert clauses == ["Xin chào.", "Em là AI."]

    @pytest.mark.asyncio
    async def test_comma_triggers_flush(self):
        """A token ending with ',' flushes the clause."""
        streamer = MicroClauseStreamer()
        clauses = await _collect(streamer, _tokens("Dạ vâng,", " em nghe đây."))
        assert clauses == ["Dạ vâng,", "em nghe đây."]

    @pytest.mark.asyncio
    async def test_question_mark_triggers_flush(self):
        """A token ending with '?' flushes the clause."""
        streamer = MicroClauseStreamer()
        clauses = await _collect(streamer, _tokens("Anh có nghe không?", " Dạ em nghe."))
        assert clauses == ["Anh có nghe không?", "Dạ em nghe."]

    @pytest.mark.asyncio
    async def test_exclamation_triggers_flush(self):
        """A token ending with '!' flushes the clause."""
        streamer = MicroClauseStreamer()
        clauses = await _collect(streamer, _tokens("Tuyệt vời!", " Cảm ơn anh."))
        assert clauses == ["Tuyệt vời!", "Cảm ơn anh."]

    @pytest.mark.asyncio
    async def test_colon_semicolon_newline_trigger_flush(self):
        """':' ';' and newline all trigger clause flush."""
        for punct in [":", ";", "\n"]:
            streamer = MicroClauseStreamer()
            clauses = await _collect(
                streamer, _tokens(f"clause one{punct}", " clause two.")
            )
            assert len(clauses) == 2, f"Expected 2 clauses for punct={punct!r}"

    @pytest.mark.asyncio
    async def test_token_ending_with_punctuation_flushes(self):
        """Token ending in punctuation triggers immediate flush (not mid-token).

        ``"word,"`` ends with ``,`` so it flushes as its own clause.
        ``"word,x"`` (mid-token punct) does NOT flush — only last char is checked.
        """
        streamer = MicroClauseStreamer(max_tokens=10)
        # "word," ends with ',' → flush immediately
        # "another." ends with '.' → flush immediately
        # "trailing" has no punct → flushed at stream end
        clauses = await _collect(
            streamer, _tokens("word,", " another.", " trailing")
        )
        assert clauses == ["word,", "another.", "trailing"]


@pytest.mark.unit
class TestTokenCountCutoff:
    """Force-cut after max_tokens when no punctuation arrives."""

    @pytest.mark.asyncio
    async def test_max_tokens_force_cut(self):
        """Buffer flushes after exactly max_tokens tokens without punctuation."""
        streamer = MicroClauseStreamer(max_tokens=3)
        clauses = await _collect(
            streamer, _tokens("one", " two", " three", " four", " five")
        )
        # First 3 tokens flush, remaining 2 flush at stream end
        assert clauses == ["one two three", "four five"]

    @pytest.mark.asyncio
    async def test_max_tokens_1_flushes_every_token(self):
        """max_tokens=1 yields one clause per token."""
        streamer = MicroClauseStreamer(max_tokens=1)
        clauses = await _collect(streamer, _tokens("a", " b", " c"))
        assert clauses == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_punctuation_takes_priority_over_count(self):
        """Punctuation flush happens before token-count cutoff."""
        streamer = MicroClauseStreamer(max_tokens=5)
        # Only 2 tokens but ends with '.' — should flush immediately
        clauses = await _collect(streamer, _tokens("short.", " next clause."))
        assert clauses == ["short.", "next clause."]

    @pytest.mark.asyncio
    async def test_long_clause_without_punctuation_force_cut(self):
        """Clause longer than max_tokens without punctuation is force-cut."""
        streamer = MicroClauseStreamer(max_tokens=4)
        clauses = await _collect(
            streamer,
            _tokens("the", " quick", " brown", " fox", " jumps", " over"),
        )
        # First 4 tokens flush, remaining 2 flush at end
        assert clauses == ["the quick brown fox", "jumps over"]


@pytest.mark.unit
class TestFirstTokenEvent:
    """first_token_event signals when LLM starts producing output."""

    @pytest.mark.asyncio
    async def test_first_token_event_set_on_first_token(self):
        """first_token_event is set after the first token is consumed."""
        streamer = MicroClauseStreamer()

        async def check_event() -> bool:
            async for _ in streamer.stream_clauses(_tokens("hello", " world.")):
                pass
            return streamer.first_token_event.is_set()

        assert await check_event() is True

    @pytest.mark.asyncio
    async def test_wait_first_token_returns_true_when_token_arrives(self):
        """wait_first_token returns True when a token arrives quickly."""
        streamer = MicroClauseStreamer()

        async def producer():
            yield "first"

        async def consume():
            async for _ in streamer.stream_clauses(producer()):
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.01)  # let stream start
        result = await streamer.wait_first_token(timeout=0.5)
        await task
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_first_token_returns_false_on_timeout(self):
        """wait_first_token returns False if no token arrives within timeout."""
        streamer = MicroClauseStreamer()
        # Never start the stream — event never fires
        result = await streamer.wait_first_token(timeout=0.01)
        assert result is False


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases: empty stream, whitespace, unicode Vietnamese."""

    @pytest.mark.asyncio
    async def test_empty_stream_yields_nothing(self):
        """Empty token stream yields zero clauses."""
        streamer = MicroClauseStreamer()
        clauses = await _collect(streamer, _tokens())
        assert clauses == []

    @pytest.mark.asyncio
    async def test_whitespace_only_tokens_yield_nothing(self):
        """Whitespace-only tokens produce empty clause (stripped)."""
        streamer = MicroClauseStreamer()
        clauses = await _collect(streamer, _tokens("   ", "  ", "."))
        # Whitespace + '.' → clause is '.' after strip; only non-empty yields
        assert all(c.strip() for c in clauses)

    @pytest.mark.asyncio
    async def test_vietnamese_text_passes_through(self):
        """Vietnamese UTF-8 text is preserved in clauses."""
        streamer = MicroClauseStreamer()
        clauses = await _collect(
            streamer,
            _tokens("Xin chào anh,", " em là trợ lý AI.", " Anh có rảnh không?"),
        )
        assert "Xin chào anh," in clauses[0]
        assert "không?" in clauses[-1]

    @pytest.mark.asyncio
    async def test_streamer_stats(self):
        """stats property tracks token and clause counts."""
        streamer = MicroClauseStreamer(max_tokens=2)
        await _collect(streamer, _tokens("a", " b", " c."))
        stats = streamer.stats
        assert stats["total_tokens"] == 3
        assert stats["total_clauses"] == 2  # "a b" (count cut) + "c." (punct cut)
        assert stats["first_token_received"] is True

    @pytest.mark.asyncio
    async def test_invalid_max_tokens_raises(self):
        """max_tokens < 1 raises ValueError."""
        with pytest.raises(ValueError):
            MicroClauseStreamer(max_tokens=0)
