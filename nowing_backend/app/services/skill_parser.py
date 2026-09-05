"""Parser for .skill.md files with YAML frontmatter and Markdown body."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

import yaml


class SkillParseError(Exception):
    """Raised when parsing or validating a .skill.md file fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class SkillDefinition:
    name: str
    slug: str
    trigger_pattern: str
    content_markdown: str
    description: str | None = None
    skill_type: Literal["prompt", "workflow"] = "prompt"
    parameters_schema: dict[str, Any] = field(default_factory=dict)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9-_]+", "-", text.lower()).strip("-_")
    return slug or "skill"


class SkillParser:
    """Parses .skill.md content into a structured SkillDefinition."""

    # Matches frontmatter enclosed between two `---` lines at the start of the string.
    # Tolerates a leading UTF-8 BOM and optional whitespace before the opening fence.
    FRONTMATTER_PATTERN = re.compile(
        r"^(?:﻿\s*)?---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL
    )

    @classmethod
    def parse(cls, content: str) -> SkillDefinition:
        """Parse raw .skill.md content.

        Raises:
            SkillParseError: If frontmatter is missing, invalid YAML, or missing required fields.
        """
        if not content or not content.strip():
            raise SkillParseError("File content is empty")

        # Strip leading whitespace and optional BOM only for fence matching.
        match = cls.FRONTMATTER_PATTERN.match(content.lstrip("﻿").lstrip())
        if not match:
            raise SkillParseError("Missing frontmatter delimiters (must start with '---')")

        frontmatter_raw, body = match.group(1), match.group(2).strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_raw)
        except Exception as exc:
            raise SkillParseError(f"Invalid YAML frontmatter: {exc}") from exc

        if not isinstance(frontmatter, dict):
            raise SkillParseError("Frontmatter must be a YAML dictionary")

        # Required fields
        name = frontmatter.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            raise SkillParseError("Missing required field: 'name'")
        name = name.strip()

        # Trigger pattern can be named 'trigger' or 'trigger_pattern'
        trigger = frontmatter.get("trigger") or frontmatter.get("trigger_pattern")
        if not trigger or not isinstance(trigger, str) or not trigger.strip():
            raise SkillParseError("Missing required field: 'trigger_pattern' or 'trigger'")
        trigger = trigger.strip()

        # Optional fields
        slug = frontmatter.get("slug")
        if slug and isinstance(slug, str) and slug.strip():
            slug = slug.strip().lower()
            if not re.match(r"^[a-z0-9-_]+$", slug):
                raise SkillParseError(f"Invalid slug format: '{slug}'. Must match ^[a-z0-9-_]+$")
        else:
            slug = _slugify(name)

        description = frontmatter.get("description")
        if description and isinstance(description, str):
            description = description.strip()
        else:
            description = None

        skill_type = frontmatter.get("skill_type") or frontmatter.get("type") or "prompt"
        if skill_type not in ("prompt", "workflow"):
            raise SkillParseError(f"Invalid skill_type '{skill_type}'. Allowed: 'prompt', 'workflow'")

        parameters = frontmatter.get("parameters") or frontmatter.get("parameters_schema")
        if parameters is None:
            parameters = {}
        elif not isinstance(parameters, dict):
            raise SkillParseError("'parameters' must be a YAML mapping (dictionary)")

        return SkillDefinition(
            name=name,
            slug=slug,
            trigger_pattern=trigger,
            content_markdown=body,
            description=description,
            skill_type=skill_type,
            parameters_schema=parameters,
        )
