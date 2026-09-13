"""Section-level revision: identify affected sections and revise only those."""

import json
import logging
import re
from typing import Any

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import HumanMessage

from ._parsing import (
    _parse_sections,
    _stitch_sections,
    _strip_wrapping_code_fences,
)
from ._prompts import (
    _FORMATTING_RULES,
    _IDENTIFY_SECTIONS_PROMPT,
    _NEW_SECTION_PROMPT,
    _REVISE_SECTION_PROMPT,
)

# Keep the old ``tools.report`` logger name after the package split.
logger = logging.getLogger(__package__)


# ─── Async Generation Helpers ───────────────────────────────────────────────


async def _revise_with_sections(
    llm: Any,
    parent_content: str,
    user_instructions: str,
    source_content: str,
    topic: str,
    report_style: str,
) -> str | None:
    """Section-level revision: identify affected sections and revise only those.

    Unchanged sections are kept byte-for-byte identical.
    Returns the revised content, or None to trigger full-document revision fallback.
    """
    sections = _parse_sections(parent_content)
    if len(sections) < 2:
        logger.info(
            "[generate_report] Too few sections for section-level revision, using full revision"
        )
        return None

    sections_listing = ""
    for i, sec in enumerate(sections):
        heading = sec["heading"] or "(preamble — content before first heading)"
        body_preview = (
            sec["body"][:200] + "..." if len(sec["body"]) > 200 else sec["body"]
        )
        sections_listing += f"\n[{i}] {heading}\n    Preview: {body_preview}\n"

    # Step 1: Ask LLM which sections need modification
    identify_prompt = _IDENTIFY_SECTIONS_PROMPT.format(
        user_instructions=user_instructions,
        sections_listing=sections_listing,
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=identify_prompt)])
        raw = response.content
        if not raw or not isinstance(raw, str):
            return None

        raw = _strip_wrapping_code_fences(raw).strip()
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            raw = json_match.group(0)

        plan = json.loads(raw)
        modify_indices: list[int] = plan.get("modify", [])
        add_sections: list[dict[str, Any]] = plan.get("add", [])
        remove_indices: list[int] = plan.get("remove", [])
        reasoning = plan.get("reasoning", "")

        logger.info(
            f"[generate_report] Section-level revision plan: "
            f"modify={modify_indices}, add={len(add_sections)}, "
            f"remove={remove_indices}, reasoning={reasoning}"
        )
    except Exception:  # section revision planning failure; fall back to full revision
        logger.warning(
            "[generate_report] Failed to identify sections for revision, "
            "falling back to full revision",
            exc_info=True,
        )
        return None

    # If ALL sections need modification, full revision is more efficient and coherent
    if len(modify_indices) >= len(sections):
        logger.info(
            "[generate_report] All sections need modification, deferring to full revision"
        )
        return None

    total_ops = len(modify_indices) + len(add_sections)
    current_op = 0

    parts = []
    if modify_indices:
        parts.append(
            f"modifying {len(modify_indices)} section{'s' if len(modify_indices) > 1 else ''}"
        )
    if add_sections:
        parts.append(
            f"adding {len(add_sections)} new section{'s' if len(add_sections) > 1 else ''}"
        )
    if remove_indices:
        parts.append(
            f"removing {len(remove_indices)} section{'s' if len(remove_indices) > 1 else ''}"
        )
    plan_summary = ", ".join(parts) if parts else "no changes needed"

    dispatch_custom_event(
        "report_progress",
        {
            "phase": "revision_plan",
            "message": plan_summary.capitalize(),
            "modify_count": len(modify_indices),
            "add_count": len(add_sections),
            "remove_count": len(remove_indices),
            "total_ops": total_ops,
        },
    )

    # Step 2: Revise only the affected sections
    revised_sections = list(sections)  # shallow copy — unmodified sections stay as-is

    for idx in modify_indices:
        if idx < 0 or idx >= len(sections):
            continue

        current_op += 1
        sec = sections[idx]

        section_name = (
            re.sub(r"^#+\s*", "", sec["heading"]).strip()
            if sec["heading"]
            else "Preamble"
        )
        dispatch_custom_event(
            "report_progress",
            {
                "phase": "revising_section",
                "message": f"Revising: {section_name} ({current_op}/{total_ops})...",
            },
        )

        section_content = (
            f"{sec['heading']}\n\n{sec['body']}" if sec["heading"] else sec["body"]
        )

        context_parts = []
        if idx > 0:
            prev = sections[idx - 1]
            prev_preview = prev["body"][:300] + (
                "..." if len(prev["body"]) > 300 else ""
            )
            context_parts.append(
                f"**Previous section:** {prev['heading']}\n{prev_preview}"
            )
        if idx < len(sections) - 1:
            nxt = sections[idx + 1]
            nxt_preview = nxt["body"][:300] + ("..." if len(nxt["body"]) > 300 else "")
            context_parts.append(f"**Next section:** {nxt['heading']}\n{nxt_preview}")
        context = (
            "\n\n".join(context_parts) if context_parts else "(No surrounding sections)"
        )

        revise_prompt = _REVISE_SECTION_PROMPT.format(
            user_instructions=user_instructions,
            section_content=section_content,
            context_sections=context,
            source_content=source_content[:40000],
            formatting_rules=_FORMATTING_RULES,
        )

        resp = await llm.ainvoke([HumanMessage(content=revise_prompt)])
        revised_text = resp.content
        if revised_text and isinstance(revised_text, str):
            revised_text = _strip_wrapping_code_fences(revised_text).strip()
            revised_parsed = _parse_sections(revised_text)
            if revised_parsed:
                revised_sections[idx] = revised_parsed[0]
            else:
                revised_sections[idx] = {
                    "heading": sec["heading"],
                    "body": revised_text,
                }

        logger.info(f"[generate_report] Revised section [{idx}]: {sec['heading']}")

    # Step 3: Handle new section additions (insert in reverse order to preserve indices)
    for add_info in sorted(
        add_sections,
        key=lambda x: x.get("after_index", len(revised_sections) - 1),
        reverse=True,
    ):
        current_op += 1
        after_idx = add_info.get("after_index", len(revised_sections) - 1)
        heading = add_info.get("heading", "## New Section")
        description = add_info.get("description", "")

        plain_heading = re.sub(r"^#+\s*", "", heading).strip()
        dispatch_custom_event(
            "report_progress",
            {
                "phase": "adding_section",
                "message": f"Adding: {plain_heading} ({current_op}/{total_ops})...",
            },
        )

        ctx_parts = []
        if 0 <= after_idx < len(revised_sections):
            before_sec = revised_sections[after_idx]
            ctx_parts.append(
                f"**Section before:** {before_sec['heading']}\n{before_sec['body'][:300]}"
            )
        insert_idx = min(after_idx + 1, len(revised_sections))
        if insert_idx < len(revised_sections):
            after_sec = revised_sections[insert_idx]
            ctx_parts.append(
                f"**Section after:** {after_sec['heading']}\n{after_sec['body'][:300]}"
            )

        new_prompt = _NEW_SECTION_PROMPT.format(
            topic=topic,
            report_style=report_style,
            heading=heading,
            description=description,
            user_instructions=user_instructions,
            context_sections="\n\n".join(ctx_parts) if ctx_parts else "(None)",
            source_content=source_content[:30000],
            formatting_rules=_FORMATTING_RULES,
        )

        resp = await llm.ainvoke([HumanMessage(content=new_prompt)])
        new_content = resp.content
        if new_content and isinstance(new_content, str):
            new_content = _strip_wrapping_code_fences(new_content).strip()
            new_parsed = _parse_sections(new_content)
            if new_parsed:
                revised_sections.insert(insert_idx, new_parsed[0])
            else:
                revised_sections.insert(
                    insert_idx,
                    {
                        "heading": heading,
                        "body": new_content,
                    },
                )

        logger.info(
            f"[generate_report] Added new section after [{after_idx}]: {heading}"
        )

    # Step 4: Handle removals (reverse order to preserve indices)
    for idx in sorted(remove_indices, reverse=True):
        if 0 <= idx < len(revised_sections):
            logger.info(
                f"[generate_report] Removed section [{idx}]: "
                f"{revised_sections[idx]['heading']}"
            )
            revised_sections.pop(idx)

    return _stitch_sections(revised_sections)
