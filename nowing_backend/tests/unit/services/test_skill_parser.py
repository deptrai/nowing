"""Unit tests for SkillParser service (Story 3.18)."""

from __future__ import annotations

import pytest

from app.services.skill_parser import SkillParseError, SkillParser

pytestmark = pytest.mark.unit


def test_parse_valid_prompt_skill():
    content = """---
name: Market Analysis
slug: market-analysis
description: Perform deep real estate market analysis
trigger_pattern: "/market-analysis"
skill_type: prompt
parameters_schema:
  location:
    type: string
    description: City or district
---
Please analyze real estate trends in {{location}}.
"""
    skill = SkillParser.parse(content)
    assert skill.name == "Market Analysis"
    assert skill.slug == "market-analysis"
    assert skill.description == "Perform deep real estate market analysis"
    assert skill.trigger_pattern == "/market-analysis"
    assert skill.skill_type == "prompt"
    assert skill.parameters_schema == {
        "location": {"type": "string", "description": "City or district"}
    }
    assert "Please analyze real estate trends in {{location}}." in skill.content_markdown


def test_parse_valid_workflow_skill():
    content = """---
name: Lead Scraping Mission
trigger: "/scrape-leads"
type: workflow
---
# Scraping workflow instructions
"""
    skill = SkillParser.parse(content)
    assert skill.name == "Lead Scraping Mission"
    assert skill.slug == "lead-scraping-mission"
    assert skill.trigger_pattern == "/scrape-leads"
    assert skill.skill_type == "workflow"
    assert "# Scraping workflow instructions" in skill.content_markdown


def test_parse_missing_frontmatter():
    content = "Just plain markdown content without frontmatter delimiters."
    with pytest.raises(SkillParseError, match="Missing frontmatter delimiters"):
        SkillParser.parse(content)


def test_parse_invalid_yaml():
    content = """---
name: Invalid: [unclosed
---
Content
"""
    with pytest.raises(SkillParseError, match="Invalid YAML frontmatter"):
        SkillParser.parse(content)


def test_parse_non_dict_frontmatter():
    content = """---
- item 1
- item 2
---
Content
"""
    with pytest.raises(SkillParseError, match="Frontmatter must be a YAML dictionary"):
        SkillParser.parse(content)


def test_parse_missing_name():
    content = """---
trigger_pattern: "/test"
---
Content
"""
    with pytest.raises(SkillParseError, match="Missing required field: 'name'"):
        SkillParser.parse(content)


def test_parse_missing_trigger():
    content = """---
name: Test Skill
---
Content
"""
    with pytest.raises(SkillParseError, match="Missing required field: 'trigger_pattern' or 'trigger'"):
        SkillParser.parse(content)


def test_parse_invalid_skill_type():
    content = """---
name: Test Skill
trigger: "/test"
skill_type: unknown_type
---
Content
"""
    with pytest.raises(SkillParseError, match="Invalid skill_type 'unknown_type'"):
        SkillParser.parse(content)
