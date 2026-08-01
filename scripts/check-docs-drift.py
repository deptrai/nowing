#!/usr/bin/env python3
"""Docs-vs-code drift check for Story 8.10.

Fails the build if forbidden pre-pivot phrases reappear in README, docs,
landing/SEO copy, or install scripts.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files/globs to scan. Social-proof.tsx contains user-generated YouTube titles
# and is intentionally excluded.
SCANS = [
    "README.md",
    "README.*.md",
    "docs/**/*.md",
    "nowing_web/content/docs/**/*.mdx",
    "nowing_web/app/layout.tsx",
    "nowing_web/components/seo/**/*.tsx",
    "nowing_web/components/homepage/compare-table.tsx",
    "nowing_web/components/homepage/hero-section.tsx",
    "nowing_web/app/(home)/free/page.tsx",
    "docker/scripts/install.sh",
    "docker/scripts/install.ps1",
]

# Forbidden regex patterns with human-readable names.
FORBIDDEN = [
    ("NotebookLM positioning", re.compile(r"(?i)notebooklm")),
    ("AI file sorting (removed feature)", re.compile(r"(?i)ai\s*file\s*sorting")),
    (
        'Workspace "Admin" role (RBAC is Owner/Editor/Viewer)',
        re.compile(
            r"(?i)(?:owner|workspace)\s*[/,]\s*admin(?:istrator)?|admin(?:istrator)?\s*[/,]\s*(?:editor|viewer)|admin(?:istrator)?\s+(?:role|roles)"
        ),
    ),
    (
        'Old "for people" positioning',
        re.compile(r"(?i)for\s+people"),
    ),
    (
        "Open-source NotebookLM alternative phrase",
        re.compile(r"(?i)open[- ]?source\s+notebooklm\s+alternative"),
    ),
]

# Required phrases in README.md (case-insensitive).
REQUIRED = [
    (
        "README one-sentence promise (or close variation)",
        re.compile(r"(?i)open-source research memory for AI agents"),
    ),
    (
        "Long-term research memory framing",
        re.compile(r"(?i)long-term research memory"),
    ),
    (
        "Hosted deep-research engine framing",
        re.compile(r"(?i)hosted deep-research engine"),
    ),
]


SKIP_DIRS = {".git", "node_modules", ".venv", ".next", ".turbo", ".knowns"}


def _walk(root: Path) -> list[Path]:
    results: list[Path] = []
    for p in root.iterdir():
        if p.is_dir() and p.name in SKIP_DIRS:
            continue
        if p.is_dir():
            results.extend(_walk(p))
        else:
            results.append(p)
    return results


def _candidates(pattern: str) -> list[Path]:
    parts = pattern.split("/")
    if len(parts) == 1:
        # e.g. "README.md" or "README.*.md"
        return [p for p in ROOT.glob(pattern) if p.is_file()]
    root = ROOT / parts[0]
    if not root.exists():
        return []
    tail = "/".join(parts[1:])
    if "**" in tail:
        return _walk(root)
    return [p for p in root.rglob(tail) if p.is_file()]


def matching_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in SCANS:
        for p in _candidates(pattern):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(
                rel, pattern.replace("**", "*")
            ):
                files.add(p)
    return sorted(files)


def check_file(path: Path) -> list[str]:
    findings: list[str] = []
    rel = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        for name, pattern in FORBIDDEN:
            if pattern.search(line):
                findings.append(f"{rel}:{line_no}: {name}")
                findings.append(f"  {line.strip()}")
    return findings


def check_readme_required(path: Path) -> list[str]:
    findings: list[str] = []
    if not path.exists():
        return findings
    text = path.read_text(encoding="utf-8")
    for name, pattern in REQUIRED:
        if not pattern.search(text):
            findings.append(f"README.md: missing required phrase: {name}")
    return findings


def main() -> int:
    all_files = matching_files()
    findings: list[str] = []
    for f in all_files:
        findings.extend(check_file(f))
    findings.extend(check_readme_required(ROOT / "README.md"))

    if findings:
        print("Docs-drift check FAILED: forbidden or missing phrases found.")
        print()
        for item in findings:
            print(item)
        return 1

    print("Docs-drift check PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
