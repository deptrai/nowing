"""Pydantic schemas for the meeting minutes service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MeetingMinutesSegment(BaseModel):
    speaker: str
    text: str
    start: float
    end: float


class MeetingMinutesActionItem(BaseModel):
    speaker: str
    task: str
    due: str | None = None


class GenerateMeetingMinutesInput(BaseModel):
    audio_url: str | None = None
    document_id: int | None = None
    workspace_id: int
    thread_id: int | None = None
    language: str | None = None


class GenerateMeetingMinutesOutput(BaseModel):
    meeting_minutes_id: int | None = None
    status: str
    title: str | None = None
    transcript: list[MeetingMinutesSegment] = Field(default_factory=list)
    summary: str | None = None
    action_items: list[MeetingMinutesActionItem] = Field(default_factory=list)
    download_url: str | None = None
    error: str | None = None


class TranscriptionResult(BaseModel):
    segments: list[dict[str, Any]] = Field(default_factory=list)
    language: str | None = None
    language_probability: float = 0.0
    duration: float = 0.0
