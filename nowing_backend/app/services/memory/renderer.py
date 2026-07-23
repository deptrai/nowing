"""Renderer from structured Memory rows back to legacy markdown."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.db import MemoryType


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            return value[:10]
    return date.today().isoformat()


def render_memory_markdown(memories: list[Any], scope: str = "team") -> str:
    """Render a list of memory rows as canonical markdown.

    Semantic and episodic memories land under ``## Facts``. Other types get
    their own heading using the normalized memory type. The output preserves
    the date-bullet contract expected by existing clients.
    """
    by_heading: dict[str, list[Any]] = {}
    for memory in memories:
        mtype = getattr(memory, "type", None)
        if mtype in (MemoryType.SEMANTIC.value, MemoryType.EPISODIC.value):
            heading = "Facts"
        else:
            heading = getattr(mtype, "value", str(mtype)).replace("_", " ").title()
        by_heading.setdefault(heading, []).append(memory)

    sections: list[str] = []
    for heading, items in by_heading.items():
        lines = [f"## {heading}"]
        for memory in items:
            entry_date = _to_iso(getattr(memory, "created_at", None))
            lines.append(f"- {entry_date}: {getattr(memory, 'content', '')}")
        sections.append("\n".join(lines).strip())

    return "\n\n".join(sections).strip()
