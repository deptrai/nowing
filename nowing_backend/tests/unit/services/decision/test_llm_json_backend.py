"""LLMJsonBackend — prompt/schema build, parse+normalize, error taxonomy."""

from __future__ import annotations

import asyncio
import json

import litellm
import pytest
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout as LiteLLMTimeout,
    UnsupportedParamsError,
)

import app.config.decision as decision_config
from app.services.decision.backends.llm_json import (
    _RESPONSE_FORMAT,
    LLMJsonBackend,
    _build_prompt,
)
from app.services.decision.errors import DecisionError, InvalidDecisionAnswer
from app.services.decision.types import (
    ChoiceQuestion,
    NoulQuestion,
    Question,
    ScoreQuestion,
)
from app.services.decision.validation import validate_answer

QUESTIONS = {
    "pick": ChoiceQuestion(instructions="pick one", criteria={"a": "A", "b": "B"}),
    "rate": ScoreQuestion(instructions="rate it", criteria=["l0", "l1", "l2"]),
    "yes": NoulQuestion(instructions="yes or no"),
}

PAYLOAD = {
    "answers": [
        {
            "question_id": "pick",
            "answer": "b",
            "confidence": 0.9,
            "probabilities": [{"id": "a", "p": 0.1}, {"id": "b", "p": 0.9}],
        },
        {
            "question_id": "rate",
            "answer": 1.85,
            "confidence": 0.8,
            "probabilities": [
                {"id": "0", "p": 0.05},
                {"id": "1", "p": 0.05},
                {"id": "2", "p": 0.9},
            ],
        },
        {
            "question_id": "yes",
            "answer": 0.7,
            "confidence": 0.6,
            "probabilities": None,
        },
    ]
}


class _FakeUsage:
    prompt_tokens = 321
    completion_tokens = 45


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


_USAGE_DEFAULT = object()


class _FakeResponse:
    def __init__(
        self, content, model="claude-haiku-4-5-20251001", usage=_USAGE_DEFAULT
    ):
        self.choices = [_FakeChoice(content)]
        self.model = model
        self.usage = _FakeUsage() if usage is _USAGE_DEFAULT else usage


def _litellm_exc(cls, message="boom"):
    return cls(message=message, model="m", llm_provider="anthropic")


def _patch_acompletion(monkeypatch, *results, delay=0.0) -> list[dict]:
    """Install a fake ``litellm.acompletion``; returns the recorded calls."""
    calls: list[dict] = []
    queue = list(results)

    async def _fake(**kwargs):
        calls.append(kwargs)
        if delay:
            await asyncio.sleep(delay)
        result = queue.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(litellm, "acompletion", _fake)
    return calls


# ---------------------------------------------------------------------------
# Prompt + schema
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_prompt_covers_every_question():
    prompt = _build_prompt({"user_message": "xin chào"}, QUESTIONS)
    for qid in QUESTIONS:
        assert json.dumps(qid) in prompt
    # options + rubric levels travel with the questions so the model sees
    # the same information Jev's criteria carry
    assert '"a": "A"' in prompt
    assert '"l0", "l1", "l2"' in prompt
    assert "xin chào" in prompt
    # strict-validation constraints are spelled out for the model
    assert "summing to 1.0" in prompt
    assert "argmax" in prompt
    assert "probability-weighted mean" in prompt


@pytest.mark.unit
def test_response_format_is_strict_array_form():
    fmt = _RESPONSE_FORMAT
    assert fmt["type"] == "json_schema"
    schema = fmt["json_schema"]["schema"]
    assert fmt["json_schema"]["strict"] is True
    item = schema["properties"]["answers"]["items"]
    # dynamic option ids must not appear in the schema — probabilities
    # travel as a [{id, p}] array instead
    assert item["properties"]["probabilities"]["items"]["properties"] == {
        "id": {"type": "string"},
        "p": {"type": "number"},
    }
    assert set(item["required"]) == {
        "question_id",
        "answer",
        "confidence",
        "probabilities",
    }
    assert item["additionalProperties"] is False


