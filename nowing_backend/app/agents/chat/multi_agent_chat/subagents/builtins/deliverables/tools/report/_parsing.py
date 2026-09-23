"""Pure parsing/render helpers for the generate_report tool.

Section splitting/stitching, wrapping-fence stripping, report metadata
extraction, and KB-hit scoping/rendering. No DB or LLM access here.
"""

import re
from typing import Any


def _report_search_types(
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
) -> tuple[str, ...] | None:
    """Build the document-type scope for the shared KB search.

    ``None`` means "search every indexed type"; a tuple narrows the scope to the
    connectors/document types the workspace actually has.
    """
    types: set[str] = set()
    if available_document_types:
        types.update(available_document_types)
    if available_connectors:
        types.update(available_connectors)
    return tuple(sorted(types)) or None


def _render_kb_hits_for_report(hits: list[Any]) -> str:
    """Render KB hits as plain titled source text for the report writer.

    Citations are intentionally omitted from reports for now, so no ``[n]``
    labels or chunk ids are emitted — just titled document content for grounding.
    """
    from app.agents.chat.multi_agent_chat.shared.document_render import source_label

    blocks: list[str] = []
    for hit in hits:
        label = source_label(hit.document_type, hit.metadata)
        header = f"{hit.title} ({label})" if label else hit.title
        body = "\n\n".join(
            chunk.content.strip() for chunk in hit.chunks if chunk.content.strip()
        )
        if not body:
            continue
        blocks.append(f"## {header}\n\n{body}")
    return "\n\n".join(blocks)


# ─── Utility Functions ──────────────────────────────────────────────────────


def _strip_wrapping_code_fences(text: str) -> str:
    """Remove wrapping code fences that LLMs often add around Markdown output.

    Handles patterns like:
        ```markdown\\n...content...\\n```
        ````markdown\\n...content...\\n````
        ```md\\n...content...\\n```
        ```\\n...content...\\n```
        ```json\\n...content...\\n```
    Supports 3 or more backticks (LLMs escalate when content has triple-backtick blocks).
    """
    stripped = text.strip()
    # Match opening fence with 3+ backticks and optional language tag
    m = re.match(r"^(`{3,})(?:markdown|md|json)?\s*\n", stripped)
    if m:
        fence = m.group(1)  # e.g. "```" or "````"
        if stripped.endswith(fence):
            stripped = stripped[m.end() :]  # remove opening fence
            stripped = stripped[: -len(fence)].rstrip()  # remove closing fence
    return stripped


def _extract_metadata(content: str) -> dict[str, Any]:
    """Extract metadata from generated Markdown content."""
    headings = re.findall(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE)
    word_count = len(content.split())
    char_count = len(content)

    return {
        "status": "ready",
        "word_count": word_count,
        "char_count": char_count,
        "section_count": len(headings),
    }


def _parse_sections(content: str) -> list[dict[str, str]]:
    """Parse Markdown content into sections split by # and ## headings.

    Returns a list of dicts: [{"heading": "## Title", "body": "content..."}, ...]
    Content before the first heading is captured with heading="".
    ### and deeper headings are kept inside their parent ## section's body.
    """
    lines = content.split("\n")
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_body_lines: list[str] = []
    in_code_block = False

    for line in lines:
        # Track fences so headings inside code blocks aren't treated as splits.
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block

        is_section_heading = (
            not in_code_block
            and re.match(r"^#{1,2}\s+", line)
            and not re.match(r"^#{3,}\s+", line)
        )

        if is_section_heading:
            if current_heading or current_body_lines:
                sections.append(
                    {
                        "heading": current_heading,
                        "body": "\n".join(current_body_lines).strip(),
                    }
                )
            current_heading = line.strip()
            current_body_lines = []
        else:
            current_body_lines.append(line)

    if current_heading or current_body_lines:
        sections.append(
            {
                "heading": current_heading,
                "body": "\n".join(current_body_lines).strip(),
            }
        )

    return sections


def _stitch_sections(sections: list[dict[str, str]]) -> str:
    """Stitch parsed sections back into a single Markdown string."""
    parts = []
    for section in sections:
        if section["heading"]:
            parts.append(section["heading"])
        if section["body"]:
            parts.append(section["body"])
    return "\n\n".join(parts)
