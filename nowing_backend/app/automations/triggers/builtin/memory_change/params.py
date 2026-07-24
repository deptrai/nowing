"""``MemoryChangeTriggerParams`` — params for the ``memory_change`` trigger type.

A memory-typed specialization of the generic ``event`` trigger (FR-35): instead
of a raw ``event_type`` + JSON filter, it exposes the two dimensions a user
actually cares about for memory — the memory ``type`` and its ``tags`` — and
maps them onto ``memory.changed`` matching internally (see ``match.py``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MemoryChangeTriggerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: str | None = Field(
        default=None,
        description="Optional memory type to filter on (e.g. 'semantic').",
        examples=["semantic"],
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags; every listed tag must be present on the memory.",
        examples=[["competitor"]],
    )
