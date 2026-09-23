"""Strict answer validation — one test per malformed case in the spec matrix."""

from __future__ import annotations

import pytest

from app.services.decision.errors import InvalidDecisionAnswer
from app.services.decision.types import (
    Answer,
    ChoiceQuestion,
    NoulQuestion,
    ScoreQuestion,
)
from app.services.decision.validation import validate_answer

CHOICE_Q = ChoiceQuestion(
    instructions="pick one",
    criteria={"a": "Option A", "b": "Option B", "c": "Option C"},
)
SCORE_Q = ScoreQuestion(instructions="rate", criteria=["l0", "l1", "l2"])
NOUL_Q = NoulQuestion(instructions="yes or no")


def _choice_answer(value="b", probs=None, confidence=0.9) -> Answer:
    return Answer(
        kind="choice",
        value=value,
        confidence=confidence,
        probabilities=probs if probs is not None else {"a": 0.05, "b": 0.9, "c": 0.05},
    )


def _score_answer(value=1.85, probs=None, confidence=0.8) -> Answer:
    return Answer(
        kind="score",
        value=value,
        confidence=confidence,
        probabilities=probs if probs is not None else {"0": 0.05, "1": 0.05, "2": 0.9},
    )


@pytest.mark.unit
def test_validate_choice_happy():
    assert validate_answer(_choice_answer(), CHOICE_Q).value == "b"


@pytest.mark.unit
def test_validate_choice_rejects_id_not_offered():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_choice_answer(value="z"), CHOICE_Q)


@pytest.mark.unit
def test_validate_choice_rejects_probability_key_mismatch():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_choice_answer(probs={"a": 0.5, "b": 0.5}), CHOICE_Q)
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(
            _choice_answer(probs={"a": 0.1, "b": 0.8, "c": 0.05, "d": 0.05}),
            CHOICE_Q,
        )


@pytest.mark.unit
def test_validate_choice_rejects_probabilities_not_summing_to_one():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_choice_answer(probs={"a": 0.4, "b": 0.4, "c": 0.4}), CHOICE_Q)


@pytest.mark.unit
def test_validate_choice_rejects_chosen_not_argmax():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(
            _choice_answer(value="a", probs={"a": 0.2, "b": 0.7, "c": 0.1}),
            CHOICE_Q,
        )


@pytest.mark.unit
def test_validate_choice_rejects_out_of_range_probability():
    for bad in (1.5, -0.1, float("nan"), float("inf")):
        with pytest.raises(InvalidDecisionAnswer):
            validate_answer(
                _choice_answer(probs={"a": bad, "b": 0.9, "c": 0.05}),
                CHOICE_Q,
            )


@pytest.mark.unit
def test_validate_choice_rejects_missing_probabilities():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(
            Answer(kind="choice", value="b", confidence=0.9, probabilities=None),
            CHOICE_Q,
        )


@pytest.mark.unit
def test_validate_score_happy():
    assert validate_answer(_score_answer(), SCORE_Q).value == 1.85


@pytest.mark.unit
def test_validate_score_rejects_out_of_range():
    for bad in (3.0, -0.5, float("nan"), "high"):
        with pytest.raises(InvalidDecisionAnswer):
            validate_answer(_score_answer(value=bad), SCORE_Q)


@pytest.mark.unit
def test_validate_score_rejects_probability_key_mismatch():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_score_answer(probs={"0": 0.5, "1": 0.5}), SCORE_Q)


@pytest.mark.unit
def test_validate_score_rejects_probabilities_not_summing_to_one():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_score_answer(probs={"0": 0.3, "1": 0.3, "2": 0.3}), SCORE_Q)


@pytest.mark.unit
def test_validate_score_rejects_score_not_weighted_mean():
    # Distribution expects ~1.85; a reported 0.5 is miscalibrated.
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_score_answer(value=0.5), SCORE_Q)


@pytest.mark.unit
def test_validate_choice_argmax_near_tie_passes():
    """Float near-ties from model arithmetic must not fail argmax check."""
    probs = {"a": 0.5, "b": 0.5 + 5e-10, "c": 0.0}
    # chosen "a" trails the max by <1e-9 — still an argmax
    assert validate_answer(_choice_answer(value="a", probs=probs), CHOICE_Q)


@pytest.mark.unit
def test_validate_noul_happy():
    assert (
        validate_answer(Answer(kind="noul", value=0.7, confidence=0.7), NOUL_Q).value
        == 0.7
    )


@pytest.mark.unit
def test_validate_noul_rejects_out_of_range():
    for bad in (1.01, -0.01, float("nan"), "yes"):
        with pytest.raises(InvalidDecisionAnswer):
            validate_answer(Answer(kind="noul", value=bad, confidence=0.5), NOUL_Q)


@pytest.mark.unit
def test_validate_noul_rejects_invalid_confidence():
    for bad in (float("nan"), 1.5, True):
        with pytest.raises(InvalidDecisionAnswer):
            validate_answer(Answer(kind="noul", value=0.7, confidence=bad), NOUL_Q)


@pytest.mark.unit
def test_validate_rejects_kind_question_mismatch():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(Answer(kind="noul", value=0.7, confidence=0.7), CHOICE_Q)
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_choice_answer(), NOUL_Q)


@pytest.mark.unit
def test_validate_choice_rejects_invalid_confidence():
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_choice_answer(confidence=1.5), CHOICE_Q)
    with pytest.raises(InvalidDecisionAnswer):
        validate_answer(_choice_answer(confidence=float("nan")), CHOICE_Q)
