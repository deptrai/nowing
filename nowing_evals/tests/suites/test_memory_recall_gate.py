"""ATDD red-phase scaffolds — Story 3.9 Memory Recall Eval-Gate.

Covers AC-6: the ship-gate enforces CONCRETE SM-10 thresholds (precision@5 >= X,
noise <= Y), rejects placeholders, and exits non-zero when the latest run fails
(RS-7 eval-gated launch).

RED PHASE: skipped tests; imports of not-yet-existing gate code live inside test
bodies so collection stays clean (only skips, 0 errors).
"""

from __future__ import annotations

import pytest

RED = "ATDD red-phase (Story 3.9): recall eval-gate not implemented yet"


def test_gate_passes_when_thresholds_met():
    """AC-6: precision@5 >= min AND noise <= max => pass."""
    from nowing_evals.core.gate import GateThresholds, evaluate_gate

    thresholds = GateThresholds(precision_at_5_min=0.80, noise_rate_max=0.20)
    metrics = {"precision_at_k": {"5": 0.82}, "noise_rate": 0.18}
    result = evaluate_gate(metrics, thresholds)
    assert result.passed is True


def test_gate_fails_when_precision_below_min():
    """AC-6: precision@5 under the floor blocks ship."""
    from nowing_evals.core.gate import GateThresholds, evaluate_gate

    thresholds = GateThresholds(precision_at_5_min=0.80, noise_rate_max=0.20)
    metrics = {"precision_at_k": {"5": 0.60}, "noise_rate": 0.40}
    result = evaluate_gate(metrics, thresholds)
    assert result.passed is False
    assert result.reasons  # explains which threshold failed


def test_gate_fails_when_noise_above_max():
    """AC-6: noise above the ceiling blocks ship even if precision passes."""
    from nowing_evals.core.gate import GateThresholds, evaluate_gate

    thresholds = GateThresholds(precision_at_5_min=0.50, noise_rate_max=0.20)
    metrics = {"precision_at_k": {"5": 0.55}, "noise_rate": 0.45}
    result = evaluate_gate(metrics, thresholds)
    assert result.passed is False


def test_thresholds_reject_placeholder_none():
    """AC-6: 'cấm placeholder' — None / missing thresholds are rejected."""
    from nowing_evals.core.gate import GateThresholds

    with pytest.raises((ValueError, TypeError)):
        GateThresholds(precision_at_5_min=None, noise_rate_max=None)


def test_thresholds_reject_out_of_range():
    """AC-6: thresholds must be concrete floats in [0, 1]."""
    from nowing_evals.core.gate import GateThresholds

    with pytest.raises(ValueError):
        GateThresholds(precision_at_5_min=1.5, noise_rate_max=0.2)


def test_default_gate_config_has_concrete_numbers():
    """AC-6: the committed gate config carries concrete floats (no '>=X%' placeholder)."""
    from nowing_evals.core.gate import load_gate_thresholds

    thresholds = load_gate_thresholds()  # loads suites/memory/recall/gate.yaml
    assert isinstance(thresholds.precision_at_5_min, float)
    assert isinstance(thresholds.noise_rate_max, float)
    assert 0.0 <= thresholds.precision_at_5_min <= 1.0
    assert 0.0 <= thresholds.noise_rate_max <= 1.0


def test_default_gate_config_has_concrete_recall_surface_params():
    """AC-6 (§6.3): the config also pins the RS-2 recall-surface params (top_k, min_similarity).

    ``precision_at_5_min``/``noise_rate_max`` alone don't fully specify the gate —
    without a concrete ``top_k``/``min_similarity`` the oracle used to score the
    run would itself be a placeholder. gate.yaml commits to top_k=5, min_similarity=0.30.
    """
    from nowing_evals.core.gate import load_gate_thresholds

    thresholds = load_gate_thresholds()
    assert isinstance(thresholds.top_k, int)
    assert thresholds.top_k <= 5  # RS-2 clamp
    assert isinstance(thresholds.min_similarity, float)
    assert 0.0 <= thresholds.min_similarity <= 1.0


def test_gate_cli_exits_nonzero_on_failure(tmp_env, capsys):
    """AC-6/RS-7: `python -m nowing_evals gate ...` returns non-zero when below threshold.

    Writes a genuinely failing run_artifact.json (precision@5 under the gate's own
    floor, noise above its ceiling — see gate.yaml: precision_at_5_min=0.80,
    noise_rate_max=0.20) into the suite's runs dir, then invokes the gate
    subcommand. Asserts the non-zero exit is tied to the threshold miss (not a
    "no artifact found" error) by checking the failure reason is surfaced.
    """
    import json

    from nowing_evals.core.cli import main
    from nowing_evals.core.config import load_config

    config = load_config()
    run_dir = config.suite_runs_dir("memory") / "2026-01-01T00-00-00Z" / "recall"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw.jsonl").write_text("", encoding="utf-8")
    (run_dir / "run_artifact.json").write_text(
        json.dumps(
            {
                "suite": "memory",
                "benchmark": "recall",
                "raw_path": "raw.jsonl",
                "metrics": {
                    "precision_at_k": {"1": 0.5, "5": 0.60},
                    "precision_at_5_ci": [0.45, 0.74],
                    "noise_rate": 0.40,
                    "recall_at_k": {"5": 0.55},
                    "mrr": 0.5,
                    "ndcg_at_10": 0.52,
                    "n_queries": 20,
                    "top_k": 5,
                    "min_similarity": 0.30,
                },
                "extra": {},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["gate", "--suite", "memory", "--benchmark", "recall"])
    assert exit_code != 0

    output = capsys.readouterr()
    combined = (output.out + output.err).lower()
    assert "precision" in combined or "noise" in combined
    assert "no artifact" not in combined and "not found" not in combined
