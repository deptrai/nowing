"""The ``memory_change`` trigger self-registers on the triggers store at import.

Red-phase ATDD (Story 6.5, AC-2). Registration canary mirroring
``builtin/event/test_definition.py`` and the bundled-import canary in
``tests/unit/automations/test_import_registrations.py``: importing
``app.automations`` must make the ``memory_change`` trigger discoverable, and the
``TriggerType`` enum must carry the new ``memory_change`` member (the postgres
``automation_trigger_type`` enum mirrors it).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_memory_change_trigger_is_registered() -> None:
    import app.automations  # noqa: F401  (force package import + registration side-effects)
    from app.automations.triggers.builtin.memory_change.params import (
        MemoryChangeTriggerParams,
    )
    from app.automations.triggers.store import get_trigger

    definition = get_trigger("memory_change")

    assert definition is not None
    assert definition.type == "memory_change"
    assert definition.params_model is MemoryChangeTriggerParams


def test_memory_change_trigger_type_enum_exists() -> None:
    from app.automations.persistence.enums.trigger_type import TriggerType

    assert TriggerType.MEMORY_CHANGE.value == "memory_change"
