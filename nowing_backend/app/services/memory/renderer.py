"""Renderers from structured Memory rows back to markdown (Story 3.8, 3.14).

``render_memory_markdown`` is the legacy, unbounded renderer used by
``MemoryService.read_memory()``/the editor — kept byte-for-byte unchanged.
``render_bounded_memory_injection`` (D7) is a separate, byte-exact, 8.000
character-bounded renderer for the main-agent injection hot path; it only
reuses the date/heading helpers below, never the legacy grouping logic
(legacy groups globally by heading, D7 groups by consecutive run).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.db import MemoryType

#: D7 rule 9/10 — exact marker text embedded inside a truncated record/name.
_TRUNCATION_MARKER = "[...truncated...]"
_MEMORY_WARNING = (
    "<memory_warning>Memory results were truncated to fit the "
    "8000-character injection budget.</memory_warning>"
)
#: D7 rule 10 — a whole HTML entity reference, or else a single code point.
_ATOM_RE = re.compile(r"&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);|.", re.DOTALL)


class MemoryRenderError(Exception):
    """Raised when the D7 bounded renderer's own invariants are violated.

    ``reason`` feeds directly into D8 telemetry (``compose_error`` or
    ``budget_violation``) — this is never a normal user-facing outcome.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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


def _heading_for_type(mtype: Any) -> str:
    if mtype in (MemoryType.SEMANTIC.value, MemoryType.EPISODIC.value):
        return "Facts"
    return getattr(mtype, "value", str(mtype)).replace("_", " ").title()


def render_memory_markdown(memories: list[Any], scope: str = "team") -> str:
    """Render a list of memory rows as canonical markdown.

    Semantic and episodic memories land under ``## Facts``. Other types get
    their own heading using the normalized memory type. The output preserves
    the date-bullet contract expected by existing clients.
    """
    by_heading: dict[str, list[Any]] = {}
    for memory in memories:
        heading = _heading_for_type(getattr(memory, "type", None))
        by_heading.setdefault(heading, []).append(memory)

    sections: list[str] = []
    for heading, items in by_heading.items():
        lines = [f"## {heading}"]
        for memory in items:
            entry_date = _to_iso(getattr(memory, "created_at", None))
            lines.append(f"- {entry_date}: {getattr(memory, 'content', '')}")
        sections.append("\n".join(lines).strip())

    return "\n\n".join(sections).strip()


# --- D7: bounded, byte-exact injection renderer -----------------------------


@dataclass(frozen=True)
class _Record:
    heading: str
    entry_date: str
    escaped_lines: list[str]


def _atoms(escaped: str) -> list[str]:
    return _ATOM_RE.findall(escaped)