# ---------------------------------------------------------------------------
# Happy path + normalization
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_decide_happy_path_batch(monkeypatch):
    calls = _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(PAYLOAD)))
    backend = LLMJsonBackend()

    result = await backend.decide(
        {"user_message": "xin chào"}, QUESTIONS, model="m", timeout=5.0
    )

    # one decide() = ONE acompletion call for the whole question dict
    assert len(calls) == 1
    call = calls[0]
    assert call["model"] == "m"
    assert call["temperature"] == 0
    assert call["num_retries"] == 1
    assert call["max_tokens"] > 0  # bounded — json_object path can't run away
    assert call["timeout"] == 5.0
    assert call["response_format"] == _RESPONSE_FORMAT
    assert len(call["messages"]) == 1
    assert call["messages"][0]["role"] == "user"

    pick = result.answers["pick"]
    assert pick.kind == "choice" and pick.value == "b"
    assert pick.probabilities == {"a": 0.1, "b": 0.9}

    rate = result.answers["rate"]
    assert rate.kind == "score" and rate.value == 1.85
    assert rate.probabilities == {"0": 0.05, "1": 0.05, "2": 0.9}

    yes = result.answers["yes"]
    assert yes.kind == "noul" and yes.value == 0.7
    # noul doubles as its own confidence, like the Jev adapter
    assert yes.confidence == 0.7
    assert yes.probabilities is None

    # normalized answers survive strict validation end-to-end
    for qid, question in QUESTIONS.items():
        validate_answer(result.answers[qid], question)

    assert result.model == "claude-haiku-4-5-20251001"
    assert result.input_tokens == 321
    assert result.output_tokens == 45
    assert result.latency_ms >= 0


@pytest.mark.unit
async def test_decide_probabilities_dict_tolerated(monkeypatch):
    """json_object mode can return probabilities as a plain dict."""
    payload = {
        "answers": [
            {
                "question_id": "pick",
                "answer": "a",
                "confidence": 0.8,
                "probabilities": {"a": 0.8, "b": 0.2},
            }
        ]
    }
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(payload)))
    result = await LLMJsonBackend().decide(
        {}, {"pick": QUESTIONS["pick"]}, model="m", timeout=5.0
    )
    assert result.answers["pick"].probabilities == {"a": 0.8, "b": 0.2}


@pytest.mark.unit
async def test_decide_skips_unknown_question_ids(monkeypatch):
    payload = {
        "answers": [
            {"question_id": "bogus", "answer": "x", "confidence": 0.5},
            {
                "question_id": "yes",
                "answer": 0.3,
                "confidence": 0.3,
                "probabilities": None,
            },
        ]
    }
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(payload)))
    result = await LLMJsonBackend().decide(
        {}, {"yes": QUESTIONS["yes"]}, model="m", timeout=5.0
    )
    assert set(result.answers) == {"yes"}
    assert result.answers["yes"].value == 0.3


@pytest.mark.unit
async def test_decide_defaults_model_and_usage(
    monkeypatch,
):
    calls = _patch_acompletion(
        monkeypatch, _FakeResponse(json.dumps(PAYLOAD), model=None, usage=None)
    )
    result = await LLMJsonBackend().decide({}, QUESTIONS, timeout=5.0)
    # no model kwarg → the configured LLM pin is used
    assert calls[0]["model"] == decision_config.DECISION_LLM_MODEL
    assert result.model == decision_config.DECISION_LLM_MODEL
    assert result.input_tokens is None
    assert result.output_tokens is None


# ---------------------------------------------------------------------------
# Malformed payloads → InvalidDecisionAnswer (never retried)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_decide_invalid_json_raises_invalid(monkeypatch):
    _patch_acompletion(monkeypatch, _FakeResponse("not json at all"))
    with pytest.raises(InvalidDecisionAnswer):
        await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=5.0)


@pytest.mark.unit
async def test_decide_missing_answers_array_raises_invalid(monkeypatch):
    for content in ("{}", '{"answers": "nope"}', "[1, 2]"):
        _patch_acompletion(monkeypatch, _FakeResponse(content))
        with pytest.raises(InvalidDecisionAnswer):
            await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=5.0)


@pytest.mark.unit
async def test_decide_missing_answer_field_raises_invalid(monkeypatch):
    payload = {"answers": [{"question_id": "yes", "confidence": 0.5}]}
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(payload)))
    with pytest.raises(InvalidDecisionAnswer):
        await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=5.0)


