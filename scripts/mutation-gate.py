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
from datetime import datetime, timezone
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
    """Find unit test files that likely cover the service."""
    tests_dir = backend / "tests" / "unit"
    if not tests_dir.exists():
        return ["tests/unit"]

    # A service may be scoped to a submodule (e.g. "memory/repository"); use the
    # package name for test discovery since submodule tests usually live under
    # the package's test files.
    search_key = service.split("/")[0] if "/" in service else service
    candidates = []
    import_pattern = f"app.services.{search_key}"

    for p in tests_dir.rglob("*.py"):
        if p.name == "conftest.py":
            continue
        name = p.stem
        # Filename match.
        if search_key in name or name in search_key.replace("_", ""):
            candidates.append(str(p.relative_to(backend)))
            continue
        # Content match: test file imports the service module.
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if import_pattern in text:
            candidates.append(str(p.relative_to(backend)))

    # Also search one directory level for service-named folders.
    for p in tests_dir.rglob("*"):
        if p.is_dir() and search_key in p.name:
            for test_file in p.glob("test_*.py"):
                rel = str(test_file.relative_to(backend))
                if rel not in candidates:
                    candidates.append(rel)

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


def generate_toml(backend: Path, service: str, project_root: Path, timeout: float) -> tuple[Path, Path]:
    """Write a cosmic-ray TOML config and session path.

    Config is placed in the backend directory so that relative module-path and
    test-command work the way cosmic-ray expects (it mutates code on disk in
    the directory it runs from).
    """
    out_dir = project_root / "_bmad-output" / "test-artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_service = service.replace("/", "-")

    config = backend / f"mutation-nowing-{safe_service}-{stamp}.toml"
    # Session path relative to backend so `cosmic-ray init/exec` can reach it.
    session = out_dir / f"mutation-nowing-{safe_service}-{stamp}.sqlite"

    module = backend / "app" / "services" / f"{service}.py"
    if not module.exists():
        # Try package directory.
        pkg = backend / "app" / "services" / service
        if pkg.is_dir():
            module = pkg
        else:
            pkg = backend / "app" / service
            if pkg.is_dir():
                module = pkg
            else:
                print(f"[warn] module for {service} not found at {module}; using file path anyway")
                module = backend / "app" / "services" / f"{service}.py"

    test_files = discover_tests(backend, service)
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


def run_cosmic_ray(backend: Path, config: Path, session: Path) -> None:
    """Run baseline, init, exec for a service."""
    for step in ("baseline", "init", "exec"):
        if step == "init":
            cmd = ["uv", "run", "--no-sync", "cosmic-ray", step, str(config), str(session)]
        elif step == "exec":
            cmd = ["uv", "run", "--no-sync", "cosmic-ray", step, str(config), str(session)]
        else:
            cmd = ["uv", "run", "--no-sync", "cosmic-ray", step, str(config)]

        print(f"[mutation] cosmic-ray {step} {config.name}")
        result = run(cmd, cwd=backend, timeout=7200)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f"cosmic-ray {step} failed for {config.name}")


def dump_session(backend: Path, session: Path) -> list[dict]:
    """Export session to JSONL and parse into records.

    cosmic-ray dump emits one JSON array per line: [mutation_meta, result].
    We merge the two dicts into a single record.
    """
    jsonl = session.with_suffix(".jsonl")
    result = run(["uv", "run", "--no-sync", "cosmic-ray", "dump", str(session)], cwd=backend, timeout=120)
    if result.returncode != 0:
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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
    args = parser.parse_args()

    os.environ["COSMIC_RAY"] = "1"

    project_root = Path(args.project_root).resolve()
    backend = project_root / args.backend_dir
    services = [s.strip() for s in args.services.split(",") if s.strip()]

    ensure_cosmic_ray(backend)

    all_results = []
    failed = False
    for service in services:
        print(f"\n[mutation] === {service} ===")
        config, session = generate_toml(backend, service, project_root, args.timeout)
        print(f"[mutation] config: {config}")
        print(f"[mutation] session: {session}")

        try:
            run_cosmic_ray(backend, config, session)
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
        "runAt": datetime.now(timezone.utc).isoformat(),
        "services": all_results,
    }
    summary_path = project_root / "_bmad-output" / "test-artifacts" / "mutation-nowing-summary-latest.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n[mutation] summary written to {summary_path}")
    print(f"[mutation] overall: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
