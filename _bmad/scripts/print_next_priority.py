#!/usr/bin/env python3
"""Print the next sprint item by dependency priority.

Reads _bmad-output/planning-artifacts/sprint-priority.md (ordered list)
and _bmad-output/implementation-artifacts/sprint-status.yaml (status),
then prints the first item that is not `done`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRIORITY_FILE = PROJECT_ROOT / "_bmad-output" / "planning-artifacts" / "sprint-priority.md"
STATUS_FILE = PROJECT_ROOT / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"


def load_statuses() -> dict[str, str]:
    data = yaml.safe_load(STATUS_FILE.read_text()) or {}
    return data.get("development_status", {})


def get_status_for_key(key: str, statuses: dict[str, str]) -> str | None:
    if key in statuses:
        return statuses[key]
    # Try prefix matching, e.g. '25-4' matches '25-4-realtime-llm-token-cost...'
    for k, v in statuses.items():
        if k == key or k.startswith(f"{key}-") or (key.endswith("-followup") and k.startswith(key)):
            return v
    return None

def load_priority_keys() -> list[str]:
    text = PRIORITY_FILE.read_text()
    keys: list[str] = []
    for line in text.splitlines():
        # Match ordered list items with backtick story keys, e.g.
        # "1. `td-2` — ..." or "- `td-2` — ..."
        m = re.search(r"^[\d\-]+\.\s+`([^`]+)`", line)
        if not m:
            m = re.search(r"^\s*-\s+`([^`]+)`", line)
        if m:
            keys.append(m.group(1))
    return keys


def main() -> int:
    statuses = load_statuses()
    priority_keys = load_priority_keys()

    next_item: str | None = None
    upcoming: list[str] = []
    for key in priority_keys:
        status = get_status_for_key(key, statuses)
        if status == "done":
            continue
        if next_item is None:
            next_item = key
        else:
            upcoming.append(f"{key} ({status or 'unknown'})")
        if len(upcoming) >= 2:
            break

    if next_item:
        status = get_status_for_key(next_item, statuses) or "unknown"
        print(f"Next by dependency priority: `{next_item}` ({status})")
        if upcoming:
            print(f"Upcoming: {', '.join(upcoming)}")
    else:
        print("No unfinished prioritized item found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
