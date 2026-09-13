"""Prompt templates and shared constants for the generate_report tool."""

# ─── Shared Formatting Rules ────────────────────────────────────────────────
# Reusable formatting instructions appended to section-level and review prompts.

_FORMATTING_RULES = """\
- IMPORTANT: Output raw Markdown directly. Do NOT wrap the entire output in a \
code fence (e.g. ```markdown, ````markdown, or any backtick fence). Individual \
code examples and diagrams inside the report should still use fenced code blocks, \
but the report itself must NOT be enclosed in one.
- Maintain proper Markdown formatting throughout.
- When including code examples, ALWAYS format them as proper fenced code blocks \
with the correct language identifier (e.g. ```java, ```python). Code inside code \
blocks MUST have proper line breaks and indentation — NEVER put multiple statements \
on a single line. Each statement, brace, and logical block must be on its own line \
with correct indentation.
- When including Mermaid diagrams, use ```mermaid fenced code blocks. Each Mermaid \
statement MUST be on its own line — NEVER use semicolons to join multiple statements \
on one line. For line breaks inside node labels, use <br> (NOT <br/>).
- When including mathematical formulas or equations, ALWAYS use LaTeX notation. \
NEVER use backtick code spans or Unicode symbols for math."""

# ─── Standard Report Footer ─────────────────────────────────────────────────
# Appended to every generated report after content generation.

_REPORT_FOOTER = "Powered by Nowing AI."

# ─── Prompt: Single-Shot Report Generation ───────────────────────────────────

_REPORT_PROMPT = """You are an expert report writer. Generate a comprehensive Markdown report.

**Topic:** {topic}
**Report Style:** {report_style}
{user_instructions_section}
{previous_version_section}

**Source Content:**
{source_content}

---

{length_instruction}

Write a well-structured Markdown report with a # title, executive summary, organized sections, and conclusion. Cite facts from the source content. Be thorough and professional.

{formatting_rules}
"""

# ─── Prompt: Full-Document Revision (fallback when section-level fails) ──────

_REVISION_PROMPT = """You are an expert report editor. Apply ONLY the requested changes — do NOT rewrite from scratch.

**Topic:** {topic}
**Report Style:** {report_style}
**Modification Instructions:** {user_instructions_section}

**Source Content (use if relevant):**
{source_content}

---

**EXISTING REPORT:**

{previous_report_content}

---

{length_instruction}

Preserve all structure and content not affected by the modification.

{formatting_rules}
"""

# ─── Prompt: Section-Level Revision — Identify Affected Sections ─────────────

_IDENTIFY_SECTIONS_PROMPT = """You are analyzing a Markdown report to determine which sections need modification based on the user's request.

**User's Modification Request:** {user_instructions}

**Report Sections (indexed starting at 0):**
{sections_listing}

---

Determine which sections need to be modified, added, or removed to fulfill the user's request.

Return ONLY a JSON object with these fields:
- "modify": Array of section indices (0-based) that need content changes
- "add": Array of objects like {{"after_index": 2, "heading": "## New Section Title", "description": "What this section should cover"}} for new sections to insert
- "remove": Array of section indices to remove entirely (use sparingly)
- "reasoning": A brief explanation of your decisions

Guidelines:
- If the change is GLOBAL (e.g., "change the tone", "make the whole report shorter", "translate to Spanish"), include ALL section indices in "modify".
- If the change is TARGETED (e.g., "expand the budget section", "fix the conclusion"), include ONLY the affected section indices.
- For "add a section about X", use the "add" field with the appropriate insertion point.
- Prefer modifying over removing+adding when possible.

Return ONLY valid JSON, no markdown fences:
"""

# ─── Prompt: Section-Level Revision — Revise a Single Section ────────────────

_REVISE_SECTION_PROMPT = """Revise ONLY this section based on the instructions. If the instructions don't apply, return it UNCHANGED.

**Modification Instructions:** {user_instructions}

**Current Section:**
{section_content}

**Context (surrounding sections — for coherence only, do NOT output them):**
{context_sections}

**Source Content:**
{source_content}

---

Keep the same heading and heading level. Preserve content not affected by the modification.
{formatting_rules}
"""

# ─── Prompt: New Section Generation (for section-level add) ─────────────────

_NEW_SECTION_PROMPT = """You are an expert report writer. Write a new section to be inserted into an existing report.

**Report Topic:** {topic}
**Report Style:** {report_style}
**Section Heading:** {heading}
**Section Goal:** {description}
**User Instructions:** {user_instructions}

**Surrounding Context:**
{context_sections}

**Source Content:**
{source_content}

---

**Rules:**
1. Write ONLY this section, starting with the heading "{heading}".
2. Ensure the section flows naturally with the surrounding context.
3. Be comprehensive — cover the topic described above.
{formatting_rules}

Write the new section now:
"""
