"""Acceptance tests for the Story 3.9 MCP selfcheck + gate CI wiring (AC-7)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# nowing_evals/tests/suites/<file> -> repo root is parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
PR_GATE_WORKFLOW = WORKFLOWS / "memory-recall-gate.yml"
RELEASE_GATE_WORKFLOW = WORKFLOWS / "memory-recall-release-gate.yml"


def _workflow_files() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])


def _pr_gate_has_required_steps() -> bool:
    if not PR_GATE_WORKFLOW.is_file():
        return False
    text = PR_GATE_WORKFLOW.read_text(encoding="utf-8")
    return "test_memory_tools" in text and "gate --suite memory" in text


def _release_gate_has_d10_contract() -> bool:
    if not RELEASE_GATE_WORKFLOW.is_file():
        return False
    text = RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8")
    return "github.run_attempt" in text and "backend_build_id" in text


def _step_text(step: dict) -> str:
    return " ".join(str(step.get(key, "")) for key in ("run", "uses", "with", "name"))


def _step_is_gating(step: dict) -> bool:
    if step.get("continue-on-error") is True:
        return False
    run = str(step.get("run", ""))
    return "|| true" not in run and "|| exit 0" not in run


@pytest.mark.skipif(
    not _pr_gate_has_required_steps(),
    reason="PR gate workflow changes not in this chunk",
)
def test_ci_workflow_exists_for_recall_gate():
    """AC-7: a CI workflow drives the memory-recall gate."""
    assert PR_GATE_WORKFLOW.is_file()


@pytest.mark.skipif(
    not _pr_gate_has_required_steps(),
    reason="PR gate workflow changes not in this chunk",
)
def test_ci_workflow_runs_gate_and_mcp_selfcheck():
    """AC-7: the same job invokes the eval-gate AND the MCP selfcheck."""
    text = "\n".join(path.read_text(encoding="utf-8") for path in _workflow_files())
    assert "nowing_evals gate" in text or "gate --suite memory" in text
    assert "selfcheck" in text or "test_memory_tools" in text


@pytest.mark.skipif(
    not _pr_gate_has_required_steps(),
    reason="PR gate workflow changes not in this chunk",
)
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


@pytest.mark.skipif(
    not _pr_gate_has_required_steps(),
    reason="PR gate workflow changes not in this chunk",
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


@pytest.mark.skipif(
    not _pr_gate_has_required_steps(),
    reason="PR gate workflow changes not in this chunk",
)
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
    assert any("-ne 1" in run or "!= 1" in run or "exit 1" in run for run in gate_steps), (
        "the PR job must assert a non-zero gate exit, not merely run the gate"
    )


@pytest.mark.skipif(
    not _pr_gate_has_required_steps(),
    reason="PR gate workflow changes not in this chunk",
)
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


@pytest.mark.skipif(
    not _pr_gate_has_required_steps(),
    reason="PR gate workflow changes not in this chunk",
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


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
def test_release_gate_is_manual_only():
    """DEC-2: the live measurement mutates a real tenant, so never on a PR."""
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML parses a bare `on:` key as the boolean True.
    triggers = doc.get("on", doc.get(True))
    assert set(triggers) == {"workflow_dispatch"}, triggers


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
def test_release_gate_measures_before_it_judges():
    """The real ship gate must ingest, run and only then gate."""
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    runs = [str(step.get("run", "")) for job in doc["jobs"].values() for step in job["steps"]]
    joined = "\n".join(runs)
    assert "ingest memory recall" in joined
    assert "run memory recall" in joined
    assert "gate --suite memory" in joined
    ingest_at = next(i for i, r in enumerate(runs) if "ingest memory recall" in r)
    run_at = next(i for i, r in enumerate(runs) if "run memory recall" in r)
    gate_at = next(i for i, r in enumerate(runs) if "gate --suite memory" in r)
    assert ingest_at < run_at < gate_at


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
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


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
def test_release_gate_purge_condition_is_exact():
    """D10: the purge condition must survive the D10 changes byte-for-byte —
    a looser rewrite (e.g. dropping `inputs.purge`) would purge unconditionally."""
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    purge_steps = [
        step
        for job in doc["jobs"].values()
        for step in job["steps"]
        if "purge" in str(step.get("run", "")) and "gate --suite" not in str(step.get("run", ""))
    ]
    assert purge_steps, "expected a purge step"
    assert all(step.get("if") == "always() && inputs.purge" for step in purge_steps)


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
def test_release_gate_requires_a_nonblank_backend_build_id():
    """D10: the artifact must be tied to the exact backend it evaluated.

    ``workflow_dispatch`` declares the input required, but that alone doesn't
    stop an API dispatch from sending an empty string, so an explicit
    fail-fast validation step is required too.
    """
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    inputs = doc.get("on", doc.get(True))["workflow_dispatch"]["inputs"]
    assert inputs["backend_build_id"]["required"] is True

    runs = [str(step.get("run", "")) for job in doc["jobs"].values() for step in job["steps"]]
    validation_steps = [r for r in runs if "backend_build_id" in r and "exit 1" in r]
    assert validation_steps, "expected a step that fails fast on a blank backend_build_id"


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
def test_release_gate_passes_backend_build_id_into_the_run_command():
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    runs = [str(step.get("run", "")) for job in doc["jobs"].values() for step in job["steps"]]
    run_step = next(r for r in runs if "run memory recall" in r)
    assert "--backend-build-id" in run_step


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
def test_release_gate_isolates_eval_data_dir_per_run_attempt():
    """D10: the run's artifacts must live in a directory keyed to this exact
    run attempt, not the checked-out repo's static ``data/`` path — otherwise
    a re-run (or another concurrent workflow) can read or clobber them."""
    text = RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8")
    assert "EVAL_DATA_DIR" in text
    assert "github.run_id" in text
    assert "github.run_attempt" in text

    doc = yaml.safe_load(text)
    runs = [str(step.get("run", "")) for job in doc["jobs"].values() for step in job["steps"]]
    assert any(
        "EVAL_DATA_DIR=" in r and "github.run_id" in r and "github.run_attempt" in r for r in runs
    ), "expected a step computing EVAL_DATA_DIR from the run id + run attempt"


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
def test_release_gate_asserts_the_isolated_dir_starts_empty():
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    runs = [str(step.get("run", "")) for job in doc["jobs"].values() for step in job["steps"]]
    ingest_at = next(i for i, r in enumerate(runs) if "ingest memory recall" in r)
    assertion_steps = [i for i, r in enumerate(runs) if "EVAL_DATA_DIR" in r and "exit 1" in r]
    assert assertion_steps, "expected a step asserting EVAL_DATA_DIR starts absent/empty"
    assert any(i < ingest_at for i in assertion_steps), (
        "the empty-dir assertion must run before the corpus is seeded into it"
    )


@pytest.mark.skipif(
    not _release_gate_has_d10_contract(),
    reason="release-gate D10 workflow changes not in this chunk",
)
def test_release_gate_uploads_exactly_the_isolated_run_dir():
    """D10: upload the run-attempt-isolated dir, not the old hardcoded path —
    a stale hardcoded path would silently upload nothing (or another run's
    leftovers) once EVAL_DATA_DIR points elsewhere."""
    doc = yaml.safe_load(RELEASE_GATE_WORKFLOW.read_text(encoding="utf-8"))
    upload_steps = [
        step
        for job in doc["jobs"].values()
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact")
    ]
    assert upload_steps, "expected an upload-artifact step"
    for step in upload_steps:
        path = str(step["with"]["path"])
        assert "EVAL_DATA_DIR" in path
        assert path == "${{ env.EVAL_DATA_DIR }}/memory/runs/"


def test_mcp_selfcheck_declares_nowing_recall():
    """AC-7: the MCP selfcheck contract still lists nowing_recall."""
    selfcheck = REPO_ROOT / "nowing_mcp" / "mcp_server" / "selfcheck.py"
    assert selfcheck.exists()
    assert "nowing_recall" in selfcheck.read_text(encoding="utf-8")


def test_mcp_memory_tools_test_present():
    """AC-7: the MCP memory-tools contract test exists to be run in the pipeline."""
    assert (REPO_ROOT / "nowing_mcp" / "tests" / "test_memory_tools.py").exists()
