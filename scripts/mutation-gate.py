#!/usr/bin/env python3
"""Server-friendly mutation gate runner for Nowing backend.

Runs cosmic-ray per service, parses the session dump, triages surviving mutants
against the 6 anti-patterns, and exits non-zero if any P0 mutant survives or the
mutation score is below the threshold.

Usage:
    uv run --dir nowing_backend python ../scripts/mutation-gate.py \
        --services token_quota_service,token_tracking_service
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

# Services where Pattern 3/4/6 survivors are P0 blockers.
P0_SERVICES = {
    "token_tracking_service",
    "token_quota_service",
    "pricing_registration",
    "provider_registry",
    "model_resolver",
    "auth",
    "llm_service",
    "llm_router_service",
    "web_crawl_credit_service",
    "platform_scrape_credit_service",
    "multi_agent_chat",
    "kb_sync_service",
    "embedding_service",
    "reranker_service",
}


def classify_pattern(operator: str, diff: str, file: str) -> str:
    """Map a cosmic-ray operator to one of the 6 anti-patterns."""
    # cosmic-ray 8.x dumps operators with a "core/" prefix (e.g.
    # "core/ReplaceComparisonOperator_Gt_Eq"); strip it so the prefix
    # checks below actually match. Without this every mutant fell through
    # to the generic "2-over-mocking" fallback and P0 triage was useless.
    operator = operator.rsplit("/", 1)[-1]
    if operator.startswith("ReplaceComparisonOperator"):
        return "3-happy-path-only"
    if operator.startswith("ReplaceAndWithOr") or operator.startswith("ReplaceOrWithAnd"):
        return "3-happy-path-only"
    if operator.startswith("ReplaceTrueWithFalse") or operator.startswith("ReplaceFalseWithTrue"):
        return "3-happy-path-only"
    if operator == "AddNot":
        return "3-happy-path-only"
    if operator.startswith("ReplaceBreakWithContinue") or operator.startswith("ReplaceContinueWithBreak"):
        return "3-happy-path-only"
    if operator == "ZeroIterationForLoop":
        return "3-happy-path-only"
    if operator == "RemoveDecorator":
        return "3-happy-path-only"
    if operator.startswith("ReplaceBinaryOperator"):
        return "4-arithmetic-not-asserted"
    if operator.startswith("ReplaceUnaryOperator"):
        if "Not" in operator:
            return "3-happy-path-only"
        return "4-arithmetic-not-asserted"
    if operator == "NumberReplacer":
        # Boundary/threshold if the changed number lives in a comparison.
        if re.search(r"[<>!=]=?|==", diff):
            return "3-happy-path-only"
        return "4-arithmetic-not-asserted"
    if operator == "ExceptionReplacer":
        return "5-error-not-asserted"
    if operator.startswith("VariableReplacer") or operator.startswith("VariableInserter"):
        # Mirror tests often assert exact return objects/values.
        return "1-mirror-test"

    # SQL mock not executed is detected by SQL-related context in the diff.
    sql_tokens = ("select(", ".where(", ".filter(", ".execute(", "session.execute",
                  "db.execute", "query", "INSERT", "UPDATE", "DELETE")
    if any(tok.lower() in diff.lower() for tok in sql_tokens):
        return "6-sql-mock-not-executed"

    return "2-over-mocking"


def priority_for(pattern: str, service: str) -> str:
    """Return P0/P1/P2 priority for a survived mutant."""
    core = pattern.split("-", 1)[0]
    is_critical = service in P0_SERVICES or any(
        s in service for s in ("token", "quota", "credit", "auth", "pricing", "provider", "model_resolver")
    )
    if is_critical and core in {"3", "4", "6"}:
        return "P0"
    if core in {"1", "2", "5"} or core in {"3", "4"}:
        return "P1"
    return "P2"


def discover_tests(backend: Path, service: str) -> list[str]:
    """Find unit test files that likely cover the service.

    Prefer an exact ``tests/unit/<service>`` package directory when it exists,
    so deep modules like ``capabilities/vn_jobs/aggregate/executor`` do not
    match every ``test_*executor*.py`` file in the tree.
    """
    tests_dir = backend / "tests" / "unit"
    if not tests_dir.exists():
        return ["tests/unit"]

    segments = service.split("/")
    target_tail = Path(service)

    # For a module like "capabilities/vn_jobs/aggregate/executor" the tests
    # live in the parent package directory (``tests/unit/capabilities/vn_jobs/aggregate``).
    # For a package module the tests may live directly under the same subpath.
    search_key = segments[0]
    last_segment = segments[-1]
    candidate_dirs = [
        tests_dir / target_tail,  # exact subpath
        tests_dir / target_tail.parent,  # parent package of the last segment
    ]
    if len(segments) > 2:
        # Also try dropping the last two segments, e.g. ``services/scraper_chunks``.
        candidate_dirs.append(tests_dir / Path("/".join(segments[:-1])))
    for exact_dir in candidate_dirs:
        if exact_dir.is_dir():
            candidates = sorted(
                {
                    str(p.relative_to(backend))
                    for p in exact_dir.rglob("test_*.py")
                    if p.stem == f"test_{last_segment}" or p.stem.startswith(f"test_{last_segment}_")
                }
            )
            if candidates:
                return candidates[:20]

    # Fallback to the previous broad discovery heuristic.
    candidates: list[str] = []
    import_patterns = [f"app.services.{search_key}", f"app.capabilities.{search_key}"]

    for p in tests_dir.rglob("*.py"):
        if p.name == "conftest.py":
            continue
        name = p.stem
        # Filename match on any path segment.
        if (
            search_key in name
            or last_segment in name
            or name in search_key.replace("_", "")
        ):
            candidates.append(str(p.relative_to(backend)))
            continue
        # Content match: test file imports the service module.
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern in text for pattern in import_patterns):
            candidates.append(str(p.relative_to(backend)))

    for p in tests_dir.rglob("*"):
        if not p.is_dir():
            continue
        rel = p.relative_to(tests_dir)
        # Full subpath match, e.g. "capabilities/chainlens/research".
        if list(rel.parts) == list(target_tail.parts) or rel.name == last_segment:
            for test_file in p.rglob("test_*.py"):
                rel_test = str(test_file.relative_to(backend))
                if rel_test not in candidates:
                    candidates.append(rel_test)
            continue
        # First-segment match (e.g. "chainlens").
        if search_key in p.name:
            for test_file in p.glob("test_*.py"):
                rel_test = str(test_file.relative_to(backend))
                if rel_test not in candidates:
                    candidates.append(rel_test)

    if not candidates:
        return ["tests/unit"]
    return sorted(set(candidates))[:20]


def run(cmd: list[str] | str, *, cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a shell command and capture output."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=isinstance(cmd, str),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def ensure_cosmic_ray(backend: Path) -> None:
    """Fail fast with install instructions if cosmic-ray is missing."""
    result = run(["uv", "run", "--no-sync", "cosmic-ray", "--version"], cwd=backend, timeout=60)
    if result.returncode != 0:
        print("cosmic-ray not available. Install with:")
        print(f"  cd {backend} && uv add --dev cosmic-ray")
        print("or for one-off runs:")
        print(f"  cd {backend} && uv pip install cosmic-ray")
        sys.exit(2)


def generate_toml(backend: Path, service: str, project_root: Path, timeout: float, test_files_override: list[str] | None = None) -> tuple[Path, Path]:
    """Write a cosmic-ray TOML config and session path.

    Config is placed in the backend directory so that relative module-path and
    test-command work the way cosmic-ray expects (it mutates code on disk in
    the directory it runs from).
    """
    out_dir = project_root / "_bmad-output" / "test-artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_service = service.replace("/", "-")

    config = backend / f"mutation-nowing-{safe_service}-{stamp}.toml"
    # Session path relative to backend so `cosmic-ray init/exec` can reach it.
    session = out_dir / f"mutation-nowing-{safe_service}-{stamp}.sqlite"

    module = backend / "app" / "services" / f"{service}.py"
    if not module.exists():
        # Try package directory in services, then top-level app packages,
        # then capabilities package layout, then full app/ subpath.
        pkg = backend / "app" / "services" / service
        if pkg.is_dir():
            module = pkg
        else:
            pkg = backend / "app" / service
            if pkg.is_dir():
                module = pkg
            else:
                pkg = backend / "app" / "capabilities" / service
                if pkg.is_dir():
                    module = pkg
                else:
                    # Full subpath under app/ (e.g. "capabilities/core/access/web_citation").
                    full = backend / "app" / service
                    if full.with_suffix(".py").exists():
                        module = full.with_suffix(".py")
                    elif full.is_dir():
                        module = full
                    else:
                        print(f"[warn] module for {service} not found at {module}; using file path anyway")
                        module = backend / "app" / "services" / f"{service}.py"

    test_files = test_files_override or discover_tests(backend, service)
    test_cmd = f'bash -c "COSMIC_RAY=1 .venv/bin/python -m pytest {" ".join(test_files)} -m \\"unit or not integration\\" -x 2>&1"'

    toml = f"""[cosmic-ray]
