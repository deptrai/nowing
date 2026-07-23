"""Lock the bundled import side-effects.

Importing ``app.automations`` (the package) registers the v1 bundled
action (``agent_task``) and the v1 bundled trigger (``schedule``). If the
import chain breaks (e.g. someone removes ``from . import definition``
in a sub-package ``__init__``), the system would silently launch with an
empty registry. These tests are the canary.
"""

from __future__ import annotations

import pytest

import app.automations  # noqa: F401  (force the package import + its side-effects)
from app.automations.actions.store import get_action
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.triggers.store import get_trigger

pytestmark = pytest.mark.unit


def test_bundled_agent_task_action_is_registered_after_package_import() -> None:
    """``agent_task`` — the v1 default action — must be discoverable in
    the registry after the package is imported."""
    definition = get_action("agent_task")

    assert definition is not None
    assert definition.type == "agent_task"



def test_write_back_actions_are_registered_after_package_import() -> None:
    """All direct write-back action types must be discoverable after import."""
    for action_type in (
        "write_back_notion",
        "write_back_linear",
        "write_back_jira",
        "write_back_slack",
    ):
        definition = get_action(action_type)
        assert definition is not None, f"{action_type!r} not registered"
        assert definition.type == action_type


def test_bundled_schedule_trigger_is_registered_after_package_import() -> None:
    """``schedule`` — the only v1 trigger — must be discoverable in the
    registry after the package is imported."""
    definition = get_trigger(TriggerType.SCHEDULE.value)

    assert definition is not None
    assert definition.type == TriggerType.SCHEDULE.value
