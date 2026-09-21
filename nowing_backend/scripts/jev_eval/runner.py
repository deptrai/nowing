"""Vietnamese eval runner — Jev vs LLM JSON-mode baseline.

Runs each EvalCase through 4 backends:
1. Jev (typesafe-sdk) — if TYPESAFE_API_KEY set
2. LLM JSON mode (litellm) — Claude/GPT structured output as baseline
3. decision_llm_json — the decision service's LLMJsonBackend contract
4. Mock — synthetic answers for harness testing (no API needed)

Usage:
    uv run scripts/jev_eval/runner.py                     # dry-run, no API keys needed
    uv run scripts/jev_eval/runner.py --live              # real Jev + LLM calls
    uv run scripts/jev_eval/runner.py --backend jev       # Jev only
    uv run scripts/jev_eval/runner.py --backend llm_json  # LLM baseline only
    uv run scripts/jev_eval/runner.py --backend decision_llm_json  # production backend contract
    uv run scripts/jev_eval/runner.py --task ENTITY_MATCH # one task only
    uv run scripts/jev_eval/runner.py --limit 10          # first N cases

Output:
    results.jsonl — one row per (case, backend) with scores
    summary.md — per-task accuracy / latency / cost table
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Add backend to path for imports
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.jev_eval.cases import (  # noqa: E402 — needs sys.path bootstrap above
    ALL_CASES,
    EvalCase,
    cases_by_task,
    get_questions_for_task,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

OUT_DIR = Path(__file__).resolve().parent
RESULTS_FILE = OUT_DIR / "results.jsonl"
SUMMARY_FILE = OUT_DIR / "summary.md"

# Jev pricing: $42 per billion input tokens, output free
JEV_PRICE_PER_BTOK_INPUT = 42.0


@dataclass
class EvalResult:
    case_id: str
    task: str
    backend: str  # jev | llm_json | decision_llm_json | mock
    predicted: Any  # choice key / noul float / score float
    confidence: float | None
    expected: Any
    correct: bool  # task-specific correctness
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Correctness scoring per task
# ---------------------------------------------------------------------------


def score_correctness(case: EvalCase, predicted: Any, backend: str) -> bool:
    """Task-specific correctness check."""
    if predicted is None:
        return False
    if case.task == "SUBAGENT_ROUTING":
        return str(predicted) == str(case.expected)
    if case.task == "ENTITY_MATCH":
        # Score: 0=different, 1=uncertain, 2=same — predicted is float
        try:
            return abs(float(predicted) - float(case.expected)) <= max(
                case.tolerance, 0.6
            )
        except (TypeError, ValueError):
            return False
    if case.task == "CONTENT_FILTER":
        # Noul: predicted is 0-1 probability of "yes"
        try:
            prob = float(predicted)
            pred_bool = prob >= 0.5
            return pred_bool == bool(case.expected)
        except (TypeError, ValueError):
            return False
    if case.task == "INTENT_CLASSIFY":
        return str(predicted) == str(case.expected)
    return False


# ---------------------------------------------------------------------------
# Backend: Jev (typesafe-sdk)
# ---------------------------------------------------------------------------


def _build_jev_questions(case: EvalCase) -> dict[str, Any]:
    """Convert question spec dicts → typed Question objects for Jev."""
    from typesafe_sdk import Choice, Noul, Score

    questions_spec = get_questions_for_task(case.task)
    q_objects: dict[str, Any] = {}
    for qid, spec in questions_spec.items():
        if spec["type"] == "choice":
            q_objects[qid] = Choice(
                instructions=spec["instructions"],
                criteria=spec["criteria"],
            )
        elif spec["type"] == "noul":
            q_objects[qid] = Noul(
                instructions=spec["instructions"],
                criteria=spec.get("criteria"),
            )
        elif spec["type"] == "score":
            q_objects[qid] = Score(
                instructions=spec["instructions"],
                criteria=spec["criteria"],
            )
    return q_objects


async def run_jev(case: EvalCase, client: Any) -> EvalResult:
    """Run a single case through Jev."""
    try:
        q_objects = _build_jev_questions(case)
    except ImportError:
        return EvalResult(
            case_id=case.id,
            task=case.task,
            backend="jev",
            predicted=None,
            confidence=None,
            expected=case.expected,
            correct=False,
            latency_ms=0.0,
            error="typesafe-sdk not installed: uv add typesafe-sdk",
        )

    start = time.perf_counter()
    try:
        response = await client.system_one(state=case.state, questions=q_objects)
    except Exception as e:
        return EvalResult(
            case_id=case.id,
            task=case.task,
            backend="jev",
            predicted=None,
            confidence=None,
            expected=case.expected,
            correct=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            error=f"{type(e).__name__}: {e}",
        )
    latency = (time.perf_counter() - start) * 1000

    # Extract answer for this case's question_id
    answers = (
        response.answers
        if hasattr(response, "answers")
        else response.get("answers", {})
    )
    ans = (
        answers.get(case.question_id)
        if isinstance(answers, dict)
        else getattr(answers, case.question_id, None)
    )
    if ans is None:
        return EvalResult(
            case_id=case.id,
            task=case.task,
            backend="jev",
            predicted=None,
            confidence=None,
            expected=case.expected,
            correct=False,
            latency_ms=latency,
            error=f"question_id '{case.question_id}' not in response answers",
        )

    # Extract the typed answer value — use explicit None checks (0.0 is falsy!)
    def _get(obj: Any, attr: str) -> Any:
        v = getattr(obj, attr, None)
        if v is None and isinstance(obj, dict):
            v = obj.get(attr)
        return v

    if case.task in ("SUBAGENT_ROUTING", "INTENT_CLASSIFY"):
        predicted = _get(ans, "choice")
        conf = _get(ans, "confidence")
    elif case.task == "ENTITY_MATCH":
        predicted = _get(ans, "score")
        conf = _get(ans, "confidence")
    elif case.task == "CONTENT_FILTER":
        predicted = _get(ans, "noul")
        conf = None  # Noul has no separate confidence
    else:
        predicted, conf = None, None

    usage = getattr(response, "usage", None) or getattr(response, "model", None)
    return EvalResult(
        case_id=case.id,
        task=case.task,
        backend="jev",
        predicted=predicted,
        confidence=conf,
        expected=case.expected,
        correct=score_correctness(case, predicted, "jev"),
        latency_ms=latency,
        input_tokens=getattr(usage, "input_tokens", None) if usage else None,
        output_tokens=getattr(usage, "output_tokens", None) if usage else None,
    )


# ---------------------------------------------------------------------------
# Backend: LLM JSON mode (litellm baseline)
# ---------------------------------------------------------------------------


def _build_llm_prompt(case: EvalCase) -> tuple[str, dict[str, Any]]:
    """Build a structured-output prompt matching the same decision."""
    questions_spec = get_questions_for_task(case.task)
    qspec = questions_spec[case.question_id]
    state_str = json.dumps(case.state, ensure_ascii=False, indent=2)

    if qspec["type"] == "choice":
        options = list(qspec["criteria"].keys())
        json_schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "enum": options},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["answer", "confidence"],
        }
        prompt = (
            f"You are a classifier. Given this state:\n\n{state_str}\n\n"
            f"Question: {qspec['instructions']}\n"
            f"Valid options: {json.dumps(options)}\n\n"
            f'Respond with JSON: {{"answer": "<option>", "confidence": <0-1>}}'
        )
    elif qspec["type"] == "noul":
        json_schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["answer"],
        }
        prompt = (
            f"You are a yes/no evaluator. Given this state:\n\n{state_str}\n\n"
            f"Question: {qspec['instructions']}\n\n"
            f'Respond with JSON: {{"answer": <probability-yes 0-1>}}'
        )
    elif qspec["type"] == "score":
        levels = qspec["criteria"]
        json_schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "number"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["answer", "confidence"],
        }
        prompt = (
            f"You are a scorer. Given this state:\n\n{state_str}\n\n"
            f"Question: {qspec['instructions']}\n"
            f"Score levels (0 to {len(levels) - 1}): {json.dumps(levels)}\n\n"
            f'Respond with JSON: {{"answer": <float-score>, "confidence": <0-1>}}'
        )
    else:
        raise ValueError(f"Unknown type {qspec['type']}")
    return prompt, json_schema


async def run_llm_json(
    case: EvalCase, model: str = "claude-haiku-4-5-20251001"
) -> EvalResult:
    """Run a single case through LLM structured output."""
    try:
        import litellm
    except ImportError:
        return EvalResult(
            case_id=case.id,
            task=case.task,
            backend="llm_json",
            predicted=None,
            confidence=None,
            expected=case.expected,
            correct=False,
            latency_ms=0.0,
            error="litellm not installed",
        )

    prompt, json_schema = _build_llm_prompt(case)
    start = time.perf_counter()
    try:
        resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "decision",
                    "schema": json_schema,
                    "strict": True,
                },
            },
            temperature=0,
        )
        latency = (time.perf_counter() - start) * 1000
        content = resp.choices[0].message.content
        data = json.loads(content)
        predicted = data.get("answer")
        conf = data.get("confidence")
        usage = getattr(resp, "usage", None)
        return EvalResult(
            case_id=case.id,
            task=case.task,
            backend="llm_json",
            predicted=predicted,
            confidence=conf,
            expected=case.expected,
            correct=score_correctness(case, predicted, "llm_json"),
            latency_ms=latency,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )
    except Exception as e:
        return EvalResult(
            case_id=case.id,
            task=case.task,
            backend="llm_json",
            predicted=None,
            confidence=None,
            expected=case.expected,
            correct=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            error=f"{type(e).__name__}: {e}",
        )


# ---------------------------------------------------------------------------
# Backend: decision-service LLMJsonBackend (production contract)
# ---------------------------------------------------------------------------


def _build_decision_questions(case: EvalCase) -> dict[str, Any]:
    """Convert question spec dicts → decision-service typed Questions."""
    from app.services.decision.types import ChoiceQuestion, NoulQuestion, ScoreQuestion

    questions_spec = get_questions_for_task(case.task)
    q_objects: dict[str, Any] = {}
    for qid, spec in questions_spec.items():
        if spec["type"] == "choice":
            q_objects[qid] = ChoiceQuestion(
                instructions=spec["instructions"],
                criteria=spec["criteria"],
            )
        elif spec["type"] == "noul":
            q_objects[qid] = NoulQuestion(
                instructions=spec["instructions"],
                criteria=spec.get("criteria"),
            )
        elif spec["type"] == "score":
            q_objects[qid] = ScoreQuestion(
                instructions=spec["instructions"],
                criteria=spec["criteria"],
            )
    return q_objects


async def run_decision_llm_json(case: EvalCase, model: str | None = None) -> EvalResult:
    """Run a case through the decision service's LLMJsonBackend.

    Exercises the production contract — one batched call over the task's
    whole question set, strict json_schema, normalized ``Answer`` — then
    applies the same strict validation ``DecisionService`` enforces, so
    a live run compares the baseline prompt against the shipped path.
    """
    from app.services.decision.backends.llm_json import LLMJsonBackend
    from app.services.decision.validation import validate_answer

    questions = _build_decision_questions(case)
    try:
        result = await LLMJsonBackend().decide(case.state, questions, model=model)
        answer = result.answers.get(case.question_id)
        if answer is None:
            raise ValueError(
                f"question_id '{case.question_id}' not in response answers"
            )
        answer = validate_answer(answer, questions[case.question_id])
    except Exception as e:
        return EvalResult(
            case_id=case.id,
            task=case.task,
            backend="decision_llm_json",
            predicted=None,
            confidence=None,
            expected=case.expected,
            correct=False,
            latency_ms=0.0,
            error=f"{type(e).__name__}: {e}",
        )
    return EvalResult(
        case_id=case.id,
        task=case.task,
        backend="decision_llm_json",
        predicted=answer.value,
        confidence=answer.confidence,
        expected=case.expected,
        correct=score_correctness(case, answer.value, "decision_llm_json"),
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


# ---------------------------------------------------------------------------
# Backend: Mock (deterministic, no API) — for harness validation
# ---------------------------------------------------------------------------


def run_mock(case: EvalCase) -> EvalResult:
    """Return the expected answer with 0.9 confidence — validates harness."""
    start = time.perf_counter()
    predicted = case.expected
    latency = (time.perf_counter() - start) * 1000
    return EvalResult(
        case_id=case.id,
        task=case.task,
        backend="mock",
        predicted=predicted,
        confidence=0.9,
        expected=case.expected,
        correct=score_correctness(case, predicted, "mock"),
        latency_ms=latency,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_all(
    backends: list[str], task_filter: str | None = None, limit: int | None = None
) -> list[EvalResult]:
    cases = cases_by_task(task_filter) if task_filter else ALL_CASES
    if limit:
        cases = cases[:limit]
    logger.info(
        "Running %d cases over backends=%s task=%s",
        len(cases),
        backends,
        task_filter or "all",
    )

    jev_client = None
    if "jev" in backends and os.environ.get("TYPESAFE_API_KEY"):
        try:
            from typesafe_sdk import AsyncTypeSafeClient

            jev_client = AsyncTypeSafeClient()
            logger.info("Jev client initialized")
        except ImportError:
            logger.error(
                "typesafe-sdk not installed — run `uv add typesafe-sdk` in nowing_backend"
            )
            backends = [b for b in backends if b != "jev"]
    elif "jev" in backends:
        logger.warning("TYPESAFE_API_KEY not set — skipping Jev backend")
        backends = [b for b in backends if b != "jev"]

    results: list[EvalResult] = []
    for i, case in enumerate(cases):
        logger.info("[%d/%d] %s (%s)", i + 1, len(cases), case.id, case.task)
        for backend in backends:
            if backend == "jev" and jev_client:
                r = await run_jev(case, jev_client)
            elif backend == "llm_json":
                r = await run_llm_json(case)
            elif backend == "decision_llm_json":
                r = await run_decision_llm_json(case)
            elif backend == "mock":
                r = run_mock(case)
            else:
                continue
            results.append(r)
            logger.info(
                "  %s → predicted=%r expected=%r correct=%s (%.0fms)",
                backend,
                r.predicted,
                r.expected,
                r.correct,
                r.latency_ms,
            )
    return results


def write_results(results: list[EvalResult]) -> None:
    with open(RESULTS_FILE, "w") as f:
        for r in results:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    logger.info("Wrote %d results to %s", len(results), RESULTS_FILE)


def write_summary(results: list[EvalResult]) -> None:
    """Aggregate per-task, per-backend stats."""
    from collections import defaultdict

    stats: dict[tuple[str, str], list[EvalResult]] = defaultdict(list)
    for r in results:
        stats[(r.task, r.backend)].append(r)

    lines = [
        "# Jev Vietnamese eval — summary",
        "",
        f"**Cases:** {len(results)} | **Date:** 2026-09-21",
        "",
        "| Task | Backend | N | Accuracy | Median latency | P95 latency | Errors |",
        "|---|---|---|---|---|---|---|",
    ]
    for (task, backend), rs in sorted(stats.items()):
        n = len(rs)
        n_correct = sum(1 for r in rs if r.correct)
        errors = sum(1 for r in rs if r.error)
        latencies = sorted(r.latency_ms for r in rs if not r.error)
        if latencies:
            med = latencies[len(latencies) // 2]
            p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)]
            acc = n_correct / n
            lines.append(
                f"| {task} | {backend} | {n} | {acc:.1%} | {med:.0f}ms | {p95:.0f}ms | {errors} |"
            )
        else:
            lines.append(f"| {task} | {backend} | {n} | — | — | — | {errors} |")

    # Cost estimate for Jev
    jev_results = [r for r in results if r.backend == "jev" and r.input_tokens]
    if jev_results:
        total_input = sum(r.input_tokens or 0 for r in jev_results)
        cost = total_input * JEV_PRICE_PER_BTOK_INPUT / 1_000_000_000
        lines += [
            "",
            "## Jev cost estimate",
            f"- Total input tokens: {total_input:,}",
            f"- Estimated cost: ${cost:.4f} (${JEV_PRICE_PER_BTOK_INPUT}/Btok input, output free)",
        ]

    lines += [
        "",
        "## Per-case detail",
        "",
        "| Case | Task | Backend | Predicted | Expected | Correct | Latency | Error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        err = (r.error or "")[:40]
        lines.append(
            f"| {r.case_id} | {r.task} | {r.backend} | `{r.predicted}` | `{r.expected}` | {'✅' if r.correct else '❌'} | {r.latency_ms:.0f}ms | {err} |"
        )
    SUMMARY_FILE.write_text("\n".join(lines))
    logger.info("Wrote summary to %s", SUMMARY_FILE)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--live", action="store_true", help="Run Jev + LLM backends (requires API keys)"
    )
    p.add_argument(
        "--backend",
        choices=["jev", "llm_json", "decision_llm_json", "mock", "all"],
        default=None,
    )
    p.add_argument(
        "--task",
        choices=[
            "SUBAGENT_ROUTING",
            "ENTITY_MATCH",
            "CONTENT_FILTER",
            "INTENT_CLASSIFY",
        ],
        default=None,
    )
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    if args.backend and args.backend != "all":
        backends = [args.backend]
    elif args.backend == "all" or args.live:
        backends = ["jev", "llm_json", "decision_llm_json", "mock"]
    else:
        backends = ["mock"]  # default: harness validation only

    results = await run_all(backends, task_filter=args.task, limit=args.limit)
    write_results(results)
    write_summary(results)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