module-path = "{module.relative_to(backend)}"
timeout = {timeout}
excluded-modules = ["tests", "migrations", "proprietary"]
test-command = '{test_cmd}'

[cosmic-ray.distributor]
name = "local"
"""
    config.write_text(toml)
    return config, session


def run_cosmic_ray(
    backend: Path,
    config: Path,
    session: Path,
    project_root: Path,
    scope_functions: str = "",
    skip_noise_operators: bool = False,
) -> None:
    """Run baseline, init, exec for a service, optionally scoping the session."""
    for step in ("baseline", "init", "exec"):
        if step == "init" or step == "exec":
            cmd = ["uv", "run", "--no-sync", "cosmic-ray", step, str(config), str(session)]
        else:
            cmd = ["uv", "run", "--no-sync", "cosmic-ray", step, str(config)]

        print(f"[mutation] cosmic-ray {step} {config.name}")
        result = run(cmd, cwd=backend, timeout=7200)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f"cosmic-ray {step} failed for {config.name}")

        # Skip mutants on lines marked with `# pragma: no mutate` after init so
        # non-runtime type annotations don't unfairly lower the score.
        if step == "init":
            print(f"[mutation] cr-filter-pragma {session.name}")
            run(
                ["uv", "run", "--no-sync", "cr-filter-pragma", str(session)],
                cwd=backend,
                timeout=60,
            )

            # Optionally scope the session to changed functions and/or skip
            # BinaryOperator/UnaryOperator noise from `from __future__ import annotations`.
            if scope_functions or skip_noise_operators:
                print(f"[mutation] scope-mutation-session {session.name}")
                scope_script = project_root / "scripts" / "scope_mutation_session.py"
                scope_cmd: list[str] = [
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    str(scope_script),
                    str(session),
                ]
                if scope_functions:
                    scope_cmd.extend(["--functions", scope_functions])
                if not skip_noise_operators:
                    scope_cmd.append("--keep-noise-operators")
                scope_result = run(scope_cmd, cwd=backend, timeout=120)
                if scope_result.returncode != 0:
                    print(scope_result.stdout)
                    print(scope_result.stderr, file=sys.stderr)
                    raise RuntimeError("scope_mutation_session failed")


def _dump_from_sqlite(session: Path) -> list[dict]:
    """Fallback parser for cosmic-ray sessions that contain SKIPPED work items.

    ``cosmic-ray dump`` can crash when a work result has no ``test_outcome``
    (e.g. after ``cr-filter-pragma``). We read the SQLite work DB directly and
    reconstruct the same record shape.
    """
    import sqlite3

    conn = sqlite3.connect(str(session))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            m.module_path,
            m.operator_name,
            m.operator_args,
            m.occurrence,
            m.start_pos_row,
            m.start_pos_col,
            m.end_pos_row,
            m.end_pos_col,
            m.definition_name,
            m.job_id,
            r.worker_outcome,
            r.test_outcome,
            r.diff
        FROM mutation_specs m
        LEFT JOIN work_results r ON m.job_id = r.job_id
        """
    )
    records = []
    for row in cur.fetchall():
        mutation = {
            "module_path": row["module_path"],
            "operator_name": row["operator_name"],
            "occurrence": row["occurrence"],
            "start_pos": [row["start_pos_row"], row["start_pos_col"]],
            "end_pos": [row["end_pos_row"], row["end_pos_col"]],
            "job_id": row["job_id"],
        }
        records.append(
            {
                "module_path": row["module_path"],
                "operator_name": row["operator_name"],
                "occurrence": row["occurrence"],
                "start_pos": [row["start_pos_row"], row["start_pos_col"]],
                "end_pos": [row["end_pos_row"], row["end_pos_col"]],
                "definition_name": row["definition_name"],
                "job_id": row["job_id"],
                "mutations": [mutation],
                "worker_outcome": (row["worker_outcome"] or "").lower(),
                "test_outcome": (row["test_outcome"] or "").lower() or None,
                "diff": row["diff"] or "",
            }
        )
    conn.close()
    return records


