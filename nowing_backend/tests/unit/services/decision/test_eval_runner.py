"""jev_eval runner — decision_llm_json path through LLMJsonBackend.

The runner lives under ``scripts/`` (not a package), so it is imported
lazily inside each test; ``litellm.acompletion`` is monkeypatched — no
unit test performs a live call.
"""

from __future__ import annotations

import importlib
import json
import logging

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


# ---------------------------------------------------------------------------
# evaluate_gate + _parse_args (Story 39.8)
# ---------------------------------------------------------------------------

TASKS = ["SUBAGENT_ROUTING", "ENTITY_MATCH", "CONTENT_FILTER", "INTENT_CLASSIFY"]

BASELINE = {
    "model": "jev-1.13.0",
    "overall": 0.963,
    "tasks": {
        "SUBAGENT_ROUTING": 1.0,
        "ENTITY_MATCH": 0.9,
        "CONTENT_FILTER": 1.0,
        "INTENT_CLASSIFY": 0.95,
    },
}


def _make_results(accuracies: dict, backend: str = "jev", n: int = 20):
    """Build n EvalResults per task with the given accuracy fraction."""
    runner = importlib.import_module("scripts.jev_eval.runner")
    results = []
    for task, acc in accuracies.items():
        n_correct = round(acc * n)
        for i in range(n):
            results.append(
                runner.EvalResult(
                    case_id=f"{task.lower()}_{i:02d}",
                    task=task,
                    backend=backend,
                    predicted="p",
                    confidence=None,
                    expected="e",
                    correct=i < n_correct,
                    latency_ms=1.0,
                )
            )
    return results


@pytest.mark.unit
def test_evaluate_gate_passes_when_all_tasks_at_floor():
    runner = importlib.import_module("scripts.jev_eval.runner")
    results = _make_results(dict.fromkeys(TASKS, 0.95))
    passed, report = runner.evaluate_gate(results, 0.90, BASELINE)
    assert passed is True
    assert report[-1].startswith("GATE PASS")


@pytest.mark.unit
def test_evaluate_gate_boundary_exact_floor_passes():
    runner = importlib.import_module("scripts.jev_eval.runner")
    results = _make_results({"ENTITY_MATCH": 0.90})
    passed, report = runner.evaluate_gate(results, 0.90, BASELINE)
    assert passed is True
    assert any("PASS ENTITY_MATCH" in line for line in report)


@pytest.mark.unit
def test_evaluate_gate_fails_below_floor_and_names_task():
    runner = importlib.import_module("scripts.jev_eval.runner")
    results = _make_results({"SUBAGENT_ROUTING": 1.0, "ENTITY_MATCH": 0.85})
    passed, report = runner.evaluate_gate(results, 0.90, BASELINE)
    assert passed is False
    assert any(
        "FAIL ENTITY_MATCH" in line and "85.0%" in line for line in report
    )
    assert report[-1].startswith("GATE FAIL")


@pytest.mark.unit
def test_evaluate_gate_no_results_fails():
    runner = importlib.import_module("scripts.jev_eval.runner")
    passed, report = runner.evaluate_gate([], 0.90, BASELINE)
    assert passed is False
    assert any("no evaluable results" in line for line in report)


@pytest.mark.unit
def test_evaluate_gate_all_errors_is_no_evaluable_results():
    runner = importlib.import_module("scripts.jev_eval.runner")
    results = _make_results({"SUBAGENT_ROUTING": 0.0})
    for r in results:
        r.error = "boom"
    passed, report = runner.evaluate_gate(results, 0.90, BASELINE)
    assert passed is False
    assert any("no evaluable results" in line for line in report)


@pytest.mark.unit
def test_evaluate_gate_missing_baseline_still_enforces_floor():
    runner = importlib.import_module("scripts.jev_eval.runner")
    good = _make_results({"SUBAGENT_ROUTING": 0.95})
    passed, report = runner.evaluate_gate(good, 0.90, None)
    assert passed is True
    assert any("comparison skipped" in line for line in report)

    bad = _make_results({"SUBAGENT_ROUTING": 0.50})
    passed, _ = runner.evaluate_gate(bad, 0.90, None)
    assert passed is False


