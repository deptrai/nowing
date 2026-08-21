#!/usr/bin/env python3
"""
First Breath — Deterministic sanctum scaffolding for BenchGuard (bmad-agent-benchmark).

Creates the sanctum folder structure at `_bmad/memory/bmad-agent-benchmark/`,
copies templates with config values substituted, copies capability files
into the sanctum, and generates CAPABILITIES.md.

Usage:
    uv run scripts/init-sanctum.py <project-root> <skill-path>
"""

import sys
import re
import shutil
from datetime import date
from pathlib import Path

SKILL_NAME = "bmad-agent-benchmark"
SANCTUM_DIR = SKILL_NAME

SKILL_ONLY_FILES = {
    "first-breath.md",
    "prompt-quality-canon.md",
}

TEMPLATE_FILES = [
    "INDEX-template.md",
    "PERSONA-template.md",
    "CREED-template.md",
    "BOND-template.md",
    "MEMORY-template.md",
    "CAPABILITIES-template.md",
]

EVOLVABLE = True


def parse_yaml_or_toml_config(bmad_dir: Path) -> dict:
    """Extract basic configuration from _bmad config files if present."""
    config = {
        "user_name": "Luisphan",
        "communication_language": "Việt Nam",
    }
    for conf_file in ["config.user.toml", "config.user.yaml", "config.toml", "config.yaml"]:
        p = bmad_dir / conf_file
        if p.exists():
            text = p.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "user_name" in line and ":" in line:
                    val = line.split(":")[1].strip().strip('"\'')
                    if val:
                        config["user_name"] = val
                elif "user_name" in line and "=" in line:
                    val = line.split("=")[1].strip().strip('"\'')
                    if val:
                        config["user_name"] = val
                elif "communication_language" in line and ":" in line:
                    val = line.split(":")[1].strip().strip('"\'')
                    if val:
                        config["communication_language"] = val
                elif "communication_language" in line and "=" in line:
                    val = line.split("=")[1].strip().strip('"\'')
                    if val:
                        config["communication_language"] = val
    return config


