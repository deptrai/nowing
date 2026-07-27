"""``ContinueResearchActionParams`` — params for the ``continue_research`` action.

Story 3.14 (D9) pins new (schema_version 1.1) writes to ``top_k`` 1..5. A
persisted ``schema_version 1.0`` (or missing-version legacy) run still needs to
honour its old 1..100 ceiling, so :class:`_LegacyContinueResearchActionParams`
keeps that wider range for ``invoke.py`` to validate against and then clamp
6..100 down to 5 with a warning — never used as a new-write producer.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.utils.strict_fields import strict_top_k


class ContinueResearchActionParams(BaseModel):
    """Resume a saved research thread: recall its memories + prior citations."""

    model_config = ConfigDict(extra="forbid")

    research_thread_id: int = Field(
        ...,
        description="Id of the research thread to continue (must exist in the workspace).",
    )
    top_k: strict_top_k(
        le=5, description="Number of thread-scoped memories to recall."
    ) = 5


class _LegacyContinueResearchActionParams(BaseModel):
    """``schema_version 1.0``-only: same shape, wider legacy ``top_k`` ceiling."""

    model_config = ConfigDict(extra="forbid")

    research_thread_id: int = Field(
        ...,
        description="Id of the research thread to continue (must exist in the workspace).",
    )
    top_k: strict_top_k(
        le=100, description="Number of thread-scoped memories to recall."
    ) = 5
