"""ATDD red-phase scaffolds — Story 3.9 Memory Recall Eval-Gate.

Covers AC-7 (AR-8): the MCP tool-contract selfcheck runs in the SAME CI pipeline as
the recall gate. A recall gate is meaningless if ``nowing_recall`` is not even
exposed, so the pipeline must fail if the MCP selfcheck fails.

These assertions are filesystem/text based (no cross-package import) so they stay
runnable from the evals test tree. RED PHASE: skipped until the CI job is wired.
"""

from __future__ import annotations

from pathlib import Path

RED = "ATDD red-phase (Story 3.9): recall-gate CI job + MCP selfcheck wiring not present yet"

# nowing_evals/tests/suites/<file> -> repo root is parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_ci_workflow_exists_for_recall_gate():
    """AC-7: a CI workflow drives the memory-recall gate."""
    workflows = REPO_ROOT / ".github" / "workflows"
    candidates = list(workflows.glob("*memory-recall*")) + list(workflows.glob("*recall-gate*"))
    assert candidates, "expected a memory-recall gate workflow under .github/workflows/"


def test_ci_workflow_runs_gate_and_mcp_selfcheck():
    """AC-7: the same job invokes the eval-gate AND the MCP selfcheck."""
    workflows = REPO_ROOT / ".github" / "workflows"
    text = "\n".join(p.read_text(encoding="utf-8") for p in workflows.glob("*.yml"))
    text += "\n".join(p.read_text(encoding="utf-8") for p in workflows.glob("*.yaml"))
    assert "nowing_evals gate" in text or "gate --suite memory" in text
    assert "selfcheck" in text or "test_memory_tools" in text


def test_ci_job_gates_exit_status_on_both_commands():
    """AC-7 (§9 risk): a gate that can't fail the build isn't a gate.

    It's not enough for the gate command and the MCP selfcheck to appear
    *somewhere* in the workflow text (the previous test's weak substring
    check) — they must live in the SAME job, as steps that are allowed to
    fail the job. A step wired with ``continue-on-error: true`` or a shell
    trick like ``... || true`` would satisfy the substring check while
    making the "gate" a no-op that can never block a ship.
    """
    import yaml

    workflows = REPO_ROOT / ".github" / "workflows"
    workflow_files = list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml"))
    assert workflow_files, "expected at least one workflow file"

    def _step_text(step: dict) -> str:
        return " ".join(str(step.get(key, "")) for key in ("run", "uses", "with", "name"))

    def _step_is_gating(step: dict) -> bool:
        if step.get("continue-on-error") is True:
            return False
        run = str(step.get("run", ""))
        return "|| true" not in run and "|| exit 0" not in run

    gate_and_selfcheck_job_found = False
    for wf_path in workflow_files:
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


def test_mcp_selfcheck_declares_nowing_recall():
    """AC-7: the MCP selfcheck contract still lists nowing_recall (the recalled tool)."""
    selfcheck = REPO_ROOT / "nowing_mcp" / "mcp_server" / "selfcheck.py"
    assert selfcheck.exists()
    assert "nowing_recall" in selfcheck.read_text(encoding="utf-8")


def test_mcp_memory_tools_test_present():
    """AC-7: the MCP memory-tools contract test exists to be run in the pipeline."""
    test_file = REPO_ROOT / "nowing_mcp" / "tests" / "test_memory_tools.py"
    assert test_file.exists()
