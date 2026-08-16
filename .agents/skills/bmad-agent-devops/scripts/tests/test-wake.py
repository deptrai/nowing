#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Unit tests for wake.py — mode routing and identity emission.

Run: uv run scripts/tests/test-wake.py
Exit codes: 0=all pass, 1=failures.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

WAKE = Path(__file__).resolve().parent.parent / "wake.py"
SKILL_NAME = "bmad-agent-devops"

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} {detail}")
        FAILURES.append(label)


def run_wake(project_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WAKE), str(project_root), *extra],
        capture_output=True,
        text=True,
    )


def make_sanctum(project_root: Path) -> Path:
    sanctum = project_root / "_bmad" / "memory" / SKILL_NAME
    sanctum.mkdir(parents=True)
    for name in [
        "INDEX.md",
        "PERSONA.md",
        "CREED.md",
        "BOND.md",
        "MEMORY.md",
        "CAPABILITIES.md",
    ]:
        (sanctum / name).write_text(f"# {name} marker\n", encoding="utf-8")
    return sanctum


def test_no_sanctum_routes_to_first_breath() -> None:
    print("test: no sanctum -> FIRST_BREATH")
    with tempfile.TemporaryDirectory() as tmp:
        result = run_wake(Path(tmp))
        check("exit 0", result.returncode == 0, f"got {result.returncode}")
        check("MODE: FIRST_BREATH", "MODE: FIRST_BREATH" in result.stdout)
        check("points at first-breath.md", "references/first-breath.md" in result.stdout)


def test_partial_sanctum_routes_to_first_breath() -> None:
    print("test: sanctum missing MEMORY.md -> FIRST_BREATH (not half-born waking)")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sanctum = make_sanctum(root)
        (sanctum / "MEMORY.md").unlink()
        result = run_wake(root)
        check("MODE: FIRST_BREATH", "MODE: FIRST_BREATH" in result.stdout)


def test_full_sanctum_routes_to_waking() -> None:
    print("test: full sanctum -> WAKING, all six files emitted in one pass")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_sanctum(root)
        result = run_wake(root)
        check("exit 0", result.returncode == 0, f"got {result.returncode}")
        check("MODE: WAKING", "MODE: WAKING" in result.stdout)
        for name in [
            "INDEX.md",
            "PERSONA.md",
            "CREED.md",
            "BOND.md",
            "MEMORY.md",
            "CAPABILITIES.md",
        ]:
            check(f"emitted {name}", f"===== {name} =====" in result.stdout)
        check("no PULSE without flag", "PULSE.md" not in result.stdout)


def test_pulse_flag_switches_mode() -> None:
    print("test: --pulse -> MODE: PULSE")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_sanctum(root)
        result = run_wake(root, "--pulse")
        check("MODE: PULSE", "MODE: PULSE" in result.stdout)


def test_missing_arg_errors() -> None:
    print("test: no project-root -> usage error, exit 2")
    result = subprocess.run(
        [sys.executable, str(WAKE)], capture_output=True, text=True
    )
    check("exit 2", result.returncode == 2, f"got {result.returncode}")
    check("usage on stderr", "Usage:" in result.stderr)


def main() -> int:
    for test in [
        test_no_sanctum_routes_to_first_breath,
        test_partial_sanctum_routes_to_first_breath,
        test_full_sanctum_routes_to_waking,
        test_pulse_flag_switches_mode,
        test_missing_arg_errors,
    ]:
        test()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): {', '.join(FAILURES)}")
        return 1
    print("all wake.py tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
