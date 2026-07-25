"""Acceptance tests for the Story 3.9 MCP selfcheck + gate CI wiring (AC-7)."""

from __future__ import annotations

from pathlib import Path

import yaml

# nowing_evals/tests/suites/<file> -> repo root is parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
PR_GATE_WORKFLOW = WORKFLOWS / "memory-recall-gate.yml"
RELEASE_GATE_WORKFLOW = WORKFLOWS / "memory-recall-release-gate.yml"


def _workflow_files() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])


def _step_text(step: dict) -> str:
    return " ".join(str(step.get(key, "")) for key in ("run", "uses", "with", "name"))


def _step_is_gating(step: dict) -> bool:
    if step.get("continue-on-error") is True:
        return False
    run = str(step.get("run", ""))
    return "|| true" not in run and "|| exit 0" not in run


def test_ci_workflow_exists_for_recall_gate():
    """AC-7: a CI workflow drives the memory-recall gate."""
    assert PR_GATE_WORKFLOW.is_file()


def test_ci_workflow_runs_gate_and_mcp_selfcheck():
    """AC-7: the same job invokes the eval-gate AND the MCP selfcheck."""
    text = "\n".join(path.read_text(encoding="utf-8") for path in _workflow_files())
    assert "nowing_evals gate" in text or "gate --suite memory" in text
    assert "selfcheck" in text or "test_memory_tools" in text


def test_ci_job_gates_exit_status_on_both_commands():
    """AC-7 (§9 risk): a gate that can't fail the build isn't a gate.

    It's not enough for the gate command and the MCP selfcheck to appear
    *somewhere* in the workflow text — they must live in the SAME job, as steps
    that are allowed to fail it. ``continue-on-error: true`` or a trailing
    ``|| true`` would satisfy a substring check while making the gate a no-op.
    """
    gate_and_selfcheck_job_found = False
    for wf_path in _workflow_files():
        doc = yaml.safe_load(wf_path.read_text(encoding="utf-8")) or {}
        for job in (doc.get("jobs") or {}).values():
            steps = job.get("steps") or []
            gate_steps = [
                s
                for s in steps
                if "gate" in _step_text(s).lower() and "memory" in _step_text(s).lower()
            ]
            selfcheck_steps = [
                s
                for s in steps
                if "selfcheck" in _step_text(s).lower()
                or "test_memory_tools" in _step_text(s).lower()
            ]
            if gate_steps and selfcheck_steps:
                gate_and_selfcheck_job_found = True
                assert all(_step_is_gating(s) for s in gate_steps), (
                    "gate step must not neutralize failure via continue-on-error/|| true"
                )
                assert all(_step_is_gating(s) for s in selfcheck_steps), (
                    "selfcheck step must not neutralize failure via continue-on-error/|| true"
                )

    assert gate_and_selfcheck_job_found, (
        "expected one job whose steps run both the memory recall gate and the MCP selfcheck"
    )


def test_pr_workflow_installs_the_test_extras_it_then_runs():
    """AC-7: the job must actually be able to run pytest.

    ``nowing_evals`` declares its test tooling under
    ``[project.optional-dependencies]``, not ``[dependency-groups]``, so
    ``uv sync --all-groups`` installs none of it and the very next step dies with
    ``No module named pytest`` — the job could never go green.
    """
    doc = yaml.safe_load(PR_GATE_WORKFLOW.read_text(encoding="utf-8"))
    evals_syncs = [
        str(step.get("run", ""))
        for job in doc["jobs"].values()
        for step in job["steps"]
        if str(step.get("working-directory", "")) == "nowing_evals"
        and "uv sync" in str(step.get("run", ""))
    ]
    assert evals_syncs, "expected a dependency sync for nowing_evals"
    for command in evals_syncs:
        assert "--all-extras" in command or "--extra dev" in command, command


