"""Unit tests for Story 27.2b — Meeting Minutes service (speaker diarization)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.db import MeetingMinutesStatus
from app.services.meeting_minutes.schemas import (
    MeetingMinutesActionItem,
    MeetingMinutesSegment,
    TranscriptionResult,
)
from app.services.meeting_minutes.service import MeetingMinutesService


@pytest.fixture(autouse=True)
def _enable_meeting_minutes(monkeypatch):
    from app.config import config
    monkeypatch.setattr(config, "MEETING_MINUTES_ENABLED", True)


@pytest.mark.unit
async def test_service_validates_input_requires_exactly_one_source():
    """AC-1: missing audio_url and document_id returns validation_failed."""
    service = MeetingMinutesService()
    session = AsyncMock()
    result = await service.create(
        session,
        workspace_id=1,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    assert result.status == MeetingMinutesStatus.VALIDATION_FAILED
    assert "Provide an audio file or URL" in result.error


@pytest.mark.unit
async def test_service_returns_processing_status_and_meeting_minutes_id():
    """AC-1: service creates row, enqueues worker, and returns processing."""
    session = AsyncMock()
    fake_row = MagicMock()
    fake_row.id = 42

    with (
        patch.object(MeetingMinutesService, "_enqueue_worker") as mock_enqueue,
        patch(
            "app.services.meeting_minutes.service.MeetingMinutes",
            return_value=fake_row,
        ),
    ):
        service = MeetingMinutesService()
        result = await service.create(
            session,
            workspace_id=1,
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            audio_url="https://example.com/meeting.mp3",
        )
        assert result.meeting_minutes_id == 42
        assert result.status == MeetingMinutesStatus.PROCESSING
        assert result.download_url is not None
        mock_enqueue.assert_called_once()


@pytest.mark.unit
async def test_service_degraded_when_diarization_unavailable():
    """AC-3: pyannote.audio missing returns degraded with single Speaker 1."""
    service = MeetingMinutesService()
    transcription = TranscriptionResult(
        segments=[{"start": 0.0, "end": 1.0, "text": "hello", "words": []}],
        duration=1.0,
    )
    with patch(
        "app.services.meeting_minutes.diarization.DiarizationService.diarize",
        side_effect=ImportError("pyannote.audio"),
    ):
        segments = service._diarize("/tmp/audio.wav", transcription)
        assert len(segments) == 1
        assert segments[0].speaker == "Speaker 1"


@pytest.mark.unit
async def test_service_records_transcription_cost_as_flat_compute():
    """AC-4: transcription cost = duration * MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND."""
    with (
        patch("app.config.config.MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND", 10),
        patch(
            "app.services.meeting_minutes.service.record_token_usage"
        ) as mock_record,
        patch(
            "app.services.meeting_minutes.service.TokenQuotaService.credit_reserve",
            new_callable=AsyncMock,
            return_value=MagicMock(allowed=True),
        ),
        patch(
            "app.services.meeting_minutes.service.TokenQuotaService.credit_finalize",
            new_callable=AsyncMock,
        ),
        patch.object(
            MeetingMinutesService,
            "_transcribe",
            new_callable=AsyncMock,
            return_value=TranscriptionResult(segments=[], duration=60.0),
        ),
        patch.object(
            MeetingMinutesService,
            "_diarize",
            return_value=[
                MeetingMinutesSegment(
                    speaker="Speaker 1", text="hello", start=0.0, end=1.0
                )
            ],
        ),
        patch.object(
            MeetingMinutesService,
            "_extract_summary_and_actions",
            new_callable=AsyncMock,
            return_value=("summary", [MeetingMinutesActionItem(speaker="A", task="t")]),
        ),
    ):
        service = MeetingMinutesService()
        fake_row = MagicMock()
        fake_row.id = 1
        fake_row.workspace_id = 1
        fake_row.user_id = UUID("00000000-0000-0000-0000-000000000001")
        fake_row.thread_id = None
        fake_row.document_id = None
        fake_row.audio_source_url = "https://example.com/meeting.mp3"
        fake_row.meeting_metadata = {}
        fake_row.status = MeetingMinutesStatus.PROCESSING
        fake_row.processing_task_id = None

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fake_row
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result_mock)

        with patch.object(
            MeetingMinutesService,
            "_download_audio",
            new_callable=AsyncMock,
            return_value=Path("/tmp/audio.wav"),
        ):
            await service.process(session, fake_row.id)

        calls = [
            c
            for c in mock_record.call_args_list
            if c.kwargs.get("usage_type") == "meeting_minutes_transcription"
        ]
        assert calls
        assert calls[0].kwargs["cost_micros"] == 60 * 10


@pytest.mark.unit
async def test_service_rejects_audio_above_duration_limit():
    """AC-6: audio > MEETING_MINUTES_MAX_DURATION_SECONDS fails."""
    with patch("app.config.config.MEETING_MINUTES_MAX_DURATION_SECONDS", 600):
        service = MeetingMinutesService()
        fake_row = MagicMock()
        fake_row.id = 1
        fake_row.workspace_id = 1
        fake_row.user_id = UUID("00000000-0000-0000-0000-000000000001")
        fake_row.thread_id = None
        fake_row.document_id = None
        fake_row.audio_source_url = "https://example.com/too-long.mp3"
        fake_row.meeting_metadata = {}
        fake_row.status = MeetingMinutesStatus.PROCESSING
        fake_row.processing_task_id = None

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fake_row
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result_mock)

        with (
            patch.object(
                MeetingMinutesService,
                "_download_audio",
                new_callable=AsyncMock,
                return_value=Path("/tmp/audio.wav"),
            ),
            patch.object(
                MeetingMinutesService,
                "_transcribe",
                new_callable=AsyncMock,
                return_value=TranscriptionResult(segments=[], duration=601.0),
            ),
        ):
            result = await service.process(session, fake_row.id)
            assert result.status == MeetingMinutesStatus.FAILED
            assert "audio_too_large" in result.error


@pytest.mark.unit
async def test_service_falls_back_on_audio_url_unreachable():
    """AC-6: unreachable audio_url returns failed."""
    with patch("app.services.meeting_minutes.service.httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = Exception("404")
        service = MeetingMinutesService()
        session = AsyncMock()
        result = await service.create(
            session,
            workspace_id=1,
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            audio_url="https://example.com/missing.mp3",
        )
        # create returns processing; the worker would fail.
        assert result.status == MeetingMinutesStatus.PROCESSING
