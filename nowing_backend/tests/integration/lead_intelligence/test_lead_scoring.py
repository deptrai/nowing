"""Pattern 6 (SQL) integration tests for Story 21.2 lead scoring."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Lead,
    LeadScore,
    Memory,
    MemoryType,
    SignalEvent,
    User,
    Workspace,
)
from app.lead_intelligence.scoring.schemas import LeadScoreInput
from app.lead_intelligence.scoring.service import LeadScoringService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _make_lead(
    db_session: AsyncSession,
    db_workspace: Workspace,
    company_name: str = "FPT",
    status: str = "open",
) -> Lead:
    lead = Lead(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id=None,
        source="test",
        company_name=company_name,
        domain="fpt.com",
        industry="software",
        status=status,
    )
    db_session.add(lead)
    await db_session.flush()
    return lead


def _make_ctx(
    db_workspace: Workspace,
    db_user: User | None = None,
    client_id: str | None = None,
) -> Any:
    return SimpleNamespace(
        workspace_id=db_workspace.id,
        run_id="run-integration-scoring",
        client_id=client_id,
        user_id=db_user.id if db_user is not None else None,
    )


async def _make_signal_event(
    db_session: AsyncSession,
    db_workspace: Workspace,
    company_name: str = "FPT",
) -> SignalEvent:
    event = SignalEvent(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id=None,
        company_name=company_name,
        signal_type="funding",
        source_url="https://example.com/funding",
        chunk_id=None,
        confidence=85.0,
        detected_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        processed=False,
    )
    db_session.add(event)
    await db_session.flush()
    return event


async def test_lead_score_persists_with_provenance_and_memory(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    patched_embed_texts: Any,
) -> None:
    """A LeadScore row and its Memory are linked by source_uuid/source_entity_type."""
    lead = await _make_lead(db_session, db_workspace)
    await _make_signal_event(db_session, db_workspace, lead.company_name)

    from app.config import config

    with mock.patch.object(config, "LEAD_SCORING_MICROS_PER_CALL", 0):
        ctx = _make_ctx(db_workspace, db_user)

        svc = LeadScoringService()
        output = await svc.score(
            db_session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

    assert len(output.items) == 1
    item = output.items[0]
    assert item.lead_id == lead.id
    assert 0 <= item.score <= 100

    lead_score_id = item.id
    result = await db_session.execute(
        select(LeadScore).where(LeadScore.id == lead_score_id)
    )
    lead_score = result.scalar_one()
    assert lead_score.workspace_id == db_workspace.id
    assert lead_score.company_name == lead.company_name

    mem_result = await db_session.execute(
        select(Memory).where(
            Memory.source_uuid == lead_score_id,
            Memory.source_entity_type == "lead_score",
        )
    )
    memory = mem_result.scalar_one()
    assert memory.workspace_id == db_workspace.id
    assert memory.type == MemoryType.SEMANTIC
    assert "lead_score" in memory.tags


async def test_lead_score_trend_compared_to_previous_score(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    patched_embed_texts: Any,
) -> None:
    """The second score for a lead references the first and computes trend."""
    lead = await _make_lead(db_session, db_workspace)
    await _make_signal_event(db_session, db_workspace, lead.company_name)

    from app.config import config

    with mock.patch.object(config, "LEAD_SCORING_MICROS_PER_CALL", 0):
        ctx = _make_ctx(db_workspace, db_user)

        svc = LeadScoringService()

        first = await svc.score(
            db_session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

        # Add a stronger signal to move intent up.
        strong = SignalEvent(
            id=uuid4(),
            workspace_id=db_workspace.id,
            client_id=None,
            company_name=lead.company_name,
            signal_type="funding",
            source_url="https://example.com/funding-2",
            chunk_id=None,
            confidence=99.0,
            detected_at=datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC),
            processed=False,
        )
        db_session.add(strong)
        await db_session.flush()

        second = await svc.score(
            db_session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

    assert first.items[0].trend is None or first.items[0].trend == "stable"
    assert second.items[0].trend == "improving"
    assert second.items[0].previous_score_id == first.items[0].id


async def test_lead_score_degrades_on_insufficient_wallet(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    monkeypatch: Any,
) -> None:
    """When wallet has no credits, the service returns degraded and writes nothing."""
    lead = await _make_lead(db_session, db_workspace)

    from app.config import config
    from app.services.wallet_credit import InsufficientCreditsError

    with mock.patch.object(config, "LEAD_SCORING_MICROS_PER_CALL", 1000):
        monkeypatch.setattr(
            "app.lead_intelligence.scoring.service.wallet_credit.check_balance",
            mock.MagicMock(side_effect=InsufficientCreditsError("empty wallet")),
        )

        ctx = _make_ctx(db_workspace, db_user)

        svc = LeadScoringService()
        output = await svc.score(
            db_session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

    assert output.degraded is True
    assert "insufficient_wallet" in output.degradation_reasons
    assert output.items == []

    result = await db_session.execute(
        select(LeadScore).where(LeadScore.lead_id == lead.id)
    )
    assert result.scalar_one_or_none() is None

    mem_result = await db_session.execute(
        select(Memory).where(Memory.workspace_id == db_workspace.id)
    )
    assert mem_result.scalar_one_or_none() is None


async def test_lead_score_respects_tenant_client_id(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    patched_embed_texts: Any,
) -> None:
    """A LeadScore created for client_id='acme' is not returned for another client."""
    lead = await _make_lead(db_session, db_workspace)
    lead.client_id = "acme"
    await db_session.flush()
    await _make_signal_event(db_session, db_workspace, lead.company_name)

    from app.config import config

    with mock.patch.object(config, "LEAD_SCORING_MICROS_PER_CALL", 0):
        ctx = _make_ctx(db_workspace, db_user, client_id="acme")

        svc = LeadScoringService()
        output = await svc.score(
            db_session,
            ctx,
            LeadScoreInput(lead_ids=[lead.id]),
        )

    assert output.items[0].client_id == "acme"

    result = await db_session.execute(
        select(LeadScore).where(
            LeadScore.lead_id == lead.id,
            LeadScore.client_id == "acme",
        )
    )
    assert result.scalar_one() is not None