def dump_session(backend: Path, session: Path) -> list[dict]:
    """Export session to JSONL and parse into records.

    cosmic-ray dump emits one JSON array per line: [mutation_meta, result].
    We merge the two dicts into a single record. If ``dump`` fails because
    the session contains SKIPPED items (e.g. after ``cr-filter-pragma``),
    we fall back to reading the SQLite work DB directly.
    """
    jsonl = session.with_suffix(".jsonl")
    result = run(["uv", "run", "--no-sync", "cosmic-ray", "dump", str(session)], cwd=backend, timeout=120)
    if result.returncode != 0:
        if "'NoneType' object has no attribute 'value'" in result.stderr:
            return _dump_from_sqlite(session)
        raise RuntimeError(f"cosmic-ray dump failed: {result.stderr}")
    jsonl.write_text(result.stdout)

    records = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if isinstance(data, list) and len(data) == 2:
            merged = {**data[0], **data[1]}
            records.append(merged)
        elif isinstance(data, dict):
            records.append(data)
        else:
            raise RuntimeError(f"Unexpected dump line shape: {type(data)}")
    return records


def evaluate_service(service: str, records: list[dict]) -> dict:
    """Compute mutation score and triage surviving mutants."""
    # Records marked as SKIPPED (e.g. by cr-filter-pragma) are excluded from the
    # score so that equivalent/untestable mutants do not drag the score down.
    records = [
        r
        for r in records
        if r.get("worker_outcome") != "skipped" and r.get("test_outcome") is not None
    ]
    total = len(records)
    outcomes = Counter(r.get("test_outcome", "pending") for r in records)
    killed = outcomes.get("killed", 0)
    survived = outcomes.get("survived", 0)
    timeout = outcomes.get("timeout", 0)
    no_tests = outcomes.get("no_coverage", 0) + outcomes.get("incompetent", 0)

    denominator = total - timeout - no_tests
    score = (killed / max(denominator, 1)) * 100

    triage = {"P0": [], "P1": [], "P2": []}
    for r in records:
        if r.get("test_outcome") != "survived":
            continue
        mutations = r.get("mutations") or []
        if not mutations:
            continue
        mut = mutations[0]
        file_path = mut.get("module_path", "")
        start_pos = mut.get("start_pos") or [0, 0]
        operator = mut.get("operator_name", "")
        diff = r.get("diff", "")
        line = start_pos[0] if isinstance(start_pos, list) else start_pos.get("line", 0)
        col = start_pos[1] if isinstance(start_pos, list) else start_pos.get("col", 0)

        pattern = classify_pattern(operator, diff, service)
        priority = priority_for(pattern, service)
        triage[priority].append({
            "file": file_path,
            "line": line,
            "col": col,
            "operator": operator,
            "pattern": pattern,
            "diff": diff,
            "recommendedTest": f"Add a test that kills {operator} at {file_path}:{line} ({pattern}).",
        })

    p0 = len(triage["P0"])
    if total == 0:
        verdict = "PASS"
    elif score < 60 or p0 > 0:
        verdict = "FAIL"
    elif score < 80:
        verdict = "PASS_WITH_WARNINGS"
    else:
        verdict = "PASS"

    return {
        "service": service,
        "total": total,
        "killed": killed,
        "survived": survived,
        "timeout": timeout,
        "noTests": no_tests,
        "mutationScore": round(score, 2),
        "verdict": verdict,
        "triage": triage,
    }


