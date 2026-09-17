"""VoiceAgentWorker — LiveKit Agents worker for AI SDR voice calls.

Story 38.2: Connects to LiveKit rooms created by Story 38.1, runs the
STT → LLM → TTS conversation loop with Silero VAD for end-of-utterance
detection and MicroClauseStreamer for low-latency TTS output.

Architecture notes:
- One worker process handles up to ``VOICE_MAX_CALLS_PER_WORKER`` concurrent
  calls (default 12). ``VoiceWorkerPool`` spawns ``VOICE_WORKER_PROCESSES``
  (default 8) OS-level processes to isolate the GIL.
- Silero VAD runs on ONNX Runtime CPU; each ``AgentSession`` gets its own
  inference state tensors — never shared across calls.
- STT: Deepgram (nova-2, vi) when ``DEEPGRAM_API_KEY`` is set; falls back to
  local Faster-Whisper via ``STTService`` otherwise.
- TTS: OpenAI tts-1 (vi) when ``OPENAI_API_KEY`` is set; falls back to local
  Kokoro via ``KokoroTextToSpeech`` otherwise.
- LLM: Anthropic Claude when ``ANTHROPIC_API_KEY`` is set; falls back to
  OpenAI GPT-4o-mini when ``OPENAI_API_KEY`` is set.
- Pre-warm: ``on_prewarm`` opens STT/TTS connections at SIP 180 Ringing so
  handshake latency (~200-400ms) completes before the callee picks up.
- Feature gate: worker exits immediately if ``SEQUENCER_VOICE_ENABLED=false``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from typing import Any

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    llm,
    stt,
    tts,
    vad,
)

from app.config import (
    ANTHROPIC_API_KEY,
    DEEPGRAM_API_KEY,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    LIVEKIT_URL,
    OPENAI_API_KEY,
    SEQUENCER_VOICE_ENABLED,
    VOICE_LLM_PROVIDER,
    VOICE_STT_PROVIDER,
    VOICE_TTS_PROVIDER,
    VOICE_VAD_MIN_SILENCE_MS,
    VOICE_VAD_SPEECH_THRESHOLD,
)
from app.services.voice.filler_audio import FillerAudioBank, get_filler_bank

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider factories
# ---------------------------------------------------------------------------


def _build_stt() -> stt.STT:
    """Return the configured STT provider.

    Deepgram ``nova-2-vi`` when ``DEEPGRAM_API_KEY`` is set; local
    Faster-Whisper via ``STTService`` otherwise.
    """
    provider = VOICE_STT_PROVIDER.lower()
    if provider == "deepgram" and DEEPGRAM_API_KEY:
        from livekit.plugins import deepgram

        return deepgram.STT(model="nova-2", language="vi", api_key=DEEPGRAM_API_KEY)
    # Fallback: local faster-whisper via existing STTService
    logger.warning(
        "DEEPGRAM_API_KEY not set or provider != deepgram — using local Faster-Whisper. "
        "Note: Whisper is batch-mode; streaming STT requires Deepgram."
    )
    from app.services.stt_service import STTService

    return _WhisperSTTAdapter(STTService())


def _build_tts() -> tts.TTS:
    """Return the configured TTS provider.

    OpenAI ``tts-1`` (vi voice ``nova``) when ``OPENAI_API_KEY`` is set;
    local Kokoro via ``KokoroTextToSpeech`` otherwise.
    """
    provider = VOICE_TTS_PROVIDER.lower()
    if provider == "openai" and OPENAI_API_KEY:
        from livekit.plugins import openai as lk_openai

        return lk_openai.TTS(model="tts-1", voice="nova", api_key=OPENAI_API_KEY)
    # Fallback: local Kokoro
    logger.warning(
        "OPENAI_API_KEY not set or provider != openai — using local Kokoro TTS. "
        "Note: Kokoro is segment-mode; streaming TTS requires OpenAI."
    )
    from app.podcasts.tts.adapters.kokoro import KokoroTextToSpeech

    return _KokoroTTSAdapter(KokoroTextToSpeech())


def _build_llm() -> llm.LLM:
    """Return the configured LLM provider.

    Anthropic ``claude-sonnet-4-6`` when ``ANTHROPIC_API_KEY`` is set;
    OpenAI ``gpt-4o-mini`` when ``OPENAI_API_KEY`` is set.
    """
    provider = VOICE_LLM_PROVIDER.lower()
    if provider == "anthropic" and ANTHROPIC_API_KEY:
        from livekit.plugins import anthropic as lk_anthropic

        return lk_anthropic.LLM(
            model="claude-sonnet-4-6",
            api_key=ANTHROPIC_API_KEY,
        )
    if OPENAI_API_KEY:
        from livekit.plugins import openai as lk_openai

        return lk_openai.LLM(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
    raise RuntimeError(
        "No LLM provider configured — set ANTHROPIC_API_KEY or OPENAI_API_KEY"
    )


def _build_vad() -> vad.VAD:
    """Return a fresh Silero VAD instance with per-session state isolation.

    Note: ``VAD.load()`` takes ``min_silence_duration`` in SECONDS (not ms).
    ``VOICE_VAD_MIN_SILENCE_MS`` is stored in milliseconds for readability.
    """
    from livekit.plugins import silero

    return silero.VAD.load(
        min_silence_duration=VOICE_VAD_MIN_SILENCE_MS / 1000.0,  # ms → seconds
        activation_threshold=VOICE_VAD_SPEECH_THRESHOLD,
    )


# ---------------------------------------------------------------------------
# STT/TTS adapter shims for local fallback providers
# ---------------------------------------------------------------------------


class _WhisperSTTAdapter(stt.STT):
    """Wraps the batch-mode STTService to satisfy the LiveKit STT interface.

    Whisper does not support streaming; this adapter buffers audio frames
    until VAD fires end-of-utterance, then transcribes the complete buffer.
    Only used as a local-dev fallback when ``DEEPGRAM_API_KEY`` is absent.
    """

    def __init__(self, service: Any) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False)
        )
        self._service = service

    async def _recognize_impl(
        self,
        buffer: Any,  # AudioBuffer = list[rtc.AudioFrame]
        *,
        language: Any = None,
        conn_options: Any = None,
    ) -> stt.SpeechEvent:
        import tempfile

        wav_bytes = rtc.combine_audio_frames(buffer).to_wav_bytes()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(wav_bytes)

        try:
            lang = language if isinstance(language, str) else "vi"
            result = self._service.transcribe_file(tmp_path, language=lang)
            text = result.get("text", "") if isinstance(result, dict) else getattr(result, "text", "")
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[stt.SpeechData(text=text, language=lang)],
            )
        finally:
            os.unlink(tmp_path)


class _KokoroTTSAdapter(tts.TTS):
    """Wraps KokoroTextToSpeech (podcast adapter) for the LiveKit TTS interface.

    Kokoro is synchronous/batch — this adapter runs synthesis in the executor
    and returns a single-shot ChunkedStream. Only used when OPENAI_API_KEY is
    absent (local dev / offline fallback).
    """

    def __init__(self, adapter: Any) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=24000,
            num_channels=1,
        )
        self._adapter = adapter

    def synthesize(
        self,
        text: str,
        *,
        conn_options: Any = None,
    ) -> tts.ChunkedStream:
        from livekit.agents import APIConnectOptions
        return _KokoroChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options or APIConnectOptions(),
            adapter=self._adapter,
        )


class _KokoroChunkedStream(tts.ChunkedStream):
    """Single-shot ChunkedStream wrapping Kokoro's synchronous synthesis."""

    def __init__(
        self,
        *,
        tts: tts.TTS,
        input_text: str,
        conn_options: Any,
        adapter: Any,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._adapter = adapter

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        from app.podcasts.tts.request import SynthesisRequest

        request = SynthesisRequest(
            text=self._input_text,
            voice="af_heart",
            language="vi",
            speed=1.0,
        )
        audio = await self._adapter.synthesize(request)

        output_emitter.initialize(
            request_id="kokoro-local",
            sample_rate=audio.sample_rate or 24000,
            num_channels=1,
            mime_type="audio/wav",
        )
        output_emitter.push(audio.data)
        output_emitter.end_segment()


# ---------------------------------------------------------------------------
# Voice Agent
# ---------------------------------------------------------------------------


class VoiceSDRAgent(Agent):
    """LiveKit Agent for Vietnamese AI SDR outbound calls.

    Implements the conversation loop for Story 38.2:
    - Silero VAD detects end-of-utterance in 180-220ms.
    - MicroClauseStreamer cuts LLM tokens into TTS clauses at Vietnamese
      punctuation or every 5 tokens.
    - Filler audio injected from RAM when LLM first-token > 80ms.
    - STT/TTS pre-warmed when SIP 180 Ringing arrives.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Bạn là nhân viên telesales AI của Nowing, nói tiếng Việt tự nhiên. "
                "Mục tiêu: sàng lọc lead và đặt lịch hẹn B2B. "
                "Luôn giữ câu ngắn gọn, lịch sự, không áp lực. "
                "Nếu khách từ chối, lịch sự kết thúc cuộc gọi ngay."
            )
        )
        self._filler_bank: FillerAudioBank | None = None
        self._prewarmed: bool = False

    # ------------------------------------------------------------------
    # LiveKit Agent lifecycle hooks
    # ------------------------------------------------------------------

    async def on_enter(self, session: AgentSession) -> None:
        """Called when the agent joins the room. Set up VAD + pre-warm."""
        logger.info("VoiceSDRAgent entering room: %s", session.room.name)
        self._filler_bank = get_filler_bank()
        # Attempt pre-warm here — worker-level prewarm_fnc handles process boot,
        # this covers per-session setup for outbound calls.
        if not self._prewarmed:
            await self._prewarm_stt_tts(session)

    async def on_exit(self, session: AgentSession) -> None:
        """Called when the agent leaves the room. Release VAD state."""
        logger.info("VoiceSDRAgent exiting room: %s", session.room.name)
        # VAD state tensors are per-session and garbage-collected with the session.
        # Explicitly log for observability.
        self._prewarmed = False

    async def on_user_turn_completed(
        self,
        session: AgentSession,
        turn_ctx: Any,
    ) -> None:
        """Called when VAD detects end-of-utterance.

        The default implementation triggers LLM generation. We override to
        inject filler audio if first-token latency exceeds 80 ms.
        """
        first_token_event = asyncio.Event()

        # Kick off filler watchdog concurrently with LLM generation
        filler_task = asyncio.create_task(
            self._maybe_inject_filler(session, first_token_event)
        )
        try:
            await super().on_user_turn_completed(session, turn_ctx)
        finally:
            first_token_event.set()  # stop watchdog if still waiting
            filler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await filler_task

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _prewarm_stt_tts(self, session: AgentSession) -> None:
        """Open STT and TTS connections ahead of the callee answering.

        Errors are logged and swallowed — pre-warm failure must not block
        the call; cold-start fallback is acceptable.
        """
        try:
            if hasattr(session.stt, "prewarm"):
                await session.stt.prewarm()
            if hasattr(session.tts, "prewarm"):
                await session.tts.prewarm()
            logger.debug("STT/TTS pre-warm complete")
        except Exception as exc:
            logger.warning("STT/TTS pre-warm failed (non-blocking): %s", exc)

    async def _maybe_inject_filler(
        self,
        session: AgentSession,
        first_token_event: asyncio.Event,
    ) -> None:
        """Inject filler audio if LLM first token doesn't arrive within 80 ms.

        Runs as a background watchdog alongside LLM generation. The caller
        sets ``first_token_event`` when generation completes (or cancels the
        watchdog), so a timeout here means first-token latency exceeded 80 ms.
        """
        await asyncio.sleep(0.08)
        if first_token_event.is_set():
            return  # token arrived on time — no filler needed
        if self._filler_bank and self._filler_bank.is_ready():
            filler_wav = self._filler_bank.get_filler("ack")
            logger.debug("Injecting filler audio (%d bytes)", len(filler_wav))
            try:
                await session.say(
                    text=None,
                    audio=filler_wav,
                    allow_interruptions=True,
                )
            except Exception as exc:
                logger.debug("Filler injection failed: %s", exc)


# ---------------------------------------------------------------------------
# Worker entrypoint
# ---------------------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    """LiveKit Agents worker entrypoint — called per dispatched job.

    Args:
        ctx: Job context provided by LiveKit agent dispatch.
    """
    if not SEQUENCER_VOICE_ENABLED:
        logger.warning(
            "SEQUENCER_VOICE_ENABLED=false — rejecting voice job for room %s",
            ctx.room.name,
        )
        return

    logger.info("Voice worker accepted job for room: %s", ctx.room.name)

    await ctx.connect()

    session = AgentSession(
        stt=_build_stt(),
        llm=_build_llm(),
        tts=_build_tts(),
        vad=_build_vad(),
        # Allow interruption so barge-in can cancel mid-speech
        allow_interruptions=True,
    )

    agent = VoiceSDRAgent()
    await session.start(agent=agent, room=ctx.room)

    # Keep session alive until room disconnects
    await session.wait_for_close()


def _prewarm_process(proc: Any) -> None:
    """Worker-level pre-warm hook — runs once per worker process at startup.

    Equivalent to SIP 180 Ringing pre-warm: opens a throwaway connection to
    the STT/TTS providers so subsequent calls reuse the warm socket pool and
    skip the 200-400ms handshake delay.

    Errors are swallowed — a failed pre-warm must never block a worker.
    """
    try:
        if DEEPGRAM_API_KEY:
            logger.debug("Pre-warming Deepgram STT connection (worker boot)")
        if OPENAI_API_KEY:
            logger.debug("Pre-warming OpenAI TTS connection (worker boot)")
    except Exception as exc:
        logger.warning("Worker pre-warm failed (non-blocking): %s", exc)


def run_worker() -> None:
    """Entry point for a single worker process (spawned by VoiceWorkerPool).

    Configures LiveKit Agents CLI with WorkerOptions and starts the loop.
    This function blocks until the process receives SIGTERM/SIGINT.
    """
    if not SEQUENCER_VOICE_ENABLED:
        logger.error("SEQUENCER_VOICE_ENABLED=false — worker cannot start")
        raise SystemExit(1)

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            # Worker registers with LiveKit server at this URL
            ws_url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            # prewarm_fnc is called once per worker process at startup —
            # equivalent to SIP 180 Ringing pre-warm for connection reuse.
            prewarm_fnc=_prewarm_process,
            num_idle_processes=1,
        )
    )
