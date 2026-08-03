#!/usr/bin/env python3
"""CI messaging guard.

Fails the build if forbidden positioning phrases appear in public-facing
copy. Scans tracked files in nowing_web/, README translations, and public
install scripts. Build artifacts and dependency directories are ignored.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Public-facing paths to guard (fnmatch patterns relative to repo root).
SCANS = [
    "README*.md",
    "docs/**/*.md",
    "nowing_web/**/*.mdx",
    "nowing_web/**/*.tsx",
    "nowing_web/**/*.ts",
    "nowing_web/**/*.md",
    "nowing_web/**/*.json",
    "docker/scripts/install.sh",
    "docker/scripts/install.ps1",
]

# Forbidden positioning phrases (case-insensitive).
FORBIDDEN = [
    (
        'Product-level "open source" claim',
        re.compile(r"(?i)open[- ]?source"),
    ),
    (
        "NotebookLM alternative positioning",
        re.compile(r"(?i)notebooklm\s+alternatives?"),
    ),
    (
        "ChatGPT alternative positioning",
        re.compile(r"(?i)chatgpt\s+alternatives?"),
    ),
    (
        "Free ChatGPT alternative positioning",
        re.compile(r"(?i)free\s+chatgpt\s+alternatives?"),
    ),
    (
        "Free, open source alternative to ChatGPT",
        re.compile(
            r"(?i)free,?\s*open[- ]?source\s+alternative\s+to\s+chatgpt"
        ),
    ),
]

# Known false-positive lines that are not claims about Nowing as a product.
ALLOWED = [
    re.compile(r"(?i)claude\s+for\s+oss"),  # Anthropic's program name
]


def _list_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def _matches_scan(path: str) -> bool:
    for pattern in SCANS:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _is_allowed(line: str) -> bool:
    return any(pattern.search(line) for pattern in ALLOWED)


def _check_file(path: Path) -> list[str]:
    findings: list[str] = []
    rel = path.relative_to(ROOT).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings

    for line_no, line in enumerate(text.splitlines(), start=1):
        if _is_allowed(line):
            continue
        for name, pattern in FORBIDDEN:
            if pattern.search(line):
                findings.append(f"{rel}:{line_no}: {name}")
                findings.append(f"  {line.strip()}")
    return findings


def main() -> int:
    all_findings: list[str] = []
    for tracked in _list_tracked_files():
        if not _matches_scan(tracked):
            continue
        file_path = ROOT / tracked
        if not file_path.is_file():
            continue
        all_findings.extend(_check_file(file_path))

    if all_findings:
        print("Messaging guard FAILED: forbidden phrases found in public copy.")
        print()
        for item in all_findings:
            print(item)
        return 1

    print("Messaging guard PASSED: no forbidden positioning phrases found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
