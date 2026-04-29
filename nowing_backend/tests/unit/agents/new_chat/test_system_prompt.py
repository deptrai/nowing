"""Unit tests for Story 0.3: Main Agent Orchestration Prompt Update.

Covers:
- AC2: Lookup table — all 4 agent names present in crypto_orchestration section
- AC3: Parallel task() example present in section
- AC5: Section isolation — <crypto_orchestration> only in NOWING (not shared) block

Implementation notes:
- Uses file-text scan anchored via __file__ (no cwd dependence, works in CI).
- Does NOT import private module-level names; scoping is done via regex on the
  source file directly. This keeps the tests resilient to internal refactors
  (e.g. renames of the shared-instructions constant).
"""

import re
from pathlib import Path

import pytest

# Anchor path from this test file — independent of pytest working directory.
# tests/unit/agents/new_chat/test_system_prompt.py
#   parents[0] new_chat  parents[1] agents  parents[2] unit
#   parents[3] tests     parents[4] nowing_backend
_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[4]
    / "app"
    / "agents"
    / "new_chat"
    / "system_prompt.py"
)


@pytest.fixture(scope="module")
def source_text() -> str:
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def nowing_block(source_text: str) -> str:
    """Extract the NOWING_SYSTEM_INSTRUCTIONS triple-quoted literal."""
    m = re.search(
        r'NOWING_SYSTEM_INSTRUCTIONS\s*=\s*"""(.*?)"""',
        source_text,
        re.DOTALL,
    )
    assert m, "NOWING_SYSTEM_INSTRUCTIONS literal not found"
    return m.group(1)


@pytest.fixture(scope="module")
def crypto_section(nowing_block: str) -> str:
    """Extract only the <crypto_orchestration>...</crypto_orchestration> body."""
    m = re.search(
        r"<crypto_orchestration>(.*?)</crypto_orchestration>",
        nowing_block,
        re.DOTALL,
    )
    assert m, "<crypto_orchestration> section not found in NOWING_SYSTEM_INSTRUCTIONS"
    return m.group(1)


@pytest.fixture(scope="module")
def shared_block(source_text: str) -> str:
    """Extract the team-thread (shared) instructions literal by scanning every
    top-level *_SYSTEM_INSTRUCTIONS_* string and taking the one that is NOT
    the NOWING block. This avoids hard-coding the private constant name."""
    literals = re.findall(
        r'(\w*SYSTEM_INSTRUCTIONS\w*)\s*=\s*"""(.*?)"""',
        source_text,
        re.DOTALL,
    )
    shared = [body for name, body in literals if name != "NOWING_SYSTEM_INSTRUCTIONS"]
    assert shared, "No team/shared instructions literal found alongside NOWING"
    return "\n".join(shared)


class TestCryptoOrchestrationSection:
    """AC5: crypto_orchestration section exists in NOWING_SYSTEM_INSTRUCTIONS."""

    def test_section_tag_present(self, nowing_block: str):
        assert "<crypto_orchestration>" in nowing_block
        assert "</crypto_orchestration>" in nowing_block

    def test_section_absent_from_shared_instructions(self, shared_block: str):
        """AC5: Section isolation — shared team-thread prompt must NOT be touched."""
        assert "<crypto_orchestration>" not in shared_block


class TestAgentLookupTable:
    """AC2: All 4 agent names present inside the crypto_orchestration section.

    Scoped to `crypto_section` (not the whole prompt) so the assertion genuinely
    validates the lookup table rather than a stray mention elsewhere.
    """

    @pytest.mark.parametrize(
        "agent_name",
        [
            "defillama_analyst",
            "sentiment_analyst",
            "news_analyst",
            "smart_contract_analyst",
        ],
    )
    def test_agent_name_in_crypto_section(self, crypto_section: str, agent_name: str):
        assert agent_name in crypto_section


class TestTaskExamples:
    """AC3: task() parallel call example present inside the section."""

    def test_task_call_pattern_in_crypto_section(self, crypto_section: str):
        # At least one task(agent_name, "...") pseudocode call.
        assert re.search(r"task\(\s*\w+", crypto_section), (
            "Expected a task(<agent>, ...) pseudocode example inside "
            "<crypto_orchestration>"
        )
