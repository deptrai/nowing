"""Inline Markdown report tool (package form of the former ``report.py``).

Re-exports every module-level name the old module exposed so that
``...deliverables.tools.report`` keeps working as an import/attribute target.
"""

from ._parsing import (
    _extract_metadata,
    _parse_sections,
    _render_kb_hits_for_report,
    _report_search_types,
    _stitch_sections,
    _strip_wrapping_code_fences,
)
from ._prompts import (
    _FORMATTING_RULES,
    _IDENTIFY_SECTIONS_PROMPT,
    _NEW_SECTION_PROMPT,
    _REPORT_FOOTER,
    _REPORT_PROMPT,
    _REVISE_SECTION_PROMPT,
    _REVISION_PROMPT,
)
from ._revise import _revise_with_sections
from .tool import create_generate_report_tool

__all__ = [
    # Names kept importable for attribute-compat with the old ``report.py``.
    "_FORMATTING_RULES",
    "_IDENTIFY_SECTIONS_PROMPT",
    "_NEW_SECTION_PROMPT",
    "_REPORT_FOOTER",
    "_REPORT_PROMPT",
    "_REVISE_SECTION_PROMPT",
    "_REVISION_PROMPT",
    "_extract_metadata",
    "_parse_sections",
    "_render_kb_hits_for_report",
    "_report_search_types",
    "_revise_with_sections",
    "_stitch_sections",
    "_strip_wrapping_code_fences",
    "create_generate_report_tool",
]
