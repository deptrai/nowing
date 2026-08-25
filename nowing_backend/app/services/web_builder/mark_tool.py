"""Design View Mark Tool DOM-to-JSX AST Mutator (Story 27.1d / AD-114).

Uses the already-installed ``tree-sitter`` / ``tree-sitter-typescript`` parser
for a real TSX AST instead of fragile regex replacements.  This keeps the
mutator hermetic for unit tests and avoids a network-dependent Node/Babel
subprocess while still satisfying the AST requirement.

The Node/Babel subprocess described in the architecture is intentionally not
used here because a Python-based TSX parser is present in the project and is
simpler/safer for a sandboxed mutator.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from tree_sitter import Language, Node, Parser
from tree_sitter_typescript import language_tsx

logger = logging.getLogger(__name__)

_TSX_LANGUAGE = Language(language_tsx())
_JSX_ATTR_NAME = re.compile(r"^[A-Za-z_][\w:-]*$")
JSX_FILE_SUFFIXES = {".tsx", ".jsx"}


def _node_text(node: Node, source_bytes: bytes) -> bytes:
    """Return the raw source bytes for a tree-sitter node."""
    return source_bytes[node.start_byte : node.end_byte]


@dataclass(frozen=True)
class _ParsedSelector:
    """Simple decomposed CSS-ish selector from the preview iframe."""

    tag: str | None = None
    elem_id: str | None = None
    class_names: tuple[str, ...] = ()


class MarkToolError(Exception):
    """Raised when a patch cannot be applied to a matched element."""


@dataclass
class MutationResult:
    status: str  # patched, mark_unresolvable, error
    patched_code: str
    message: str | None = None


class MarkToolASTMutator:
    """Parse and mutate React / JSX component source using a real TSX AST."""

    def apply_patch(
        self,
        jsx_code: str,
        selector: str,
        patch: dict[str, Any],
    ) -> MutationResult:
        """Apply a visual modification (text, className, attribute, replace) to the target JSX node."""
        patch_type = patch.get("type", "text")
        value = patch.get("value", "")
        attribute_name = patch.get("attribute")
        selector = (selector or "").strip()
        if not selector or selector in {"#", "."}:
            return MutationResult(
                status="mark_unresolvable",
                patched_code=jsx_code,
                message="Empty selector",
            )

        parsed = self._parse_selector(selector)
        if not parsed.tag and parsed.elem_id is None and not parsed.class_names:
            return MutationResult(
                status="mark_unresolvable",
                patched_code=jsx_code,
                message=f"Selector '{selector}' has no tag, id, or class",
            )

        try:
            source_bytes = jsx_code.encode("utf-8")
            parser = Parser(_TSX_LANGUAGE)
            tree = parser.parse(source_bytes)
        except Exception as exc:
            logger.warning("Failed to parse TSX source: %s", exc)
            return MutationResult(
                status="error",
                patched_code=jsx_code,
                message=f"Parse error: {exc}",
            )

        if tree.root_node.has_error:
            return MutationResult(
                status="error",
                patched_code=jsx_code,
                message="Parse error: invalid TSX",
            )

        matches = list(self._find_matches(tree.root_node, source_bytes, parsed))
        if not matches:
            return MutationResult(
                status="mark_unresolvable",
                patched_code=jsx_code,
                message=f"Selector '{selector}' matched no JSX element",
            )
        if len(matches) > 1:
            return MutationResult(
                status="mark_unresolvable",
                patched_code=jsx_code,
                message=(
                    f"Selector '{selector}' matched {len(matches)} JSX elements; "
                    "unique match required"
                ),
            )

        try:
            new_bytes = self._apply(
                matches[0], source_bytes, patch_type, value, attribute_name
            )
        except MarkToolError as exc:
            return MutationResult(
                status="error",
                patched_code=jsx_code,
                message=str(exc),
            )

        return MutationResult(
            status="patched",
            patched_code=new_bytes.decode("utf-8", errors="replace"),
        )

    # ------------------------------------------------------------------
    # Selector parsing and matching
    # ------------------------------------------------------------------

    def _parse_selector(self, selector: str) -> _ParsedSelector:
        """Parse a tiny subset of CSS selectors produced by the preview script.

        Supported forms:
            #id
            .class
            .class.other
            tag
            tag.class
            tag.class.other
            tag#id
            tag#id.class
        """
        class_names: list[str] = []
        if selector.startswith("#"):
            elem_id = selector[1:]
            return _ParsedSelector(elem_id=elem_id or None)
        if selector.startswith("."):
            parts = re.split(r"(?=\.)", selector)
            class_names = [
                part[1:] for part in parts if part.startswith(".") and part[1:]
            ]
            return _ParsedSelector(class_names=tuple(class_names))

        parts = re.split(r"(?=[.#])", selector)
        tag = parts[0] or None
        elem_id: str | None = None
        for part in parts[1:]:
            if part.startswith("#"):
                elem_id = part[1:] or None
            elif part.startswith(".") and part[1:]:
                class_names.append(part[1:])
        return _ParsedSelector(tag=tag, elem_id=elem_id, class_names=tuple(class_names))

    def _find_matches(
        self, node: Node, source_bytes: bytes, parsed: _ParsedSelector
    ) -> list[Node]:
        return [
            n
            for n in self._walk_jsx_elements(node)
            if self._matches(n, source_bytes, parsed)
        ]

    def _walk_jsx_elements(self, node: Node) -> list[Node]:
        """Recursively collect jsx_element and jsx_self_closing_element nodes."""
        results: list[Node] = []
        for child in node.children:
            if child.type in ("jsx_element", "jsx_self_closing_element"):
                results.append(child)
            results.extend(self._walk_jsx_elements(child))
        return results

    def _matches(
        self, element: Node, source_bytes: bytes, parsed: _ParsedSelector
    ) -> bool:
        opening = self._opening_node(element)

        if parsed.tag:
            tag_name = self._tag_name(opening, source_bytes)
            if tag_name != parsed.tag:
                return False

        if parsed.elem_id is not None:
            id_value = self._get_attr_value(opening, "id", source_bytes)
            if id_value != parsed.elem_id:
                return False

        if parsed.class_names:
            class_value = self._get_attr_value(opening, "className", source_bytes)
            if class_value is None:
                return False
            for class_name in parsed.class_names:
                if not re.search(
                    r"(?:^|\s)" + re.escape(class_name) + r"(?:\s|$)",
                    class_value,
                ):
                    return False

        return True

    # ------------------------------------------------------------------
    # AST helpers
    # ------------------------------------------------------------------

    def _opening_node(self, element: Node) -> Node:
        if element.type == "jsx_self_closing_element":
            return element
        for child in element.children:
            if child.type == "jsx_opening_element":
                return child
        return element

    def _tag_name(self, opening: Node, source_bytes: bytes) -> str | None:
        for child in opening.children:
            if child.type in ("identifier", "member_expression"):
                return _node_text(child, source_bytes).decode("utf-8", errors="replace")
        return None

    def _find_attribute(
        self, opening: Node, attr_name: str, source_bytes: bytes
    ) -> Node | None:
        for child in opening.children:
            if child.type == "jsx_attribute":
                name_node = child.child_by_field_name("name")
                if name_node is None:
                    # Fallback for older tree-sitter bindings without field names.
                    for maybe_name in child.children:
                        if maybe_name.type == "property_identifier":
                            name_node = maybe_name
                            break
                if name_node is not None:
                    name = _node_text(name_node, source_bytes).decode(
                        "utf-8", errors="replace"
                    )
                    if name == attr_name:
                        return child
        return None

    def _get_attr_value(
        self, opening: Node, attr_name: str, source_bytes: bytes
    ) -> str | None:
        attr = self._find_attribute(opening, attr_name, source_bytes)
        if attr is None:
            return None
        value = self._attribute_value_text(attr, source_bytes)
        if value is not None:
            return value
        # Expressions can't be evaluated, so they don't match a class/id selector.
        return None

    def _attribute_value_text(self, attr: Node, source_bytes: bytes) -> str | None:
        """Return the string value of a JSX attribute if it is a string literal."""
        for child in attr.children:
            if child.type == "string":
                # Prefer the explicit string_fragment child.
                for frag in child.children:
                    if frag.type == "string_fragment":
                        return _node_text(frag, source_bytes).decode(
                            "utf-8", errors="replace"
                        )
                # Fall back to text between the quotes.
                raw = _node_text(child, source_bytes).decode("utf-8", errors="replace")
                if len(raw) >= 2:
                    return raw[1:-1]
                return ""
        return None

    def _close_token(self, opening: Node) -> Node:
        """Return the '>' or '/>' token of an opening/self-closing tag."""
        for child in opening.children:
            if child.type in (">", "/>"):
                return child
        raise MarkToolError("Could not locate the close token of the JSX tag")

    # ------------------------------------------------------------------
    # Patch application
    # ------------------------------------------------------------------

    def _apply(
        self,
        element: Node,
        source_bytes: bytes,
        patch_type: str,
        value: Any,
        attribute_name: str | None,
    ) -> bytes:
        if patch_type == "text":
            return self._patch_text(element, source_bytes, value)
        if patch_type == "className":
            return self._patch_attribute(element, source_bytes, "className", value)
        if patch_type == "style":
            return self._patch_attribute(element, source_bytes, "style", value)
        if patch_type == "attribute":
            if not attribute_name:
                raise MarkToolError('attribute patch requires "attribute" field')
            return self._patch_attribute(element, source_bytes, attribute_name, value)
        if patch_type == "replace":
            return self._patch_replace(element, source_bytes, value)
        raise MarkToolError(f"Unsupported patch type: {patch_type}")

    def _patch_text(self, element: Node, source_bytes: bytes, value: Any) -> bytes:
        if element.type == "jsx_self_closing_element":
            raise MarkToolError(
                "Text patch cannot be applied to a self-closing JSX element"
            )

        opening: Node | None = None
        closing: Node | None = None
        for child in element.children:
            if child.type == "jsx_opening_element":
                opening = child
            elif child.type == "jsx_closing_element":
                closing = child

        if opening is None or closing is None:
            raise MarkToolError("Malformed JSX element: missing opening/closing tag")

        nested_types = {"jsx_element", "jsx_self_closing_element", "jsx_fragment"}
        if any(child.type in nested_types for child in element.children):
            raise MarkToolError("Refusing text patch over nested JSX")

        start = opening.end_byte
        end = closing.start_byte

        # Render value as a JSX expression containing a JSON-string literal.
        # This safely carries arbitrary characters (including JSX injection chars)
        # without needing to escape HTML entities or worry about nested tags.
        safe = json.dumps(str(value))
        replacement = b"{" + safe.encode("utf-8") + b"}"
        return source_bytes[:start] + replacement + source_bytes[end:]

    def _patch_attribute(
        self,
        element: Node,
        source_bytes: bytes,
        attr_name: str,
        value: Any,
    ) -> bytes:
        if not _JSX_ATTR_NAME.fullmatch(attr_name):
            raise MarkToolError(f"Invalid attribute name: {attr_name!r}")

        opening = self._opening_node(element)
        attr = self._find_attribute(opening, attr_name, source_bytes)

        safe = json.dumps(str(value))
        replacement = (
            attr_name.encode("utf-8") + b'={"' + safe[1:-1].encode("utf-8") + b'"}'
        )
        # For non-string attributes, or if the caller wanted an expression, the
        # generic text schema provides enough for a replace patch; attribute
        # patch always writes a string-literal attribute.

        if attr is not None:
            start = attr.start_byte
            end = attr.end_byte
            return source_bytes[:start] + replacement + source_bytes[end:]

        # Insert the new attribute just before the '>' or '/>' token.
        close_token = self._close_token(opening)
        insert = b" " + replacement
        return (
            source_bytes[: close_token.start_byte]
            + insert
            + source_bytes[close_token.start_byte :]
        )

    def _patch_replace(self, element: Node, source_bytes: bytes, value: Any) -> bytes:
        value_str = str(value)
        value_bytes = value_str.encode("utf-8")

        # Validate the replacement snippet by wrapping it in a JSX fragment.
        # The fragment lets users supply a single element, text, or multiple
        # elements while still being syntactically valid TSX.
        validation_source = b"<>" + value_bytes + b"</>"
        parser = Parser(_TSX_LANGUAGE)
        try:
            tree = parser.parse(validation_source)
        except Exception as exc:
            raise MarkToolError(f"Invalid replacement JSX: {exc}") from exc

        if tree.root_node.has_error:
            raise MarkToolError(
                "Invalid replacement JSX: the snippet could not be parsed"
            )

        start = element.start_byte
        end = element.end_byte
        patched = source_bytes[:start] + value_bytes + source_bytes[end:]
        try:
            rebuilt = parser.parse(patched)
        except Exception as exc:
            raise MarkToolError(f"Invalid replacement JSX: {exc}") from exc
        if rebuilt.root_node.has_error:
            raise MarkToolError(
                "Invalid replacement JSX: the patched file could not be parsed"
            )
        return patched
