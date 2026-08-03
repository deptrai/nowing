"""Acceptance tests for Story 3.9's memory-recall eval gate (AC-6, RS-7)."""

from __future__ import annotations

import json

import pytest

from nowing_evals.core.gate import (
    GateConfigError,
    GateThresholds,
    evaluate_gate,
    load_gate_thresholds,
)
from nowing_evals.suites.memory.recall.runner import GATE_CONFIG_PATH


def _thresholds(**overrides) -> GateThresholds:
    base = {
        "recall_at_5_min": 0.90,
        "mrr_min": 0.70,
        "distractor_noise_rate_max": 0.10,
        "off_corpus_rate_max": 0.05,
        "min_queries": 30,
        "top_k": 5,
        "required_oracle_mode": "rank_only",
        "baseline_ratified": True,
        "baseline_source": "2026-07-25T00-00-00Z live run",
    }
    base.update(overrides)
    return GateThresholds(**base)


def _metrics(**overrides) -> dict:
    base = {
        "recall_at_k": {"1": 0.92, "5": 0.95},
        "mrr": 0.88,
        "distractor_noise_rate": 0.04,
        "off_corpus_rate": 0.0,
        "off_corpus_measured": True,
        "n_queries": 36,
        "n_failed_queries": 0,
        "primary_k": 5,
        "top_k": 5,
        "oracle_mode": "rank_only",
    }
    base.update(overrides)
    return base


def test_gate_passes_when_every_threshold_is_met():
    """AC-6: a genuinely good, ratified run clears the gate."""
    result = evaluate_gate(_metrics(), _thresholds())
    assert result.passed is True, result.reasons


def test_gate_fails_when_recall_below_min():
    """AC-6: not finding the memory blocks ship."""
    result = evaluate_gate(_metrics(recall_at_k={"5": 0.60}), _thresholds())
    assert result.passed is False
    assert any("recall" in reason for reason in result.reasons)


def test_gate_fails_when_mrr_below_min():
    """AC-6: present-but-badly-ranked is not remembering."""
    result = evaluate_gate(_metrics(mrr=0.20), _thresholds())
    assert result.passed is False
    assert any("MRR" in reason for reason in result.reasons)


def test_gate_fails_when_distractor_noise_above_max():
    """DEC-4: recalling labeled must-not-recall memories blocks ship."""
    result = evaluate_gate(_metrics(distractor_noise_rate=0.45), _thresholds())
    assert result.passed is False
    assert any("distractor" in reason for reason in result.reasons)


def test_gate_fails_when_workspace_is_polluted():
    """Results the labels cannot judge must count against the run.

    Without this, a workspace full of foreign memories that outrank the labeled
    one scores perfectly, because foreign items are simply absent from the qrels.
    """
    result = evaluate_gate(_metrics(off_corpus_rate=0.40), _thresholds())
    assert result.passed is False
    assert any("off-corpus" in reason for reason in result.reasons)


def test_gate_fails_when_off_corpus_was_never_measured():
    """"Clean" and "never looked" must not produce the same verdict."""
    result = evaluate_gate(
        _metrics(off_corpus_measured=False, off_corpus_rate=0.0), _thresholds()
    )
    assert result.passed is False
    assert any("off_corpus_rate was not measured" in reason for reason in result.reasons)


def test_gate_reports_every_miss_not_just_the_first():
    result = evaluate_gate(
        _metrics(recall_at_k={"5": 0.10}, mrr=0.05, distractor_noise_rate=0.9),
        _thresholds(),
    )
    assert result.passed is False
    assert len(result.reasons) >= 3


# --------------------------------------------------------------------------- #
# Evidence admissibility — a verdict on no evidence is not a verdict
# --------------------------------------------------------------------------- #


def test_gate_rejects_zero_query_run():
    """A zero-query run is "no evidence", not "no noise"."""
    result = evaluate_gate(
        _metrics(n_queries=0, recall_at_k={"5": 0.0}, mrr=0.0), _thresholds()
    )
    assert result.passed is False
    assert any("n_queries" in reason for reason in result.reasons)


