"""Entity resolution — pairwise verdicts, fan-out confirm, refine loop (39.3)."""

from __future__ import annotations

import pytest

import app.config.decision as decision_config
import app.services.entity_resolution.service as er
from app.services.decision.backends.mock import MockBackend
from app.services.decision.errors import DecisionError
from app.services.decision.service import DecisionService
from app.services.decision.types import Answer, BackendResult
from app.services.entity_resolution import (
    EntityVerdict,
    confirm_entity_match,
    refine_entity_groups,
    score_entity_pair,
)

pytestmark = pytest.mark.unit

_TASK_FLAGS = ("ROUTING", "FILTER", "ENTITY", "INTENT", "VOICE")


class _StubBackend:
    """In-memory backend — canned BackendResult, callable, or raises."""

    name = "stub"

    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        self.calls = 0

    async def decide(self, state, questions, *, model=None, timeout=None):
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        if callable(self._result):
            return self._result(state, questions)
        return self._result


@pytest.fixture
def _enabled(monkeypatch):
    """Enable master + all per-task flags; fallback pinned off."""
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "none")
    for task in _TASK_FLAGS:
        monkeypatch.setenv(f"DECISION_{task}_ENABLED", "true")


def _patch_service(monkeypatch, service: DecisionService) -> None:
    monkeypatch.setattr(er, "get_decision_service", lambda: service)


def _score_answer(top: int, confidence: float = 0.9) -> Answer:
    """3-level score whose value IS the probability-weighted mean."""
    probs = {str(i): (0.9 if i == top else 0.05) for i in range(3)}
    value = sum(int(level) * p for level, p in probs.items())
    return Answer(
        kind="score", value=value, confidence=confidence, probabilities=probs
    )


def _choice_answer(
    chosen: str, options: list[str], confidence: float = 0.9
) -> Answer:
    rest = (1.0 - 0.9) / (len(options) - 1)
    probs = {o: (0.9 if o == chosen else rest) for o in options}
    return Answer(
        kind="choice", value=chosen, confidence=confidence, probabilities=probs
    )


def _result(answers: dict[str, Answer]) -> BackendResult:
    return BackendResult(answers=answers, model="stub-1", latency_ms=1.0)


# ---------------------------------------------------------------------------
# score_entity_pair — pairwise Score verdicts
# ---------------------------------------------------------------------------


async def test_score_pair_high_score_auto_merge(_enabled, monkeypatch):
    _patch_service(
        monkeypatch,
        DecisionService(
            _StubBackend(_result({"is_same": _score_answer(2)}))
        ),
    )
    res = await score_entity_pair({"name": "A"}, {"name": "A"})
    assert res.verdict is EntityVerdict.AUTO_MERGE
    assert res.answer is not None


async def test_score_pair_middle_score_review(_enabled, monkeypatch):
    _patch_service(
        monkeypatch,
        DecisionService(
            _StubBackend(_result({"is_same": _score_answer(1)}))
        ),
    )
    res = await score_entity_pair({"name": "A"}, {"name": "B"})
    assert res.verdict is EntityVerdict.REVIEW


async def test_score_pair_low_score_separate(_enabled, monkeypatch):
    _patch_service(
        monkeypatch,
        DecisionService(
            _StubBackend(_result({"is_same": _score_answer(0)}))
        ),
    )
    res = await score_entity_pair({"name": "A"}, {"name": "B"})
    assert res.verdict is EntityVerdict.SEPARATE


async def test_score_pair_low_confidence_reviews(_enabled, monkeypatch):
    """A high score below the 0.7 confidence gate is uncertain → REVIEW."""
    _patch_service(
        monkeypatch,
        DecisionService(
            _StubBackend(
                _result({"is_same": _score_answer(2, confidence=0.5)})
            )
        ),
    )
    res = await score_entity_pair({"name": "A"}, {"name": "A"})
    assert res.verdict is EntityVerdict.REVIEW


async def test_score_pair_decision_error_propagates(_enabled, monkeypatch):
    _patch_service(
        monkeypatch,
        DecisionService(
            _StubBackend(exc=DecisionError("down", code="timeout"))
        ),
    )
    with pytest.raises(DecisionError):
        await score_entity_pair({"name": "A"}, {"name": "A"})


# ---------------------------------------------------------------------------
# confirm_entity_match — fan-out Choice over candidates + no_match
# ---------------------------------------------------------------------------


