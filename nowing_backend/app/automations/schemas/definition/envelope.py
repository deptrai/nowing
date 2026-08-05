"""``AutomationDefinition`` — top-level envelope persisted in ``automations.definition``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .execution import Execution
from .inputs import Inputs
from .metadata import Metadata
from .plan_step import PlanStep
from .trigger_spec import TriggerSpec


class AutomationModels(BaseModel):
    """Captured model profile for an automation.

    Snapshotted from the workspace's model roles at create time so runs are
    insulated from later chat/workspace model changes. Model-id conventions
    match the shared scheme (``0`` Auto, ``< 0`` global, ``> 0`` BYOK).
    """

    model_config = ConfigDict(extra="forbid")

    chat_model_id: int = 0
    image_gen_model_id: int = 0
    vision_model_id: int = 0


class AutomationDefinition(BaseModel):
    """Top-level shape of an automation."""

    model_config = ConfigDict(extra="forbid")

    # B11/B3: only 1.0 (legacy-read) and 1.1 (new-write producer) are supported.
    # The default is the current new-write producer version so a missing
    # schema_version is treated as today's strict contract; an explicit "1.0"
    # in a persisted snapshot still selects the legacy contract at runtime.
    # create/update always overwrite to "1.1" to be explicit.
    schema_version: Literal["1.0", "1.1"] = "1.1"
    name: str = Field(..., min_length=1, max_length=200)
    goal: str | None = None
    inputs: Inputs | None = None
    triggers: list[TriggerSpec] = Field(default_factory=list)
    plan: list[PlanStep] = Field(..., min_length=1)
    execution: Execution = Field(default_factory=Execution)
    metadata: Metadata = Field(default_factory=Metadata)
    # Captured server-side at create() and preserved across update(); resolved
    # at runtime instead of the live workspace. Optional so drafts/builder
    # payloads validate without it.
    models: AutomationModels | None = None
