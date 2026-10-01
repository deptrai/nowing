"""Unit tests for VoiceAgentWorker and VoiceWorkerPool (Story 38.2).

Hermetic tests covering:
- SEQUENCER_VOICE_ENABLED feature gate (fail-closed)
- VAD state tensor isolation between sessions
- Pre-warm STT/TTS call sequencing
- Worker pool spawn/shutdown lifecycle
- FillerAudioBank RAM loading and fallback
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.voice.filler_audio import FillerAudioBank, FillerAudioError
from app.services.voice.worker_pool import VoiceWorkerPool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def filler_dir(tmp_path: Path) -> Path:
    """Create a temp dir with minimal WAV files for FillerAudioBank."""
    import struct

    def _make_wav(path: Path, n_samples: int = 100) -> None:
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + n_samples * 2, b"WAVE",
            b"fmt ", 16, 1, 1, 24000, 48000, 2, 16,
            b"data", n_samples * 2,
        )
        path.write_bytes(header + b"\x00" * (n_samples * 2))

    _make_wav(tmp_path / "ack_da_vang.wav")
    _make_wav(tmp_path / "thinking_um.wav")
    _make_wav(tmp_path / "hold_xin_loi.wav")
    _make_wav(tmp_path / "breath_50ms.wav")
    return tmp_path


@pytest.fixture
def filler_bank(filler_dir: Path) -> FillerAudioBank:
    return FillerAudioBank(filler_dir=str(filler_dir))


# ---------------------------------------------------------------------------
# FillerAudioBank tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFillerAudioBank:
    """FillerAudioBank loads WAV files into RAM at startup."""

    def test_loads_all_known_fillers(self, filler_bank: FillerAudioBank):
        """All 4 canonical filler kinds are loaded from disk."""
        kinds = filler_bank.available_kinds()
        assert "ack" in kinds
        assert "thinking" in kinds
        assert "hold" in kinds
        assert "breath" in kinds

    def test_get_filler_returns_bytes(self, filler_bank: FillerAudioBank):
        """get_filler returns non-empty bytes for each loaded kind."""
        for kind in filler_bank.available_kinds():
            data = filler_bank.get_filler(kind)
            assert isinstance(data, bytes)
            assert len(data) > 0
            assert data[:4] == b"RIFF"  # WAV magic bytes

    def test_get_filler_fallback_when_kind_missing(self, tmp_path: Path):
        """Missing kind falls back to first available clip."""
        import struct
        # Only create 'ack' file
        n = 50
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + n * 2, b"WAVE",
            b"fmt ", 16, 1, 1, 24000, 48000, 2, 16,
            b"data", n * 2,
        )
        (tmp_path / "ack_da_vang.wav").write_bytes(header + b"\x00" * (n * 2))

        bank = FillerAudioBank(filler_dir=str(tmp_path))
        data = bank.get_filler("thinking")  # not loaded — should fallback
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_empty_dir_raises_on_get_filler(self, tmp_path: Path):
        """Empty filler directory → FillerAudioError on get_filler."""
        bank = FillerAudioBank(filler_dir=str(tmp_path / "nonexistent"))
        assert not bank.is_ready()
        with pytest.raises(FillerAudioError):
            bank.get_filler("ack")

    def test_is_ready_false_when_empty(self, tmp_path: Path):
        """is_ready() returns False when no clips loaded."""
        bank = FillerAudioBank(filler_dir=str(tmp_path / "empty_dir"))
        assert bank.is_ready() is False

    def test_is_ready_true_when_loaded(self, filler_bank: FillerAudioBank):
        """is_ready() returns True after successful load."""
        assert filler_bank.is_ready() is True


# ---------------------------------------------------------------------------
# VoiceWorkerPool tests
# ---------------------------------------------------------------------------

def _stub_worker(worker_id: int) -> None:
    """Module-level stub worker — picklable by multiprocessing."""
    time.sleep(0.05)  # brief sleep then exit cleanly


@pytest.mark.unit
class TestVoiceWorkerPool:
    """VoiceWorkerPool manages N worker subprocesses."""

    def _make_pool_with_stub(self, n: int) -> VoiceWorkerPool:
        """Create pool with stub target injected via Process monkeypatch."""
        pool = VoiceWorkerPool(num_workers=n)
        return pool

    def test_spawn_workers_creates_n_handles(self):
        """spawn_workers creates exactly num_workers WorkerHandles."""
        pool = VoiceWorkerPool(num_workers=3)

        # Patch Process to use stub instead of real worker
        class StubProcess:
            def __init__(self, target=None, args=(), name=None, daemon=None):
                self._target = target
                self._args = args
                self._name = name
                self.daemon = daemon
                self._alive = False
                self._pid = 90000 + (args[0] if args else 0)

            def start(self):
                self._alive = True

            def join(self, timeout=None):
                self._alive = False

            def is_alive(self):
                return self._alive

            def kill(self):
                self._alive = False

            @property
            def pid(self):
                return self._pid

        with patch(
            "app.services.voice.worker_pool.multiprocessing.Process",
            StubProcess,
        ):
            handles = pool.spawn_workers()
            assert len(handles) == 3
            assert pool.alive_count() == 3

        pool.shutdown()

    def test_spawn_raises_if_already_running(self):
        """Calling spawn_workers twice raises RuntimeError."""
        pool = VoiceWorkerPool(num_workers=1)

        class _StubProc:
            def __init__(self, **kw):
                pass
            def start(self): pass
            def join(self, timeout=None): pass
            def is_alive(self): return True
            def kill(self): pass
            @property
            def pid(self): return 9999

        with patch(
            "app.services.voice.worker_pool.multiprocessing.Process",
            lambda **kw: _StubProc(**kw),
        ):
            pool.spawn_workers()
            with pytest.raises(RuntimeError, match="already spawned"):
                pool.spawn_workers()
        pool.shutdown()

    def test_is_alive_reflects_worker_state(self):
        """is_alive returns True for running worker, False after shutdown."""
        pool = VoiceWorkerPool(num_workers=1)

        class _StubProc:
            def __init__(self, **kw): self._alive = False
            def start(self): self._alive = True
            def join(self, timeout=None): self._alive = False
            def is_alive(self): return self._alive
            def kill(self): self._alive = False
            @property
            def pid(self): return 9998

        with patch(
            "app.services.voice.worker_pool.multiprocessing.Process",
            lambda **kw: _StubProc(**kw),
        ):
            pool.spawn_workers()
            assert pool.is_alive(0) is True
            pool.shutdown()
            assert pool.is_alive(0) is False

    def test_health_returns_summary_dict(self):
        """health() returns expected keys."""
        pool = VoiceWorkerPool(num_workers=3)

        class _StubProc:
            def __init__(self, **kw): pass
            def start(self): pass
            def join(self, timeout=None): pass
            def is_alive(self): return True
            def kill(self): pass
            @property
            def pid(self): return 9997

        with patch(
            "app.services.voice.worker_pool.multiprocessing.Process",
            lambda **kw: _StubProc(**kw),
        ):
            pool.spawn_workers()
            h = pool.health()
            assert h["total_workers"] == 3
            assert "alive_workers" in h
            assert "workers" in h
            assert len(h["workers"]) == 3
        pool.shutdown()

    def test_context_manager_spawns_and_shuts_down(self):
        """Pool works as context manager."""
        class _StubProc:
            def __init__(self, **kw): self._alive = False
            def start(self): self._alive = True
            def join(self, timeout=None): self._alive = False
            def is_alive(self): return self._alive
            def kill(self): self._alive = False
            @property
            def pid(self): return 9996

        with patch(
            "app.services.voice.worker_pool.multiprocessing.Process",
            lambda **kw: _StubProc(**kw),
        ):
            with VoiceWorkerPool(num_workers=1) as pool:
                assert pool.alive_count() == 1
            assert pool.alive_count() == 0


# ---------------------------------------------------------------------------
# Feature gate tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSequencerVoiceEnabledGate:
    """SEQUENCER_VOICE_ENABLED must gate all voice worker activity."""

    @pytest.mark.asyncio
    async def test_entrypoint_rejects_when_flag_off(self):
        """entrypoint returns immediately when SEQUENCER_VOICE_ENABLED=False."""
        from app.services.voice import agent_worker

        mock_ctx = MagicMock()
        mock_ctx.room.name = "call_test_001"

        with patch.object(agent_worker, "SEQUENCER_VOICE_ENABLED", False):
            await agent_worker.entrypoint(mock_ctx)
            # connect() must NOT be called
            mock_ctx.connect.assert_not_called()

    def test_run_worker_exits_when_flag_off(self):
        """run_worker raises SystemExit(1) when SEQUENCER_VOICE_ENABLED=False."""
        from app.services.voice import agent_worker

        with patch.object(agent_worker, "SEQUENCER_VOICE_ENABLED", False):
            with pytest.raises(SystemExit) as exc_info:
                agent_worker.run_worker()
            assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Sequencer channel validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestVoiceChannelCompliance:
    """validate_step_channel must accept 'voice' only when flag is on."""

    @pytest.mark.asyncio
    async def test_voice_channel_rejected_when_flag_off(self):
        """'voice' channel raises DeferredChannelError when flag is off."""
        from app.services.sequencer.compliance import SequencerComplianceMixin
        from app.services.sequencer.constants import DeferredChannelError

        mixin = SequencerComplianceMixin()
        with patch("app.services.sequencer.compliance.config") as mock_cfg:
            mock_cfg.SEQUENCER_VOICE_ENABLED = False
            mock_cfg.SEQUENCER_OUTBOUND_CHANNELS = ["email"]
            with pytest.raises(DeferredChannelError, match="voice"):
                await mixin.validate_step_channel("voice")

    @pytest.mark.asyncio
    async def test_voice_channel_accepted_when_flag_on(self):
        """'voice' channel returns True when SEQUENCER_VOICE_ENABLED=True."""
        from app.services.sequencer.compliance import SequencerComplianceMixin

        mixin = SequencerComplianceMixin()
        with patch("app.services.sequencer.compliance.config") as mock_cfg:
            mock_cfg.SEQUENCER_VOICE_ENABLED = True
            result = await mixin.validate_step_channel("voice")
            assert result is True

    @pytest.mark.asyncio
    async def test_email_channel_still_accepted(self):
        """'email' channel still passes validation normally."""
        from app.services.sequencer.compliance import SequencerComplianceMixin

        mixin = SequencerComplianceMixin()
        with patch("app.services.sequencer.compliance.config") as mock_cfg:
            mock_cfg.SEQUENCER_VOICE_ENABLED = False
            mock_cfg.SEQUENCER_OUTBOUND_CHANNELS = ["email"]
            result = await mixin.validate_step_channel("email")
            assert result is True


# ---------------------------------------------------------------------------
# Story 38.2 Review Patch Tests: VoiceSDRAgent, Providers, VAD Isolation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestVoiceSDRAgentLifecycle:
    """Tests for VoiceSDRAgent lifecycle hooks and provider factories."""

    def test_build_stt_deepgram(self):
        """_build_stt returns deepgram STT when API key is present."""
        from app.services.voice import agent_worker

        with patch.object(agent_worker, "VOICE_STT_PROVIDER", "deepgram"), \
             patch.object(agent_worker, "DEEPGRAM_API_KEY", "mock-key"), \
             patch("livekit.plugins.deepgram.STT") as mock_dg:
            res = agent_worker._build_stt()
            mock_dg.assert_called_once_with(model="nova-2", language="vi", api_key="mock-key")
            assert res == mock_dg.return_value

    def test_build_stt_fallback_whisper(self):
        """_build_stt falls back to WhisperSTTAdapter when Deepgram key missing."""
        from app.services.voice import agent_worker

        with patch.object(agent_worker, "VOICE_STT_PROVIDER", "deepgram"), \
             patch.object(agent_worker, "DEEPGRAM_API_KEY", ""), \
             patch("app.services.stt_service.STTService"):
            res = agent_worker._build_stt()
            assert isinstance(res, agent_worker._WhisperSTTAdapter)

    def test_build_tts_openai(self):
        """_build_tts returns OpenAI TTS when API key is present."""
        from app.services.voice import agent_worker

        with patch.object(agent_worker, "VOICE_TTS_PROVIDER", "openai"), \
             patch.object(agent_worker, "OPENAI_API_KEY", "mock-key"), \
             patch("livekit.plugins.openai.TTS") as mock_tts:
            res = agent_worker._build_tts()
            mock_tts.assert_called_once_with(model="tts-1", voice="nova", api_key="mock-key")
            assert res == mock_tts.return_value

    def test_build_tts_missing_key_raises(self):
        """_build_tts raises RuntimeError when OPENAI_API_KEY missing for Vietnamese."""
        from app.services.voice import agent_worker

        with (
            patch.object(agent_worker, "OPENAI_API_KEY", ""),
            pytest.raises(RuntimeError, match="No supported Vietnamese TTS provider"),
        ):
            agent_worker._build_tts()

    def test_build_llm_anthropic(self):
        """_build_llm returns Anthropic LLM when API key is present."""
        from app.services.voice import agent_worker

        with patch.object(agent_worker, "VOICE_LLM_PROVIDER", "anthropic"), \
             patch.object(agent_worker, "ANTHROPIC_API_KEY", "mock-key"), \
             patch("livekit.plugins.anthropic.LLM") as mock_llm:
            res = agent_worker._build_llm()
            mock_llm.assert_called_once_with(model="claude-sonnet-4-6", api_key="mock-key")
            assert res == mock_llm.return_value

    def test_build_vad_state_tensor_isolation(self):
        """Each _build_vad call returns a fresh isolated VAD instance."""
        from app.services.voice import agent_worker

        with patch("livekit.plugins.silero.VAD.load") as mock_vad:
            mock_vad.side_effect = lambda **kwargs: MagicMock()
            vad1 = agent_worker._build_vad()
            vad2 = agent_worker._build_vad()
            assert vad1 is not vad2
            assert mock_vad.call_count == 2

    @pytest.mark.asyncio
    async def test_agent_lifecycle_hooks_signatures(self):
        """on_enter and on_exit take 0 arguments, on_user_turn_completed takes 2."""
        from app.services.voice.agent_worker import VoiceSDRAgent

        agent = VoiceSDRAgent()
        # Verify no TypeError when called with expected framework signatures
        with patch.object(VoiceSDRAgent, "session", property(lambda self: MagicMock())):
            await agent.on_enter()
            await agent.on_exit()

    @pytest.mark.asyncio
    async def test_wav_to_audio_frames_decodes(self, filler_dir: Path):
        """_wav_to_audio_frames decodes raw WAV bytes into rtc.AudioFrame."""
        from app.services.voice.agent_worker import _wav_to_audio_frames

        wav_path = filler_dir / "ack_da_vang.wav"
        wav_bytes = wav_path.read_bytes()

        frames = [f async for f in _wav_to_audio_frames(wav_bytes)]
        assert len(frames) == 1
        assert frames[0].sample_rate == 24000
        assert frames[0].num_channels == 1
        assert frames[0].samples_per_channel > 0


# ---------------------------------------------------------------------------
# Story 39.6: Post-STT semantic decisions in on_user_turn_completed
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVoiceSDRAgentSemanticGate:
    """Semantic gating: suppress / transfer / frustration / fail-open."""

    @staticmethod
    def _msg(text: str) -> MagicMock:
        msg = MagicMock()
        msg.text_content = text
        return msg

    @staticmethod
    def _session_with_say() -> MagicMock:
        session = MagicMock()
        handle = MagicMock()
        handle.wait_for_playout = AsyncMock()
        session.say = MagicMock(return_value=handle)
        return session

    @staticmethod
    async def _cleanup(agent) -> None:
        """Release the filler watchdog task so tests don't leak it."""
        await agent.on_exit()

    @pytest.mark.asyncio
    async def test_suppress_raises_stop_response_and_cancels_filler(self):
        """Confident no-response → filler cancelled, StopResponse, no say()."""
        from livekit.agents.llm import StopResponse

        from app.services.voice import agent_worker
        from app.services.voice.agent_worker import (
            VoiceSDRAgent,
            VoiceTurnAssessment,
        )

        agent = VoiceSDRAgent()
        session = self._session_with_say()
        assessment = VoiceTurnAssessment(suppress_response=True)

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            agent_worker,
            "evaluate_voice_turn",
            AsyncMock(return_value=assessment),
        ) as mock_eval, pytest.raises(StopResponse):
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("vâng ạ")
            )

        mock_eval.assert_awaited_once()
        assert agent._first_token_event.is_set()
        session.interrupt.assert_called_once()  # cut any in-flight filler
        session.say.assert_not_called()  # no dangling filler, no line
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_transfer_says_line_waits_and_ends_call(self):
        """Confident transfer → say → wait_for_playout → end_call → stop."""
        from livekit.agents.llm import StopResponse

        from app.services.voice import agent_worker
        from app.services.voice.agent_worker import (
            VoiceSDRAgent,
            VoiceTurnAssessment,
        )

        user_id = uuid4()
        agent = VoiceSDRAgent(
            workspace_id=7,
            user_id=user_id,
            call_session_id="sess-1",
            room_name="call_sess-1",
        )
        session = self._session_with_say()
        assessment = VoiceTurnAssessment(transfer=True)

        telephony_client = MagicMock()
        telephony_client.__aenter__.return_value.end_call = AsyncMock()

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            agent_worker,
            "evaluate_voice_turn",
            AsyncMock(return_value=assessment),
        ) as mock_eval, patch.object(
            agent_worker,
            "LiveKitTelephonyClient",
            return_value=telephony_client,
        ) as client_cls, pytest.raises(StopResponse):
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("cho tôi nói chuyện với người thật")
            )

        mock_eval.assert_awaited_once_with(
            "cho tôi nói chuyện với người thật",
            workspace_id=7,
            user_id=user_id,
            client_id="sess-1",
        )
        client_cls.assert_called_once_with()
        session.interrupt.assert_called_once()  # no filler overlapping line
        session.say.assert_called_once()
        say_kwargs = session.say.call_args
        assert say_kwargs.args[0] == agent_worker._VOICE_TRANSFER_LINE
        assert say_kwargs.kwargs["allow_interruptions"] is False
        assert say_kwargs.kwargs["add_to_chat_ctx"] is False
        session.say.return_value.wait_for_playout.assert_awaited_once()
        telephony_client.__aenter__.return_value.end_call.assert_awaited_once_with(
            room_name="call_sess-1"
        )
        assert agent._first_token_event.is_set()
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_transfer_wins_over_suppress(self):
        """Both flags set → escalation path runs, suppression ignored."""
        from livekit.agents.llm import StopResponse

        from app.services.voice import agent_worker
        from app.services.voice.agent_worker import (
            VoiceSDRAgent,
            VoiceTurnAssessment,
        )

        agent = VoiceSDRAgent(room_name="call_x")
        session = self._session_with_say()
        assessment = VoiceTurnAssessment(suppress_response=True, transfer=True)

        telephony_client = MagicMock()
        telephony_client.__aenter__.return_value.end_call = AsyncMock()

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            agent_worker,
            "evaluate_voice_turn",
            AsyncMock(return_value=assessment),
        ), patch.object(
            agent_worker,
            "LiveKitTelephonyClient",
            return_value=telephony_client,
        ), pytest.raises(StopResponse):
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("gặp người thật")
            )

        # Escalation ran — the canned line was played, not just silence.
        session.say.assert_called_once()
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_transfer_without_room_name_fails_open(self):
        """Transfer intent but no room_name → cannot end_call → generate."""
        from app.services.voice import agent_worker
        from app.services.voice.agent_worker import (
            VoiceSDRAgent,
            VoiceTurnAssessment,
        )

        agent = VoiceSDRAgent()  # no room_name
        session = self._session_with_say()
        assessment = VoiceTurnAssessment(transfer=True)

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            agent_worker,
            "evaluate_voice_turn",
            AsyncMock(return_value=assessment),
        ):
            # Returns normally — no StopResponse, no say(), no end_call.
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("gặp người thật")
            )

        session.say.assert_not_called()
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_transfer_end_call_failure_fails_open(self):
        """end_call raising → fail-open, turn generates normally."""
        from app.services.voice import agent_worker
        from app.services.voice.agent_worker import (
            VoiceSDRAgent,
            VoiceTurnAssessment,
        )

        agent = VoiceSDRAgent(room_name="call_y")
        session = self._session_with_say()
        assessment = VoiceTurnAssessment(transfer=True)

        telephony_client = MagicMock()
        telephony_client.__aenter__.return_value.end_call = AsyncMock(
            side_effect=RuntimeError("livekit down")
        )

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            agent_worker,
            "evaluate_voice_turn",
            AsyncMock(return_value=assessment),
        ), patch.object(
            agent_worker,
            "LiveKitTelephonyClient",
            return_value=telephony_client,
        ):
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("gặp người thật")
            )

        session.say.assert_called_once()  # line played, teardown failed
        # Fail-open re-arms the filler watchdog for the generation path —
        # a dead watchdog would mean dead air on a slow LLM first token.
        assert agent._filler_task is not None
        assert not agent._filler_task.done()
        assert not agent._first_token_event.is_set()
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_frustration_logs_and_continues(self, monkeypatch, caplog):
        """Frustration score → structured [voice_turn] log; generation proceeds."""
        monkeypatch.setenv("DECISION_ENABLED", "true")
        monkeypatch.setenv("DECISION_VOICE_ENABLED", "true")
        from app.services.decision.types import Answer, DecisionResult
        from app.services.voice import semantic_gate
        from app.services.voice.agent_worker import VoiceSDRAgent

        agent = VoiceSDRAgent()
        session = self._session_with_say()
        service = MagicMock()
        service.decide = AsyncMock(
            return_value=DecisionResult(
                answers={
                    "should_respond": Answer(
                        kind="noul", value=0.9, confidence=0.9
                    ),
                    "caller_frustration": Answer(
                        kind="score", value=2.5, confidence=0.8
                    ),
                    "transfer_to_human": Answer(
                        kind="noul", value=0.1, confidence=0.1
                    ),
                },
                model="jev-1.13.0",
                backend="jev",
                latency_ms=100.0,
            )
        )

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            semantic_gate, "get_decision_service", return_value=service
        ), caplog.at_level("INFO", logger="app.services.voice.semantic_gate"):
            # Returns normally — generation proceeds.
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("sao gọi hoài vậy, phiền quá")
            )

        assert "[voice_turn] frustration=2.5" in caplog.text
        service.decide.assert_awaited_once()
        session.say.assert_not_called()
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_local_backchannel_suppresses_without_jev(self, monkeypatch):
        """'ừ' suppresses via LOCAL_BACKCHANNELS — StopResponse, zero decide."""
        from livekit.agents.llm import StopResponse

        monkeypatch.setenv("DECISION_ENABLED", "true")
        monkeypatch.setenv("DECISION_VOICE_ENABLED", "true")
        from app.services.voice import semantic_gate
        from app.services.voice.agent_worker import VoiceSDRAgent

        agent = VoiceSDRAgent()
        session = self._session_with_say()
        service = MagicMock()
        service.decide = AsyncMock()

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            semantic_gate, "get_decision_service", return_value=service
        ), pytest.raises(StopResponse):
            await agent.on_user_turn_completed(MagicMock(), self._msg("ừ"))

        service.decide.assert_not_called()
        session.interrupt.assert_called_once()
        session.say.assert_not_called()
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_evaluation_exception_fails_open(self):
        """decide() exploding (timeout/error) → normal generation."""
        from app.services.voice import agent_worker
        from app.services.voice.agent_worker import VoiceSDRAgent

        agent = VoiceSDRAgent()
        session = self._session_with_say()

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            agent_worker,
            "evaluate_voice_turn",
            AsyncMock(side_effect=RuntimeError("decide timeout")),
        ):
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("cho tôi hỏi giá nhà")
            )

        session.say.assert_not_called()
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_flags_off_means_zero_decide_calls(self, monkeypatch):
        """DECISION_ENABLED=false → real gate short-circuits, no call."""
        monkeypatch.setenv("DECISION_ENABLED", "false")
        from app.services.voice import semantic_gate
        from app.services.voice.agent_worker import VoiceSDRAgent

        agent = VoiceSDRAgent()
        session = self._session_with_say()
        service = MagicMock()
        service.decide = AsyncMock()

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            semantic_gate, "get_decision_service", return_value=service
        ):
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("vâng ạ")
            )

        service.decide.assert_not_called()
        session.say.assert_not_called()
        await self._cleanup(agent)

    @pytest.mark.asyncio
    async def test_empty_transcript_skips_decide(self, monkeypatch):
        """Whitespace transcript → gate early-returns, no paid call."""
        monkeypatch.setenv("DECISION_ENABLED", "true")
        monkeypatch.setenv("DECISION_VOICE_ENABLED", "true")
        from app.services.voice import semantic_gate
        from app.services.voice.agent_worker import VoiceSDRAgent

        agent = VoiceSDRAgent()
        session = self._session_with_say()
        service = MagicMock()
        service.decide = AsyncMock()

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ), patch.object(
            semantic_gate, "get_decision_service", return_value=service
        ):
            await agent.on_user_turn_completed(
                MagicMock(), self._msg("   ")
            )

        service.decide.assert_not_called()
        await self._cleanup(agent)