@pytest.mark.unit
def test_evaluate_gate_groups_per_backend():
    """Every (task, backend) group must clear the floor — a synthetic
    mock group drags the verdict down even when jev passes."""
    runner = importlib.import_module("scripts.jev_eval.runner")
    results = _make_results(dict.fromkeys(TASKS, 1.0), backend="jev")
    results += _make_results(dict.fromkeys(TASKS, 0.10), backend="mock")
    passed, report = runner.evaluate_gate(results, 0.90, BASELINE)
    assert passed is False
    assert any("FAIL SUBAGENT_ROUTING [mock]" in line for line in report)
    assert any("PASS SUBAGENT_ROUTING [jev]" in line for line in report)


@pytest.mark.unit
def test_evaluate_gate_reports_baseline_delta():
    runner = importlib.import_module("scripts.jev_eval.runner")
    results = _make_results({"ENTITY_MATCH": 0.85})
    passed, report = runner.evaluate_gate(results, 0.80, BASELINE)
    assert passed is True
    assert any("delta -5.0%" in line for line in report)


@pytest.mark.unit
def test_parse_args_dry_run_alias():
    runner = importlib.import_module("scripts.jev_eval.runner")
    args = runner._parse_args(["--dry-run"])
    assert args.dry_run is True
    assert args.backend is None


@pytest.mark.unit
def test_parse_args_dry_run_conflicts_with_backend():
    runner = importlib.import_module("scripts.jev_eval.runner")
    with pytest.raises(SystemExit):
        runner._parse_args(["--dry-run", "--backend", "jev"])


@pytest.mark.unit
def test_parse_args_gate_floor_and_model_flags():
    runner = importlib.import_module("scripts.jev_eval.runner")
    args = runner._parse_args(
        ["--backend", "jev", "--gate", "--floor", "0.8", "--model", "jev-1.14.0"]
    )
    assert args.gate is True
    assert args.floor == 0.8
    assert args.model == "jev-1.14.0"


@pytest.mark.unit
def test_parse_args_floor_defaults_to_090():
    runner = importlib.import_module("scripts.jev_eval.runner")
    args = runner._parse_args(["--gate"])
    assert args.floor == 0.90


@pytest.mark.unit
async def test_run_jev_passes_model_to_system_one():
    runner = importlib.import_module("scripts.jev_eval.runner")
    from scripts.jev_eval.cases import SUBAGENT_ROUTING_CASES

    calls: list[str | None] = []

    class _Response:
        answers = {"subagent": {"choice": "batdongsan", "confidence": 0.9}}
        usage = None

    class _Client:
        async def system_one(self, state=None, questions=None, model=None):
            calls.append(model)
            return _Response()

    result = await runner.run_jev(
        SUBAGENT_ROUTING_CASES[0], _Client(), model="jev-1.14.0"
    )

    assert calls == ["jev-1.14.0"]
    assert result.model == "jev-1.14.0"
    assert result.correct is True


@pytest.mark.unit
async def test_run_jev_model_defaults_to_none():
    runner = importlib.import_module("scripts.jev_eval.runner")
    from scripts.jev_eval.cases import SUBAGENT_ROUTING_CASES

    calls: list[str | None] = []

    class _Response:
        answers = {"subagent": {"choice": "batdongsan", "confidence": 0.9}}
        usage = None

    class _Client:
        async def system_one(self, state=None, questions=None, model=None):
            calls.append(model)
            return _Response()

    result = await runner.run_jev(SUBAGENT_ROUTING_CASES[0], _Client())

    assert calls == [None]
    assert result.model is None


@pytest.mark.unit
def test_parse_args_live_conflicts_with_backend():
    runner = importlib.import_module("scripts.jev_eval.runner")
    with pytest.raises(SystemExit):
        runner._parse_args(["--live", "--backend", "jev"])


@pytest.mark.unit
def test_parse_args_task_filter_scopes_gate():
    """--task filters which cases run; the gate then evaluates only that
    task's (task, backend) group."""
    runner = importlib.import_module("scripts.jev_eval.runner")
    args = runner._parse_args(["--task", "INTENT_CLASSIFY", "--gate"])
    assert args.task == "INTENT_CLASSIFY"

    results = _make_results({"INTENT_CLASSIFY": 0.95})
    passed, report = runner.evaluate_gate(results, args.floor, BASELINE)
    assert passed is True
    task_lines = [
        line for line in report if line.startswith(("PASS", "FAIL"))
    ]
    assert len(task_lines) == 1
    assert "INTENT_CLASSIFY" in task_lines[0]


@pytest.mark.unit
async def test_run_all_skips_jev_without_api_key(monkeypatch):
    """KEY_MISSING: --backend jev without TYPESAFE_API_KEY → backend is
    dropped, zero results (which a --gate would report as no evaluable)."""
    runner = importlib.import_module("scripts.jev_eval.runner")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    results = await runner.run_all(["jev"], limit=2)
    assert results == []


