"""Unit tests for ProjectContextService (Story 3.18)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.documents import Document
from app.models.projects import Project, ProjectPinnedDocument
from app.services.project_context_service import (
    ProjectContextService,
    _approx_tokens,
    _count_tokens,
)

pytestmark = pytest.mark.unit


def test_approx_tokens():
    assert _approx_tokens("") == 1
    assert _approx_tokens("1234") == 1
    assert _approx_tokens("12345678") == 2
    assert _approx_tokens("a" * 400) == 100


def test_count_tokens_fallback():
    assert _count_tokens("") == 0
    assert _count_tokens("hello world", llm=None) == _approx_tokens("hello world")


def test_build_project_context_empty():
    project = Project(
        id=1,
        workspace_id=10,
        name="Empty Project",
        master_instructions="",
        is_archived=False,
    )
    result = ProjectContextService.build_project_context(project, [])
    assert result == ""


def test_build_project_context_master_instructions_only():
    project = Project(
        id=1,
        workspace_id=10,
        name="Apollo Project",
        master_instructions="You are a senior analyst for Apollo.",
        is_archived=False,
    )
    result = ProjectContextService.build_project_context(project, [])
    assert "<project_context id=\"1\" name=\"Apollo Project\">" in result
    assert "<project_master_instructions name=\"Apollo Project\">" in result
    assert "You are a senior analyst for Apollo." in result
    assert "</project_master_instructions>" in result
    assert "</project_context>" in result


def test_build_project_context_with_pinned_docs():
    project = Project(
        id=2,
        workspace_id=10,
        name="Real Estate Strategy",
        master_instructions="Focus on residential properties in HCMC.",
        is_archived=False,
    )
    now = datetime.now(UTC)
    pin1 = ProjectPinnedDocument(id=1, project_id=2, document_id=101, pinned_at=now)
    doc1 = Document(
        id=101,
        workspace_id=10,
        title="Q3 Strategy Note",
        source_markdown="District 2 market cap has grown by 15%.",
        content="District 2 market cap has grown by 15%.",
    )

    pin2 = ProjectPinnedDocument(id=2, project_id=2, document_id=102, pinned_at=now)
    doc2 = Document(
        id=102,
        workspace_id=10,
        title="Legal Guidelines",
        source_markdown=None,
        content="Law on real estate business 2024 compliance notes.",
    )

    pinned_pairs = [(pin1, doc1), (pin2, doc2)]
    result = ProjectContextService.build_project_context(project, pinned_pairs)

    assert "<project_context id=\"2\" name=\"Real Estate Strategy\">" in result
    assert "<project_pinned_documents>" in result
    assert "<pinned_document id=\"101\" title=\"Q3 Strategy Note\">" in result
    assert "District 2 market cap has grown by 15%." in result
    assert "<pinned_document id=\"102\" title=\"Legal Guidelines\">" in result
    assert "Law on real estate business 2024 compliance notes." in result


def test_build_project_context_pinned_docs_budget_truncation():
    project = Project(
        id=3,
        workspace_id=10,
        name="Heavy Project",
        master_instructions="Brief instructions.",
        is_archived=False,
    )
    now = datetime.now(UTC)
    pin1 = ProjectPinnedDocument(id=1, project_id=3, document_id=201, pinned_at=now)
    # Long text: ~12,000 characters -> ~3,000 tokens
    doc1 = Document(
        id=201,
        workspace_id=10,
        title="Big Doc 1",
        source_markdown="Lorem ipsum dolor sit amet " * 400,
    )

    pin2 = ProjectPinnedDocument(id=2, project_id=3, document_id=202, pinned_at=now)
    # Another long text: ~12,000 characters
    doc2 = Document(
        id=202,
        workspace_id=10,
        title="Big Doc 2",
        source_markdown="Consectetur adipiscing elit " * 400,
    )

    pinned_pairs = [(pin1, doc1), (pin2, doc2)]
    result = ProjectContextService.build_project_context(
        project,
        pinned_pairs,
        max_pinned_tokens=4000,
        max_total_chars=25000,
    )

    assert "<pinned_document id=\"201\" title=\"Big Doc 1\">" in result
    # Doc 2 should be truncated or capped
    assert "<pinned_document id=\"202\" title=\"Big Doc 2\">" in result
    assert "...[truncated]" in result or "Big Doc 2" in result


@pytest.mark.asyncio
async def test_load_project_with_pinned_docs_active():
    session = AsyncMock()
    project = Project(
        id=1,
        workspace_id=10,
        name="Active Project",
        master_instructions="Instructions",
        is_archived=False,
    )
    doc = Document(
        id=101,
        workspace_id=10,
        title="Doc 1",
        source_markdown="Content 1",
    )
    pin = ProjectPinnedDocument(
        id=1,
        project_id=1,
        document_id=101,
        pinned_at=datetime.now(UTC),
    )

    mock_proj_res = MagicMock()
    mock_proj_res.scalars.return_value.first.return_value = project

    mock_pins_res = MagicMock()
    mock_pins_res.all.return_value = [(pin, doc)]

    session.execute.side_effect = [mock_proj_res, mock_pins_res]

    loaded_proj, pinned_pairs = await ProjectContextService.load_project_with_pinned_docs(
        session, project_id=1, workspace_id=10
    )
    assert loaded_proj is not None
    assert loaded_proj.id == 1
    assert len(pinned_pairs) == 1
    assert pinned_pairs[0][1].title == "Doc 1"


@pytest.mark.asyncio
async def test_load_project_with_pinned_docs_archived_returns_none():
    session = AsyncMock()
    project = Project(
        id=1,
        workspace_id=10,
        name="Archived Project",
        master_instructions="Instructions",
        is_archived=True,
    )

    mock_proj_res = MagicMock()
    mock_proj_res.scalars.return_value.first.return_value = project

    session.execute.side_effect = [mock_proj_res]

    loaded_proj, pinned_pairs = await ProjectContextService.load_project_with_pinned_docs(
        session, project_id=1, workspace_id=10
    )
    assert loaded_proj is None
    assert pinned_pairs == []
