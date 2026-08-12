"""``memory.changed`` payload contract + catalog registration (Story 6.5, AC-1).

Mirrors ``test_document_entered_folder``: locks the fields a ``memory_change``
trigger filters on (``type``, ``tags``) plus the identifiers a downstream step
needs (``memory_id``, ``workspace_id``, ``research_thread_id``), the origin
marker the selector's loop-guard reads (``automation_run_id``), and that the
event type is registered so subscribers can discover it.
"""

from __future__ import annotations

import pytest

from app.event_bus.catalog import catalog
from app.event_bus.events.memory_changed import EVENT_TYPE, MemoryChangedPayload

pytestmark = pytest.mark.unit


def _payload(**overrides: object) -> MemoryChangedPayload:
    base: dict[str, object] = {
        "memory_id": 42,
        "workspace_id": 7,
        "type": "semantic",
        "change": "created",
        "source_type": "manual",
        "client_id": None,
        "agent_id": None,
    }
    base.update(overrides)
    return MemoryChangedPayload(**base)


def test_payload_carries_the_filterable_and_routing_fields() -> None:
    payload = _payload(tags=["competitor", "pricing"], research_thread_id=3)

    assert payload.memory_id == 42
    assert payload.workspace_id == 7
    assert payload.type == "semantic"
    assert payload.tags == ["competitor", "pricing"]
    assert payload.change == "created"
    assert payload.source_type == "manual"
    assert payload.research_thread_id == 3


def test_optional_fields_default_to_empty_and_none() -> None:
    """A non-thread, non-origin write omits ``tags``/``research_thread_id``/
    ``automation_run_id`` — they must default rather than be required."""
    payload = _payload()

    assert payload.tags == []
    assert payload.research_thread_id is None
    assert payload.automation_run_id is None


def test_automation_run_id_marks_origin_for_the_selector_loop_guard() -> None:
    """The origin marker (mechanism 2) round-trips through the serialized payload
    the selector inspects."""
    dumped = _payload(automation_run_id=99).model_dump(mode="json")

    assert dumped["automation_run_id"] == 99


def test_extra_keys_are_forbidden() -> None:
    """``extra="forbid"`` keeps the payload a stable, typed contract."""
    with pytest.raises(ValueError):
        _payload(unexpected="nope")


def test_event_type_is_registered_in_the_catalog() -> None:
    registered = catalog.get(EVENT_TYPE)

    assert registered is not None
    assert registered.payload_model is MemoryChangedPayload


def test_payload_carries_client_and_agent_scope() -> None:
    """AC-18.6: memory change events carry client_id/agent_id so automations can
    filter by vertical tenant."""
    payload = _payload(client_id="bds", agent_id="bds-agent-1")

    assert payload.client_id == "bds"
    assert payload.agent_id == "bds-agent-1"


def test_client_and_agent_default_to_none() -> None:
    """Unscoped memories still emit the event with null client/agent fields."""
    payload = _payload()

    assert payload.client_id is None
    assert payload.agent_id is None