@pytest.mark.unit
def test_load_baseline_missing_file_returns_none(tmp_path, caplog):
    runner = importlib.import_module("scripts.jev_eval.runner")
    with caplog.at_level(logging.WARNING):
        assert runner.load_baseline(tmp_path / "missing.json") is None
    assert "baseline.json" in caplog.text


@pytest.mark.unit
def test_load_baseline_invalid_json_returns_none(tmp_path, caplog):
    runner = importlib.import_module("scripts.jev_eval.runner")
    path = tmp_path / "baseline.json"
    path.write_text("{not valid json")
    with caplog.at_level(logging.WARNING):
        assert runner.load_baseline(path) is None
    assert "baseline.json" in caplog.text


@pytest.mark.unit
def test_load_baseline_non_dict_json_returns_none(tmp_path, caplog):
    runner = importlib.import_module("scripts.jev_eval.runner")
    path = tmp_path / "baseline.json"
    path.write_text('["x"]')
    with caplog.at_level(logging.WARNING):
        assert runner.load_baseline(path) is None
    assert "malformed" in caplog.text


@pytest.mark.unit
def test_load_baseline_tasks_non_dict_returns_none(tmp_path, caplog):
    runner = importlib.import_module("scripts.jev_eval.runner")
    path = tmp_path / "baseline.json"
    path.write_text('{"model": "jev-1.13.0", "tasks": ["not", "a", "dict"]}')
    with caplog.at_level(logging.WARNING):
        assert runner.load_baseline(path) is None
    assert "malformed" in caplog.text


@pytest.mark.unit
def test_load_baseline_missing_tasks_key_is_ok(tmp_path):
    runner = importlib.import_module("scripts.jev_eval.runner")
    path = tmp_path / "baseline.json"
    path.write_text('{"model": "jev-1.13.0"}')
    assert runner.load_baseline(path) == {"model": "jev-1.13.0"}


@pytest.mark.unit
def test_write_summary_gate_section_present_and_absent(tmp_path, monkeypatch):
    runner = importlib.import_module("scripts.jev_eval.runner")
    monkeypatch.setattr(runner, "SUMMARY_FILE", tmp_path / "summary.md")
    results = _make_results({"SUBAGENT_ROUTING": 0.95})

    runner.write_summary(
        results,
        gate_report=[
            "PASS SUBAGENT_ROUTING [mock] 95.0% (floor 90%)",
            "GATE PASS — all evaluated tasks ≥ floor",
        ],
    )
    gated = (tmp_path / "summary.md").read_text()
    assert "## Gate" in gated
    assert "GATE PASS" in gated

    runner.write_summary(results)
    ungated = (tmp_path / "summary.md").read_text()
    assert "## Gate" not in ungated


@pytest.fixture
def hermetic_runner(tmp_path, monkeypatch):
    """Import the runner with all artifact paths redirected to tmp_path."""
    runner = importlib.import_module("scripts.jev_eval.runner")
    monkeypatch.setattr(runner, "RESULTS_FILE", tmp_path / "results.jsonl")
    monkeypatch.setattr(runner, "SUMMARY_FILE", tmp_path / "summary.md")
    monkeypatch.setattr(runner, "BASELINE_FILE", tmp_path / "baseline.json")
    return runner


@pytest.mark.unit
async def test_main_dry_run_writes_artifacts(hermetic_runner, tmp_path):
    code = await hermetic_runner.main(["--dry-run"])
    assert code == 0
    results_path = tmp_path / "results.jsonl"
    assert results_path.exists()
    assert (tmp_path / "summary.md").exists()
    lines = results_path.read_text().strip().splitlines()
    assert len(lines) == 80
    assert json.loads(lines[0])["backend"] == "mock"


@pytest.mark.unit
async def test_main_dry_run_gate_fails_on_mock_floor(hermetic_runner, tmp_path):
    code = await hermetic_runner.main(["--dry-run", "--gate"])
    assert code == 1
    summary = (tmp_path / "summary.md").read_text()
    assert "## Gate" in summary
    assert "GATE FAIL" in summary


@pytest.mark.unit
async def test_main_dry_run_gate_floor_zero_passes(hermetic_runner, tmp_path):
    code = await hermetic_runner.main(["--dry-run", "--gate", "--floor", "0.0"])
    assert code == 0
    assert "GATE PASS" in (tmp_path / "summary.md").read_text()
