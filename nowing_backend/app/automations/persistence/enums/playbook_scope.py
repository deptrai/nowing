"""Scope of a playbook: workspace-owned or system-wide."""

from __future__ import annotations

from enum import StrEnum


class PlaybookScope(StrEnum):
    WORKSPACE = "workspace"
    SYSTEM = "system"
