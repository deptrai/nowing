#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Unit tests for init-sanctum.py — scaffolding, substitution, capability discovery.

Runs the real script against a temp project root and a temp skill bundle so the
test exercises the same code path First Breath does.

Run: uv run scripts/tests/test-init-sanctum.py
Exit codes: 0=all pass, 1=failures.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
INIT = SKILL_ROOT / "scripts" / "init-sanctum.py"
SKILL_NAME = "bmad-agent-devops"

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} {detail}")
        FAILURES.append(label)


def run_init(project_root: Path, skill_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INIT), str(project_root), str(skill_path)],
        capture_output=True,
        text=True,
    )


def make_project(root: Path) -> None:
    bmad = root / "_bmad"
    bmad.mkdir(parents=True)
    (bmad / "config.yaml").write_text(
        "user_name: TestOwner\ncommunication_language: Vietnamese\n", encoding="utf-8"
    )


def test_scaffolds_full_sanctum() -> None:
    print("test: scaffolds sanctum from the real skill bundle")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_project(root)
        result = run_init(root, SKILL_ROOT)
        check("exit 0", result.returncode == 0, result.stderr[-300:])

        sanctum = root / "_bmad" / "memory" / SKILL_NAME
        check("sanctum created", sanctum.is_dir())
        for name in [
            "INDEX.md",
            "PERSONA.md",
            "CREED.md",
            "BOND.md",
            "MEMORY.md",
            "CAPABILITIES.md",
        ]:
            check(f"{name} exists", (sanctum / name).is_file())
        check("capabilities/ dir", (sanctum / "capabilities").is_dir())
        check("sessions/ dir", (sanctum / "sessions").is_dir())
        check(
            "references copied into sanctum",
            (sanctum / "references" / "deploy.md").is_file(),
        )
        check(
            "canon copied (agent resolves standard from own root)",
            (sanctum / "references" / "prompt-quality-canon.md").is_file(),
        )


def test_substitutes_config_values() -> None:
    print("test: config values land in sanctum files")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_project(root)
        run_init(root, SKILL_ROOT)
        sanctum = root / "_bmad" / "memory" / SKILL_NAME

        bond = (sanctum / "BOND.md").read_text(encoding="utf-8")
        check("user_name substituted", "TestOwner" in bond)
        check("language substituted", "Vietnamese" in bond)
        check("no leftover {user_name}", "{user_name}" not in bond)

        persona = (sanctum / "PERSONA.md").read_text(encoding="utf-8")
        check("birth_date substituted", "{birth_date}" not in persona)


def test_discovers_all_eight_capabilities() -> None:
    print("test: CAPABILITIES.md discovers the 8 built-in capabilities")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_project(root)
        run_init(root, SKILL_ROOT)
        caps = (root / "_bmad" / "memory" / SKILL_NAME / "CAPABILITIES.md").read_text(
            encoding="utf-8"
        )
        for code in ["DP", "EV", "DM", "PG", "IN", "TS", "ST", "BK"]:
            check(f"capability [{code}] registered", f"[{code}]" in caps)
        check("Learned section (evolvable)", "## Learned" in caps)
        check(
            "guidance files not registered as capabilities",
            "memory-guidance" not in caps and "first-breath" not in caps,
        )


def test_idempotent() -> None:
    print("test: second run is a no-op, does not clobber sanctum")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_project(root)
        run_init(root, SKILL_ROOT)
        sanctum = root / "_bmad" / "memory" / SKILL_NAME
        marker = sanctum / "MEMORY.md"
        marker.write_text("# real memory the owner accrued\n", encoding="utf-8")

        result = run_init(root, SKILL_ROOT)
        check("exit 0", result.returncode == 0)
        check("reports already born", "already exists" in result.stdout)
        check(
            "owner memory preserved",
            "real memory the owner accrued" in marker.read_text(encoding="utf-8"),
        )


def test_missing_args_errors() -> None:
    print("test: missing args -> usage, exit 1")
    result = subprocess.run(
        [sys.executable, str(INIT)], capture_output=True, text=True
    )
    check("exit 1", result.returncode == 1, f"got {result.returncode}")
    check("usage printed", "Usage:" in result.stdout + result.stderr)


def main() -> int:
    for test in [
        test_scaffolds_full_sanctum,
        test_substitutes_config_values,
        test_discovers_all_eight_capabilities,
        test_idempotent,
        test_missing_args_errors,
    ]:
        test()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): {', '.join(FAILURES)}")
        return 1
    print("all init-sanctum.py tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
