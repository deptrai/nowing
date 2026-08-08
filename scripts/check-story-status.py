#!/usr/bin/env python3
"""Check that story status in sprint-status.yaml matches implementation state.

If a commit message matches "Story X-Y" pattern, the corresponding story
in sprint-status.yaml should NOT be in `ready-for-dev` or `backlog` status.

Usage:
    python scripts/check-story-status.py [--sprint-status PATH] [--commit-range RANGE]

Defaults:
    --sprint-status: _bmad-output/implementation-artifacts/sprint-status.yaml
    --commit-range: HEAD~1..HEAD (most recent commit)

Exit codes:
    0 — all stories referenced in commits have non-backlog status
    1 — one or more stories are stuck in ready-for-dev/backlog
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Matches "Story 3-15", "Story 3.15", "story(3-9)", etc.
_STORY_RE = re.compile(r"[Ss]tory[\s(]*(\d+)[.-](\d+)", re.IGNORECASE)


def parse_sprint_status(path: Path) -> dict[str, str]:
    """Parse sprint-status.yaml into {story_key: status}."""
    statuses: dict[str, str] = {}
    if not path.exists():
        return statuses
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("epic-") and re.match(r"\d+-\d+", line):
            # Format: "  3-15: done"
            match = re.match(r"(\d+-\d+[a-z]?):(\s*)(\S+)", line)
            if match:
                key = match.group(1)
                status = match.group(3).strip()
                statuses[key] = status
    return statuses


def get_commit_messages(commit_range: str) -> list[str]:
    """Get commit messages for a range."""
    result = subprocess.run(
        ["git", "log", "--format=%s%n%b", commit_range],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return result.stdout.split("\n---\n") if result.stdout else []


def extract_story_keys(messages: list[str]) -> set[str]:
    """Extract story keys (e.g. '3-15') from commit messages."""
    keys: set[str] = set()
    for msg in messages:
        for match in _STORY_RE.finditer(msg):
            epic, story = match.group(1), match.group(2)
            keys.add(f"{epic}-{story}")
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sprint-status",
        default="_bmad-output/implementation-artifacts/sprint-status.yaml",
        help="Path to sprint-status.yaml",
    )
    parser.add_argument(
        "--commit-range",
        default="HEAD~1..HEAD",
        help="Git commit range to check",
    )
    args = parser.parse_args()

    sprint_status = Path(args.sprint_status)
    if not sprint_status.exists():
        print(f"ERROR: sprint-status.yaml not found at {sprint_status}")
        return 1

    statuses = parse_sprint_status(sprint_status)
    messages = get_commit_messages(args.commit_range)
    story_keys = extract_story_keys(messages)

    if not story_keys:
        print("No story references found in commits.")
        return 0

    stuck: list[tuple[str, str]] = []
    for key in sorted(story_keys):
        status = statuses.get(key)
        if status is None:
            print(f"WARN: story {key} referenced in commit but not found in sprint-status.yaml")
            continue
        if status in ("ready-for-dev", "backlog"):
            stuck.append((key, status))
            print(f"FAIL: story {key} is '{status}' but has implementation commits")
        else:
            print(f"OK: story {key} is '{status}'")

    if stuck:
        print(f"\n{len(stuck)} story(s) stuck in pre-implementation status despite commits:")
        for key, status in stuck:
            print(f"  - {key}: {status}")
        print("\nUpdate sprint-status.yaml to reflect implementation state.")
        return 1

    print(f"\nAll {len(story_keys)} story(s) referenced in commits have correct status.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
