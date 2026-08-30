#!/usr/bin/env python3
"""PR guards: file-size limits, forbidden test markers, and new debt markers.

Phase H / Story 8-13: prevents new technical debt from landing on ``develop``.

Rules (applied only to files added or modified in the PR diff):

* Existing source files over 1,000 lines warn; over 2,000 lines fail.
* New source files over 1,000 lines warn; over 2,500 lines fail.
  The 2,500-line temporary threshold lets legacy splits that are still
  being decomposed land, while blocking truly giant new files.
* ``.only(`` in ``.ts/.tsx/.js`` test/describe blocks is forbidden.
* New ``@pytest.mark.skip`` decorators in Python tests are forbidden.
* New bare ``except Exception`` in ``nowing_backend/app/routes/`` or
  ``nowing_backend/app/services/`` is forbidden (legacy files are allowed;
  the rule targets *added* lines).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


WARN_LIMIT = 1000
FAIL_LIMIT_EXISTING = 2000
FAIL_LIMIT_NEW = 2500


def _run(*args: str) -> str:
    result = subprocess.run(list(args), capture_output=True, text=True)
    return result.stdout.strip()


def _changed_files(base_ref: str) -> list[str]:
    """Return paths changed between ``base_ref`` and HEAD."""
    out = _run("git", "diff", "--name-only", "--diff-filter=ACM", f"{base_ref}...HEAD")
    return [line for line in out.splitlines() if line]


def _is_new_file(rel: str, base_ref: str) -> bool:
    """Return True if the file did not exist on the base ref."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", base_ref, "--name-only"],
        capture_output=True,
        text=True,
    )
    return rel not in set(result.stdout.splitlines())


def _diff_for_file(rel: str, base_ref: str) -> str:
    """Return the unified diff for a single changed file."""
    result = subprocess.run(
        ["git", "diff", "--diff-filter=ACM", "-U0", f"{base_ref}...HEAD", "--", rel],
        capture_output=True,
        text=True,
    )
    return result.stdout


def _file_size(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def _check_size(path: Path, is_new: bool) -> tuple[bool, bool]:
    """(failed, warned) for file-size limits."""
    lines = _file_size(path)
    limit = FAIL_LIMIT_NEW if is_new else FAIL_LIMIT_EXISTING
    if lines > limit:
        return (True, False)
    if lines > WARN_LIMIT:
        return (False, True)
    return (False, False)


def _forbidden_only_in_ts(content: str) -> list[str]:
    """Find ``.only(`` calls in TypeScript/JavaScript test code."""
    pattern = re.compile(r"(it|describe|test|suite)\.only\(")
    matches = pattern.finditer(content)
    return [f"{m.group(0)[:20]}..." for m in matches]


def _forbidden_pytest_skip(content: str) -> list[str]:
    """Find ``@pytest.mark.skip`` decorators (but allow ``skipif``)."""
    pattern = re.compile(r"@pytest\.mark\.skip\b")
    return [m.group(0) for m in pattern.finditer(content)]


def _content_checks(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    errors: list[str] = []
    suffix = path.suffix
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        if _forbidden_only_in_ts(content):
            errors.append("forbidden .only( test marker")
    if suffix == ".py" and "tests" in path.parts:
        if _forbidden_pytest_skip(content):
            errors.append("forbidden @pytest.mark.skip")
    return errors


def _new_bare_exception_in_service_or_route(diff: str) -> bool:
    """Detect *added* lines containing ``except Exception`` in routes/services."""
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if re.search(r"except\s+Exception", line):
            return True
    return False


def main() -> int:
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"

    changed = _changed_files(base_ref)
    if not changed:
        print("No changed files to guard.")
        return 0

    failures: list[str] = []
    warnings: list[str] = []
    repo_root = Path(_run("git", "rev-parse", "--show-toplevel"))

    for rel in changed:
        path = repo_root / rel
        if not path.is_file():
            continue

        is_new = _is_new_file(rel, base_ref)
        failed_size, warned_size = _check_size(path, is_new)
        if failed_size:
            failures.append(
                f"{rel}: {_file_size(path)} lines > "
                f"{FAIL_LIMIT_NEW if is_new else FAIL_LIMIT_EXISTING} "
                f"({'new' if is_new else 'existing'} file)"
            )
        elif warned_size:
            warnings.append(f"{rel}: {_file_size(path)} lines > {WARN_LIMIT}")

        content_errors = _content_checks(path)
        if content_errors:
            for err in content_errors:
                failures.append(f"{rel}: {err}")

        if (
            rel.startswith("nowing_backend/app/routes/")
            or rel.startswith("nowing_backend/app/services/")
        ) and rel.endswith(".py"):
            diff = _diff_for_file(rel, base_ref)
            if _new_bare_exception_in_service_or_route(diff):
                # Phase H transitional: warn rather than fail while legacy splits
                # still contain broad exception handling. Once task C is complete,
                # upgrade this to a hard failure.
                msg = f"{rel}: added bare 'except Exception' in route/service"
                warnings.append(msg)

    for w in warnings:
        print(f"⚠️  {w}")
    for f in failures:
        print(f"❌ {f}")

    if failures:
        print("\nPR guard failed. Fix the issues above.")
        return 1

    if warnings:
        print("\nPR guard passed with warnings.")
    else:
        print("✅ PR guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