def test_gate_rejects_run_below_minimum_sample_size():
    """`run --n 1` must not be able to clear a ship gate on one lucky query."""
    result = evaluate_gate(_metrics(n_queries=1), _thresholds())
    assert result.passed is False
    assert any("minimum sample size" in reason for reason in result.reasons)


def test_gate_rejects_partial_run():
    """A run where queries errored out cannot clear a ship gate."""
    result = evaluate_gate(_metrics(n_failed_queries=3), _thresholds())
    assert result.passed is False
    assert any("failed" in reason for reason in result.reasons)


def test_gate_rejects_artifact_scored_with_a_different_window():
    """RS-2: `run --top-k 1` must not pass a gate that pins top_k=5.

    Otherwise "precision@5" is really precision@1, trivially near 1.0, while the
    console prints the pinned values as though they had been applied.
    """
    result = evaluate_gate(_metrics(top_k=1), _thresholds(top_k=5))
    assert result.passed is False
    assert any("top_k" in reason for reason in result.reasons)


def test_gate_rejects_artifact_scored_under_a_different_oracle():
    """DEC-3: a run claiming a similarity threshold it could not apply is rejected."""
    result = evaluate_gate(_metrics(oracle_mode="score_threshold"), _thresholds())
    assert result.passed is False
    assert any("oracle_mode" in reason for reason in result.reasons)


@pytest.mark.parametrize("bad", [None, "0.9", True, float("nan"), 1.5, -0.1])
def test_gate_fails_closed_on_unusable_metric_values(bad):
    """A malformed metric must fail, never silently pass."""
    result = evaluate_gate(_metrics(mrr=bad), _thresholds())
    assert result.passed is False


# --------------------------------------------------------------------------- #
# Missing-metric reasons — every "is missing" branch, not just "out of range"
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("drop_key", "expected_substring"),
    [
        ("n_queries", "n_queries is missing"),
        ("top_k", "top_k is missing from the artifact"),
        ("oracle_mode", "oracle_mode is missing from the artifact"),
        ("distractor_noise_rate", "distractor_noise_rate is missing"),
        ("off_corpus_rate", "off_corpus_rate is missing"),
        ("recall_at_k", "recall@5 is missing"),
        ("mrr", "mrr is missing"),
    ],
)
def test_gate_reports_missing_metric_by_name(drop_key, expected_substring):
    """A metric absent from the artifact must be reported distinctly from
    a metric that is merely below/above threshold."""
    metrics = _metrics()
    del metrics[drop_key]
    result = evaluate_gate(metrics, _thresholds())
    assert result.passed is False
    assert any(expected_substring in reason for reason in result.reasons)


def test_gate_reports_non_integer_n_failed_queries_as_missing():
    """Unlike ``n_queries``, ``n_failed_queries`` defaults to 0 when absent —
    but a present, non-integer value must still be reported as unusable
    rather than silently coerced."""
    result = evaluate_gate(_metrics(n_failed_queries="none"), _thresholds())
    assert result.passed is False
    assert any("n_failed_queries is missing" in reason for reason in result.reasons)


def test_gate_reports_empty_oracle_mode_string_as_missing():
    """An empty string is not a usable oracle_mode, and must not compare
    equal to itself as if it were a legitimate value."""
    result = evaluate_gate(_metrics(oracle_mode=""), _thresholds())
    assert result.passed is False
    assert any("oracle_mode is missing" in reason for reason in result.reasons)


def test_gate_observed_dict_reports_none_for_missing_oracle_mode():
    """``observed['oracle_mode']`` must be ``None``, not the raw non-string value,
    so the CLI table renders 'missing' rather than crashing on ``:.3f``."""
    result = evaluate_gate(_metrics(oracle_mode=123), _thresholds())
    assert result.observed["oracle_mode"] is None


# --------------------------------------------------------------------------- #
# Threshold field validators not otherwise exercised
# --------------------------------------------------------------------------- #


def test_thresholds_reject_unsupported_oracle_mode():
    with pytest.raises(ValueError, match="rank_only, score_threshold"):
        _thresholds(required_oracle_mode="fuzzy_match")


