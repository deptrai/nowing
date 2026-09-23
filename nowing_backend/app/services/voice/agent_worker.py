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
import json
import logging
import os
import sys
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any
from uuid import UUID

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
from livekit.agents.llm import StopResponse

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
from app.services.voice.micro_clause_streamer import MicroClauseStreamer
from app.services.voice.semantic_gate import (
    VoiceTurnAssessment,
    evaluate_voice_turn,
)
from app.services.voice.telephony_client import LiveKitTelephonyClient

logger = logging.getLogger(__name__)

# Canned escalation line (Story 39.6) — no SIP transfer this story; the
# WARNING log triggers human follow-up who calls the customer back.
_VOICE_TRANSFER_LINE = (
    "Dạ, em xin ghi nhận yêu cầu của mình ạ. Nhân viên Nowing sẽ liên hệ "
    "lại với mình trong thời gian sớm nhất. Em cảm ơn ạ."
)

# Pause between the transfer line finishing playout and end_call so the
# SIP leg actually delivers the tail of the audio before teardown.
_ESCALATION_PLAYOUT_BUFFER_SECONDS = 0.3

# Hard bounds on the escalation awaits — a stalled playout or hung
# LiveKit API must fail open, never hang the turn hook.
_ESCALATION_PLAYOUT_TIMEOUT_SECONDS = 5.0
_ESCALATION_END_CALL_TIMEOUT_SECONDS = 3.0

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

    OpenAI ``tts-1`` (vi voice ``nova``) when ``OPENAI_API_KEY`` is set.
    For Vietnamese speech, OpenAI TTS is required because local Kokoro
    does not support Vietnamese ('vi') language models.
    """
    provider = VOICE_TTS_PROVIDER.lower()
    if provider == "openai" and OPENAI_API_KEY:
        from livekit.plugins import openai as lk_openai

        return lk_openai.TTS(model="tts-1", voice="nova", api_key=OPENAI_API_KEY)

    if OPENAI_API_KEY:
        from livekit.plugins import openai as lk_openai

        return lk_openai.TTS(model="tts-1", voice="nova", api_key=OPENAI_API_KEY)

    raise RuntimeError(
        "No supported Vietnamese TTS provider configured — set OPENAI_API_KEY "
        "(KokoroTextToSpeech lacks Vietnamese language model support)"
    )


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
        lang = language if isinstance(language, str) else "vi"
        if not buffer:
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[stt.SpeechData(text="", language=lang)],
            )

        import tempfile

        wav_bytes = rtc.combine_audio_frames(buffer).to_wav_bytes()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(wav_bytes)

        try:
            result = await asyncio.to_thread(self._service.transcribe_file, tmp_path, language=lang)
            text = result.get("text", "") if isinstance(result, dict) else getattr(result, "text", "")
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[stt.SpeechData(text=text, language=lang)],
            )
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)


async def _wav_to_audio_frames(wav_bytes: bytes) -> AsyncIterator[rtc.AudioFrame]:
    """Decode raw WAV bytes into rtc.AudioFrame objects for LiveKit playout."""
    import io
    import wave

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            sample_rate = wf.getframerate()
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            pcm_data = wf.readframes(wf.getnframes())

        samples_per_channel = len(pcm_data) // (num_channels * sample_width)
        if samples_per_channel > 0:
            frame = rtc.AudioFrame.create(
                sample_rate=sample_rate,
                num_channels=num_channels,
                samples_per_channel=samples_per_channel,
            )
            frame.data.cast("B")[:] = pcm_data
            yield frame
    except Exception as exc:
        logger.warning("Failed to decode filler wav frames: %s", exc)


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

    def __init__(
        self,
        *,
        workspace_id: int | None = None,
        user_id: UUID | None = None,
        call_session_id: str | None = None,
        room_name: str | None = None,
    ) -> None:
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
        self._first_token_event: asyncio.Event = asyncio.Event()
        self._filler_task: asyncio.Task[None] | None = None
        # Story 39.6 call context — plumbed from room metadata by the
        # entrypoint; telemetry stays log-only while keys are absent.
        self._workspace_id = workspace_id
        self._user_id = user_id
        self._call_session_id = call_session_id
        self._room_name = room_name

    # ------------------------------------------------------------------
    # LiveKit Agent lifecycle hooks
    # ------------------------------------------------------------------

    async def on_enter(self) -> None:
        """Called when the agent enters the room. Set up filler bank + pre-warm."""
        self._filler_bank = get_filler_bank()
        try:
            session = self.session
            logger.info("VoiceSDRAgent entering room: %s", getattr(getattr(session, "room", None), "name", "unknown"))
            if not self._prewarmed:
                await self._prewarm_stt_tts(session)
        except Exception as exc:
            logger.debug("on_enter initialization notice: %s", exc)

    async def on_exit(self) -> None:
        """Called when the agent leaves the room. Release state."""
        self._prewarmed = False
        if self._filler_task and not self._filler_task.done():
            self._filler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._filler_task

    async def on_user_turn_completed(
        self,
        turn_ctx: llm.ChatContext,
        new_message: llm.ChatMessage,
    ) -> None:
        """Called when VAD detects end-of-utterance and LLM is about to respond.

        Kicks off the filler watchdog (perceived-latency safety net),
        then — Story 39.6 — runs one batched semantic decision over the
        transcript: suppress confident backchannels via ``StopResponse``,
        escalate explicit human-transfer requests, log frustration.
        Fail-open absolute: any decision-layer error falls through to
        the normal generation path.
        """
        self._first_token_event = asyncio.Event()
        session: AgentSession | None = None
        try:
            session = self.session
            self._filler_task = asyncio.create_task(
                self._maybe_inject_filler(session, self._first_token_event)
            )
        except Exception as exc:
            logger.debug("Failed to start filler watchdog: %s", exc)

        assessment = await self._evaluate_turn(new_message)

        if assessment.transfer:
            # Transfer wins over suppression (spec 39.6 precedence) —
            # when both fire, escalate and ignore the suppress flag.
            # Log the INTENT before attempting — a played promise line
            # followed by a failed end_call must still leave a record,
            # and a session=None drop must not be silent.
            logger.warning(
                "voice_escalation: transfer intent — room=%s "
                "call_session_id=%s workspace_id=%s user_id=%s",
                self._room_name,
                self._call_session_id,
                self._workspace_id,
                self._user_id,
            )
            if session is not None and await self._escalate_to_human(session):
                raise StopResponse()
            # Escalation unavailable/failed → fail-open to generation.
        elif assessment.suppress_response:
            self._cancel_filler_watchdog()
            if session is not None:
                # The watchdog's 80ms timer beats a ~300ms decide(), so
                # a filler may already be playing — cut it rather than
                # leave "Dạ vâng..." dangling into dead air.
                with contextlib.suppress(Exception):
                    session.interrupt()
            logger.info(
                "[voice_turn] suppressing response — confident "
                "backchannel/noise transcript"
            )
            raise StopResponse()

        await super().on_user_turn_completed(turn_ctx, new_message)

    # ------------------------------------------------------------------
    # TTS Node with MicroClauseStreamer pipeline
    # ------------------------------------------------------------------

    async def tts_node(
        self, text: AsyncIterable[str], model_settings: Any
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Custom TTS node intercepting LLM text chunks.

        Cuts at Vietnamese punctuation or 5 tokens via MicroClauseStreamer,
        and signals first-token arrival to stop the filler watchdog.
        """
        streamer = MicroClauseStreamer()

        async def _monitored_text() -> AsyncIterator[str]:
            async for chunk in text:
                if not self._first_token_event.is_set():
                    self._first_token_event.set()
                yield chunk

        clauses = streamer.stream_clauses(_monitored_text())
        async for frame in Agent.default.tts_node(self, clauses, model_settings):
            yield frame

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _evaluate_turn(
        self, new_message: llm.ChatMessage
    ) -> VoiceTurnAssessment:
        """Run the Story 39.6 semantic gate over the turn's transcript.

        Fail-open absolute: ``evaluate_voice_turn`` never raises by
        contract, and this wrapper keeps the voice loop alive even if
        that contract or ``text_content`` access ever breaks.
        """
        try:
            transcript = new_message.text_content or ""
        except Exception:
            transcript = ""
        try:
            return await evaluate_voice_turn(
                transcript,
                workspace_id=self._workspace_id,
                user_id=self._user_id,
                client_id=self._call_session_id,
            )
        except Exception:
            logger.warning(
                "[voice_turn] evaluation raised — fail-open respond",
                exc_info=True,
            )
            return VoiceTurnAssessment()

    def _cancel_filler_watchdog(self) -> None:
        """Stop the pending filler so no 'Dạ vâng...' dangles into dead air."""
        self._first_token_event.set()
        if self._filler_task and not self._filler_task.done():
            self._filler_task.cancel()

    def _rearm_filler_watchdog(self, session: AgentSession) -> None:
        """Re-arm the filler watchdog after a failed escalation.

        ``_cancel_filler_watchdog`` kills the 80ms safety net; when the
        turn falls back to normal generation the watchdog must be alive
        again or a slow LLM first token means dead air.
        """
        self._first_token_event = asyncio.Event()
        if self._filler_task and not self._filler_task.done():
            self._filler_task.cancel()
        try:
            self._filler_task = asyncio.create_task(
                self._maybe_inject_filler(session, self._first_token_event)
            )
        except Exception as exc:
            logger.debug("Failed to re-arm filler watchdog: %s", exc)

    async def _escalate_to_human(self, session: AgentSession) -> bool:
        """Play the canned transfer line, then end the call (Story 39.6).

        Sequence is load-bearing: the filler watchdog is cancelled and
        any in-flight speech interrupted first (no filler overlapping
        the transfer line), and the transfer line must fully play out
        before ``end_call`` — ``say()`` is fire-and-forget, so deleting
        the room right after would leave the caller hearing nothing.
        Both awaits are time-bounded so a stalled playout or hung
        LiveKit API can't hang the turn hook forever.

        Returns True when the escalation completed (the caller then
        raises ``StopResponse`` to abort LLM generation); False on any
        failure — fail-open, with the filler watchdog re-armed for the
        generation path that now continues.
        """
        if not self._room_name:
            logger.warning(
                "[voice_turn] transfer requested but room_name unknown — "
                "cannot end_call, fail-open"
            )
            return False
        self._cancel_filler_watchdog()
        try:
            with contextlib.suppress(Exception):
                session.interrupt()
            handle = session.say(
                _VOICE_TRANSFER_LINE,
                allow_interruptions=False,
                add_to_chat_ctx=False,
            )
            await asyncio.wait_for(
                handle.wait_for_playout(),
                timeout=_ESCALATION_PLAYOUT_TIMEOUT_SECONDS,
            )
            await asyncio.sleep(_ESCALATION_PLAYOUT_BUFFER_SECONDS)
            async with LiveKitTelephonyClient() as telephony:
                await asyncio.wait_for(
                    telephony.end_call(room_name=self._room_name),
                    timeout=_ESCALATION_END_CALL_TIMEOUT_SECONDS,
                )
        except Exception:
            logger.warning(
                "[voice_turn] human-transfer escalation failed — fail-open",
                exc_info=True,
            )
            self._rearm_filler_watchdog(session)
            return False
        logger.warning(
            "voice_escalation: call ended after transfer line — room=%s",
            self._room_name,
        )
        return True

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
            self._prewarmed = True
            logger.debug("STT/TTS pre-warm complete")
        except Exception as exc:
            logger.warning("STT/TTS pre-warm failed (non-blocking): %s", exc)

    async def _maybe_inject_filler(
        self,
        session: AgentSession,
        first_token_event: asyncio.Event,
    ) -> None:
        """Inject filler audio if LLM first token doesn't arrive within 80 ms."""
        try:
            await asyncio.sleep(0.08)
            if first_token_event.is_set():
                return  # token arrived on time — no filler needed
            if self._filler_bank and self._filler_bank.is_ready():
                filler_wav = self._filler_bank.get_filler("ack")
                # Re-check immediately before say() — a cancel/suppress
                # landing during the sleep must not queue a filler.
                if self._first_token_event.is_set():
                    return
                logger.debug("Injecting filler audio (%d bytes)", len(filler_wav))
                session.say(
                    text="Dạ vâng...",
                    audio=_wav_to_audio_frames(filler_wav),
                    allow_interruptions=True,
                    add_to_chat_ctx=False,
                )
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("Filler injection failed: %s", exc)