def test_pr_workflow_proves_the_gate_blocks_a_failing_run():
    """DEC-2: the per-PR job must demonstrate the gate can FAIL.

    The previous wiring hand-wrote a run_artifact.json whose metrics were exactly
    equal to the thresholds and then gated on it — a constant PASS that proves
    nothing about recall and cannot fail. A negative fixture is what actually
    evidences a working gate.
    """
    doc = yaml.safe_load(PR_GATE_WORKFLOW.read_text(encoding="utf-8"))
    gate_steps = [
        str(step.get("run", ""))
        for job in doc["jobs"].values()
        for step in job["steps"]
        if "nowing_evals gate" in str(step.get("run", ""))
    ]
    assert gate_steps, "expected the PR job to invoke the gate"
    assert any(
        "-ne 1" in run or "!= 1" in run or "exit 1" in run for run in gate_steps
    ), "the PR job must assert a non-zero gate exit, not merely run the gate"


def test_pr_workflow_does_not_fabricate_a_passing_artifact():
    """A fixture that satisfies every threshold is theatre, not a gate."""
    text = PR_GATE_WORKFLOW.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    fixtures = [
        str(step.get("run", ""))
        for job in doc["jobs"].values()
        for step in job["steps"]
        if "run_artifact.json" in str(step.get("run", ""))
    ]
    for run in fixtures:
        assert "below threshold" in run.lower() or "-ne 1" in run, (
            "a committed CI fixture must be deliberately failing; a passing one makes "
            "the gate unable to fail"
        )


def test_pr_workflow_writes_fixtures_outside_the_real_data_dir():
    """A fixture must not squat in the run history.

    ``_collect_artifacts`` picks the latest run by lexicographic directory name,
    and a hand-made name like ``ci-fixture`` sorts after every ISO timestamp — so
    it would shadow every subsequent genuine run.
    """
    doc = yaml.safe_load(PR_GATE_WORKFLOW.read_text(encoding="utf-8"))
    fixture_steps = [
        str(step.get("run", ""))
        for job in doc["jobs"].values()
        for step in job["steps"]
        if "run_artifact.json" in str(step.get("run", ""))
    ]
    assert fixture_steps, "expected the PR job to write a gate fixture"
    for run in fixture_steps:
        # Checked against the executed script, not the file text: the surrounding
        # comments legitimately mention the old name to explain the trap.
        assert "ci-fixture" not in run
        assert "EVAL_DATA_DIR" in run, "the CI fixture must live in a temporary data dir"


def test_release_gate_is_manual_only():
    """DEC-2: the live measurement mutates a real tenant, so never on a PR."""
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML parses a bare `on:` key as the boolean True.
    triggers = doc.get("on", doc.get(True))
    assert set(triggers) == {"workflow_dispatch"}, triggers


def test_release_gate_measures_before_it_judges():
    """The real ship gate must ingest, run and only then gate."""
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    runs = [
        str(step.get("run", ""))
        for job in doc["jobs"].values()
        for step in job["steps"]
    ]
    joined = "\n".join(runs)
    assert "ingest memory recall" in joined
    assert "run memory recall" in joined
    assert "gate --suite memory" in joined
    ingest_at = next(i for i, r in enumerate(runs) if "ingest memory recall" in r)
    run_at = next(i for i, r in enumerate(runs) if "run memory recall" in r)
    gate_at = next(i for i, r in enumerate(runs) if "gate --suite memory" in r)
    assert ingest_at < run_at < gate_at


def test_release_gate_purges_even_when_the_gate_fails():
    """Fixture memories must not be left behind in a real tenant on failure."""
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    purge_steps = [
        step
        for job in doc["jobs"].values()
        for step in job["steps"]
        if "purge" in str(step.get("run", ""))
    ]
    assert purge_steps, "expected a purge step"
    assert any("always()" in str(step.get("if", "")) for step in purge_steps)


def test_mcp_selfcheck_declares_nowing_recall():
    """AC-7: the MCP selfcheck contract still lists nowing_recall."""
    selfcheck = REPO_ROOT / "nowing_mcp" / "mcp_server" / "selfcheck.py"
    assert selfcheck.exists()
    assert "nowing_recall" in selfcheck.read_text(encoding="utf-8")


def test_mcp_memory_tools_test_present():
    """AC-7: the MCP memory-tools contract test exists to be run in the pipeline."""
    assert (REPO_ROOT / "nowing_mcp" / "tests" / "test_memory_tools.py").exists()
