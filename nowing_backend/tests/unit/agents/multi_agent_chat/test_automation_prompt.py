"""Story 3.14 (D9): the automation drafter must only ever emit ``schema_version``
``1.1`` — the parser's ``"1.0"`` default is legacy-read compatibility only, not a
new-write producer (see story Dev Notes, "Definitive touch set")."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.main_agent.tools.automation.prompt import (
    build_draft_prompt,
)

pytestmark = pytest.mark.unit


def test_rendered_prompt_emits_four_schema_version_1_1_occurrences() -> None:
    prompt = build_draft_prompt(workspace_id=7, intent="do something useful")
    assert prompt.count('"schema_version": "1.1"') == 4


def test_rendered_prompt_never_emits_a_new_write_schema_version_1_0() -> None:
    prompt = build_draft_prompt(workspace_id=7, intent="do something useful")
    assert '"schema_version": "1.0"' not in prompt
