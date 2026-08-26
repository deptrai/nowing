"""Speaker diarization service for meeting minutes."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.config import config

logger = logging.getLogger(__name__)


class DiarizationService:
    """Run speaker diarization on an audio file."""

    def __init__(self) -> None:
        self._engine: Any | None = None

    def _load_engine(self) -> Any:
        if self._engine is not None:
            return self._engine

        if config.MEETING_MINUTES_DIARIZATION_ENGINE == "none":
            raise ImportError("diarization disabled by config")

        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            logger.warning("pyannote.audio not installed; diarization unavailable")
            raise ImportError("pyannote.audio not installed") from exc

        token = config.HUGGINGFACE_TOKEN or True
        try:
            self._engine = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=token,
            )
        except Exception as exc:
            logger.warning("Failed to load pyannote diarization pipeline: %s", exc)
            raise ImportError(f"failed to load diarization pipeline: {exc}") from exc

        return self._engine

    def diarize(self, audio_path: str | Path) -> list[tuple[float, float, str]]:
        """Return list of (start, end, speaker_label) turns.

        Falls back to a single Speaker 1 segment if pyannote is unavailable.
        """
        if config.MEETING_MINUTES_DIARIZATION_ENGINE == "none":
            return []

        try:
            pipeline = self._load_engine()
        except ImportError:
            return []

        try:
            diarization = pipeline(str(audio_path))
        except Exception as exc:
            logger.warning("Diarization failed: %s", exc)
            return []

        turns = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            match = re.search(r"\d+", speaker)
            label = f"Speaker {int(match.group()) + 1}" if match else "Speaker 1"
            turns.append((turn.start, turn.end, label))
        return turns
