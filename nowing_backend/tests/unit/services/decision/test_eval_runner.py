"""jev_eval runner — decision_llm_json path through LLMJsonBackend.

The runner lives under ``scripts/`` (not a package), so it is imported
lazily inside each test; ``litellm.acompletion`` is monkeypatched — no
unit test performs a live call.
"""

from __future__ import annotations

import importlib
import json

import litellm
import pytest


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [
            type("C", (), {"message": type("M", (), {"content": content})()})()
        ]
        self.model = "claude-haiku-4-5-20251001"
        self.usage = None


@pytest.mark.unit
async def test_run_decision_llm_json_maps_validated_answer(monkeypatch):
    runner = importlib.import_module("scripts.jev_eval.runner")
    from scripts.jev_eval.cases import SUBAGENT_OPTIONS, SUBAGENT_ROUTING_CASES

    case = SUBAGENT_ROUTING_CASES[0]  # route_01 → expected "batdongsan"
    # Strict validation requires a full distribution over all 16 ids
    # summing to 1 with the answer as argmax.
    rest = 0.1 / (len(SUBAGENT_OPTIONS) - 1)
    payload = {
        "answers": [
            {
                "question_id": "subagent",
                "answer": "batdongsan",
                "confidence": 0.9,
                "probabilities": [
                    {"id": key, "p": 0.9 if key == "batdongsan" else rest}
                    for key in SUBAGENT_OPTIONS
                ],
            }
        ]
    }
    calls: list[dict] = []

    async def _fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _FakeResponse(json.dumps(payload))

    monkeypatch.setattr(litellm, "acompletion", _fake_acompletion)

    result = await runner.run_decision_llm_json(case)

    assert result.backend == "decision_llm_json"
    assert result.predicted == "batdongsan"
    assert result.confidence == 0.9
    assert result.correct is True
    assert result.error is None
    assert len(calls) == 1


@pytest.mark.unit
async def test_run_decision_llm_json_backend_error_becomes_eval_error(
    monkeypatch,
):
    runner = importlib.import_module("scripts.jev_eval.runner")
    from scripts.jev_eval.cases import SUBAGENT_ROUTING_CASES

    async def _boom(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(litellm, "acompletion", _boom)

    result = await runner.run_decision_llm_json(SUBAGENT_ROUTING_CASES[0])

    assert result.backend == "decision_llm_json"
    assert result.predicted is None
    assert result.correct is False
    assert result.error is not None
    assert "DecisionError" in result.error


@pytest.mark.unit
async def test_run_decision_llm_json_strict_validation_rejects_bad_probs(
    monkeypatch,
):
    """The eval path applies the service's strict validation — a payload
    the baseline prompt would accept still fails the shipped contract."""
    runner = importlib.import_module("scripts.jev_eval.runner")
    from scripts.jev_eval.cases import SUBAGENT_ROUTING_CASES

    # probabilities cover only a subset of the offered ids — invalid.
    payload = {
        "answers": [
            {
                "question_id": "subagent",
                "answer": "batdongsan",
                "confidence": 0.9,
                "probabilities": [{"id": "batdongsan", "p": 1.0}],
            }
        ]
    }

    async def _fake_acompletion(**kwargs):
        return _FakeResponse(json.dumps(payload))

    monkeypatch.setattr(litellm, "acompletion", _fake_acompletion)

    result = await runner.run_decision_llm_json(SUBAGENT_ROUTING_CASES[0])

    assert result.backend == "decision_llm_json"
    assert result.predicted is None
    assert result.correct is False
    assert result.error is not None
    assert "InvalidDecisionAnswer" in result.error
