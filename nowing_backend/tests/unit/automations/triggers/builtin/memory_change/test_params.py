"""``MemoryChangeTriggerParams`` contract (Story 6.5, AC-2, FR-35).

Red-phase ATDD scaffolds. The ``memory_change`` trigger params model does not
exist yet, so every app import is performed *inside* a test — the module
collects cleanly while the feature is unimplemented, and each test is skipped
until ``dev-story`` builds it (red -> green).

Expected surface (mirrors ``builtin/event/params.py``):
    app.automations.triggers.builtin.memory_change.params.MemoryChangeTriggerParams
      - memory_type: str | None = None   # optional memory-type filter
      - tags: list[str] = []             # optional tag filter (subset match)
      - model_config = ConfigDict(extra="forbid")
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_accepts_memory_type_and_tags() -> None:
    from app.automations.triggers.builtin.memory_change.params import (
        MemoryChangeTriggerParams,
    )

    params = MemoryChangeTriggerParams(memory_type="semantic", tags=["competitor"])

    assert params.memory_type == "semantic"
    assert params.tags == ["competitor"]


def test_memory_type_and_tags_are_optional() -> None:
    from app.automations.triggers.builtin.memory_change.params import (
        MemoryChangeTriggerParams,
    )

    params = MemoryChangeTriggerParams()

    assert params.memory_type is None
    assert params.tags == []


def test_extra_keys_are_forbidden() -> None:
    from app.automations.triggers.builtin.memory_change.params import (
        MemoryChangeTriggerParams,
    )

    with pytest.raises(ValueError):
        MemoryChangeTriggerParams(memory_type="semantic", typo=True)
