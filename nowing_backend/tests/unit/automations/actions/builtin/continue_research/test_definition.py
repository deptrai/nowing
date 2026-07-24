"""The ``continue_research`` action self-registers on the actions store at import.

Red-phase ATDD (Story 6.5, AC-3). Registration canary mirroring the write-back
canaries in ``tests/unit/automations/test_import_registrations.py``: importing
``app.automations`` must make ``continue_research`` discoverable via
``get_action``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_continue_research_action_is_registered() -> None:
    import app.automations  # noqa: F401  (force package import + registration side-effects)
    from app.automations.actions.builtin.continue_research.params import (
        ContinueResearchActionParams,
    )
    from app.automations.actions.store import get_action

    definition = get_action("continue_research")

    assert definition is not None
    assert definition.type == "continue_research"
    assert definition.params_model is ContinueResearchActionParams
