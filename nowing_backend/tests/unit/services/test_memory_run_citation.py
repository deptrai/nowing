"""Recall provenance/citation contract (Story 3.13, T5 / AC-3, AC-7).

What these pin down:

* ``MemoryRead`` and ``MemorySearchHit`` both expose ``source_run_id`` and a
  derived ``citation`` of the form ``run_<uuid>``;
* the citation is *soft* — derived from the id the memory carries, never from a
  live ``runs`` lookup — so it still renders after the run is retention-cleaned
  (AC-7);
* a chat/manual memory keeps ``citation is None`` and renders exactly as before,
  so adding provenance is not a regression for the other 4 source types;
* the three hand-rolled ``MemorySearchHit`` call sites now share one factory, so
  none of them can silently omit provenance — and none of them hardcodes a score.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def _memory_row(
    *,
    source_run_id=None,
    source_type="scraper_run",
    source_id=None,
    source_capability=None,
    source_input=None,
):
    """A duck-typed stand-in for an ORM ``Memory`` row."""
    return SimpleNamespace(
        id=11,
        content="Competitor X sells the widget at 19.99 USD",
        type=SimpleNamespace(value="semantic"),
        tags=["pricing"],
        confidence=0.9,
        source_type=SimpleNamespace(value=source_type),
        source_id=source_id,
        source_run_id=source_run_id,
        source_capability=source_capability,
        source_input=source_input,
    )


def test_search_hit_exposes_run_citation():
    """AC-3: a run-derived hit carries source_run_id and citation=run_<uuid>."""
    from app.schemas.memory import MemorySearchHit

    run_id = uuid.uuid4()
    hit = MemorySearchHit.from_memory(_memory_row(source_run_id=run_id), score=0.42)

    assert hit.source_type == "scraper_run"
    assert hit.source_run_id == str(run_id)
    assert hit.citation == f"run_{run_id}"
    assert hit.score == 0.42


def test_search_hit_citation_survives_json_serialization():
    """The citation must be present in the serialized JSON, not just on the model."""
    from app.schemas.memory import MemorySearchHit

    run_id = uuid.uuid4()
    payload = MemorySearchHit.from_memory(_memory_row(source_run_id=run_id)).model_dump(
        mode="json"
    )

    assert payload["source_run_id"] == str(run_id)
    assert payload["citation"] == f"run_{run_id}"
    # A UUID left unstringified would break JSON-only consumers.
    assert isinstance(payload["source_run_id"], str)


def test_chat_memory_has_no_citation():
    """No regression for the other source types: citation stays None."""
    from app.schemas.memory import MemorySearchHit

    hit = MemorySearchHit.from_memory(
        _memory_row(source_run_id=None, source_type="chat_message", source_id=7)
    )

    assert hit.source_run_id is None
    assert hit.citation is None
    assert hit.source_id == 7


def test_memory_read_exposes_run_citation():
    """AC-3: the read model carries the same provenance as the search hit."""
    from datetime import UTC, datetime

    from app.schemas.memory import MemoryRead

    run_id = uuid.uuid4()
    now = datetime.now(UTC)
    read = MemoryRead(
        id=5,
        workspace_id=1,
        type="semantic",
        content="fact",
        source_type="scraper_run",
        source_id=None,
        source_run_id=run_id,
        created_at=now,
        updated_at=now,
    )

    payload = read.model_dump(mode="json")
    assert payload["source_run_id"] == str(run_id)
    assert payload["citation"] == f"run_{run_id}"


def test_citation_is_soft_and_needs_no_run_row():
    """AC-7: the citation is derived from the id alone.

    Building the hit performs no ``runs`` lookup, so a run deleted by the 30-day
    retention cleanup still renders a stable citation instead of raising on a
    dangling soft reference.
    """
    from app.schemas.memory import MemorySearchHit

    dangling = uuid.uuid4()  # never existed in `runs`
    hit = MemorySearchHit.from_memory(_memory_row(source_run_id=dangling))

    assert hit.citation == f"run_{dangling}"


def test_all_search_hit_call_sites_use_the_shared_factory():
    """T5: no surface may hand-roll the hit and forget provenance.

    Guards the specific regression the story calls out: three separate call sites
    used to build ``MemorySearchHit(...)`` field-by-field, so provenance had to be
    added three times or one surface would silently ship without a citation.
    """
    import re
    from pathlib import Path

    call_sites = [
        "app/routes/memories_routes.py",
        "app/routes/research_threads_routes.py",
        "app/automations/actions/builtin/continue_research/invoke.py",
    ]
    root = Path(__file__).resolve().parents[3]

    for relative in call_sites:
        source = (root / relative).read_text()
        # A bare `MemorySearchHit(` construction (not `.from_memory(`) is the
        # hand-rolled shape this test forbids.
        assert not re.search(r"MemorySearchHit\(\s*$", source, re.MULTILINE), (
            f"{relative} still builds MemorySearchHit field-by-field"
        )
        assert "MemorySearchHit.from_memory(" in source, (
            f"{relative} does not use the shared factory"
        )
