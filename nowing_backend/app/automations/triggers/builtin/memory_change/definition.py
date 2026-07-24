"""``memory_change`` ``TriggerDefinition`` registration."""

from __future__ import annotations

from app.automations.triggers.store import register_trigger
from app.automations.triggers.types import TriggerDefinition

from .params import MemoryChangeTriggerParams

MEMORY_CHANGE_TRIGGER = TriggerDefinition(
    type="memory_change",
    description=(
        "Fire when a workspace memory is created or updated, optionally filtered "
        "by memory type and tags."
    ),
    params_model=MemoryChangeTriggerParams,
)

register_trigger(MEMORY_CHANGE_TRIGGER)