@pytest.mark.unit
async def test_decide_malformed_probabilities_raise_invalid(monkeypatch):
    payload = {
        "answers": [
            {
                "question_id": "pick",
                "answer": "a",
                "confidence": 0.9,
                "probabilities": "not-an-array",
            }
        ]
    }
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(payload)))
    with pytest.raises(InvalidDecisionAnswer):
        await LLMJsonBackend().decide(
            {}, {"pick": QUESTIONS["pick"]}, model="m", timeout=5.0
        )


@pytest.mark.unit
async def test_decide_empty_choices_raise_invalid(monkeypatch):
    class _NoChoices:
        choices = []
        model = "m"
        usage = None

    _patch_acompletion(monkeypatch, _NoChoices())
    with pytest.raises(InvalidDecisionAnswer):
        await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=5.0)


# ---------------------------------------------------------------------------
# Error taxonomy — litellm exceptions never leak
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc,code",
    [
        (_litellm_exc(LiteLLMTimeout), "timeout"),
        (_litellm_exc(APIConnectionError), "backend_error"),
        (_litellm_exc(RateLimitError), "backend_error"),
        (_litellm_exc(ServiceUnavailableError), "backend_error"),
        (_litellm_exc(InternalServerError), "backend_error"),
        (_litellm_exc(AuthenticationError), "missing_api_key"),
        (RuntimeError("surprise"), "backend_error"),
    ],
)
async def test_decide_error_taxonomy(monkeypatch, exc, code):
    _patch_acompletion(monkeypatch, exc)
    with pytest.raises(DecisionError) as exc_info:
        await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=5.0)
    assert exc_info.value.code == code


@pytest.mark.unit
async def test_decide_asyncio_timeout_maps_to_timeout(monkeypatch):
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(PAYLOAD)), delay=5.0)
    with pytest.raises(DecisionError) as exc_info:
        await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=0.01)
    assert exc_info.value.code == "timeout"


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc",
    [
        _litellm_exc(BadRequestError, "json_schema not supported"),
        _litellm_exc(UnsupportedParamsError, "response_format unsupported"),
    ],
)
async def test_decide_degrades_to_json_object_once(monkeypatch, exc):
    """Provider rejecting strict json_schema → one retry as json_object."""
    calls = _patch_acompletion(monkeypatch, exc, _FakeResponse(json.dumps(PAYLOAD)))
    result = await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=5.0)
    assert len(calls) == 2
    assert calls[0]["response_format"] == _RESPONSE_FORMAT
    assert calls[1]["response_format"] == {"type": "json_object"}
    assert result.answers["pick"].value == "b"


@pytest.mark.unit
async def test_decide_persistent_schema_rejection_is_backend_error(monkeypatch):
    """Schema rejection on BOTH calls → one json_object retry, then give up."""
    calls = _patch_acompletion(
        monkeypatch,
        _litellm_exc(BadRequestError, "json_schema not supported"),
        _litellm_exc(BadRequestError, "json_schema not supported"),
    )
    with pytest.raises(DecisionError) as exc_info:
        await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=5.0)
    assert exc_info.value.code == "backend_error"
    assert len(calls) == 2  # strict + one json_object retry, then it gives up


@pytest.mark.unit
async def test_decide_non_schema_bad_request_does_not_retry(monkeypatch):
    """BadRequestError without a response_format cause (bad model,
    context length) must not pay for a doomed second call."""
    calls = _patch_acompletion(
        monkeypatch,
        _litellm_exc(BadRequestError, "context length exceeded"),
    )
    with pytest.raises(DecisionError) as exc_info:
        await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=5.0)
    assert exc_info.value.code == "backend_error"
    assert len(calls) == 1


@pytest.mark.unit
async def test_decide_none_timeout_uses_configured_ceiling(monkeypatch):
    """Direct callers bypassing the service still get a bounded wait_for."""
    calls = _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(PAYLOAD)))
    await LLMJsonBackend().decide({}, QUESTIONS, model="m", timeout=None)
    assert calls[0]["timeout"] == decision_config.DECISION_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Normalization edge cases (items 8, 16, 17, 18)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_decide_missing_confidence_raises_invalid(monkeypatch):
    payload = {"answers": [{"question_id": "yes", "answer": 0.7}]}
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(payload)))
    with pytest.raises(InvalidDecisionAnswer):
        await LLMJsonBackend().decide(
            {}, {"yes": QUESTIONS["yes"]}, model="m", timeout=5.0
        )


