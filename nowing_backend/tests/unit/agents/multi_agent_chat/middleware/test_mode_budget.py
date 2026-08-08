"""Unit tests for the mode-aware tool-call budget middleware."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.agents.chat.multi_agent_chat.main_agent.middleware.mode_budget import (
    ModeBudgetMiddleware,
    _breakdown_tool_call,
)


def _tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "args": args, "id": f"call_{name}"}


@pytest.fixture
def mw() -> ModeBudgetMiddleware:
    return ModeBudgetMiddleware()


@pytest.mark.parametrize(
    ("tool_call", "expected_kb", "expected_non_kb", "expected_other"),
    [
        (_tool_call("ask_knowledge_base", {"query": "x"}), 1, 0, 0),
        (_tool_call("task", {"subagent_type": "knowledge_base"}), 1, 0, 0),
        (_tool_call("task", {"subagent_type": "knowledge_base_readonly"}), 1, 0, 0),
        (
            _tool_call(
                "task",
                {"tasks": [{"subagent_type": "knowledge_base", "description": "x"}]},
            ),
            1,
            0,
            0,
        ),
        (_tool_call("task", {"subagent_type": "chainlens"}), 0, 1, 0),
        (_tool_call("task", {"subagent_type": "google_search"}), 0, 1, 0),
        (_tool_call("update_memory", {"content": "x"}), 0, 0, 1),
        (_tool_call("read_run", {"run_id": 1}), 0, 0, 1),
        (
            _tool_call(
                "task",
                {
                    "tasks": [
                        {"subagent_type": "knowledge_base", "description": "x"},
                        {"subagent_type": "google_search", "description": "y"},
                    ]
                },
            ),
            1,
            1,
            0,
        ),
    ],
)
def test_breakdown_tool_call(
    tool_call: dict[str, Any],
    expected_kb: int,
    expected_non_kb: int,
    expected_other: int,
) -> None:
    bd = _breakdown_tool_call(tool_call)
    assert bd.kb_count == expected_kb
    assert bd.non_kb_count == expected_non_kb
    assert bd.other_count == expected_other


class TestModeBudgetAfterModel:
    @pytest.fixture(autouse=True)
    def _patch_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.agents.chat.multi_agent_chat.main_agent.middleware import mode_budget

        def _config(mode: str) -> dict[str, Any]:
            return {
                "configurable": {
                    "thread_id": "t1",
                    "turn_id": "turn1",
                    "research_mode": mode,
                }
            }

        self._config_factory = _config
        monkeypatch.setattr(
            mode_budget,
            "get_config",
            lambda: self._current_config,
        )

    def _run(
        self,
        mw: ModeBudgetMiddleware,
        mode: str,
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        self._current_config = self._config_factory(mode)
        state: dict[str, Any] = {
            "messages": [AIMessage(content="", tool_calls=tool_calls)]
        }
        return mw.after_model(state, MagicMock())

    def test_speed_allows_knowledge_base(self, mw: ModeBudgetMiddleware) -> None:
        result = self._run(
            mw, "speed", [_tool_call("ask_knowledge_base", {"query": "x"})]
        )
        assert result is None

    def test_speed_blocks_web_search(self, mw: ModeBudgetMiddleware) -> None:
        result = self._run(
            mw,
            "speed",
            [
                _tool_call(
                    "task", {"subagent_type": "google_search", "description": "x"}
                )
            ],
        )
        assert result is not None
        messages = result["messages"]
        assert any("blocked" in m.content for m in messages)

    def test_speed_forces_end_after_exhausting_budget(
        self, mw: ModeBudgetMiddleware
    ) -> None:
        # First call is allowed; second call is blocked and triggers jump_to end.
        self._run(mw, "speed", [_tool_call("ask_knowledge_base", {"query": "x"})])
        result = self._run(
            mw, "speed", [_tool_call("ask_knowledge_base", {"query": "y"})]
        )
        assert result is not None
        assert result.get("jump_to") == "end"
        assert any(
            isinstance(m, AIMessage) and "budget" in m.content
            for m in result["messages"]
        )

    def test_balanced_allows_one_non_kb(self, mw: ModeBudgetMiddleware) -> None:
        self._run(mw, "balanced", [_tool_call("ask_knowledge_base", {"query": "x"})])
        self._run(mw, "balanced", [_tool_call("ask_knowledge_base", {"query": "y"})])
        result = self._run(
            mw,
            "balanced",
            [
                _tool_call(
                    "task", {"subagent_type": "google_search", "description": "x"}
                )
            ],
        )
        assert result is None

    def test_balanced_blocks_second_non_kb(self, mw: ModeBudgetMiddleware) -> None:
        self._run(mw, "balanced", [_tool_call("ask_knowledge_base", {"query": "x"})])
        self._run(
            mw, "balanced", [_tool_call("task", {"subagent_type": "google_search"})]
        )
        result = self._run(
            mw,
            "balanced",
            [_tool_call("task", {"subagent_type": "google_search"})],
        )
        assert result is not None

    def test_auto_caps_at_five(self, mw: ModeBudgetMiddleware) -> None:
        for i in range(5):
            result = self._run(
                mw,
                "auto",
                [
                    _tool_call(
                        "task",
                        {"subagent_type": "google_search", "description": f"x{i}"},
                    )
                ],
            )
            assert result is None

        # Sixth call is blocked and jumps to end.
        result = self._run(
            mw,
            "auto",
            [
                _tool_call(
                    "task", {"subagent_type": "google_search", "description": "x5"}
                )
            ],
        )
        assert result is not None
        assert result.get("jump_to") == "end"

    def test_auto_batch_counts_each_subagent(self, mw: ModeBudgetMiddleware) -> None:
        # One batch with 3 non-kb subagents in auto counts as 3 toward total=5.
        result = self._run(
            mw,
            "auto",
            [
                _tool_call(
                    "task",
                    {
                        "tasks": [
                            {"subagent_type": "google_search", "description": "a"},
                            {"subagent_type": "web_crawler", "description": "b"},
                            {"subagent_type": "reddit", "description": "c"},
                        ]
                    },
                )
            ],
        )
        assert result is None

        # A second batch of 3 would exceed the total budget of 5.
        result = self._run(
            mw,
            "auto",
            [
                _tool_call(
                    "task",
                    {
                        "tasks": [
                            {"subagent_type": "google_search", "description": "d"},
                            {"subagent_type": "web_crawler", "description": "e"},
                            {"subagent_type": "reddit", "description": "f"},
                        ]
                    },
                )
            ],
        )
        assert result is not None

    # ------------------------------------------------------------------
    # Quality mode: budget (3 KB, 2 non-KB, 5 total)
    # ------------------------------------------------------------------

    def test_quality_allows_three_kb_calls(self, mw: ModeBudgetMiddleware) -> None:
        for i in range(3):
            result = self._run(
                mw, "quality", [_tool_call("ask_knowledge_base", {"query": f"q{i}"})]
            )
            assert result is None

    def test_quality_allows_two_non_kb_calls(self, mw: ModeBudgetMiddleware) -> None:
        for i in range(2):
            result = self._run(
                mw,
                "quality",
                [
                    _tool_call(
                        "task",
                        {"subagent_type": "google_search", "description": f"s{i}"},
                    )
                ],
            )
            assert result is None

    def test_quality_blocks_sixth_call_with_jump_to_end(
        self, mw: ModeBudgetMiddleware
    ) -> None:
        # 3 KB + 2 non-KB = 5 total (the cap). 6th call is blocked.
        for i in range(3):
            self._run(
                mw, "quality", [_tool_call("ask_knowledge_base", {"query": f"q{i}"})]
            )
        for i in range(2):
            self._run(
                mw,
                "quality",
                [
                    _tool_call(
                        "task",
                        {"subagent_type": "google_search", "description": f"s{i}"},
                    )
                ],
            )
        result = self._run(
            mw,
            "quality",
            [_tool_call("ask_knowledge_base", {"query": "q3"})],
        )
        assert result is not None
        assert result.get("jump_to") == "end"

    def test_quality_allows_chainlens(self, mw: ModeBudgetMiddleware) -> None:
        """ChainLens is allowed in quality mode (unlike speed/balanced)."""
        result = self._run(
            mw,
            "quality",
            [_tool_call("task", {"subagent_type": "chainlens", "description": "x"})],
        )
        assert result is None

    def test_quality_allows_web_research(self, mw: ModeBudgetMiddleware) -> None:
        """Web/deep-research tools are allowed in quality mode (unlike speed)."""
        result = self._run(
            mw,
            "quality",
            [
                _tool_call(
                    "task", {"subagent_type": "google_search", "description": "x"}
                )
            ],
        )
        assert result is None
