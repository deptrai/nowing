"""Meeting minutes service."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Document,
    MeetingMinutes,
    MeetingMinutesStatus,
    TokenUsage,
)
from app.file_storage.persistence.enums import DocumentFileKind
from app.file_storage.service import get_document_file, open_document_file_stream
from app.services.billable_calls import (
    QuotaInsufficientError,
    _resolve_agent_billing_for_workspace,
    billable_call,
)
from app.services.meeting_minutes.diarization import DiarizationService
from app.services.meeting_minutes.schemas import (
    GenerateMeetingMinutesOutput,
    MeetingMinutesActionItem,
    MeetingMinutesSegment,
    TranscriptionResult,
)
from app.services.stt_service import stt_service
from app.services.token_quota_service import TokenQuotaService
from app.services.token_tracking_service import UsageType, record_token_usage
from app.tasks.celery_tasks import get_celery_session_maker
from app.tasks.celery_tasks.meeting_minutes_heartbeat import (
    start_meeting_minutes_pending_heartbeat,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _celery_billable_session():
    """Session factory used by billable_call inside the Celery worker loop."""
    async with get_celery_session_maker()() as session:
        yield session


class MeetingMinutesService:
    """Create and process meeting minutes from audio."""

    def __init__(self) -> None:
        self.diarization = DiarizationService()

    async def create(
        self,
        session: AsyncSession,
        *,
        workspace_id: int,
        user_id: UUID | str,
        audio_url: str | None = None,
        document_id: int | None = None,
        thread_id: int | None = None,
        language: str | None = None,
    ) -> GenerateMeetingMinutesOutput:
        """Validate input, create a MeetingMinutes row, and enqueue processing."""
        user_id = self._coerce_user_id(user_id)

        if not config.MEETING_MINUTES_ENABLED:
            return GenerateMeetingMinutesOutput(
                status="validation_failed",
                error="Meeting Minutes is not enabled on this workspace plan",
            )

        if not ((audio_url is not None) ^ (document_id is not None)):
            return GenerateMeetingMinutesOutput(
                status="validation_failed",
                error="Provide an audio file or URL",
            )

        # Validate document exists and belongs to workspace if provided.
        if document_id is not None:
            doc = (
                await session.execute(
                    select(Document).where(
                        Document.id == document_id,
                        Document.workspace_id == workspace_id,
                    )
                )
            ).scalar_one_or_none()
            if doc is None:
                return GenerateMeetingMinutesOutput(
                    status="validation_failed",
                    error="Document not found",
                )

        if audio_url is not None:
            audio_url = audio_url.strip()
            if not audio_url:
                return GenerateMeetingMinutesOutput(
                    status="validation_failed",
                    error="Provide an audio file or URL",
                )

        row = MeetingMinutes(
            workspace_id=workspace_id,
            user_id=user_id,
            thread_id=thread_id,
            document_id=document_id,
            audio_source_url=audio_url,
            status=MeetingMinutesStatus.PENDING,
            transcript=[],
            action_items=[],
            summary="",
            meeting_metadata={"language": language} if language else {},
        )
        session.add(row)
        await session.flush()

        # Long-lived heartbeat for rows waiting to be picked up by a worker.
        # Workers overwrite this with a short-lived heartbeat once they start.
        start_meeting_minutes_pending_heartbeat(row.id)

        try:
            self._enqueue_worker(row.id, workspace_id, user_id)
        except Exception as exc:
            logger.warning("Failed to enqueue meeting minutes worker: %s", exc)

        return GenerateMeetingMinutesOutput(
            meeting_minutes_id=row.id,
            status="processing",
            download_url=f"/api/v1/meeting-minutes/{row.id}/download",
        )

    async def process(
        self,
        session: AsyncSession,
        meeting_minutes_id: int,
        *,
        processing_task_id: str | None = None,
    ) -> GenerateMeetingMinutesOutput:
        """Run the full worker processing pipeline for a MeetingMinutes row."""
        row = (
            await session.execute(
                select(MeetingMinutes).where(MeetingMinutes.id == meeting_minutes_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return GenerateMeetingMinutesOutput(
                status="failed", error="meeting_minutes_not_found"
            )

        # Idempotency: if another worker owns this row, skip.
        if (
            row.processing_task_id is not None
            and processing_task_id is not None
            and row.processing_task_id != processing_task_id
        ):
            logger.info(
                "MeetingMinutes %s already owned by task %s; skipping %s",
                row.id,
                row.processing_task_id,
                processing_task_id,
            )
            return GenerateMeetingMinutesOutput(
                meeting_minutes_id=row.id,
                status=row.status.value,
                title=row.title,
                transcript=row.transcript or [],
                summary=row.summary,
                action_items=row.action_items or [],
                error=row.error,
            )

        if processing_task_id:
            row.processing_task_id = processing_task_id

        row.status = MeetingMinutesStatus.PROCESSING
        await session.commit()

        audio_path: Path | None = None
        try:
            audio_path = await self._download_audio(session, row)
            if audio_path is None:
                raise ValueError("audio_source_unreachable")

            # Single transcription pass: used for duration check and diarization.
            transcription = await self._transcribe(str(audio_path), row)
            if transcription.duration > config.MEETING_MINUTES_MAX_DURATION_SECONDS:
                raise ValueError("audio_too_large")

            # Reserve flat compute cost before extraction.
            reserve_result = await TokenQuotaService.credit_reserve(
                session,
                user_id=row.user_id,
                request_id=f"mm-transcription-{row.id}",
                reserve_micros=int(transcription.duration * config.MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND),
            )
            if not reserve_result.allowed:
                raise QuotaInsufficientError(
                    usage_type=UsageType.MEETING_MINUTES_TRANSCRIPTION,
                    balance_micros=reserve_result.balance,
                    remaining_micros=reserve_result.remaining,
                )

            degraded = False
            try:
                loop = asyncio.get_running_loop()
                segments_with_speakers = await loop.run_in_executor(
                    None, self._diarize, str(audio_path), transcription
                )
            except Exception as exc:
                logger.warning("Diarization failed for MeetingMinutes %s: %s", row.id, exc)
                segments_with_speakers = self._degraded_segments(transcription)
                degraded = True

            # Finalize transcription compute cost.
            actual_micros = int(transcription.duration * config.MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND)
            await TokenQuotaService.credit_finalize(
                session,
                user_id=row.user_id,
                request_id=f"mm-transcription-{row.id}",
                actual_micros=actual_micros,
                reserved_micros=int(transcription.duration * config.MEETING_MINUTES_TRANSCRIPTION_MICROS_PER_SECOND),
            )
            await record_token_usage(
                session,
                usage_type=UsageType.MEETING_MINUTES_TRANSCRIPTION,
                workspace_id=row.workspace_id,
                user_id=row.user_id,
                cost_micros=actual_micros,
                thread_id=row.thread_id,
                call_details={"duration_seconds": transcription.duration},
            )

            summary, action_items = await self._extract_summary_and_actions(
                session, row, segments_with_speakers
            )

            row.transcript = [seg.model_dump() for seg in segments_with_speakers]
            row.summary = summary
            row.action_items = [item.model_dump() for item in action_items]
            row.raw_transcript = "\n".join(seg.text for seg in segments_with_speakers)
            row.title = (summary or "Meeting Minutes").split("\n")[0][:100]

            if degraded or (not summary and not action_items and segments_with_speakers):
                row.status = MeetingMinutesStatus.DEGRADED
                row.error = "transcript_ready_extraction_degraded" if not degraded else "diarization_unavailable"
            else:
                row.status = MeetingMinutesStatus.READY

            # Hard-delete source Document after minutes are saved.
            if row.document_id:
                await self._purge_document(session, row)

            await session.commit()

            return GenerateMeetingMinutesOutput(
                meeting_minutes_id=row.id,
                status=row.status.value,
                title=row.title,
                transcript=row.transcript,
                summary=row.summary,
                action_items=row.action_items,
                download_url=f"/api/v1/meeting-minutes/{row.id}/download",
                error=None,
            )

        except QuotaInsufficientError:
            row.status = MeetingMinutesStatus.FAILED
            row.error = "insufficient_credits"
            await session.commit()
            return GenerateMeetingMinutesOutput(
                meeting_minutes_id=row.id,
                status="failed",
                error="insufficient_credits",
            )
        except ValueError as exc:
            error = str(exc)
            row.status = MeetingMinutesStatus.FAILED
            row.error = error
            await session.commit()
            return GenerateMeetingMinutesOutput(
                meeting_minutes_id=row.id,
                status="failed",
                error=error,
            )
        except Exception:
            logger.exception("MeetingMinutes %s processing failed", row.id)
            row.status = MeetingMinutesStatus.FAILED
            row.error = "processing_error"
            await session.commit()
            return GenerateMeetingMinutesOutput(
                meeting_minutes_id=row.id,
                status="failed",
                error="processing_error",
            )
        finally:
            if audio_path and audio_path.exists():
                with contextlib.suppress(Exception):
                    os.unlink(audio_path)

    async def get(
        self,
        session: AsyncSession,
        meeting_minutes_id: int,
        workspace_id: int,
    ) -> MeetingMinutes:
        row = (
            await session.execute(
                select(MeetingMinutes).where(
                    MeetingMinutes.id == meeting_minutes_id,
                    MeetingMinutes.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("meeting_minutes_not_found")
        return row

    async def delete(
        self,
        session: AsyncSession,
        meeting_minutes_id: int,
        workspace_id: int,
        *,
        raise_on_cleanup: bool = False,
    ) -> bool:
        try:
            row = await self.get(session, meeting_minutes_id, workspace_id)
        except ValueError:
            return False
        if raise_on_cleanup:
            raise RuntimeError("forced cleanup failure")
        await session.delete(row)
        await session.commit()
        return True

    async def update_status(
        self,
        session: AsyncSession,
        meeting_minutes_id: int,
        workspace_id: int,
        status: MeetingMinutesStatus,
        **fields,
    ) -> MeetingMinutes | None:
        row = (
            await session.execute(
                select(MeetingMinutes).where(
                    MeetingMinutes.id == meeting_minutes_id,
                    MeetingMinutes.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row.status = status
        for key, value in fields.items():
            setattr(row, key, value)
        await session.commit()
        return row

    async def record_token_usage(
        self,
        session: AsyncSession,
        *,
        meeting_minutes_id: int,
        workspace_id: int,
        user_id: UUID | str,
        usage_type: str,
        cost_micros: int,
    ) -> TokenUsage | None:
        return await record_token_usage(
            session,
            usage_type=usage_type,
            workspace_id=workspace_id,
            user_id=self._coerce_user_id(user_id),
            cost_micros=cost_micros,
            call_details={"meeting_minutes_id": meeting_minutes_id},
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_user_id(user_id: UUID | str) -> UUID:
        if isinstance(user_id, UUID):
            return user_id
        if isinstance(user_id, str):
            return UUID(user_id)
        raise ValueError(f"Invalid user_id type: {type(user_id)}")

    def _enqueue_worker(self, meeting_minutes_id: int, workspace_id: int, user_id: UUID) -> None:
        from app.tasks.process_meeting_minutes import process_meeting_minutes

        process_meeting_minutes.delay(
            meeting_minutes_id=meeting_minutes_id,
            workspace_id=workspace_id,
            user_id=str(user_id),
        )

    async def _download_audio(
        self, session: AsyncSession, row: MeetingMinutes
    ) -> Path | None:
        if row.document_id:
            file = await get_document_file(
                session, document_id=row.document_id, kind=DocumentFileKind.ORIGINAL
            )
            if file is None:
                return None
            return await self._stream_to_temp(open_document_file_stream(file))

        if row.audio_source_url:
            try:
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
                        downloaded = 0
                        async with client.stream("GET", row.audio_source_url) as response:
                            if response.status_code >= 400:
                                return None
                            async for chunk in response.aiter_bytes():
                                downloaded += len(chunk)
                                if downloaded > config.MEETING_MINUTES_MAX_AUDIO_BYTES:
                                    raise ValueError("audio_too_large")
                                tmp.write(chunk)
                        tmp.flush()
                        return Path(tmp.name)
            except httpx.HTTPError as exc:
                logger.warning("Audio download failed for %s: %s", row.audio_source_url, exc)
                return None

        return None

    async def _stream_to_temp(self, stream) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
            async for chunk in stream:
                tmp.write(chunk)
            tmp.flush()
            return Path(tmp.name)

    async def _transcribe(
        self, audio_path: str, row: MeetingMinutes
    ) -> TranscriptionResult:
        language = row.meeting_metadata.get("language") if row.meeting_metadata else None
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, stt_service.transcribe_file_segments, audio_path, language
        )
        return TranscriptionResult(**result)

    def _diarize(
        self, audio_path: str, transcription: TranscriptionResult
    ) -> list[MeetingMinutesSegment]:
        try:
            turns = self.diarization.diarize(audio_path)
        except Exception:
            return self._degraded_segments(transcription)

        if not turns:
            return self._degraded_segments(transcription)

        # Map each word in each segment to a speaker turn by overlap.
        words = []
        for seg in transcription.segments:
            for w in seg.get("words", []):
                words.append(
                    {
                        "start": w.get("start", seg.get("start", 0.0)),
                        "end": w.get("end", seg.get("end", 0.0)),
                        "word": w.get("word", ""),
                        "seg_text": seg.get("text", ""),
                    }
                )

        if not words:
            return self._degraded_segments(transcription)

        speaker_texts: dict[str, list[dict]] = {speaker: [] for _, _, speaker in turns}
        for word in words:
            best_speaker = None
            best_overlap = 0.0
            for start, end, speaker in turns:
                overlap = max(0.0, min(word["end"], end) - max(word["start"], start))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = speaker
            if best_speaker:
                speaker_texts[best_speaker].append(word)

        # Cap speaker labels.
        sorted_speakers = sorted(
            speaker_texts.keys(),
            key=lambda s: min(w["start"] for w in speaker_texts[s]) if speaker_texts[s] else float("inf"),
        )[: config.MEETING_MINUTES_MAX_SPEAKER_LABELS]

        segments = []
        for speaker in sorted_speakers:
            words_for_speaker = sorted(speaker_texts[speaker], key=lambda w: w["start"])
            if not words_for_speaker:
                continue
            text = " ".join(w["word"] for w in words_for_speaker)
            segments.append(
                MeetingMinutesSegment(
                    speaker=speaker,
                    text=text,
                    start=words_for_speaker[0]["start"],
                    end=words_for_speaker[-1]["end"],
                )
            )

        if not segments:
            return self._degraded_segments(transcription)

        return sorted(segments, key=lambda s: s.start)

    def _degraded_segments(self, transcription: TranscriptionResult) -> list[MeetingMinutesSegment]:
        text = " ".join(seg.get("text", "").strip() for seg in transcription.segments)
        if not text:
            text = "No speech detected."
        return [
            MeetingMinutesSegment(
                speaker="Speaker 1",
                text=text,
                start=0.0,
                end=max((seg.get("end", 0.0) for seg in transcription.segments), default=0.0),
            )
        ]

    async def _extract_summary_and_actions(
        self, session: AsyncSession, row: MeetingMinutes, segments: list[MeetingMinutesSegment]
    ) -> tuple[str, list[MeetingMinutesActionItem]]:
        if not segments:
            return "No speech detected.", []

        text = "\n".join(f"{seg.speaker}: {seg.text}" for seg in segments)
        prompt = (
            "Summarize the following meeting transcript and extract action items "
            "grouped by speaker. Return ONLY valid JSON with keys 'summary' (string) "
            "and 'action_items' (list of {speaker, task, due}).\n\n"
            f"{text}"
        )

        try:
            (
                owner_user_id,
                billing_tier,
                base_model,
            ) = await _resolve_agent_billing_for_workspace(
                session, row.workspace_id, thread_id=row.thread_id
            )
        except Exception:
            billing_tier = "free"
            base_model = "auto"
            owner_user_id = row.user_id

        try:
            from app.services.llm_service import llm_service

            async with billable_call(
                user_id=owner_user_id,
                workspace_id=row.workspace_id,
                billing_tier=billing_tier,
                base_model=base_model,
                usage_type=UsageType.MEETING_MINUTES_EXTRACTION,
                thread_id=row.thread_id,
                call_details={"meeting_minutes_id": row.id},
                billable_session_factory=_celery_billable_session,
            ):
                response = await llm_service.ainvoke(prompt)
                content = response.get("content", "") if isinstance(response, dict) else str(response)
                parsed = self._parse_llm_json(content)
                summary = parsed.get("summary", "")
                action_items = [
                    MeetingMinutesActionItem(
                        speaker=item.get("speaker", ""),
                        task=item.get("task", ""),
                        due=item.get("due"),
                    )
                    for item in parsed.get("action_items", [])
                ]
                return summary, action_items
        except QuotaInsufficientError:
            # Return degraded but keep transcript.
            return "", []
        except Exception as exc:
            logger.warning("Summary extraction failed for MeetingMinutes %s: %s", row.id, exc)
            return "", []

    @staticmethod
    def _parse_llm_json(content: str) -> dict:
        # Try to find JSON block or bare JSON.
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.DOTALL)
        try:
            import json

            return json.loads(content)
        except Exception:
            return {}

    async def _purge_document(self, session: AsyncSession, row: MeetingMinutes) -> None:
        doc = (
            await session.execute(select(Document).where(Document.id == row.document_id))
        ).scalar_one_or_none()
        if doc:
            # Also delete associated DocumentFile blobs via cascade.
            await session.delete(doc)
            await session.commit()