@pytest.mark.unit
@pytest.mark.parametrize("field", ["answer", "confidence"])
async def test_decide_bool_fields_raise_invalid(monkeypatch, field):
    """float(True) coercion must not smuggle a bool into a numeric field."""
    item = {"question_id": "yes", "answer": 0.7, "confidence": 0.7}
    item[field] = True
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps({"answers": [item]})))
    with pytest.raises(InvalidDecisionAnswer):
        await LLMJsonBackend().decide(
            {}, {"yes": QUESTIONS["yes"]}, model="m", timeout=5.0
        )


@pytest.mark.unit
async def test_decide_duplicate_question_id_raises_invalid(monkeypatch):
    payload = {
        "answers": [
            {"question_id": "yes", "answer": 0.7, "confidence": 0.5},
            {"question_id": "yes", "answer": 0.4, "confidence": 0.5},
        ]
    }
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(payload)))
    with pytest.raises(InvalidDecisionAnswer):
        await LLMJsonBackend().decide(
            {}, {"yes": QUESTIONS["yes"]}, model="m", timeout=5.0
        )


@pytest.mark.unit
async def test_decide_quoted_question_id_is_matched(monkeypatch):
    """A model echoing the JSON-quoted id from the prompt still resolves."""
    payload = {
        "answers": [
            {"question_id": '"yes"', "answer": 0.7, "confidence": 0.7},
        ]
    }
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(payload)))
    result = await LLMJsonBackend().decide(
        {}, {"yes": QUESTIONS["yes"]}, model="m", timeout=5.0
    )
    assert result.answers["yes"].value == 0.7


@pytest.mark.unit
async def test_decide_malformed_probability_entries_raise_invalid(monkeypatch):
    payload = {
        "answers": [
            {
                "question_id": "pick",
                "answer": "a",
                "confidence": 0.9,
                "probabilities": [{"id": "a"}],  # missing "p"
            }
        ]
    }
    _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(payload)))
    with pytest.raises(InvalidDecisionAnswer):
        await LLMJsonBackend().decide(
            {}, {"pick": QUESTIONS["pick"]}, model="m", timeout=5.0
        )


# ---------------------------------------------------------------------------
# Prompt-building contract violations → invalid_request, never paid (13/14/15)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_build_prompt_empty_criteria_is_invalid_request():
    backend = LLMJsonBackend()
    for question in (
        ChoiceQuestion(instructions="i", criteria={}),
        ScoreQuestion(instructions="i", criteria=[]),
    ):
        with pytest.raises(DecisionError) as exc_info:
            await backend.decide({}, {"q": question}, model="m", timeout=5.0)
        assert exc_info.value.code == "invalid_request"


@pytest.mark.unit
async def test_build_prompt_unknown_question_type_is_invalid_request():
    class _Weird(Question):
        pass

    with pytest.raises(DecisionError) as exc_info:
        _build_prompt({}, {"q": _Weird(instructions="i")})
    assert exc_info.value.code == "invalid_request"


@pytest.mark.unit
def test_build_prompt_includes_noul_labels():
    questions = {
        "yes": NoulQuestion(instructions="i", criteria={"yes": "Có", "no": "Không"})
    }
    prompt = _build_prompt({}, questions)
    assert '"yes": "Có"' in prompt
    assert '"no": "Không"' in prompt


@pytest.mark.unit
async def test_decide_non_serializable_state_is_backend_error(monkeypatch):
    calls = _patch_acompletion(monkeypatch, _FakeResponse(json.dumps(PAYLOAD)))
    with pytest.raises(DecisionError) as exc_info:
        await LLMJsonBackend().decide(
            {"bad": object()}, QUESTIONS, model="m", timeout=5.0
        )
    assert exc_info.value.code == "backend_error"
    assert calls == []  # the LLM is never reached
