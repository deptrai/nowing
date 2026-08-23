"""Design View Mark Tool DOM-to-JSX AST Mutator (Story 27.1, AC-4)."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class MutationResult:
    status: str  # patched, mark_unresolvable, error
    patched_code: str
    message: str | None = None


class MarkToolASTMutator:
    """Parses and mutates React / JSX component code based on visual Mark Tool bounding box selectors."""

    def apply_patch(
        self,
        jsx_code: str,
        selector: str,
        patch: dict[str, Any],
    ) -> MutationResult:
        """Apply a visual modification (text, className/style) to the target JSX node matching selector."""
        patch_type = patch.get("type", "text")
        new_val = patch.get("value", "")

        # 1. Match ID selectors e.g. #hero-title or id="hero-title"
        if selector.startswith("#"):
            elem_id = selector[1:]
            id_pattern = rf'(<[A-Za-z0-9_]+[^>]*id=["\']{re.escape(elem_id)}["\'][^>]*>)(.*?)(</[A-Za-z0-9_]+>)'

            if patch_type == "text":
                match = re.search(id_pattern, jsx_code, flags=re.DOTALL)
                if match:
                    prefix, _old_text, suffix = match.groups()
                    patched = (
                        jsx_code[: match.start()]
                        + f"{prefix}{new_val}{suffix}"
                        + jsx_code[match.end() :]
                    )
                    return MutationResult(status="patched", patched_code=patched)

            elif patch_type in ["className", "class"]:
                tag_pattern = (
                    rf'(<[A-Za-z0-9_]+[^>]*id=["\']{re.escape(elem_id)}["\'][^>]*>)'
                )
                match = re.search(tag_pattern, jsx_code)
                if match:
                    opening_tag = match.group(1)
                    if "className=" in opening_tag:
                        new_tag = re.sub(
                            r'className=["\'][^"\']*["\']',
                            f'className="{new_val}"',
                            opening_tag,
                        )
                    else:
                        new_tag = opening_tag[:-1] + f' className="{new_val}">'
                    patched = (
                        jsx_code[: match.start()] + new_tag + jsx_code[match.end() :]
                    )
                    return MutationResult(status="patched", patched_code=patched)

        # 2. Match Class selectors e.g. .description
        elif selector.startswith("."):
            class_name = selector[1:]
            class_pattern = rf'(<[A-Za-z0-9_]+[^>]*className=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'][^>]*>)(.*?)(</[A-Za-z0-9_]+>)'

            if patch_type == "text":
                match = re.search(class_pattern, jsx_code, flags=re.DOTALL)
                if match:
                    prefix, _old_text, suffix = match.groups()
                    patched = (
                        jsx_code[: match.start()]
                        + f"{prefix}{new_val}{suffix}"
                        + jsx_code[match.end() :]
                    )
                    return MutationResult(status="patched", patched_code=patched)

        # 3. Match Tag selectors e.g. h1, button
        elif re.match(r"^[A-Za-z0-9_]+$", selector):
            tag_name = selector
            tag_pattern = rf"(<{tag_name}[^>]*>)(.*?)(</{tag_name}>)"
            match = re.search(tag_pattern, jsx_code, flags=re.DOTALL)
            if match:
                prefix, _old_text, suffix = match.groups()
                if patch_type == "text":
                    patched = (
                        jsx_code[: match.start()]
                        + f"{prefix}{new_val}{suffix}"
                        + jsx_code[match.end() :]
                    )
                    return MutationResult(status="patched", patched_code=patched)

        return MutationResult(
            status="mark_unresolvable",
            patched_code=jsx_code,
            message=f"Could not map selector '{selector}' to a unique JSX component node",
        )
