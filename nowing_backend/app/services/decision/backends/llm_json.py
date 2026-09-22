"""LLM JSON backend — litellm structured output (story 39.1b, AD-J2).

Usable as ``DECISION_BACKEND=llm_json`` and as the fallback leg when the
primary backend raises a retryable ``DecisionError`` (timeout /
backend_error / backend_unavailable / missing_api_key).

One ``decide()`` issues one batched completion covering the whole
``questions`` dict — the same batching as Jev ``system_one`` —
``temperature=0``, strict ``json_schema`` response format. Two bounded
exception paths may add a second call: providers that reject strict
``json_schema`` degrade once to plain ``json_object`` (hybrid_llm_router
precedent), and litellm itself retries transient failures once via
``num_retries=1``. Prompt/schema ported from the eval baseline
``scripts/jev_eval/runner.py:193-296``, adapted from
one-question-per-call to a single batched call.

Failures never leak litellm exceptions: transport/timeout/auth →
``DecisionError`` (uniform taxonomy, same codes callers already handle);
unparseable or schema-mismatched payloads → ``InvalidDecisionAnswer`` —
malformed output is never retried as a backend error.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import app.config.decision as decision_config
from app.services.decision.errors import DecisionError, InvalidDecisionAnswer
from app.services.decision.types import (
    Answer,
    BackendResult,
    ChoiceQuestion,
    NoulQuestion,
    Question,
    ScoreQuestion,
)

logger = logging.getLogger(__name__)

# Upper bound on generated tokens — keeps the degraded json_object path
# from running unbounded when the schema stop-conditions don't apply.
_MAX_TOKENS = 4096

# Strict schema stays key-stable regardless of how many questions or how
# many option ids a call carries — dynamic keys are not allowed under
# OpenAI-style strict mode, so probabilities travel as an array of
# {"id", "p"} pairs and are normalized back to a str-keyed dict.
_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "decision_answers",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_id": {"type": "string"},
                            "answer": {"type": ["string", "number"]},
                            "confidence": {"type": "number"},
                            "probabilities": {
                                "type": ["array", "null"],
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "p": {"type": "number"},
                                    },
                                    "required": ["id", "p"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": [
                            "question_id",
                            "answer",
                            "confidence",
                            "probabilities",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["answers"],
            "additionalProperties": False,
        },
    },
}


def _build_prompt(state: dict[str, Any], questions: dict[str, Question]) -> str:
    """Batch version of the eval ``_build_llm_prompt`` — all questions in
    one prompt, with the constraints strict validation demands spelled
    out (full distribution over the offered ids, sum ≈ 1, answer is the
    argmax / probability-weighted mean).
    """
    state_str = json.dumps(state, ensure_ascii=False, indent=2)
    lines = [
        "You are a decision engine. Evaluate every question below against this state:",
        "",
        state_str,
        "",
        'Reply with a single JSON object {"answers": [...]} holding exactly '
        "one entry per question:",
        '- "question_id": the question id, copied verbatim',
        '- "answer": choice → the chosen option id; score → the numeric '
        'score; noul → the probability that the answer is "yes" in [0,1]',
        '- "confidence": your confidence in [0,1]',
        '- "probabilities": choice/score → [{"id": "<option id>", "p": <0-1>}] '
        "covering EVERY offered id exactly once and summing to 1.0; "
        "noul → null",
        "",
        "Rules:",
        "- The answer must be the argmax of your probabilities (choice), or "
        "the probability-weighted mean of the level indices (score).",
        "- Output JSON only — no prose, no markdown fences.",
        "",
        "Questions:",
    ]
    for i, (qid, question) in enumerate(questions.items(), 1):
        lines.append(f"{i}. question_id={json.dumps(qid)} type={question.kind}")
        lines.append(f"   instructions: {question.instructions}")
        if isinstance(question, ChoiceQuestion):
            if not question.criteria:
                raise DecisionError(
                    f"choice question {qid!r} has no options to offer",
                    code="invalid_request",
                )
            lines.append(
                "   options (id → description): "
                + json.dumps(question.criteria, ensure_ascii=False)
            )
        elif isinstance(question, ScoreQuestion):
            if not question.criteria:
                raise DecisionError(
                    f"score question {qid!r} has no rubric levels",
                    code="invalid_request",
                )
            last = len(question.criteria) - 1
            lines.append(
                f'   levels (ids "0".."{last}"): '
                + json.dumps(question.criteria, ensure_ascii=False)
            )
        elif isinstance(question, NoulQuestion):
            # Optional true/false labels give the model the same context
            # Jev's Noul criteria carry.
            if question.criteria:
                lines.append(
                    "   labels: " + json.dumps(question.criteria, ensure_ascii=False)
                )
        else:
            # A contract violation — deterministic, so it must NOT sit
            # in the fallback-trigger code set.
            raise DecisionError(
                f"Unsupported question type {type(question).__name__!r} "
                "for llm_json backend",
                code="invalid_request",
            )
    return "\n".join(lines)


def _is_schema_rejection(exc: BaseException) -> bool:
    """True when the provider plausibly rejected ``response_format``.

    ``UnsupportedParamsError`` is definitive; ``BadRequestError`` needs a
    schema hint in the message — anything else (bad model, context
    length) is a real request failure and must not pay for a doomed
    second call.
    """
    if type(exc).__name__ == "UnsupportedParamsError":
        return True
    message = str(exc).lower()
    return any(
        token in message for token in ("response_format", "json_schema", "structured")
    )


async def _call(
    litellm: Any,
    *,
    model: str,
    messages: list[dict[str, str]],
    timeout: float,
    schema_errors: tuple[type[Exception], ...],
) -> Any:
    """One batched completion.

    On a schema rejection (see ``_is_schema_rejection``) the request is
    retried once with plain ``json_object`` — the hybrid_llm_router
    precedent. Transient failures and non-schema bad requests propagate
    unchanged.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "timeout": timeout,
        "num_retries": 1,
        "max_tokens": _MAX_TOKENS,
        "response_format": _RESPONSE_FORMAT,
    }
    try:
        return await litellm.acompletion(**kwargs)
    except schema_errors as exc:
        if not _is_schema_rejection(exc):
            raise
        kwargs["response_format"] = {"type": "json_object"}
        return await litellm.acompletion(**kwargs)