def _truncate_atoms(escaped: str, budget: int, marker: str = _TRUNCATION_MARKER) -> str | None:
    """Entity-aware head/tail truncation (D7 rules 10-11).

    Returns ``None`` when even ``marker + 1`` atom cannot fit in ``budget`` —
    callers treat that as "omit it" (rule 11).
    """
    if budget < len(marker) + 1:
        return None

    avail = budget - len(marker)
    atoms = _atoms(escaped)
    n = len(atoms)
    head_budget = -(-avail // 2)  # ceil
    tail_budget = avail // 2  # floor

    head_end = 0
    head_len = 0
    while head_end < n:
        atom_len = len(atoms[head_end])
        if head_len + atom_len > head_budget:
            break
        head_len += atom_len
        head_end += 1

    tail_start = n
    tail_len = 0
    while tail_start > head_end:
        atom_len = len(atoms[tail_start - 1])
        if tail_len + atom_len > tail_budget:
            break
        tail_len += atom_len
        tail_start -= 1

    # Spend any leftover capacity alternately on the next head atom, then the
    # next tail atom, until neither fits (rule 10's "spend remainder" pass).
    remaining = avail - head_len - tail_len
    while remaining > 0 and head_end < tail_start:
        advanced = False
        atom_len = len(atoms[head_end])
        if atom_len <= remaining:
            head_len += atom_len
            head_end += 1
            remaining -= atom_len
            advanced = True
        if remaining > 0 and tail_start > head_end:
            atom_len = len(atoms[tail_start - 1])
            if atom_len <= remaining:
                tail_len += atom_len
                tail_start -= 1
                remaining -= atom_len
                advanced = True
        if not advanced:
            break

    return "".join(atoms[:head_end]) + marker + "".join(atoms[tail_start:])


def _first_name_value(display_name: str | None) -> str | None:
    """D7 rule 2: first token of the normalized, escaped display name."""
    if not display_name:
        return None
    normalized = "\n".join(str(display_name).splitlines()).strip()
    if not normalized:
        return None
    parts = normalized.split()
    if not parts:
        return None
    return html.escape(parts[0], quote=True)


def _fit_name(name_value: str, remaining: int) -> str | None:
    if remaining <= 0:
        return None
    if len(name_value) <= remaining:
        return name_value
    return _truncate_atoms(name_value, remaining)


def _render_name_only(name_value: str, max_chars: int) -> str:
    tag_overhead = len("<user_name></user_name>")
    remaining = max_chars - tag_overhead
    if len(name_value) <= remaining:
        value = name_value
    else:
        truncated = _truncate_atoms(name_value, remaining)
        if truncated is None:
            raise MemoryRenderError("compose_error")
        value = truncated
    return f"<user_name>{value}</user_name>"


def _build_records(hits: list[Any]) -> list[_Record]:
    records: list[_Record] = []
    for hit in hits:
        memory = getattr(hit, "memory", hit)
        content = getattr(memory, "content", "")
        normalized = "\n".join(str(content).splitlines()).strip()
        if not normalized:
            continue
        escaped_lines = [html.escape(line, quote=True) for line in normalized.split("\n")]
        entry_date = _to_iso(getattr(memory, "created_at", None))
        heading = _heading_for_type(getattr(memory, "type", None))
        records.append(_Record(heading=heading, entry_date=entry_date, escaped_lines=escaped_lines))
    return records


def _record_lines(record: _Record) -> list[str]:
    lines = [f"- {record.entry_date}: {record.escaped_lines[0]}"]
    lines.extend(f"  {line}" for line in record.escaped_lines[1:])
    return lines


def _compose_body(records: list[_Record]) -> str:
    """D7 rule 5: consecutive-run heading grouping, no global grouping."""
    sections: list[str] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    for record in records:
        if record.heading != current_heading:
            if current_lines:
                sections.append("\n".join(current_lines))
            current_heading = record.heading
            current_lines = [f"## {record.heading}"]
        current_lines.extend(_record_lines(record))
    if current_lines:
        sections.append("\n".join(current_lines))
    return "\n\n".join(sections)


def _compose_truncated_body(records: list[_Record], *, tag: str, max_chars: int) -> str:
    """D7 rules 9-11: full records first, then one truncated record, then stop.

    ``records`` is bounded to at most 5 (D6), so a direct "does prefix N fit"
    scan is simpler and just as correct as an incremental accumulator.
    """
    fixed_overhead = (
        len(f"<{tag}>\n") + len(f"\n</{tag}>") + len("\n\n") + len(_MEMORY_WARNING)
    )
    budget = max_chars - fixed_overhead
    if budget <= 0:
        raise MemoryRenderError("compose_error")

    fitted: list[_Record] = []
    fitted_body = ""
    for i in range(len(records) + 1):
        candidate_body = _compose_body(records[:i])
        if len(candidate_body) <= budget:
            fitted = records[:i]
            fitted_body = candidate_body
        else:
            break

    if len(fitted) == len(records):
        # Everything fits after all — caller only reaches here when the full
        # untruncated memory block overflows, but stay defensive.
        return fitted_body

    next_record = records[len(fitted)]
    heading_open = not fitted or fitted[-1].heading != next_record.heading
    prefix = (f"## {next_record.heading}\n" if heading_open else "") + f"- {next_record.entry_date}: "
    if not fitted_body:
        separator = ""
    elif heading_open:
        separator = "\n\n"
    else:
        separator = "\n"

    remaining_for_record = budget - len(fitted_body) - len(separator) - len(prefix)
    content_blob = "\n  ".join(next_record.escaped_lines)
    truncated_content = _truncate_atoms(content_blob, remaining_for_record)

    if truncated_content is None:
        if not fitted_body:
            raise MemoryRenderError("compose_error")
        return fitted_body

    piece = prefix + truncated_content
    return f"{fitted_body}{separator}{piece}" if fitted_body else piece


def render_bounded_memory_injection(
    hits: list[Any],
    *,
    scope: str,
    display_name: str | None = None,
    max_chars: int = 8_000,
) -> str | None:
    """D7: byte-exact, 8.000-char-bounded main-agent injection renderer.

    Returns ``None`` when there is nothing to inject at all (zero results and
    either team scope or no usable private name).
    """
    if scope not in ("user", "team"):
        raise ValueError(f"unknown memory injection scope: {scope!r}")

    name_value = _first_name_value(display_name) if scope == "user" else None
    tag = "user_memory" if scope == "user" else "team_memory"

    records = _build_records(hits)
    body = _compose_body(records)

    if not body:
        if name_value is None:
            return None
        return _render_name_only(name_value, max_chars)

    memory_block = f"<{tag}>\n{body}\n</{tag}>"
    pieces = []
    if name_value is not None:
        pieces.append(f"<user_name>{name_value}</user_name>")
    pieces.append(memory_block)
    full_message = "\n\n".join(pieces)

    # Rule 7: full memory + optional full name fits — no marker/warning.
    if len(full_message) <= max_chars:
        return full_message

    # Rule 8: memory outranks the name — memory never truncates; the name
    # shrinks, then is omitted, before the memory itself is ever touched.
    if len(memory_block) <= max_chars:
        if name_value is None:
            return memory_block
        name_tag_overhead = len("<user_name></user_name>")
        remaining = max_chars - len(memory_block) - len("\n\n") - name_tag_overhead
        fitted_name = _fit_name(name_value, remaining)
        if fitted_name is None:
            return memory_block
        return f"<user_name>{fitted_name}</user_name>\n\n{memory_block}"

    # Rule 9: memory itself overflows — omit name, truncate body, add warning.
    truncated_body = _compose_truncated_body(records, tag=tag, max_chars=max_chars)
    result = f"<{tag}>\n{truncated_body}\n</{tag}>\n\n{_MEMORY_WARNING}"
    if len(result) > max_chars:
        raise MemoryRenderError("budget_violation")
    return result
