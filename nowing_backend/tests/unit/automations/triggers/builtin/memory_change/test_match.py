"""Which triggers a ``memory.changed`` event fires: type + tags filter.

Red-phase ATDD (Story 6.5, AC-2). Pure predicate mirroring
``builtin/event/match.py::trigger_matches_event`` — a memory-typed
specialization that fires only for the ``memory.changed`` event and matches the
event payload's ``type`` and ``tags`` against the trigger's optional filter.

Expected surface:
    app.automations.triggers.builtin.memory_change.match.trigger_matches_event(
        params: dict, event: Event
    ) -> bool
where ``params`` is the persisted trigger params, e.g.
``{"memory_type": "semantic", "tags": ["competitor"]}`` (empty/omitted filter
matches any ``memory.changed`` event); ``tags`` uses subset semantics (every
trigger tag must be present in the event payload's tags).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_matches_memory_changed_event_by_type_and_tags() -> None:
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"memory_type": "semantic", "tags": ["competitor"]}
    event = Event(
        event_type="memory.changed",
        payload={"type": "semantic", "tags": ["competitor", "pricing"]},
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is True


def test_no_match_when_event_type_is_not_memory_changed() -> None:
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"memory_type": "semantic", "tags": []}
    event = Event(
        event_type="document.indexed",
        payload={"type": "semantic", "tags": []},
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is False


def test_no_match_when_memory_type_differs() -> None:
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"memory_type": "episodic", "tags": []}
    event = Event(
        event_type="memory.changed",
        payload={"type": "semantic", "tags": []},
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is False


def test_no_match_when_a_required_tag_is_absent() -> None:
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"memory_type": None, "tags": ["competitor", "pricing"]}
    event = Event(
        event_type="memory.changed",
        payload={"type": "semantic", "tags": ["competitor"]},
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is False


def test_empty_filter_matches_any_memory_changed_event() -> None:
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"memory_type": None, "tags": []}
    event = Event(
        event_type="memory.changed",
        payload={"type": "procedural", "tags": ["anything"]},
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is True


def test_match_tolerates_params_missing_the_tags_key() -> None:
    """Persisted params may omit ``tags`` entirely (not just pass ``[]``);
    a missing key is read as "no tag filter" via ``.get(...) or []``."""
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"memory_type": "semantic"}  # no "tags" key at all
    event = Event(
        event_type="memory.changed",
        payload={"type": "semantic", "tags": ["competitor"]},
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is True


def test_match_tolerates_params_missing_the_memory_type_key() -> None:
    """A params dict with no ``memory_type`` key matches any memory type."""
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"tags": ["competitor"]}  # no "memory_type" key
    event = Event(
        event_type="memory.changed",
        payload={"type": "episodic", "tags": ["competitor"]},
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is True


def test_match_tolerates_event_payload_missing_the_tags_key() -> None:
    """When the payload omits ``tags``, it is read as an empty set; a trigger
    that requires a tag then correctly does not match."""
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"memory_type": None, "tags": ["competitor"]}
    event = Event(
        event_type="memory.changed",
        payload={"type": "semantic"},  # no "tags" key
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is False


def test_match_ignores_automation_run_id_on_the_payload() -> None:
    """``match`` is a pure type/tags predicate; the origin marker is the
    *selector's* concern (mechanism 2). A stamped payload still matches here so
    the loop-guard stays a single, well-located drop."""
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    params = {"memory_type": "semantic", "tags": ["competitor"]}
    event = Event(
        event_type="memory.changed",
        payload={
            "type": "semantic",
            "tags": ["competitor"],
            "automation_run_id": 123,
        },
        workspace_id=7,
    )

    assert trigger_matches_event(params, event) is True


# --- Mutation-hardening (Story 6.5, Stage 5) ---------------------------------
# cosmic-ray could not run in this environment (only `uv run` resolves the
# correct litellm; its per-mutant native test-command is unavailable), so these
# tests explicitly pin the mutation-sensitive branches of the tag/type filter
# that a weaker suite would let survive: the subset DIRECTION (issubset vs
# issuperset/equality) and the memory_type None-vs-set boundary.


def test_tag_filter_is_subset_not_superset_or_equality() -> None:
    """required ⊊ event → True. Kills `.issubset`→`.issuperset` and
    `.issubset`→`==`: a strict-subset match must still fire."""
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    event = Event(
        event_type="memory.changed",
        payload={"type": "semantic", "tags": ["a", "b", "c"]},
        workspace_id=7,
    )
    # required is a strict subset of the event tags.
    assert trigger_matches_event({"tags": ["a"]}, event) is True
    # superset direction must NOT match (required has a tag the event lacks).
    assert trigger_matches_event({"tags": ["a", "z"]}, event) is False


def test_memory_type_none_matches_any_but_set_is_strict() -> None:
    """memory_type=None matches any payload type (kills `is not None`→`is None`);
    a set memory_type only matches its own type (kills the guard removal)."""
    from app.automations.triggers.builtin.memory_change.match import (
        trigger_matches_event,
    )
    from app.event_bus import Event

    for payload_type in ("semantic", "episodic", "procedural", "working"):
        event = Event(
            event_type="memory.changed",
            payload={"type": payload_type, "tags": []},
            workspace_id=7,
        )
        assert trigger_matches_event({"memory_type": None, "tags": []}, event) is True
        assert trigger_matches_event(
            {"memory_type": "semantic", "tags": []}, event
        ) is (payload_type == "semantic")
