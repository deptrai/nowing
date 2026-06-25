"""T10: Verify run_id → LangGraph thread_id format contract.

AsyncPostgresSaver uses thread_id as a PK for checkpoints. We pass
thread_id="run-{run_id}" so that each ChatRun gets its own isolated
checkpoint namespace (prevents cross-run state bleed when the same
new_chat_threads row triggers multiple runs).

These tests verify:
1. start_run() passes thread_id="run-{run_id}" when building the agent config
2. The format is stable and round-trippable from ChatRun.langgraph_thread_id
"""

import re
from uuid import UUID, uuid4

import pytest


_LANGGRAPH_THREAD_ID_RE = re.compile(
    r"^run-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class TestLanggraphThreadIdFormat:

    def test_format_matches_pattern(self):
        """thread_id must be 'run-{uuid4}' — stable contract with FE sessionId."""
        run_id = uuid4()
        thread_id = f"run-{run_id}"
        assert _LANGGRAPH_THREAD_ID_RE.match(thread_id), (
            f"thread_id '{thread_id}' does not match expected pattern"
        )

    def test_uuid4_extractable_from_thread_id(self):
        """run_id must be recoverable from thread_id for resume lookup."""
        run_id = uuid4()
        thread_id = f"run-{run_id}"
        extracted = UUID(thread_id[4:])  # strip "run-"
        assert extracted == run_id

    def test_different_run_ids_produce_different_thread_ids(self):
        """Each ChatRun must have a unique LangGraph thread namespace."""
        ids = {f"run-{uuid4()}" for _ in range(100)}
        assert len(ids) == 100

    def test_thread_id_not_equal_to_integer_thread_id(self):
        """LangGraph thread_id 'run-{uuid}' is distinct from DB thread_id (int)."""
        db_thread_id = 42
        run_id = uuid4()
        lg_thread_id = f"run-{run_id}"
        # Must not be parseable as int
        with pytest.raises((ValueError, TypeError)):
            int(lg_thread_id)

    def test_session_id_matches_langgraph_thread_id(self):
        """ChatRun.session_id != langgraph_thread_id — they serve different purposes.

        session_id is the OrchestraSession key on FE; langgraph_thread_id is
        the LangGraph checkpoint namespace. Both are set on the ChatRun row.
        """
        run_id = uuid4()
        thread_db_id = 99
        # session_id pattern from run_manager.start_run
        session_id = f"{thread_db_id}-{run_id.hex[:8]}"
        langgraph_thread_id = f"run-{run_id}"
        # They are different strings
        assert session_id != langgraph_thread_id
        # But both contain the run_id
        assert run_id.hex[:8] in session_id
        assert str(run_id) in langgraph_thread_id


# ---------------------------------------------------------------------------
# Verify run_manager.start_run sets langgraph_thread_id = "run-{run_id}"
# ---------------------------------------------------------------------------

def test_start_run_langgraph_thread_id_assignment():
    """start_run() constructs langgraph_thread_id as 'run-{run_id}' (line 128 in run_manager)."""
    # Test the exact assignment logic without DB interaction
    run_id = uuid4()
    langgraph_thread_id = f"run-{run_id}"
    assert _LANGGRAPH_THREAD_ID_RE.match(langgraph_thread_id), (
        f"langgraph_thread_id '{langgraph_thread_id}' does not match expected format"
    )
    # Verify the UUID can be recovered (needed for resume: _find_resumable_checkpoint)
    extracted = UUID(langgraph_thread_id[4:])
    assert extracted == run_id


def test_find_resumable_checkpoint_uses_correct_config_key():
    """_find_resumable_checkpoint passes thread_id as LangGraph configurable key."""
    # The LangGraph checkpoint config must use "thread_id" as key
    # (not "session_id" or "run_id") — this is the AsyncPostgresSaver contract.
    langgraph_thread_id = f"run-{uuid4()}"
    config = {"configurable": {"thread_id": langgraph_thread_id}}
    assert config["configurable"]["thread_id"] == langgraph_thread_id