def test_thresholds_reject_extra_unknown_fields():
    """``extra='forbid'``: a typo'd threshold key must not be silently ignored."""
    with pytest.raises(ValueError):
        GateThresholds(
            recall_at_5_min=0.9,
            mrr_min=0.7,
            distractor_noise_rate_max=0.1,
            off_corpus_rate_max=0.05,
            min_queries=30,
            recall_at_1_min=0.5,  # not a real field
        )


# --------------------------------------------------------------------------- #
# load_gate_thresholds — failure modes beyond "file missing" / "not a mapping"
# --------------------------------------------------------------------------- #


def test_gate_config_loader_rejects_malformed_yaml(tmp_path):
    """Broken YAML syntax must raise GateConfigError, not the raw yaml.YAMLError."""
    bad = tmp_path / "gate.yaml"
    bad.write_text("recall_at_5_min: [unclosed\n", encoding="utf-8")
    with pytest.raises(GateConfigError, match="not valid YAML"):
        load_gate_thresholds(bad)


def test_gate_config_loader_rejects_invalid_utf8(tmp_path):
    """A config file that isn't valid UTF-8 must raise GateConfigError."""
    bad = tmp_path / "gate.yaml"
    bad.write_bytes(b"recall_at_5_min: 0.9\xff\xfe")
    with pytest.raises(GateConfigError, match="not valid UTF-8"):
        load_gate_thresholds(bad)


def test_gate_config_loader_surfaces_field_validation_errors(tmp_path):
    """A structurally valid YAML mapping with an out-of-range value must still
    raise GateConfigError (wrapping the pydantic ValueError), not propagate a
    raw pydantic exception type the CLI does not catch."""
    bad = tmp_path / "gate.yaml"
    bad.write_text(
        "recall_at_5_min: 1.5\n"
        "mrr_min: 0.7\n"
        "distractor_noise_rate_max: 0.1\n"
        "off_corpus_rate_max: 0.05\n"
        "min_queries: 30\n",
        encoding="utf-8",
    )
    with pytest.raises(GateConfigError, match="Invalid gate configuration"):
        load_gate_thresholds(bad)


# --------------------------------------------------------------------------- #
# AC-6 — thresholds must be concrete AND ratified
# --------------------------------------------------------------------------- #


def test_thresholds_reject_placeholder_none():
    """AC-6 'cấm placeholder' — None / missing thresholds are rejected."""
    with pytest.raises((ValueError, TypeError)):
        GateThresholds(
            recall_at_5_min=None,
            mrr_min=None,
            distractor_noise_rate_max=None,
            off_corpus_rate_max=None,
            min_queries=30,
        )


def test_thresholds_reject_placeholder_string():
    with pytest.raises((ValueError, TypeError)):
        _thresholds(recall_at_5_min=">=90%")


def test_thresholds_reject_out_of_range():
    """AC-6: thresholds must be concrete floats in [0, 1]."""
    with pytest.raises(ValueError):
        _thresholds(recall_at_5_min=1.5)


def test_thresholds_reject_top_k_above_rs2_cap():
    with pytest.raises(ValueError):
        _thresholds(top_k=20)


def test_thresholds_reject_vacuous_configuration():
    """A config that accepts every conceivable run is not a gate.

    ``0.0`` floors with ``1.0`` ceilings are each individually "concrete floats
    in [0, 1]", so per-field validation alone lets a do-nothing gate through.
    """
    with pytest.raises(ValueError, match="vacuous"):
        _thresholds(
            recall_at_5_min=0.0,
            mrr_min=0.0,
            distractor_noise_rate_max=1.0,
            off_corpus_rate_max=1.0,
        )


def test_thresholds_reject_zero_minimum_sample_size():
    with pytest.raises(ValueError):
        _thresholds(min_queries=0)


def test_ratified_thresholds_require_evidence_pointer():
    """Claiming ratification without naming the baseline is not ratification."""
    with pytest.raises(ValueError, match="baseline_source"):
        _thresholds(baseline_ratified=True, baseline_source="   ")


