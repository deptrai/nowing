"""Chat quality benchmark with LLM-as-judge (Story 4.8d).

Each case is a (query, reference_answer, rubric) triple. The harness:

1. Asks Nowing the query.
2. Sends the Nowing answer, reference, and rubric to an OpenRouter judge.
3. Parses four 1-5 dimension scores from the judge response.
4. Aggregates mean scores overall and per tag, plus judge cost / latency.
5. Evaluates ``gate.yaml`` thresholds and raises on failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml

from ....core.arms import NowingArm
from ....core.arms.base import ArmRequest, ArmResult
from ....core.clients import NewChatClient
from ....core.config import utc_iso_timestamp
from ....core.providers.openrouter_chat import OpenRouterChatProvider
from ....core.registry import ReportSection, RunArtifact, RunContext, register
from .prompt import _JUDGE_SYSTEM, SCORE_FIELDS, build_judge_prompt, parse_judge_scores

logger = logging.getLogger(__name__)


_DESCRIPTION = (
    "Quality benchmark with LLM-as-judge. Scores Nowing answers against "
    "reference answers and a rubric on correctness, citation faithfulness, "
    "completeness, and harmfulness."
)


@dataclass
class _Case:
    case_id: str
    query: str
    reference_answer: str
    rubric: str
    tags: list[str] = field(default_factory=list)
    mentioned_document_ids: list[int] = field(default_factory=list)
    disabled_tools: list[str] | None = None
    mode: str = "balanced"


@dataclass
class _ScoreResult:
    case_id: str
    query: str
    answer: str
    answer_error: str | None
    answer_cost_micros: int
    answer_latency_ms: int
    judge_raw: str
    judge_cost_micros: int
    judge_latency_ms: int
    scores: dict[str, float]
    tags: list[str]


_JUDGE_MODEL_DEFAULT = "anthropic/claude-sonnet-4.5"
_JUDGE_TIMEOUT_DEFAULT = 120.0
_JUDGE_MAX_TOKENS_DEFAULT = 256
_JUDGE_CONCURRENCY_DEFAULT = 4


_DEFAULT_DATASET: list[dict[str, Any]] = [
    {
        "case_id": "q-001",
        "query": "What are the three most important factors when choosing a cloud provider?",
        "reference_answer": (
            "The three most important factors are cost, reliability / uptime, "
            "and data security / compliance certifications."
        ),
        "rubric": "Must list exactly three factors: cost, reliability/uptime, security/compliance.",
        "tags": ["general"],
    },
    {
        "case_id": "q-002",
        "query": "Summarize the main point of the attached memo in one sentence.",
        "reference_answer": (
            "The memo announces a company-wide transition to a four-day work week."
        ),
        "rubric": "Answer must mention the four-day work week policy and be a single sentence.",
        "tags": ["summarization"],
    },
]


def _list_of_str(value: Any, field: str, case_id: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value  # type: ignore[return-value]
    raise RuntimeError(
        f"Invalid type for '{field}' in case {case_id!r}: expected list of strings, got {value!r}"
    )


def _list_of_int(value: Any, field: str, case_id: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list) and all(isinstance(v, int) for v in value):
        return value  # type: ignore[return-value]
    raise RuntimeError(
        f"Invalid type for '{field}' in case {case_id!r}: expected list of ints, got {value!r}"
    )


def _validate_case_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise RuntimeError("Case row must be a JSON object")

    case_id = row.get("case_id")
    if not case_id:
        raise RuntimeError("Case row is missing 'case_id'")

    query = row.get("query")
    if not query or not isinstance(query, str):
        raise RuntimeError(f"Case {case_id!r} is missing or has invalid 'query'")

    reference_answer = row.get("reference_answer")
    if not reference_answer or not isinstance(reference_answer, str):
        raise RuntimeError(f"Case {case_id!r} is missing or has invalid 'reference_answer'")

    rubric = row.get("rubric")
    if not rubric or not isinstance(rubric, str):
        raise RuntimeError(f"Case {case_id!r} is missing or has invalid 'rubric'")

    tags = _list_of_str(row.get("tags"), "tags", case_id)
    mentioned_document_ids = _list_of_int(
        row.get("mentioned_document_ids"), "mentioned_document_ids", case_id
    )
    disabled_tools = _list_of_str(row.get("disabled_tools"), "disabled_tools", case_id) or None
    disabled_tools = disabled_tools if disabled_tools else None

    mode = str(row.get("mode") or "balanced").strip()
    if mode not in {"speed", "balanced", "quality", "auto"}:
        raise RuntimeError(
            f"Case {case_id!r} has invalid 'mode': {mode!r}. "
            "Allowed: speed, balanced, quality, auto."
        )

    return {
        "case_id": str(case_id),
        "query": query,
        "reference_answer": reference_answer,
        "rubric": rubric,
        "tags": tags,
        "mentioned_document_ids": mentioned_document_ids,
        "disabled_tools": disabled_tools,
        "mode": mode,
    }


def _cases_path(ctx: RunContext) -> Path:
    return ctx.benchmark_data_dir() / "cases.jsonl"


def _load_cases(path: Path) -> list[_Case]:
    cases: list[_Case] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = _validate_case_row(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Malformed JSONL at {path}:{line_no}: {exc}") from exc
            cases.append(
                _Case(
                    case_id=row["case_id"],
                    query=row["query"],
                    reference_answer=row["reference_answer"],
                    rubric=row["rubric"],
                    tags=row["tags"],
                    mentioned_document_ids=row["mentioned_document_ids"],
                    disabled_tools=row["disabled_tools"],
                    mode=row["mode"],
                )
            )
    return cases


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    idx = (n - 1) * p
    low = int(idx)
    high = low + 1
    if high >= n:
        return s[-1]
    weight = idx - low
    return s[low] * (1 - weight) + s[high] * weight


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _aggregate_scores(results: list[_ScoreResult]) -> dict[str, Any]:
    def _bucket(items: list[_ScoreResult]) -> dict[str, Any]:
        n = len(items)
        if not n:
            return {"samples": 0}

        scores: dict[str, list[float]] = {field: [] for field in SCORE_FIELDS}
        judge_latencies: list[float] = []
        judge_costs: list[float] = []
        answer_latencies: list[float] = []
        answer_costs: list[float] = []
        n_answer_errors = 0

        for r in items:
            for score_field in SCORE_FIELDS:
                scores[score_field].append(r.scores.get(score_field, 0.0))
            judge_latencies.append(float(r.judge_latency_ms))
            judge_costs.append(float(r.judge_cost_micros))
            answer_latencies.append(float(r.answer_latency_ms))
            answer_costs.append(float(r.answer_cost_micros))
            if r.answer_error:
                n_answer_errors += 1

        bucket: dict[str, Any] = {
            "samples": n,
            "n_answer_errors": n_answer_errors,
            "answer_error_rate": n_answer_errors / n,
        }
        for score_field in SCORE_FIELDS:
            bucket[f"mean_{score_field}"] = _mean(scores[score_field])
        bucket["p50_judge_latency_ms"] = _percentile(judge_latencies, 0.5)
        bucket["p95_judge_latency_ms"] = _percentile(judge_latencies, 0.95)
        bucket["p50_answer_latency_ms"] = _percentile(answer_latencies, 0.5)
        bucket["p95_answer_latency_ms"] = _percentile(answer_latencies, 0.95)
        bucket["total_judge_cost_micros"] = int(sum(judge_costs))
        bucket["total_answer_cost_micros"] = int(sum(answer_costs))
        bucket["total_cost_micros"] = int(sum(judge_costs) + sum(answer_costs))
        return bucket

    overall = _bucket(results)

    per_tag: dict[str, list[_ScoreResult]] = {}
    for r in results:
        for tag in r.tags:
            per_tag.setdefault(tag, []).append(r)

    return {
        "overall": overall,
        "per_tag": {tag: _bucket(items) for tag, items in per_tag.items()},
    }


def _evaluate_gate(metrics: dict[str, Any], gate_path: Path) -> list[str]:
    """Evaluate gate.yaml thresholds against the quality metrics."""

    if not gate_path.is_file():
        return []

    try:
        with gate_path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [f"Failed to load gate config: {exc}"]

    thresholds = config.get("thresholds", {})
    baseline_ratified = bool(config.get("baseline_ratified", False))
    violations: list[str] = []

    def _check(
        name: str, value: float | None, min_val: float | None = None, max_val: float | None = None
    ) -> None:
        if value is None:
            return
        if min_val is not None and value < min_val:
            violations.append(f"{name} {value:.3f} is below min {min_val:.3f}")
        if max_val is not None and value > max_val:
            violations.append(f"{name} {value:.3f} exceeds max {max_val:.3f}")

    overall = metrics.get("overall", {})
    _check(
        "mean correctness",
        overall.get("mean_correctness"),
        min_val=thresholds.get("min_mean_correctness"),
    )
    _check(
        "mean citation faithfulness",
        overall.get("mean_citation_faithfulness"),
        min_val=thresholds.get("min_citation_faithfulness"),
    )
    _check(
        "mean completeness",
        overall.get("mean_completeness"),
        min_val=thresholds.get("min_mean_completeness"),
    )
    _check(
        "mean harmfulness",
        overall.get("mean_harmfulness"),
        max_val=thresholds.get("max_mean_harmfulness"),
    )
    _check(
        "answer error rate",
        overall.get("answer_error_rate"),
        max_val=thresholds.get("max_answer_error_rate"),
    )

    if violations and not baseline_ratified:
        return [f"{v} (baseline not ratified)" for v in violations]

    return violations


class ChatQualityBenchmark:
    suite: str = "chat"
    name: str = "quality"
    headline: bool = False
    description: str = _DESCRIPTION
    requires_suite_setup: bool = False
    requires_auth_for_ingest: bool = False

    @staticmethod
    def gate_config_path() -> str:
        return str(Path(__file__).with_name("gate.yaml"))

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--search-space-id",
            type=int,
            default=None,
            help="SearchSpace used for thread creation.",
        )
        parser.add_argument(
            "--workspace-id",
            type=int,
            default=None,
            help="Workspace id for thread creation and audit/reporting.",
        )
        parser.add_argument(
            "--dataset",
            type=Path,
            default=None,
            help="JSONL dataset (default: data/chat/quality/cases.jsonl).",
        )
        parser.add_argument(
            "--n",
            dest="sample_n",
            type=int,
            default=None,
            help="Cap the number of cases.",
        )
        parser.add_argument(
            "--tags",
            default=None,
            help="Comma-separated tag filter (e.g. memory,document).",
        )
        parser.add_argument(
            "--chat-mode",
            default="balanced",
            choices=["speed", "balanced", "quality", "auto"],
            help="Chat mode to use for Nowing answers.",
        )
        parser.add_argument(
            "--judge-model",
            default=_JUDGE_MODEL_DEFAULT,
            help="OpenRouter model slug used as the judge.",
        )
        parser.add_argument(
            "--judge-timeout",
            type=float,
            default=_JUDGE_TIMEOUT_DEFAULT,
            help="Timeout in seconds for each judge call.",
        )
        parser.add_argument(
            "--judge-max-tokens",
            type=int,
            default=_JUDGE_MAX_TOKENS_DEFAULT,
            help="Max tokens for each judge response.",
        )
        parser.add_argument(
            "--judge-concurrency",
            type=int,
            default=_JUDGE_CONCURRENCY_DEFAULT,
            help="Concurrent judge calls.",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=600.0,
            help="Per-question timeout for the Nowing answer in seconds.",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=1,
            help="Concurrent Nowing answer calls.",
        )
        parser.add_argument(
            "--backend-build-id",
            type=str,
            default=None,
            help="Deployed backend build/commit identifier this run evaluates.",
        )
        parser.add_argument(
            "--max-total-cost-micros",
            type=int,
            default=None,
            help="Abort if the total run cost exceeds this cap.",
        )
        parser.add_argument(
            "--fail-on-unratified",
            action="store_true",
            help="Fail the run if gate.yaml baseline_ratified is false.",
        )

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        dataset_path: Path | None = opts.get("dataset")
        target = _cases_path(ctx)

        if dataset_path:
            if not dataset_path.is_file():  # noqa: ASYNC240
                raise RuntimeError(f"Dataset not found: {dataset_path}")
            text = dataset_path.read_text(encoding="utf-8")  # noqa: ASYNC240
            with target.open("w", encoding="utf-8") as fh:
                for line_no, line in enumerate(text.splitlines(), start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = _validate_case_row(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            f"Malformed JSONL at {dataset_path}:{line_no}: {exc}"
                        ) from exc
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            logger.info("Installed %d cases from %s", len(_load_cases(target)), dataset_path)
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            for row in _DEFAULT_DATASET:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("Wrote default %d sample cases to %s", len(_DEFAULT_DATASET), target)

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        search_space_id = opts.get("search_space_id") or ctx.search_space_id
        if not search_space_id:
            raise RuntimeError("--search-space-id or a suite setup with a SearchSpace is required.")
        workspace_id = opts.get("workspace_id")
        sample_n = opts.get("sample_n")
        tags_filter = opts.get("tags")
        mode = str(opts.get("chat_mode") or "balanced")
        valid_modes = {"speed", "balanced", "quality", "auto"}
        if mode not in valid_modes:
            raise RuntimeError(
                f"Invalid --mode: {mode}. Allowed: {', '.join(sorted(valid_modes))}."
            )

        judge_model = str(opts.get("judge_model") or _JUDGE_MODEL_DEFAULT)
        judge_timeout = float(opts.get("judge_timeout") or _JUDGE_TIMEOUT_DEFAULT)
        judge_max_tokens = int(opts.get("judge_max_tokens") or _JUDGE_MAX_TOKENS_DEFAULT)
        judge_concurrency = max(1, int(opts.get("judge_concurrency") or _JUDGE_CONCURRENCY_DEFAULT))
        concurrency = max(1, int(opts.get("concurrency") or 1))
        timeout_s = float(opts.get("timeout") or 600.0)
        build_id = opts.get("backend_build_id")
        max_total_cost_micros = opts.get("max_total_cost_micros")
        fail_on_unratified = bool(opts.get("fail_on_unratified"))

        if sample_n is not None and sample_n < 1:
            raise RuntimeError("--n must be >= 1.")
        if judge_timeout <= 0:
            raise RuntimeError("--judge-timeout must be > 0.")
        if timeout_s <= 0:
            raise RuntimeError("--timeout must be > 0.")

        dataset_path = opts.get("dataset") or _cases_path(ctx)
        if not dataset_path.is_file():
            raise RuntimeError(
                f"Dataset not found: {dataset_path}. Run "
                f"`python -m nowing_evals ingest chat quality` first."
            )

        all_cases = _load_cases(dataset_path)
        cases = all_cases
        if tags_filter:
            wanted = {t.strip() for t in tags_filter.split(",") if t.strip()}
            cases = [c for c in cases if any(t in wanted for t in c.tags)]
        if sample_n is not None:
            cases = cases[:sample_n]

        if not cases:
            raise RuntimeError("No chat quality cases selected for the requested filters.")

        run_dir = ctx.runs_dir(run_timestamp=utc_iso_timestamp())
        raw_path = run_dir / "raw.jsonl"

        client = NewChatClient(ctx.http, ctx.config.nowing_api_base)
        arm = NowingArm(
            client=client,
            search_space_id=search_space_id,
            workspace_id=workspace_id if workspace_id is not None else search_space_id,
        )

        # ponytail: preload source text for cited documents so the judge can
        # verify citation_faithfulness against actual chunks. Failure to load a
        # document is non-fatal; the prompt falls back to "(no source material)".
        documents_client = ctx.documents_client()
        unique_doc_ids = {doc_id for c in cases for doc_id in c.mentioned_document_ids}
        source_text_map: dict[int, str] = {}
        if unique_doc_ids:

            async def _load_doc(doc_id: int) -> None:
                try:
                    chunks = await documents_client.list_chunks(doc_id, page_size=100)
                    # Number the source passages [1], [2], ... so the judge can map
                    # the agent's bare [n] citation markers to a specific chunk.
                    source_text_map[doc_id] = "\n\n".join(
                        f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks)
                    )
                except Exception as exc:
                    logger.warning("Failed to load chunks for document %s: %s", doc_id, exc)
                    source_text_map[doc_id] = ""

            await asyncio.gather(*(_load_doc(d) for d in unique_doc_ids))

        api_key = ctx.config.openrouter_api_key
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is required for the chat/quality judge. "
                "Set the env var or --openrouter-api-key."
            )

        provider = OpenRouterChatProvider(
            api_key=api_key,
            base_url=ctx.config.openrouter_base_url,
            model=judge_model,
            timeout_s=judge_timeout,
        )

        sem = asyncio.Semaphore(concurrency)
        judge_sem = asyncio.Semaphore(judge_concurrency)

        results: list[_ScoreResult] = []
        total_cost = 0

        async def _score_one(case: _Case) -> _ScoreResult:
            nonlocal total_cost
            async with sem:
                request = ArmRequest(
                    question_id=case.case_id,
                    prompt=case.query,
                    mentioned_document_ids=case.mentioned_document_ids,
                    options={
                        "mode": case.mode or mode,
                        "disabled_tools": case.disabled_tools,
                        "delete_thread": True,
                    },
                )
                try:
                    answer = await asyncio.wait_for(arm.answer(request), timeout=timeout_s)
                except TimeoutError:
                    answer = ArmResult(
                        arm="nowing",
                        question_id=case.case_id,
                        raw_text="",
                        error="TimeoutError: Nowing answer exceeded timeout",
                        latency_ms=int(timeout_s * 1000),
                    )

                answer_text = answer.raw_text or ""
                source_text = "\n\n".join(
                    source_text_map.get(d, "") for d in case.mentioned_document_ids
                )
                judge_prompt = build_judge_prompt(
                    query=case.query,
                    reference_answer=case.reference_answer,
                    rubric=case.rubric,
                    answer=answer_text,
                    source_text=source_text,
                )

                judge_raw = ""
                judge_cost = 0
                judge_latency = 0
                scores: dict[str, float] = {field: 0.0 for field in SCORE_FIELDS}

                if answer.error:
                    logger.warning(
                        "Nowing answer failed for %s: %s; scoring as zero",
                        case.case_id,
                        answer.error,
                    )
                else:
                    async with judge_sem:
                        # Try JSON-mode first; some providers reject it.
                        try:
                            response = await provider.complete(
                                prompt=judge_prompt,
                                system_prompt=_JUDGE_SYSTEM,
                                max_tokens=judge_max_tokens,
                                response_format={"type": "json_object"},
                            )
                        except httpx.HTTPStatusError as exc:
                            if exc.response.status_code in {400, 422}:
                                logger.debug(
                                    "Judge JSON-mode rejected for %s; retrying without it",
                                    case.case_id,
                                )
                                response = await provider.complete(
                                    prompt=judge_prompt,
                                    system_prompt=_JUDGE_SYSTEM,
                                    max_tokens=judge_max_tokens,
                                )
                            else:
                                raise
                        judge_raw = response.text
                        judge_cost = response.cost_micros
                        judge_latency = response.latency_ms
                        scores = parse_judge_scores(response.text)

                total_cost += answer.cost_micros + judge_cost
                if max_total_cost_micros is not None and total_cost > max_total_cost_micros:
                    raise RuntimeError(
                        f"Total run cost {total_cost} micros exceeds cap {max_total_cost_micros}"
                    )

                return _ScoreResult(
                    case_id=case.case_id,
                    query=case.query,
                    answer=answer_text,
                    answer_error=answer.error,
                    answer_cost_micros=answer.cost_micros,
                    answer_latency_ms=answer.latency_ms,
                    judge_raw=judge_raw,
                    judge_cost_micros=judge_cost,
                    judge_latency_ms=judge_latency,
                    scores=scores,
                    tags=case.tags,
                )

        try:
            scored = await asyncio.gather(*(_score_one(c) for c in cases), return_exceptions=True)
        except Exception as exc:
            logger.exception("chat/quality run failed")
            raise RuntimeError(f"chat/quality run failed: {exc}") from exc

        for item in scored:
            if isinstance(item, Exception):
                raise RuntimeError(f"chat/quality case failed: {item}") from item
            results.append(item)

        # Write raw JSONL.
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with raw_path.open("w", encoding="utf-8") as fh:
            for r in results:
                fh.write(
                    json.dumps(
                        {
                            "case_id": r.case_id,
                            "query": r.query,
                            "answer": r.answer,
                            "answer_error": r.answer_error,
                            "answer_cost_micros": r.answer_cost_micros,
                            "answer_latency_ms": r.answer_latency_ms,
                            "judge_raw": r.judge_raw,
                            "judge_cost_micros": r.judge_cost_micros,
                            "judge_latency_ms": r.judge_latency_ms,
                            "scores": r.scores,
                            "tags": r.tags,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        metrics = _aggregate_scores(results)

        gate_path = Path(self.gate_config_path())
        gate_violations = _evaluate_gate(metrics, gate_path)

        extra = {
            "judge_model": judge_model,
            "judge_timeout": judge_timeout,
            "judge_max_tokens": judge_max_tokens,
            "judge_concurrency": judge_concurrency,
            "search_space_id": search_space_id,
            "workspace_id": workspace_id,
            "n_cases": len(cases),
            "backend_build_id": build_id,
            "answer_concurrency": concurrency,
            "answer_timeout": timeout_s,
            "gate_violations": gate_violations,
        }

        run_artifact_path = run_dir / "run_artifact.json"
        _write_json_atomic(
            run_artifact_path,
            {
                "suite": self.suite,
                "benchmark": self.name,
                "raw_path": "raw.jsonl",
                "metrics": metrics,
                "extra": extra,
            },
        )

        if gate_violations:
            logger.warning("Chat quality gate violations: %s", "; ".join(gate_violations))
            # _evaluate_gate already tags messages with "(baseline not ratified)".
            if fail_on_unratified or not any(
                "(baseline not ratified)" in v for v in gate_violations
            ):
                raise RuntimeError(f"Chat quality gate failed: {'; '.join(gate_violations)}")

        return RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_dir.parent.name,
            raw_path=raw_path,
            metrics=metrics,
            extra=extra,
        )

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="Chat quality",
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        overall = m.get("overall", {})
        judge_model = latest.extra.get("judge_model", "unknown")

        lines = [
            f"- Judge model: {judge_model}",
            f"- Cases: {overall.get('samples', '?')} "
            f"(answer errors: {overall.get('n_answer_errors', 0)}, "
            f"error rate: {overall.get('answer_error_rate', 0):.2%})",
            f"- Mean correctness: {overall.get('mean_correctness') or 0:.2f}",
            f"- Mean citation faithfulness: {overall.get('mean_citation_faithfulness') or 0:.2f}",
            f"- Mean completeness: {overall.get('mean_completeness') or 0:.2f}",
            f"- Mean harmfulness: {overall.get('mean_harmfulness') or 0:.2f} (lower is better)",
            f"- p95 judge latency: {overall.get('p95_judge_latency_ms') or 0:.0f} ms",
            f"- Total cost: {overall.get('total_cost_micros') or 0} micros",
        ]

        per_tag = m.get("per_tag", {})
        if per_tag:
            lines.append("")
            lines.append("### Per-tag mean scores")
            lines.append("| tag | correctness | citation | completeness | harmfulness |")
            lines.append("|---|---|---|---|---|")
            for tag in sorted(per_tag):
                vals = per_tag[tag]
                lines.append(
                    f"| {tag} | "
                    f"{vals.get('mean_correctness') or 0:.2f} | "
                    f"{vals.get('mean_citation_faithfulness') or 0:.2f} | "
                    f"{vals.get('mean_completeness') or 0:.2f} | "
                    f"{vals.get('mean_harmfulness') or 0:.2f} |"
                )

        return ReportSection(
            title="Chat quality",
            headline=False,
            body_md="\n".join(lines),
            body_json={
                "judge_model": judge_model,
                "overall": overall,
                "per_tag": per_tag,
            },
        )


register(ChatQualityBenchmark())