async def test_confirm_match_returns_chosen_candidate(_enabled, monkeypatch):
    options = ["cand-1", "cand-2", "no_match"]

    def _answer(state, questions):
        criteria = list(questions["match_decision"].criteria.keys())
        # candidates first, no_match last (MockBackend picks options[0])
        assert criteria == options
        return _result(
            {"match_decision": _choice_answer("cand-1", criteria)}
        )

    _patch_service(monkeypatch, DecisionService(_StubBackend(_answer)))
    chosen = await confirm_entity_match(
        {"name": "anchor"},
        {"cand-1": {"name": "A"}, "cand-2": {"name": "B"}},
    )
    assert chosen == "cand-1"


async def test_confirm_match_no_match_returns_none(_enabled, monkeypatch):
    def _answer(state, questions):
        criteria = list(questions["match_decision"].criteria.keys())
        return _result(
            {"match_decision": _choice_answer("no_match", criteria)}
        )

    _patch_service(monkeypatch, DecisionService(_StubBackend(_answer)))
    chosen = await confirm_entity_match(
        {"name": "anchor"}, {"cand-1": {"name": "A"}}
    )
    assert chosen is None


async def test_confirm_match_low_confidence_returns_none(
    _enabled, monkeypatch
):
    def _answer(state, questions):
        criteria = list(questions["match_decision"].criteria.keys())
        return _result(
            {
                "match_decision": _choice_answer(
                    "cand-1", criteria, confidence=0.4
                )
            }
        )

    _patch_service(monkeypatch, DecisionService(_StubBackend(_answer)))
    chosen = await confirm_entity_match(
        {"name": "anchor"}, {"cand-1": {"name": "A"}}
    )
    assert chosen is None


async def test_confirm_match_empty_candidates_no_decide(
    _enabled, monkeypatch
):
    backend = _StubBackend(_result({}))
    _patch_service(monkeypatch, DecisionService(backend))
    chosen = await confirm_entity_match({"name": "anchor"}, {})
    assert chosen is None
    assert backend.calls == 0


async def test_confirm_match_mock_backend_confirms_first_candidate(
    _enabled, monkeypatch
):
    """MockBackend answers options[0]; no_match-last keeps it deterministic."""
    _patch_service(monkeypatch, DecisionService(MockBackend()))
    chosen = await confirm_entity_match(
        {"name": "anchor"},
        {"cand-x": {"name": "X"}, "cand-y": {"name": "Y"}},
    )
    assert chosen == "cand-x"


# ---------------------------------------------------------------------------
# refine_entity_groups — per-anchor decide → union-find → merge
# ---------------------------------------------------------------------------


def _item(item_id: str) -> dict:
    return {"id": item_id, "name": f"entity-{item_id}"}


def _merge_group(items: list[dict]) -> dict:
    merged = dict(items[0])
    merged["members"] = sorted(i["id"] for i in items)
    return merged


def _kwargs():
    return {
        "id_of": lambda i: i["id"],
        "state_of": lambda i: dict(i),
        "describe": lambda i: i["name"],
        "merge_group": _merge_group,
    }


async def test_refine_confirmed_pair_merges(_enabled, monkeypatch):
    def _answer(state, questions):
        criteria = list(questions["match_decision"].criteria.keys())
        return _result({"match_decision": _choice_answer("b", criteria)})

    _patch_service(monkeypatch, DecisionService(_StubBackend(_answer)))
    refined, stats = await refine_entity_groups(
        [_item("a"), _item("b")], {0: [1]}, **_kwargs()
    )
    assert len(refined) == 1
    assert refined[0]["members"] == ["a", "b"]
    assert stats.calls == 1
    assert stats.confirmed == 1


async def test_refine_no_match_keeps_separate(_enabled, monkeypatch):
    def _answer(state, questions):
        criteria = list(questions["match_decision"].criteria.keys())
        return _result(
            {"match_decision": _choice_answer("no_match", criteria)}
        )

    _patch_service(monkeypatch, DecisionService(_StubBackend(_answer)))
    items = [_item("a"), _item("b")]
    refined, stats = await refine_entity_groups(items, {0: [1]}, **_kwargs())
    assert refined == items
    assert stats.no_match == 1
    assert stats.confirmed == 0


async def test_refine_empty_pairs_returns_input(_enabled, monkeypatch):
    backend = _StubBackend(_result({}))
    _patch_service(monkeypatch, DecisionService(backend))
    items = [_item("a"), _item("b")]
    refined, stats = await refine_entity_groups(items, {}, **_kwargs())
    assert refined == items
    assert stats.calls == 0
    assert backend.calls == 0


