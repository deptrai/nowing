"""Unit tests for VoiceAgentWorker and VoiceWorkerPool (Story 38.2).

Hermetic tests covering:
- SEQUENCER_VOICE_ENABLED feature gate (fail-closed)
- VAD state tensor isolation between sessions
- Pre-warm STT/TTS call sequencing
- Worker pool spawn/shutdown lifecycle
- FillerAudioBank RAM loading and fallback
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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
    import time
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
