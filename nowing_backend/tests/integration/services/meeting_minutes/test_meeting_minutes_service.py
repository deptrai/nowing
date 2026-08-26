"""Integration tests for MeetingMinutesService (Story 27.2b — Pattern 6 SQL)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import MeetingMinutes, MeetingMinutesStatus, TokenUsage, Workspace
from app.services.meeting_minutes.service import MeetingMinutesService

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def patch_feature_flag(monkeypatch):
    """Enable the feature for integration tests."""
    monkeypatch.setattr("app.config.config.MEETING_MINUTES_ENABLED", True)


@pytest.mark.asyncio
async def test_create_meeting_minutes_persists_row(db_session, db_user, db_workspace):
    """AC-1/AC-4: service creates a MeetingMinutes row and returns processing."""
    service = MeetingMinutesService()
    result = await service.create(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        audio_url="https://example.com/meeting.mp3",
    )
    row = (
        await db_session.execute(
            select(MeetingMinutes).where(MeetingMinutes.id == result.meeting_minutes_id)
        )
    ).scalar_one()
    assert row.workspace_id == db_workspace.id
    assert row.user_id == db_user.id
    assert row.status == MeetingMinutesStatus.PENDING
    assert row.audio_source_url == "https://example.com/meeting.mp3"


@pytest.mark.asyncio
async def test_meeting_minutes_status_transition(db_session, db_user, db_workspace):
    """AC-4: worker updates status pending → processing → ready in real DB."""
    service = MeetingMinutesService()
    result = await service.create(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        audio_url="https://example.com/meeting.mp3",
    )

    await service.update_status(
        db_session, result.meeting_minutes_id, db_workspace.id, MeetingMinutesStatus.PROCESSING
    )
    row = (
        await db_session.execute(
            select(MeetingMinutes).where(MeetingMinutes.id == result.meeting_minutes_id)
        )
    ).scalar_one()
    assert row.status == MeetingMinutesStatus.PROCESSING

    await service.update_status(
        db_session,
        result.meeting_minutes_id,
        db_workspace.id,
        MeetingMinutesStatus.READY,
        transcript=[{"speaker": "Speaker 1", "text": "hello", "start": 0.0, "end": 1.0}],
        summary="A meeting",
        action_items=[{"speaker": "Speaker 1", "task": "follow up", "due": None}],
    )
    row = (
        await db_session.execute(
            select(MeetingMinutes).where(MeetingMinutes.id == result.meeting_minutes_id)
        )
    ).scalar_one()
    assert row.status == MeetingMinutesStatus.READY
    assert len(row.transcript) == 1


@pytest.mark.asyncio
async def test_meeting_minutes_fk_constraint_on_nonexistent_workspace(db_session, db_user):
    """AC-4: insert with non-existent workspace_id raises IntegrityError."""
    service = MeetingMinutesService()
    with pytest.raises(IntegrityError):
        await service.create(
            session=db_session,
            workspace_id=999_999,
            user_id=db_user.id,
            audio_url="https://example.com/meeting.mp3",
        )


@pytest.mark.asyncio
async def test_token_usage_records_for_meeting_minutes(db_session, db_user, db_workspace):
    """AC-4: worker records meeting_minutes_transcription and meeting_minutes_extraction TokenUsage rows."""
    service = MeetingMinutesService()
    result = await service.create(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        audio_url="https://example.com/meeting.mp3",
    )

    await service.record_token_usage(
        db_session,
        meeting_minutes_id=result.meeting_minutes_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        usage_type="meeting_minutes_transcription",
        cost_micros=0,
    )
    await service.record_token_usage(
        db_session,
        meeting_minutes_id=result.meeting_minutes_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        usage_type="meeting_minutes_extraction",
        cost_micros=1234,
    )

    rows = (
        await db_session.execute(
            select(TokenUsage)
            .where(TokenUsage.workspace_id == db_workspace.id)
            .order_by(TokenUsage.id)
        )
    ).scalars().all()
    usage_types = {r.usage_type for r in rows}
    assert "meeting_minutes_transcription" in usage_types
    assert "meeting_minutes_extraction" in usage_types
    assert any(r.cost_micros == 1234 for r in rows)


@pytest.mark.asyncio
async def test_workspace_isolation(db_session, db_user, db_workspace):
    """AC-5: service queries only rows within the workspace."""
    other_workspace = Workspace(name="Other Space", user_id=db_user.id)
    db_session.add(other_workspace)
    await db_session.flush()

    service = MeetingMinutesService()
    result = await service.create(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        audio_url="https://example.com/meeting.mp3",
    )

    row = await service.get(db_session, result.meeting_minutes_id, db_workspace.id)
    assert row is not None

    with pytest.raises(ValueError):
        await service.get(db_session, result.meeting_minutes_id, other_workspace.id)


@pytest.mark.asyncio
async def test_delete_meeting_minutes_rolls_back_transaction_on_error(db_session, db_user, db_workspace):
    """AC-6/AD-28.3: delete with failing side-effect should roll back and leave row."""
    service = MeetingMinutesService()
    result = await service.create(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        audio_url="https://example.com/meeting.mp3",
    )

    with pytest.raises(RuntimeError, match="forced cleanup failure"):
        await service.delete(db_session, result.meeting_minutes_id, db_workspace.id, raise_on_cleanup=True)

    row = (
        await db_session.execute(
            select(MeetingMinutes).where(MeetingMinutes.id == result.meeting_minutes_id)
        )
    ).scalar_one_or_none()
    assert row is not None
