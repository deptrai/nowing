"""FillerAudioBank — pre-loads local WAV filler clips into RAM for <80ms injection.

Filler phrases are short acknowledgment/thinking sounds played immediately when
the LLM first-token latency exceeds the 80ms threshold, masking the gap before
the first real TTS clause arrives.

Fillers are loaded once at worker startup from ``VOICE_FILLER_DIR`` — never
read from disk mid-call (disk I/O would blow the 80ms budget).

Story 38.2 / Invariant: sub-80ms filler injection, no disk I/O at call time.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

FillerKind = Literal["ack", "thinking", "hold", "breath"]

# Canonical filename → kind mapping.
# Add new entries here when more filler phrases are recorded.
_FILLER_FILES: dict[FillerKind, str] = {
    "ack": "ack_da_vang.wav",
    "thinking": "thinking_um.wav",
    "hold": "hold_xin_loi.wav",
    "breath": "breath_50ms.wav",
}

# Fallback order when a requested kind is missing
_FALLBACK_ORDER: list[FillerKind] = ["ack", "thinking", "hold", "breath"]


class FillerAudioError(Exception):
    """Raised when the filler audio bank cannot be initialised."""


class FillerAudioBank:
    """In-memory store of filler WAV bytes, keyed by filler kind.

    Usage:
        bank = FillerAudioBank()          # loads from VOICE_FILLER_DIR
        wav_bytes = bank.get_filler("ack") # zero I/O, sub-microsecond
    """

    def __init__(self, filler_dir: str | None = None) -> None:
        from app.config.voice import VOICE_FILLER_DIR

        self._dir = Path(filler_dir or VOICE_FILLER_DIR)
        self._bank: dict[FillerKind, bytes] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_filler(self, kind: FillerKind = "ack") -> bytes:
        """Return WAV bytes for *kind*, falling back to the first available clip.

        Args:
            kind: The filler type — ``"ack"``, ``"thinking"``, ``"hold"``,
                or ``"breath"``.

        Returns:
            Raw WAV file bytes ready to publish to a LiveKit audio track.

        Raises:
            FillerAudioError: If the bank is empty (directory missing or no
                WAV files found at startup).
        """
        if not self._bank:
            raise FillerAudioError(
                f"FillerAudioBank is empty — no WAV files found in {self._dir}"
            )
        # Try requested kind, then fall back in order
        if kind in self._bank:
            return self._bank[kind]
        for fallback in _FALLBACK_ORDER:
            if fallback in self._bank:
                logger.debug(
                    "Filler kind '%s' not loaded, falling back to '%s'",
                    kind,
                    fallback,
                )
                return self._bank[fallback]
        # Return first available bytes as last resort
        return next(iter(self._bank.values()))

    def available_kinds(self) -> list[FillerKind]:
        """Return list of filler kinds that were successfully loaded."""
        return list(self._bank.keys())

    def is_ready(self) -> bool:
        """True if at least one filler clip is loaded."""
        return bool(self._bank)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Scan filler directory and load all known WAV files into RAM."""
        if not self._dir.exists():
            logger.warning(
                "Filler audio directory does not exist: %s — bank will be empty",
                self._dir,
            )
            return

        for kind, filename in _FILLER_FILES.items():
            wav_path = self._dir / filename
            if not wav_path.exists():
                logger.debug("Filler file not found, skipping: %s", wav_path)
                continue
            try:
                self._bank[kind] = wav_path.read_bytes()
                logger.debug("Loaded filler '%s' (%d bytes)", kind, len(self._bank[kind]))
            except OSError as exc:
                logger.warning("Failed to load filler %s: %s", wav_path, exc)

        if not self._bank:
            logger.warning(
                "FillerAudioBank loaded 0 clips from %s — filler injection will fail",
                self._dir,
            )
        else:
            logger.info(
                "FillerAudioBank ready: %d clips loaded from %s",
                len(self._bank),
                self._dir,
            )


# ---------------------------------------------------------------------------
# Module-level singleton (shared across all sessions in one worker process)
# ---------------------------------------------------------------------------

_bank: FillerAudioBank | None = None


def get_filler_bank() -> FillerAudioBank:
    """Return the process-wide FillerAudioBank singleton, initialising on first call."""
    global _bank
    if _bank is None:
        _bank = FillerAudioBank()
    return _bank