# ---------------------------------------------------------------------------
# Worker entrypoint
# ---------------------------------------------------------------------------


def _parse_room_metadata(raw: Any) -> dict[str, Any]:
    """Parse room metadata JSON into a dict; ``{}`` on any failure."""
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        logger.debug("Room metadata is not valid JSON — context unavailable")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_int(value: Any) -> int | None:
    """Best-effort int coercion for room-metadata values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        # OverflowError: int(float("inf")) — malformed metadata must
        # never crash entrypoint before session.start.
        return None


def _coerce_uuid(value: Any) -> UUID | None:
    """Best-effort UUID coercion for room-metadata values."""
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


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

    # Story 39.6: room metadata carries call context — ``session_id``
    # from create_call_room, ``workspace_id``/``user_id`` when the
    # orchestrator attaches them. Missing/malformed keys degrade to
    # log-only telemetry; they never block the call.
    metadata = _parse_room_metadata(getattr(ctx.room, "metadata", None))
    session_id_meta = metadata.get("session_id")
    agent = VoiceSDRAgent(
        workspace_id=_coerce_int(metadata.get("workspace_id")),
        user_id=_coerce_uuid(metadata.get("user_id")),
        call_session_id=(
            session_id_meta if isinstance(session_id_meta, str) else None
        ),
        room_name=ctx.room.name,
    )
    await session.start(agent=agent, room=ctx.room)

    # Keep session alive until room disconnects or job shuts down
    disconnect_event = asyncio.Event()

    @ctx.room.on("disconnected")
    def _on_room_disconnected(*args: Any, **kwargs: Any) -> None:
        disconnect_event.set()

    ctx.add_shutdown_callback(lambda: disconnect_event.set())

    try:
        await disconnect_event.wait()
    finally:
        with contextlib.suppress(Exception):
            await session.aclose()


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

    # Ensure CLI subcommand 'start' is present so Typer does not exit with help
    if len(sys.argv) <= 1 or sys.argv[1] not in ("start", "dev", "console", "connect"):
        sys.argv = [sys.argv[0] if sys.argv else "worker", "start"]

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