@pytest.mark.unit
class TestEntrypointMetadataPlumbing:
    """entrypoint parses ctx.room.metadata into VoiceSDRAgent context."""

    @pytest.mark.asyncio
    async def test_entrypoint_passes_metadata_context(self):
        """workspace_id/user_id/session_id/room_name reach the agent."""
        from app.services.voice import agent_worker

        user_id = uuid4()
        ctx = MagicMock()
        ctx.room.name = "call_sess-9"
        ctx.room.metadata = json.dumps(
            {
                "session_id": "sess-9",
                "workspace_id": 7,
                "user_id": str(user_id),
            }
        )
        ctx.connect = AsyncMock()

        # Fire "disconnected" immediately on registration so the
        # entrypoint's wait loop exits right after session.start.
        def _on(_event: str):
            def _deco(fn):
                fn()
                return fn

            return _deco

        ctx.room.on = MagicMock(side_effect=_on)
        session = MagicMock()
        session.start = AsyncMock()
        session.aclose = AsyncMock()

        with patch.object(
            agent_worker, "SEQUENCER_VOICE_ENABLED", True
        ), patch.object(
            agent_worker, "AgentSession", return_value=session
        ), patch.object(agent_worker, "_build_stt"), patch.object(
            agent_worker, "_build_llm"
        ), patch.object(agent_worker, "_build_tts"), patch.object(
            agent_worker, "_build_vad"
        ), patch.object(
            agent_worker, "VoiceSDRAgent"
        ) as agent_cls:
            await agent_worker.entrypoint(ctx)

        kwargs = agent_cls.call_args.kwargs
        assert kwargs["workspace_id"] == 7
        assert kwargs["user_id"] == user_id
        assert kwargs["call_session_id"] == "sess-9"
        assert kwargs["room_name"] == "call_sess-9"
        session.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_entrypoint_missing_metadata_is_log_only(self):
        """No/malformed metadata → Nones, call still proceeds."""
        from app.services.voice import agent_worker

        ctx = MagicMock()
        ctx.room.name = "call_plain"
        ctx.room.metadata = "not-json{"
        ctx.connect = AsyncMock()

        def _on(_event: str):
            def _deco(fn):
                fn()
                return fn

            return _deco

        ctx.room.on = MagicMock(side_effect=_on)
        session = MagicMock()
        session.start = AsyncMock()
        session.aclose = AsyncMock()

        with patch.object(
            agent_worker, "SEQUENCER_VOICE_ENABLED", True
        ), patch.object(
            agent_worker, "AgentSession", return_value=session
        ), patch.object(agent_worker, "_build_stt"), patch.object(
            agent_worker, "_build_llm"
        ), patch.object(agent_worker, "_build_tts"), patch.object(
            agent_worker, "_build_vad"
        ), patch.object(
            agent_worker, "VoiceSDRAgent"
        ) as agent_cls:
            await agent_worker.entrypoint(ctx)

        kwargs = agent_cls.call_args.kwargs
        assert kwargs["workspace_id"] is None
        assert kwargs["user_id"] is None
        assert kwargs["call_session_id"] is None
        assert kwargs["room_name"] == "call_plain"

    @pytest.mark.asyncio
    async def test_entrypoint_inf_workspace_id_does_not_crash(self):
        """JSON ``1e999`` parses to float inf → int() would OverflowError;
        _coerce_int must swallow it so the call still starts."""
        from app.services.voice import agent_worker

        ctx = MagicMock()
        ctx.room.name = "call_inf"
        ctx.room.metadata = '{"session_id": "s1", "workspace_id": 1e999}'
        ctx.connect = AsyncMock()

        def _on(_event: str):
            def _deco(fn):
                fn()
                return fn

            return _deco

        ctx.room.on = MagicMock(side_effect=_on)
        session = MagicMock()
        session.start = AsyncMock()
        session.aclose = AsyncMock()

        with patch.object(
            agent_worker, "SEQUENCER_VOICE_ENABLED", True
        ), patch.object(
            agent_worker, "AgentSession", return_value=session
        ), patch.object(agent_worker, "_build_stt"), patch.object(
            agent_worker, "_build_llm"
        ), patch.object(agent_worker, "_build_tts"), patch.object(
            agent_worker, "_build_vad"
        ), patch.object(
            agent_worker, "VoiceSDRAgent"
        ) as agent_cls:
            await agent_worker.entrypoint(ctx)

        kwargs = agent_cls.call_args.kwargs
        assert kwargs["workspace_id"] is None
        assert kwargs["call_session_id"] == "s1"
        session.start.assert_awaited_once()