def test_gate_fails_closed_while_baseline_is_unratified():
    """The core Story 3.9 decision, enforced in code rather than a checklist.

    ``epics.md`` requires the SM-10 numbers to be chosen *after* a measured
    baseline, and the PRD warns that setting thresholds before measuring repeats
    the NFR6 mistake. So perfect metrics against provisional thresholds must
    still fail: the gate cannot go green on invented figures.
    """
    result = evaluate_gate(_metrics(), _thresholds(baseline_ratified=False))
    assert result.passed is False
    assert any("not ratified" in reason for reason in result.reasons)


# --------------------------------------------------------------------------- #
# The committed configuration
# --------------------------------------------------------------------------- #


def test_committed_gate_config_loads_with_concrete_numbers():
    """AC-6: the committed config carries concrete floats (no '>=X%' placeholder)."""
    thresholds = load_gate_thresholds(GATE_CONFIG_PATH)
    for field in (
        "recall_at_5_min",
        "mrr_min",
        "distractor_noise_rate_max",
        "off_corpus_rate_max",
    ):
        value = getattr(thresholds, field)
        assert isinstance(value, float), field
        assert 0.0 <= value <= 1.0, field
    assert isinstance(thresholds.min_queries, int)
    assert thresholds.min_queries >= 1


def test_committed_gate_config_pins_the_recall_surface_contract():
    """AC-6 (§6.3): the config pins the RS-2 window and the oracle definition.

    Thresholds alone do not specify a gate — without a pinned ``top_k`` and
    oracle mode, the definition that produced the numbers would itself be
    unspecified.
    """
    thresholds = load_gate_thresholds(GATE_CONFIG_PATH)
    assert thresholds.top_k <= 5  # RS-2 clamp
    assert thresholds.required_oracle_mode in {"rank_only", "score_threshold"}


def test_committed_gate_config_is_ratified_with_baseline_source():
    """SM-10 baseline is ratified and names the measured run that produced it."""

    thresholds = load_gate_thresholds(GATE_CONFIG_PATH)
    assert thresholds.baseline_ratified is True
    assert thresholds.baseline_source.strip(), "ratified baseline must name its source"
    assert "2026-07-28T16-28-54Z" in thresholds.baseline_source


def test_committed_gate_config_is_real_yaml_with_provenance_comments():
    """The config is YAML, not JSON wearing a .yaml extension.

    It was previously parsed with ``json.loads``, so ordinary YAML — including
    the comments that record where the SM-10 numbers came from — was rejected.
    """
    text = GATE_CONFIG_PATH.read_text(encoding="utf-8")
    assert not text.lstrip().startswith("{")
    assert "#" in text, "the gate config must document where its numbers come from"
    assert "SM-10" in text


def test_gate_config_loader_reports_config_errors_distinctly():
    """A broken config must not look like a quality failure."""
    with pytest.raises(GateConfigError):
        load_gate_thresholds(GATE_CONFIG_PATH.with_name("does-not-exist.yaml"))


def test_gate_config_loader_rejects_non_mapping(tmp_path):
    bad = tmp_path / "gate.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(GateConfigError):
        load_gate_thresholds(bad)


# --------------------------------------------------------------------------- #
# CLI wiring
# --------------------------------------------------------------------------- #


def _write_artifact(config, metrics: dict, *, run_timestamp="2026-01-01T00-00-00Z") -> None:
    run_dir = config.suite_runs_dir("memory") / run_timestamp / "recall"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw.jsonl").write_text("", encoding="utf-8")
    (run_dir / "run_artifact.json").write_text(
        json.dumps(
            {
                "suite": "memory",
                "benchmark": "recall",
                "raw_path": "raw.jsonl",
                "metrics": metrics,
                "extra": {},
            }
        ),
        encoding="utf-8",
    )


def test_gate_cli_exits_nonzero_on_quality_failure(tmp_env, capsys):  # noqa: ARG001
    """AC-6/RS-7: `python -m nowing_evals gate ...` returns 1 below threshold.

    Asserts the non-zero exit is tied to the threshold miss rather than a
    "no artifact" or "bad config" error, by checking the surfaced reason.
    """
    from nowing_evals.core.cli import GATE_EXIT_QUALITY_FAIL, main
    from nowing_evals.core.config import load_config

    _write_artifact(
        load_config(),
        _metrics(recall_at_k={"1": 0.2, "5": 0.55}, mrr=0.31, distractor_noise_rate=0.42),
    )

    exit_code = main(["gate", "--suite", "memory", "--benchmark", "recall"])
    assert exit_code == GATE_EXIT_QUALITY_FAIL

    output = capsys.readouterr()
    combined = (output.out + output.err).lower()
    assert "gate fail" in combined
    assert "recall" in combined or "distractor" in combined
    assert "no run artifact found" not in combined


