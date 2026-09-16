"""Unit tests for Presentation Studio format entitlement gating (Story 31.4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.capabilities.presentation.generate.executor import (
    execute_generate_presentation,
)
from app.capabilities.presentation.generate.schemas import PresentationCapabilityInput
from app.services.presentation.schemas import GeneratePresentationInput
from app.services.presentation.service import PresentationStudioService


@pytest.fixture
def mock_deck_llm(monkeypatch):
    """Mock LLM deck generator and marp render so tests don't make real network or subprocess calls."""
    deck_spec = {
        "title": "Test Deck",
        "slug": "test-deck",
        "slides": [{"title": "Slide 1", "bullets": ["Point A"]}],
    }
    monkeypatch.setattr(
        "app.services.presentation.service.PresentationStudioService._call_llm_for_deck",
        AsyncMock(return_value=(deck_spec, {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})),
    )
    monkeypatch.setattr(
        "app.services.presentation.service.render_marp_html",
        AsyncMock(return_value=(True, None)),
    )


def _make_mock_session():
    session = MagicMock()
    session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.mark.unit
async def test_free_tier_pptx_is_hard_blocked(monkeypatch):
    """Free tier + pptx -> 403 HTTPException with exact upgrade detail."""
    monkeypatch.setattr(
        "app.services.presentation.service.WorkspaceLimitService.get_effective_limits",
        AsyncMock(return_value=MagicMock(plan_tier="free")),
    )
    service = PresentationStudioService()
    session = _make_mock_session()

    build_input = GeneratePresentationInput(
        prompt="Create a deck",
        output_format="pptx",
        workspace_id=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.generate(build_input=build_input, session=session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "PPTX format generation is not enabled on this workspace plan; use Marp or upgrade"


@pytest.mark.unit
async def test_free_tier_marp_is_allowed(monkeypatch, mock_deck_llm):
    """Free tier + marp -> generation proceeds with format=marp."""
    monkeypatch.setattr(
        "app.services.presentation.service.WorkspaceLimitService.get_effective_limits",
        AsyncMock(return_value=MagicMock(plan_tier="free")),
    )
    service = PresentationStudioService()
    session = _make_mock_session()

    build_input = GeneratePresentationInput(
        prompt="Create a deck",
        output_format="marp",
        workspace_id=1,
    )

    result = await service.generate(build_input=build_input, session=session)
    assert result.status == "ready"
    assert result.format == "marp"


@pytest.mark.unit
@pytest.mark.parametrize("paid_tier", ["team", "growth", "enterprise", "TEAM", "Enterprise"])
async def test_paid_tier_pptx_is_allowed(monkeypatch, mock_deck_llm, paid_tier):
    """Paid tier (team, growth, enterprise) + pptx -> generation proceeds with format=pptx."""
    monkeypatch.setattr(
        "app.services.presentation.service.WorkspaceLimitService.get_effective_limits",
        AsyncMock(return_value=MagicMock(plan_tier=paid_tier)),
    )
    service = PresentationStudioService()
    session = _make_mock_session()

    build_input = GeneratePresentationInput(
        prompt="Create a pitch deck",
        output_format="pptx",
        workspace_id=42,
    )

    result = await service.generate(build_input=build_input, session=session)
    assert result.status == "ready"
    assert result.format == "pptx"


@pytest.mark.unit
async def test_paid_tier_marp_is_allowed(monkeypatch, mock_deck_llm):
    """Paid tier + marp -> generation proceeds with format=marp."""
    monkeypatch.setattr(
        "app.services.presentation.service.WorkspaceLimitService.get_effective_limits",
        AsyncMock(return_value=MagicMock(plan_tier="growth")),
    )
    service = PresentationStudioService()
    session = _make_mock_session()

    build_input = GeneratePresentationInput(
        prompt="Create a deck",
        output_format="marp",
        workspace_id=1,
    )

    result = await service.generate(build_input=build_input, session=session)
    assert result.status == "ready"
    assert result.format == "marp"


@pytest.mark.unit
async def test_missing_workspace_id_treated_as_free_and_blocked(monkeypatch):
    """Missing workspace (workspace_id=None) + pptx -> fails closed as free (403)."""
    service = PresentationStudioService()
    session = _make_mock_session()

    build_input = MagicMock(
        prompt="Create a pitch deck",
        output_format="pptx",
        workspace_id=None,
        language="en",
        user_id=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.generate(build_input=build_input, session=session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "PPTX format generation is not enabled on this workspace plan; use Marp or upgrade"


@pytest.mark.unit
async def test_missing_workspace_id_marp_is_allowed(monkeypatch, mock_deck_llm):
    """Missing workspace (workspace_id=None) + marp -> proceeds."""
    service = PresentationStudioService()
    session = _make_mock_session()

    build_input = MagicMock(
        prompt="Create a deck",
        output_format="marp",
        workspace_id=None,
        language="en",
        user_id=None,
    )

    result = await service.generate(build_input=build_input, session=session)
    assert result.status == "ready"
    assert result.format == "marp"


@pytest.mark.unit
@pytest.mark.parametrize("unknown_tier", [None, "starter", "pro", "unknown"])
async def test_unknown_or_none_plan_tier_treated_as_free(monkeypatch, unknown_tier):
    """plan_tier=None or non-entitled tier + pptx -> treated as free and blocked (403)."""
    monkeypatch.setattr(
        "app.services.presentation.service.WorkspaceLimitService.get_effective_limits",
        AsyncMock(return_value=MagicMock(plan_tier=unknown_tier)),
    )
    service = PresentationStudioService()
    session = _make_mock_session()

    build_input = GeneratePresentationInput(
        prompt="Create a deck",
        output_format="pptx",
        workspace_id=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.generate(build_input=build_input, session=session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "PPTX format generation is not enabled on this workspace plan; use Marp or upgrade"


@pytest.mark.unit
async def test_capability_executor_blocked_on_free_tier_pptx(monkeypatch):
    """Capability executor delegates to service and fails closed with 403 on free tier pptx."""
    monkeypatch.setattr(
        "app.services.presentation.service.WorkspaceLimitService.get_effective_limits",
        AsyncMock(return_value=MagicMock(plan_tier="free")),
    )
    session = _make_mock_session()

    input_data = PresentationCapabilityInput(
        prompt="Create a deck",
        output_format="pptx",
        workspace_id=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        await execute_generate_presentation(session=session, input_data=input_data)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "PPTX format generation is not enabled on this workspace plan; use Marp or upgrade"