# ---------------------------------------------------------------------------
# Story 38.3: Anti-False-Interruption & Multi-tier Barge-in Integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVoiceSDRAgentBargeIn:
    """Tests for VoiceSDRAgent barge-in integration in tts_node and speech events."""

    @staticmethod
    def _session_with_say() -> MagicMock:
        session = MagicMock()
        handle = MagicMock()
        handle.wait_for_playout = AsyncMock()
        session.say = MagicMock(return_value=handle)
        session.interrupt = MagicMock()
        session.on = MagicMock()
        return session

    @staticmethod
    def _make_tts_frame() -> object:
        """A minimal valid TTS output frame (20ms @ 48kHz mono)."""
        from livekit import rtc

        return rtc.AudioFrame.create(
            sample_rate=48000, num_channels=1, samples_per_channel=960
        )

    def test_barge_in_engine_flag_gated(self):
        """SEQUENCER_VOICE_ENABLED=True enables engine; False leaves it None."""
        from app.services.voice import agent_worker
        from app.services.voice.agent_worker import VoiceSDRAgent

        with patch.object(agent_worker, "SEQUENCER_VOICE_ENABLED", True):
            agent_enabled = VoiceSDRAgent()
            assert agent_enabled.barge_in_engine is not None
            assert agent_enabled.barge_in_engine.enabled is True

        with patch.object(agent_worker, "SEQUENCER_VOICE_ENABLED", False):
            agent_disabled = VoiceSDRAgent()
            assert agent_disabled.barge_in_engine is None

    @pytest.mark.asyncio
    async def test_tts_node_applies_ducking_gain(self):
        """tts_node applies ducking gain from BargeInEngine to audio frames."""
        import numpy as np
        from livekit import rtc

        from app.services.voice.agent_worker import VoiceSDRAgent
        from app.services.voice.barge_in import BargeInEngine, BargeInState

        engine = BargeInEngine(enabled=True)
        agent = VoiceSDRAgent(barge_in_engine=engine)

        frame1 = rtc.AudioFrame.create(
            sample_rate=24000, num_channels=1, samples_per_channel=4
        )
        samples = np.array([10000, -10000, 20000, -20000], dtype=np.int16)
        frame1.data.cast("B")[:] = samples.tobytes()

        frame2 = rtc.AudioFrame.create(
            sample_rate=24000, num_channels=1, samples_per_channel=4
        )
        frame2.data.cast("B")[:] = samples.tobytes()

        async def mock_default_tts_node(self_agent, clauses, model_settings):
            async for _ in clauses:
                pass
            yield frame1
            # Customer speaks after 450ms lockout -> triggers ducking
            engine.on_speech_detected(
                0.95, timestamp=engine._bot_speaking_started_at + 0.45
            )
            engine.ducking_controller.get_gain_db = MagicMock(return_value=-14.0)
            yield frame2

        async def text_stream():
            yield "Chào bạn, tôi là trợ lý ảo."

        with patch(
            "livekit.agents.voice.agent.Agent.default.tts_node",
            mock_default_tts_node,
        ):
            frames = [f async for f in agent.tts_node(text_stream(), MagicMock())]
            assert len(frames) == 2

            # Frame 1: before customer speaks, 0dB gain
            res1 = np.frombuffer(frames[0].data, dtype=np.int16)
            np.testing.assert_array_equal(res1, samples)

            # Frame 2: after customer speaks, -14dB gain applied
            res2 = np.frombuffer(frames[1].data, dtype=np.int16)
            factor = 10.0 ** (-14.0 / 20.0)
            expected = np.clip(
                np.round(samples * factor), -32768, 32767
            ).astype(np.int16)
            np.testing.assert_array_equal(res2, expected)

        # After tts_node generator completes, bot speech is stopped
        assert engine.state == BargeInState.IDLE

    @pytest.mark.asyncio
    async def test_tts_node_passthrough_when_engine_disabled(self):
        """When barge-in is disabled, tts_node passes frames through unmodified."""
        import numpy as np
        from livekit import rtc

        from app.services.voice.agent_worker import VoiceSDRAgent

        agent = VoiceSDRAgent(barge_in_engine=None)

        frame = rtc.AudioFrame.create(
            sample_rate=24000, num_channels=1, samples_per_channel=4
        )
        samples = np.array([5000, -5000, 10000, -10000], dtype=np.int16)
        frame.data.cast("B")[:] = samples.tobytes()

        async def mock_default_tts_node(self_agent, clauses, model_settings):
            async for _ in clauses:
                pass
            yield frame

        async def text_stream():
            yield "Hello"

        with patch(
            "livekit.agents.voice.agent.Agent.default.tts_node",
            mock_default_tts_node,
        ):
            frames = [f async for f in agent.tts_node(text_stream(), MagicMock())]
            assert len(frames) == 1
            res = np.frombuffer(frames[0].data, dtype=np.int16)
            np.testing.assert_array_equal(res, samples)

    @pytest.mark.asyncio
    async def test_preflight_transcript_triggers_interrupt_and_silence_packet(self):
        """PREFLIGHT_TRANSCRIPT for real speech calls session.interrupt and silence."""
        from livekit.agents import stt

        from app.services.voice.agent_worker import (
            BargeInEngine,
            BargeInState,
            VoiceSDRAgent,
        )

        session = self._session_with_say()
        engine = BargeInEngine(enabled=True)
        agent = VoiceSDRAgent(barge_in_engine=engine)

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ):
            # Bot speech started 1 second ago
            t0 = 1000.0
            engine.on_bot_speech_started(timestamp=t0)

            # Customer interrupts with real speech
            ev = stt.SpeechEvent(
                type=stt.SpeechEventType.PREFLIGHT_TRANSCRIPT,
                alternatives=[
                    stt.SpeechData(
                        text="Khoan đã em ơi",
                        language="vi",
                        confidence=0.95,
                    )
                ],
            )

            state = await agent.handle_speech_event(ev)
            assert state == BargeInState.INTERRUPTED

            # session.interrupt() called to kill turn in < 50ms
            session.interrupt.assert_called_once()

            # 40ms silence packet sent. allow_interruptions=False so the
            # silence dispatches immediately instead of queueing behind
            # _user_silence_event (the customer is mid-barge-in, not silent).
            session.say.assert_called_once()
            say_kwargs = session.say.call_args
            text_arg = say_kwargs.kwargs.get("text", say_kwargs.args[0] if say_kwargs.args else "")
            assert text_arg == ""
            assert say_kwargs.kwargs["allow_interruptions"] is False
            assert say_kwargs.kwargs["add_to_chat_ctx"] is False

    @pytest.mark.asyncio
    async def test_preflight_transcript_filler_does_not_interrupt(self):
        """PREFLIGHT_TRANSCRIPT with filler ('dạ') recovers gain, no interrupt."""
        from livekit.agents import stt

        from app.services.voice.agent_worker import (
            BargeInEngine,
            BargeInState,
            VoiceSDRAgent,
        )

        session = self._session_with_say()
        engine = BargeInEngine(enabled=True)
        agent = VoiceSDRAgent(barge_in_engine=engine)

        with patch.object(
            VoiceSDRAgent, "session", property(lambda self: session)
        ):
            t0 = 1000.0
            engine.on_bot_speech_started(timestamp=t0)

            # Customer says conversational filler
            ev = stt.SpeechEvent(
                type=stt.SpeechEventType.PREFLIGHT_TRANSCRIPT,
                alternatives=[
                    stt.SpeechData(
                        text="dạ",
                        language="vi",
                        confidence=0.95,
                    )
                ],
            )

            state = await agent.handle_speech_event(ev)
            assert state == BargeInState.IDLE

            session.interrupt.assert_not_called()
            session.say.assert_not_called()

    @pytest.mark.asyncio
    async def test_stt_node_forwards_speech_events_to_barge_in(self):
        """stt_node is the in-pipeline hook — it must feed handle_speech_event.

        The AgentSession has no "speech_event" emission, so stt_node is the
        ONLY path by which STT speech events reach the barge-in engine.
        """
        from livekit.agents import stt as livekit_stt
        from livekit.agents.voice.agent import Agent

        from app.services.voice.agent_worker import (
            BargeInEngine,
            VoiceSDRAgent,
        )

        engine = BargeInEngine(enabled=True)
        agent = VoiceSDRAgent(barge_in_engine=engine)
        event = livekit_stt.SpeechEvent(
            type=livekit_stt.SpeechEventType.INTERIM_TRANSCRIPT,
            alternatives=[
                livekit_stt.SpeechData(
                    language="vi", text="khoan đã", confidence=0.95
                )
            ],
        )

        async def _default_stt_node(agent_inst, audio, model_settings):
            yield event

        async def _empty_audio():
            if False:
                yield None

        with patch.object(Agent.default, "stt_node", _default_stt_node):
            out = [e async for e in agent.stt_node(_empty_audio(), MagicMock())]
            assert engine.state is not None

        assert out == [event], "stt_node must forward the event downstream"
        assert engine.state.name in {"IDLE", "DUCKING", "INTERRUPTED"}

    @pytest.mark.asyncio
    async def test_stt_node_invokes_handle_speech_event(self):
        """Regression guard: stt_node must call handle_speech_event per event.

        Removing the `await self.handle_speech_event(event)` line inside
        stt_node would silently disable the whole barge-in pipeline while
        every other test still passed.
        """
        from livekit.agents import stt as livekit_stt
        from livekit.agents.voice.agent import Agent

        from app.services.voice.agent_worker import VoiceSDRAgent

        agent = VoiceSDRAgent()
        event = livekit_stt.SpeechEvent(
            type=livekit_stt.SpeechEventType.INTERIM_TRANSCRIPT,
            alternatives=[
                livekit_stt.SpeechData(language="vi", text="khoan đã")
            ],
        )

        async def _default_stt_node(agent_inst, audio, model_settings):
            yield event

        seen: list[object] = []

        async def _spy(ev: object) -> None:
            seen.append(ev)

        async def _empty_audio():
            if False:
                yield None

        with (
            patch.object(Agent.default, "stt_node", _default_stt_node),
            patch.object(agent, "handle_speech_event", _spy),
        ):
            out = [e async for e in agent.stt_node(_empty_audio(), MagicMock())]

        assert out == [event]
        assert seen == [event], "stt_node must route each SpeechEvent to the engine"

    @pytest.mark.asyncio
    async def test_tts_node_checks_kws_timeout_each_frame(self):
        """tts_node evaluates check_timeouts per frame so DUCKING cannot stick."""
        from livekit.agents.voice.agent import Agent

        from app.services.voice.agent_worker import (
            BargeInEngine,
            VoiceSDRAgent,
        )

        engine = BargeInEngine(enabled=True)
        agent = VoiceSDRAgent(barge_in_engine=engine)

        async def _default_tts_node(agent_inst, text, model_settings):
            for _ in range(3):
                yield self._make_tts_frame()

        async def _empty_text():
            if False:
                yield ""

        checked: list[int] = []
        real_check = engine.check_timeouts
        engine.check_timeouts = lambda *a, **k: (  # type: ignore[method-assign]
            checked.append(1) or real_check(*a, **k)
        )

        with patch.object(Agent.default, "tts_node", _default_tts_node):
            frames = [f async for f in agent.tts_node(_empty_text(), MagicMock())]

        assert len(frames) == 3
        assert len(checked) == 3, "tts_node must evaluate check_timeouts every frame"

    @pytest.mark.asyncio
    async def test_tts_node_interrupts_when_kws_deadline_expires(self):
        """A stuck DUCKING (no transcript) must escalate to a real interrupt."""
        from livekit.agents.voice.agent import Agent

        from app.services.voice.agent_worker import (
            BargeInEngine,
            BargeInState,
            VoiceSDRAgent,
        )

        engine = BargeInEngine(enabled=True)
        agent = VoiceSDRAgent(barge_in_engine=engine)
        session = self._session_with_say()

        async def _default_tts_node(agent_inst, text, model_settings):
            for _ in range(4):
                yield self._make_tts_frame()

        async def _empty_text():
            if False:
                yield ""

        # Simulate an already-expired KWS deadline. The deadline arithmetic
        # itself is covered in test_barge_in.py; this test only asserts the
        # tts_node → interrupt wiring. (tts_node calls on_bot_speech_started()
        # on the first frame, which would otherwise reset the engine state.)
        engine.check_timeouts = lambda *a, **k: BargeInState.INTERRUPTED  # type: ignore[method-assign]

        triggered: list[bool] = []

        async def _fake_interrupt() -> None:
            triggered.append(True)

        with (
            patch.object(Agent.default, "tts_node", _default_tts_node),
            patch.object(VoiceSDRAgent, "session", property(lambda self: session)),
            patch.object(agent, "_trigger_barge_in_interruption", _fake_interrupt),
        ):
            async for _ in agent.tts_node(_empty_text(), MagicMock()):
                pass

        assert triggered, "expired KWS deadline must trigger a barge-in interrupt"