def _probs_to_dict(raw: Any) -> dict[str, float] | None:
    """Normalize the schema's ``[{"id": str, "p": float}]`` array (and,
    tolerantly, plain dicts from json_object mode) to a str-keyed dict."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        try:
            return {str(k): float(v) for k, v in raw.items()}
        except (TypeError, ValueError) as exc:
            raise InvalidDecisionAnswer("probabilities values must be numeric") from exc
    if isinstance(raw, list):
        try:
            return {str(entry["id"]): float(entry["p"]) for entry in raw}
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidDecisionAnswer(
                'probabilities entries must look like {"id": ..., "p": ...}'
            ) from exc
    raise InvalidDecisionAnswer(f"probabilities is not an array: {type(raw).__name__}")


def _to_answer(question: Question, item: dict[str, Any]) -> Answer:
    """Normalize one ``answers[]`` entry into an ``Answer``.

    Missing/unrecognized fields raise ``InvalidDecisionAnswer`` — a
    malformed answer is not a transport failure and must not be retried.
    ``confidence`` is required by the schema, so a missing one (or a
    bool smuggled through ``float()``) is malformed too.
    """
    raw = item.get("answer")
    if raw is None or isinstance(raw, bool):
        raise InvalidDecisionAnswer(
            f"{question.kind} answer is missing a valid 'answer'"
        )
    confidence = item.get("confidence")
    if confidence is None or isinstance(confidence, bool):
        raise InvalidDecisionAnswer(f"{question.kind} answer is missing 'confidence'")
    confidence = float(confidence)
    probs = _probs_to_dict(item.get("probabilities"))
    if isinstance(question, ChoiceQuestion):
        return Answer(
            kind="choice",
            value=str(raw),
            confidence=confidence,
            probabilities=probs or {},
        )
    if isinstance(question, ScoreQuestion):
        return Answer(
            kind="score",
            value=float(raw),
            confidence=confidence,
            probabilities=probs or {},
        )
    if isinstance(question, NoulQuestion):
        value = float(raw)
        # Like Jev: a noul IS a probability — it doubles as its own
        # confidence so ConfidenceGate treats every kind uniformly.
        return Answer(kind="noul", value=value, confidence=value, probabilities=None)
    raise InvalidDecisionAnswer(
        f"llm_json cannot answer question type {type(question).__name__!r}"
    )


def _parse_payload(payload: Any, questions: dict[str, Question]) -> dict[str, Answer]:
    items = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise InvalidDecisionAnswer("llm_json response has no 'answers' array")
    answers: dict[str, Answer] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id")
        if not isinstance(qid, str):
            continue
        # Literal-minded models can echo the JSON-quoted id from the
        # prompt — strip whitespace and surrounding double quotes.
        qid = qid.strip().strip('"').strip()
        # Skip entries that don't address a question we asked — the
        # service flags still-missing answers itself (_require_answer).
        if qid not in questions:
            continue
        if qid in answers:
            raise InvalidDecisionAnswer(f"duplicate answer for question {qid!r}")
        answers[qid] = _to_answer(questions[qid], item)
    return answers


class LLMJsonBackend:
    """``litellm.acompletion`` structured-output adapter implementing
    ``DecisionBackend``."""

    name = "llm_json"

    async def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, Question],
        *,
        model: str | None = None,
        timeout: float | None = None,
    ) -> BackendResult:
        try:
            import litellm
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
        except ImportError as exc:
            raise DecisionError(
                "litellm is not installed — llm_json backend unavailable",
                code="backend_unavailable",
            ) from exc

        model = model or decision_config.DECISION_LLM_MODEL
        if timeout is None:
            # Direct callers bypassing the service still get the
            # configured ceiling — never an unbounded wait_for.
            timeout = decision_config.DECISION_TIMEOUT_SECONDS
        try:
            prompt = _build_prompt(state, questions)
        except DecisionError:
            raise
        except (TypeError, ValueError) as exc:
            # e.g. non-JSON-serializable state — surface it inside the
            # documented taxonomy instead of leaking a raw TypeError.
            raise DecisionError(
                f"decision state is not JSON-serializable: {type(exc).__name__}",
                code="backend_error",
            ) from exc
        messages = [{"role": "user", "content": prompt}]

        start = time.perf_counter()
        try:
            # asyncio.wait_for is the belt-and-suspenders ceiling on top
            # of litellm's own timeout, same as the Jev adapter.
            response = await asyncio.wait_for(
                _call(
                    litellm,
                    model=model,
                    messages=messages,
                    timeout=timeout,
                    schema_errors=(BadRequestError, UnsupportedParamsError),
                ),
                timeout=timeout,
            )
        except DecisionError:
            raise
        except (TimeoutError, LiteLLMTimeout) as exc:
            raise DecisionError(
                "LLM decision request timed out", code="timeout"
            ) from exc
        except AuthenticationError as exc:
            # Same code JevBackend uses for a missing TYPESAFE_API_KEY —
            # callers handle "fix the key" uniformly.
            logger.exception("llm_json request failed")
            raise DecisionError(
                f"llm_json authentication failed: {type(exc).__name__}",
                code="missing_api_key",
            ) from exc
        except (
            APIConnectionError,
            RateLimitError,
            ServiceUnavailableError,
            InternalServerError,
        ) as exc:
            logger.exception("llm_json request failed")
            raise DecisionError(
                f"llm_json request failed: {type(exc).__name__}",
                code="backend_error",
            ) from exc
        except Exception as exc:
            # Any other litellm failure (persistent bad request,
            # response-schema quirks) — the exception may embed request
            # data; log it, don't interpolate it into the message.
            logger.exception("llm_json request failed")
            raise DecisionError(
                f"llm_json request failed: {type(exc).__name__}",
                code="backend_error",
            ) from exc
        latency_ms = (time.perf_counter() - start) * 1000

        try:
            content = response.choices[0].message.content
            answers = _parse_payload(json.loads(content), questions)
        except InvalidDecisionAnswer:
            raise
        except Exception as exc:
            # JSON decode errors, missing choices/content — malformed
            # answer, never retryable as a backend error.
            logger.exception("Failed to parse llm_json response")
            raise InvalidDecisionAnswer(
                f"failed to parse llm_json response: {type(exc).__name__}"
            ) from exc

        usage = getattr(response, "usage", None)
        return BackendResult(
            answers=answers,
            model=getattr(response, "model", None) or model,
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            output_tokens=(
                getattr(usage, "completion_tokens", None) if usage else None
            ),
        )
