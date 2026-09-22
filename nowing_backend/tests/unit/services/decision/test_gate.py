"""ConfidenceGate — per-task thresholds + DECISION_{TASK}_THRESHOLD override."""

from __future__ import annotations

import pytest

from app.services.decision.gate import DEFAULT_THRESHOLDS, ConfidenceGate
from app.services.decision.types import Answer

_THRESHOLD_ENVS = [f"DECISION_{task.upper()}_THRESHOLD" for task in DEFAULT_THRESHOLDS]


def _answer(confidence: float) -> Answer:
    return Answer(kind="choice", value="a", confidence=confidence)


@pytest.mark.unit
def test_gate_passes_at_and_above_threshold():
    gate = ConfidenceGate(threshold=0.6)
    assert gate.passes(_answer(0.6))
    assert gate.passes(_answer(0.95))
    assert not gate.passes(_answer(0.59))
    assert not gate.passes(_answer(0.0))


@pytest.mark.unit
def test_gate_rejects_missing_or_bad_confidence():
    gate = ConfidenceGate(threshold=0.5)
    assert not gate.passes(None)
    assert not gate.passes(_answer(float("nan")))


@pytest.mark.unit
def test_gate_for_task_defaults(monkeypatch):
    for env in _THRESHOLD_ENVS:
        monkeypatch.delenv(env, raising=False)
    assert ConfidenceGate.for_task("routing").threshold == 0.6
    assert ConfidenceGate.for_task("filter").threshold == 0.5
    assert ConfidenceGate.for_task("entity").threshold == 0.7
    assert ConfidenceGate.for_task("intent").threshold == 0.5
    # Unknown tasks get the conservative fallback.
    assert ConfidenceGate.for_task("bogus").threshold == 0.5


@pytest.mark.unit
def test_gate_env_override(monkeypatch):
    monkeypatch.setenv("DECISION_ROUTING_THRESHOLD", "0.9")
    assert ConfidenceGate.for_task("routing").threshold == 0.9


@pytest.mark.unit
def test_gate_env_override_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("DECISION_ROUTING_THRESHOLD", "not-a-float")
    assert ConfidenceGate.for_task("routing").threshold == 0.6


@pytest.mark.unit
def test_gate_env_override_non_finite_falls_back(monkeypatch):
    """nan/inf parse as floats but are meaningless thresholds."""
    for raw in ("nan", "inf", "-inf"):
        monkeypatch.setenv("DECISION_ROUTING_THRESHOLD", raw)
        assert ConfidenceGate.for_task("routing").threshold == 0.6


@pytest.mark.unit
def test_gate_env_override_clamped_to_unit_interval(monkeypatch):
    monkeypatch.setenv("DECISION_ENTITY_THRESHOLD", "1.7")
    assert ConfidenceGate.for_task("entity").threshold == 1.0
    monkeypatch.setenv("DECISION_ENTITY_THRESHOLD", "-2")
    assert ConfidenceGate.for_task("entity").threshold == 0.0


# ---------------------------------------------------------------------------
# passes_negative — noul "confidently false" (spec-39-1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_gate_passes_negative_noul_inversion():
    """A noul value IS P(yes) — confidently false means P(yes) is LOW."""
    gate = ConfidenceGate(threshold=0.9)
    assert gate.passes_negative(Answer(kind="noul", value=0.05, confidence=0.05))
    assert gate.passes_negative(Answer(kind="noul", value=0.1, confidence=0.1))
    assert not gate.passes_negative(Answer(kind="noul", value=0.95, confidence=0.95))
    assert not gate.passes_negative(Answer(kind="noul", value=0.5, confidence=0.5))


@pytest.mark.unit
def test_gate_passes_negative_non_noul_kinds():
    """Only noul answers have a meaningful negative direction."""
    gate = ConfidenceGate(threshold=0.5)
    assert not gate.passes_negative(Answer(kind="choice", value="a", confidence=0.99))
    assert not gate.passes_negative(Answer(kind="score", value=0.0, confidence=1.0))


@pytest.mark.unit
def test_gate_passes_negative_missing_or_bad_value():
    gate = ConfidenceGate(threshold=0.5)
    assert not gate.passes_negative(None)
    assert not gate.passes_negative(
        Answer(kind="noul", value=float("nan"), confidence=0.5)
    )
    assert not gate.passes_negative(
        Answer(kind="noul", value=float("inf"), confidence=0.5)
    )
    assert not gate.passes_negative(
        Answer(kind="noul", value="not-a-number", confidence=0.5)
    )