def test_gate_cli_exit_code_distinguishes_missing_artifact(tmp_env, capsys):  # noqa: ARG001
    """"Nothing to judge" must not be reported as "quality failure"."""
    from nowing_evals.core.cli import GATE_EXIT_NO_ARTIFACT, main

    exit_code = main(["gate", "--suite", "memory", "--benchmark", "recall"])
    assert exit_code == GATE_EXIT_NO_ARTIFACT
    combined = capsys.readouterr().out.lower()
    assert "no run artifact found" in combined


def test_gate_cli_exit_code_distinguishes_config_error(tmp_env, tmp_path, capsys):  # noqa: ARG001
    """A misconfigured gate must be distinguishable from a failing run in CI."""
    from nowing_evals.core.cli import GATE_EXIT_CONFIG_ERROR, main
    from nowing_evals.core.config import load_config

    _write_artifact(load_config(), _metrics())
    broken = tmp_path / "gate.yaml"
    broken.write_text("recall_at_5_min: not-a-number\n", encoding="utf-8")

    exit_code = main(
        ["gate", "--suite", "memory", "--benchmark", "recall", "--config", str(broken)]
    )
    assert exit_code == GATE_EXIT_CONFIG_ERROR
    _ = capsys.readouterr()


def test_gate_cli_rejects_unknown_benchmark(tmp_env, capsys):  # noqa: ARG001
    """A gate that does not consult the registry can bless a stale artifact.

    If the benchmark package fails to import, discovery logs a warning and moves
    on — the ``gate`` verb must not keep evaluating the last artifact it left
    behind and print PASS.
    """
    from nowing_evals.core.cli import GATE_EXIT_CONFIG_ERROR, main

    exit_code = main(["gate", "--suite", "memory", "--benchmark", "not-a-benchmark"])
    assert exit_code == GATE_EXIT_CONFIG_ERROR
    _ = capsys.readouterr()


def test_gate_cli_ignores_non_timestamp_run_directories(tmp_env, capsys):  # noqa: ARG001
    """A hand-made run directory must not win the "latest run" lookup.

    ``"ci-fixture"`` sorts after every ISO timestamp, so a fixture dropped into a
    real data dir would shadow every subsequent genuine run forever.
    """
    from nowing_evals.core.cli import GATE_EXIT_QUALITY_FAIL, main
    from nowing_evals.core.config import load_config

    config = load_config()
    _write_artifact(config, _metrics(recall_at_k={"5": 0.10}), run_timestamp="2026-01-01T00-00-00Z")
    _write_artifact(config, _metrics(), run_timestamp="ci-fixture")

    # The always-passing "ci-fixture" artifact must be skipped, leaving the real
    # (failing) run as the latest.
    assert main(["gate", "--suite", "memory", "--benchmark", "recall"]) == GATE_EXIT_QUALITY_FAIL
    _ = capsys.readouterr()


def test_gate_cli_refuses_to_fall_back_to_an_older_run(tmp_env):  # noqa: ARG001
    """A corrupt newest manifest must not silently promote a stale passing run."""
    from nowing_evals.core.cli import main
    from nowing_evals.core.config import load_config

    config = load_config()
    _write_artifact(config, _metrics(), run_timestamp="2026-01-01T00-00-00Z")
    later = config.suite_runs_dir("memory") / "2026-02-01T00-00-00Z" / "recall"
    later.mkdir(parents=True, exist_ok=True)
    (later / "run_artifact.json").write_text("{ this is not json", encoding="utf-8")

    # main() traps the error and returns 1 rather than reporting a verdict from
    # the older artifact.
    assert main(["gate", "--suite", "memory", "--benchmark", "recall"]) != 0