def parse_frontmatter(file_path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    meta = {}
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return meta

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return meta

    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("'\"")
    return meta


def copy_references(source_dir: Path, dest_dir: Path) -> list[str]:
    """Copy reference files into the sanctum."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []

    if not source_dir.exists():
        return copied

    for source_file in sorted(source_dir.iterdir()):
        if source_file.name in SKILL_ONLY_FILES:
            continue
        if source_file.is_file():
            shutil.copy2(source_file, dest_dir / source_file.name)
            copied.append(source_file.name)

    return copied


def discover_capabilities(references_dir: Path, sanctum_refs_path: str) -> list[dict]:
    """Scan references/ for capability prompt files with frontmatter."""
    capabilities = []
    if not references_dir.exists():
        return capabilities

    for md_file in sorted(references_dir.glob("*.md")):
        if md_file.name in SKILL_ONLY_FILES:
            continue
        meta = parse_frontmatter(md_file)
        if meta.get("name") and meta.get("code"):
            capabilities.append({
                "name": meta["name"],
                "description": meta.get("description", ""),
                "code": meta["code"],
                "source": f"{sanctum_refs_path}/{md_file.name}",
            })
    return capabilities


def generate_capabilities_md(capabilities: list[dict], evolvable: bool) -> str:
    """Generate CAPABILITIES.md content from discovered capabilities."""
    lines = [
        "# Capabilities",
        "",
        "## Built-in",
        "",
        "| Code | Name | Description | Source |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for cap in capabilities:
        lines.append(
            f"| [{cap['code']}] | {cap['name']} | {cap['description']} | `{cap['source']}` |"
        )

    if evolvable:
        lines.extend([
            "",
            "## Learned",
            "",
            "_Capabilities added by the owner over time. Prompts live in `capabilities/`._",
            "",
            "| Code | Name | Description | Source | Added |",
            "| :--- | :--- | :--- | :--- | :--- |",
            "",
            "## How to Add a Capability",
            "",
            'Tell me "I want you to be able to benchmark X" and we\'ll create it together.',
            "I'll write the prompt, save it to `capabilities/`, and register it here.",
            "Next session, I'll know how.",
            "Load `references/capability-authoring.md` for the full creation framework.",
        ])

    lines.extend([
        "",
        "## Tools & Harness",
        "",
        "Executes benchmarks through Nowing's official `nowing_evals` harness and parses CLI artifacts deterministically.",
        "",
        "### Available Suites",
        "- `lead_extraction`: DSH extraction F1 Phone, Hallucination Rate, MST Modulo-11 accuracy (`--mode replay` / `--mode live`)",
        "- `chat regression`: Chat streaming response regression, TTFB, p95 latency, cost/turn, finish rate across modes",
        "- `memory recall`: Memory retrieval accuracy, precision@5, noise rate with Wilson CI",
    ])

    return "\n".join(lines) + "\n"


def substitute_vars(content: str, variables: dict) -> str:
    """Replace {var_name} placeholders with values from the variables dict."""
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", value)
    return content


def main():
    if len(sys.argv) < 3:
        print("Usage: uv run scripts/init-sanctum.py <project-root> <skill-path>")
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    skill_path = Path(sys.argv[2]).resolve()

    # Paths
    bmad_dir = project_root / "_bmad"
    memory_dir = bmad_dir / "memory"
    sanctum_path = memory_dir / SANCTUM_DIR
    assets_dir = skill_path / "assets"
    references_dir = skill_path / "references"

    # Subdirectories
    sanctum_refs = sanctum_path / "references"

    if sanctum_path.exists() and (sanctum_path / "CREED.md").exists():
        print(f"Sanctum already exists at {sanctum_path}")
        print("BenchGuard has already taken First Breath. Skipping scaffolding.")
        sys.exit(0)

    config = parse_yaml_or_toml_config(bmad_dir)
    today = date.today().isoformat()
    variables = {
        "user_name": config.get("user_name", "Luisphan"),
        "communication_language": config.get("communication_language", "Việt Nam"),
        "birth_date": today,
        "project_root": str(project_root),
        "sanctum_path": str(sanctum_path),
        "agent-title": "Master System Benchmark & Quality Guardian",
        "vibe-prompt": "Data-driven, uncompromising on accuracy, vigilant against latency & cost regressions.",
        "bond-summary": f"{config.get('user_name', 'Luisphan')} (Nowing Founder & Lead Developer)",
    }

    sanctum_path.mkdir(parents=True, exist_ok=True)
    (sanctum_path / "capabilities").mkdir(exist_ok=True)
    (sanctum_path / "sessions").mkdir(exist_ok=True)
    print(f"Created sanctum at {sanctum_path}")

    copied_refs = copy_references(references_dir, sanctum_refs)
    print(f"  Copied {len(copied_refs)} reference files to sanctum/references/")

    for template_name in TEMPLATE_FILES:
        template_path = assets_dir / template_name
        if not template_path.exists():
            continue

        output_name = template_name.replace("-template", "")
        base_name = output_name.replace(".md", "").upper() + ".md"

        content = template_path.read_text(encoding="utf-8")
        content = substitute_vars(content, variables)

        output_path = sanctum_path / base_name
        output_path.write_text(content, encoding="utf-8")
        print(f"  Created {base_name}")

    capabilities = discover_capabilities(references_dir, "references")
    capabilities_content = generate_capabilities_md(capabilities, evolvable=EVOLVABLE)
    (sanctum_path / "CAPABILITIES.md").write_text(capabilities_content, encoding="utf-8")
    print(f"  Created CAPABILITIES.md ({len(capabilities)} built-in capabilities discovered)")

    print()
    print("First Breath scaffolding complete for BenchGuard.")
    print(f"Sanctum initialized at: {sanctum_path}")


if __name__ == "__main__":
    main()