def write_report(project_root: Path, service: str, result: dict) -> Path:
    """Write per-service mutation gate report."""
    out_dir = project_root / "_bmad-output" / "test-artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_service = service.replace("/", "-")
    path = out_dir / f"mutation-nowing-{safe_service}-{stamp}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Nowing mutation gate on one or more services")
    parser.add_argument("--services", required=True, help="Comma-separated service names")
    parser.add_argument("--project-root", default=".", help="Repo root (default: current directory)")
    parser.add_argument("--backend-dir", default="nowing_backend", help="Backend directory name")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-mutant timeout in seconds")
    parser.add_argument("--test-files", default="", help="Optional comma-separated focused test file paths (relative to backend). Overrides auto-discovery.")
    parser.add_argument("--functions", default="", help="Comma-separated function definition names to keep (scope all others as SKIPPED).")
    parser.add_argument("--skip-noise-operators", action="store_true", help="Skip BinaryOperator/UnaryOperator mutants (type-hint noise under `from __future__ import annotations`).")
    args = parser.parse_args()

    os.environ["COSMIC_RAY"] = "1"

    project_root = Path(args.project_root).resolve()
    backend = project_root / args.backend_dir
    services = [s.strip() for s in args.services.split(",") if s.strip()]

    ensure_cosmic_ray(backend)

    test_files_override = [t.strip() for t in args.test_files.split(",") if t.strip()] or None
    scope_functions = args.functions.strip()

    all_results = []
    failed = False
    for service in services:
        print(f"\n[mutation] === {service} ===")
        config, session = generate_toml(backend, service, project_root, args.timeout, test_files_override)
        print(f"[mutation] config: {config}")
        print(f"[mutation] session: {session}")

        try:
            run_cosmic_ray(
                backend,
                config,
                session,
                project_root,
                scope_functions=scope_functions,
                skip_noise_operators=args.skip_noise_operators,
            )
            records = dump_session(backend, session)
            result = evaluate_service(service, records)
            report_path = write_report(project_root, service, result)
            result["reportPath"] = str(report_path)
            result["sessionPath"] = str(session)
            result["configPath"] = str(config)
            # Keep the repo clean; config is reproducible from the report and session.
            config.unlink(missing_ok=True)
        except Exception as exc:
            import traceback
            result = {
                "service": service,
                "verdict": "FAIL",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            failed = True

        all_results.append(result)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result.get("verdict") == "FAIL":
            failed = True

    # Summary report.
    summary = {
        "dimension": "mutation",
        "runAt": datetime.now(UTC).isoformat(),
        "services": all_results,
    }
    summary_path = project_root / "_bmad-output" / "test-artifacts" / "mutation-nowing-summary-latest.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n[mutation] summary written to {summary_path}")
    print(f"[mutation] overall: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