async def test_refine_decision_error_skips_anchor(_enabled, monkeypatch):
    """One failing anchor is skipped; the next anchor still gets decided."""
    calls = {"n": 0}

    def _backend(state, questions):
        calls["n"] += 1
        if calls["n"] == 1:
            raise DecisionError("flaky", code="backend_error")
        criteria = list(questions["match_decision"].criteria.keys())
        return _result({"match_decision": _choice_answer("d", criteria)})

    _patch_service(monkeypatch, DecisionService(_StubBackend(_backend)))
    # Anchors sorted by candidate count desc → anchor 0 (2 cands) runs
    # first and fails; anchor 1 (1 cand) still confirms d.
    items = [_item("a"), _item("b"), _item("c"), _item("d")]
    refined, stats = await refine_entity_groups(
        items, {0: [1, 2], 1: [3]}, **_kwargs()
    )
    assert stats.errors == 1
    assert stats.confirmed == 1
    assert stats.aborted is False
    assert len(refined) == 3  # b+d merged; a, c untouched


async def test_refine_circuit_breaker_aborts_after_3_errors(
    _enabled, monkeypatch
):
    backend = _StubBackend(exc=DecisionError("down", code="timeout"))
    _patch_service(monkeypatch, DecisionService(backend))
    items = [_item(c) for c in "abcde"]
    pairs = {0: [4], 1: [4], 2: [4], 3: [4]}
    refined, stats = await refine_entity_groups(items, pairs, **_kwargs())
    assert refined == items
    assert stats.calls == 3  # stopped at the 3rd consecutive error
    assert stats.errors == 3
    assert stats.aborted is True
    assert backend.calls == 3


async def test_refine_max_calls_cap(_enabled, monkeypatch):
    backend = _StubBackend(
        lambda s, q: _result(
            {
                "match_decision": _choice_answer(
                    "no_match", list(q["match_decision"].criteria.keys())
                )
            }
        )
    )
    _patch_service(monkeypatch, DecisionService(backend))
    items = [_item(c) for c in "abcdef"]
    pairs = {0: [5], 1: [5], 2: [5], 3: [5]}
    refined, stats = await refine_entity_groups(
        items, pairs, max_calls=2, **_kwargs()
    )
    assert refined == items
    assert stats.calls == 2
    assert stats.skipped_cap == 2


async def test_refine_candidate_cap_per_anchor(_enabled, monkeypatch):
    monkeypatch.setattr(er, "MAX_CANDIDATES_PER_ANCHOR", 2)
    seen: dict = {}

    def _backend(state, questions):
        seen["criteria"] = list(questions["match_decision"].criteria.keys())
        seen["candidates"] = list(state["candidates"].keys())
        return _result(
            {
                "match_decision": _choice_answer(
                    "no_match", seen["criteria"]
                )
            }
        )

    _patch_service(monkeypatch, DecisionService(_StubBackend(_backend)))
    items = [_item(c) for c in "abcde"]
    await refine_entity_groups(items, {0: [1, 2, 3, 4]}, **_kwargs())
    # capped at 2 candidates + trailing no_match
    assert seen["criteria"] == ["b", "c", "no_match"]
    assert seen["candidates"] == ["b", "c"]


async def test_refine_single_pass_no_reeval_after_merge(
    _enabled, monkeypatch
):
    """A merged entity is never re-decided: each pair gets ONE call."""
    calls: list[tuple[str, list[str]]] = []

    def _backend(state, questions):
        anchor = state["anchor"]["id"]
        criteria = list(questions["match_decision"].criteria.keys())
        calls.append((anchor, criteria))
        # confirm the first candidate offered
        return _result(
            {"match_decision": _choice_answer(criteria[0], criteria)}
        )

    _patch_service(monkeypatch, DecisionService(_StubBackend(_backend)))
    items = [_item("a"), _item("b"), _item("c")]
    refined, stats = await refine_entity_groups(
        items, {0: [1], 1: [2]}, **_kwargs()
    )
    assert stats.calls == 2  # both anchors ran, exactly once each
    # a+b merged via anchor a; c merged into the same component via b —
    # union-find collapses transitively even though "a" was never
    # re-evaluated against "c".
    assert len(refined) == 1
    assert refined[0]["members"] == ["a", "b", "c"]
