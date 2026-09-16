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
_WHITELISTED_CALLEES = frozenset({"cn", "clsx", "classnames", "classNames"})


def _node_text(node: Node, source_bytes: bytes) -> bytes:
    """Return the raw source bytes for a tree-sitter node."""
    return source_bytes[node.start_byte : node.end_byte]


def _js_str(val: Any) -> str:
    """Coerce a statically resolved value to its JavaScript string form."""
    if val is True:
        return "true"
    if val is False:
        return "false"
    if val is _UNDEFINED:
        return "undefined"
    if val is None:
        return "null"
    return str(val)


class _Sentinel:
    """Sentinel representing a non-statically-determinable expression."""

    def __repr__(self) -> str:
        return "<UNKNOWN>"


_UNKNOWN = _Sentinel()


class _UndefinedSentinel:
    """Sentinel for JS ``undefined`` — distinct from ``null`` for coercion."""

    def __repr__(self) -> str:
        return "<UNDEFINED>"


_UNDEFINED = _UndefinedSentinel()


def _js_truthy(val: Any) -> bool:
    """Evaluate JavaScript truthiness of a statically resolved value."""
    return not (
        val is _UNKNOWN
        or val is _UNDEFINED
        or val is None
        or val is False
        or val == 0
        or val == ""
    )


def _decode_js_escapes(content: str) -> str:
    """Decode JavaScript escape sequences in a string-literal body.

    JSON decoding handles the common escapes. For escapes valid in JS but not
    in JSON (\\', \\xHH, \\v, \\0, Tailwind's \\:), fall back to a conservative
    unescape so raw backslashes do not leak into the resolved class string.
    """
    simple = {
        "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
        "v": "\v", "0": "\0", "\\": "\\", '"': '"', "'": "'",
        "`": "`", "/": "/",
    }
    out: list[str] = []
    i = 0
    while i < len(content):
        ch = content[i]
        if ch == "\\" and i + 1 < len(content):
            nxt = content[i + 1]
            if nxt == "x" and i + 3 < len(content):
                try:
                    out.append(chr(int(content[i + 2 : i + 4], 16)))
                    i += 4
                    continue
                except ValueError:
                    pass
            if nxt == "u" and i + 5 < len(content):
                try:
                    out.append(chr(int(content[i + 2 : i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
            # Unknown escape (e.g. Tailwind \\:): emit char without backslash.
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _extract_string_literal(node: Node, source_bytes: bytes) -> str:
    """Return the decoded string contents of a string literal node."""
    raw = _node_text(node, source_bytes).decode("utf-8", errors="replace")
    if len(raw) >= 2 and (
        (raw.startswith('"') and raw.endswith('"'))
        or (raw.startswith("'") and raw.endswith("'"))
    ):
        content = raw[1:-1]
        if "\\" in content:
            return _decode_js_escapes(content)
        return content
    return ""


def _eval_spread(node: Node, source_bytes: bytes) -> Any:
    """Evaluate a spread_element (`...expr`) to a list, or _UNKNOWN."""
    inner = None
    for child in node.children:
        if child.type not in (".", "...", "comment"):
            inner = child
            break
    if inner is None:
        return _UNKNOWN
    val = _eval_node(inner, source_bytes)
    if val is _UNKNOWN:
        return _UNKNOWN
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return val.split()
    return _UNKNOWN


def _object_key_to_str(key_node: Node, source_bytes: bytes) -> Any:
    """Resolve an object-literal key to a string, including computed names."""
    if key_node.type == "property_identifier":
        return _node_text(key_node, source_bytes).decode("utf-8", errors="replace")
    if key_node.type == "string":
        return _extract_string_literal(key_node, source_bytes)
    if key_node.type == "computed_property_name":
        inner = None
        for child in key_node.children:
            if child.type not in ("[", "]", "comment"):
                inner = child
                break
        if inner is None:
            return _UNKNOWN
        val = _eval_node(inner, source_bytes)
        if val is _UNKNOWN or val is None:
            return _UNKNOWN
        return _js_str(val)
    if key_node.type == "number":
        # clsx object keys may be bare numeric literals: {100: true}.
        raw = _node_text(key_node, source_bytes).decode("utf-8", errors="replace")
        return raw.strip() or _UNKNOWN
    return _UNKNOWN


def _eval_node(node: Node, source_bytes: bytes) -> Any:
    """Recursively evaluate an AST expression node in a safe, static manner."""
    if node.type == "parenthesized_expression":
        for child in node.children:
            if child.type not in ("(", ")", "comment"):
                return _eval_node(child, source_bytes)
        return _UNKNOWN

    if node.type == "as_expression":
        # TypeScript type assertion, e.g. expr as string
        children = [c for c in node.children if c.type not in ("as", "comment")]
        if children:
            return _eval_node(children[0], source_bytes)
        return _UNKNOWN

    if node.type == "type_assertion":
        # TypeScript <string>expr
        children = [c for c in node.children if c.type not in ("type_arguments", "comment")]
        if children:
            return _eval_node(children[-1], source_bytes)
        return _UNKNOWN

    if node.type == "satisfies_expression":
        # `"a" satisfies string` — evaluate the value, ignore the type.
        children = [c for c in node.children if c.type not in ("satisfies", "comment")]
        if children:
            return _eval_node(children[0], source_bytes)
        return _UNKNOWN

    if node.type == "non_null_expression":
        # `expr!` — unwrap; still fail-safe if the inner node is unknown.
        children = [c for c in node.children if c.type not in ("!", "comment")]
        if children:
            return _eval_node(children[0], source_bytes)
        return _UNKNOWN

    if node.type == "array":
        items: list[Any] = []
        for child in node.children:
            if child.type in ("[", "]", ",", "comment"):
                continue
            if child.type == "spread_element":
                inner = _eval_spread(child, source_bytes)
                if inner is _UNKNOWN:
                    return _UNKNOWN
                if isinstance(inner, list):
                    items.extend(inner)
                else:
                    items.append(inner)
                continue
            val = _eval_node(child, source_bytes)
            if val is _UNKNOWN:
                return _UNKNOWN
            items.append(val)
        return items

    if node.type == "object":
        keys: list[str] = []
        for child in node.children:
            if child.type != "pair":
                continue
            key_node = child.child_by_field_name("key")
            val_node = child.child_by_field_name("value")
            if key_node is None or val_node is None:
                p_children = [c for c in child.children if c.type not in (":", "comment")]
                if len(p_children) == 2:
                    key_node, val_node = p_children
            if not key_node or not val_node:
                continue
            val = _eval_node(val_node, source_bytes)
            if val is _UNKNOWN or not _js_truthy(val):
                continue
            k = _object_key_to_str(key_node, source_bytes)
            if k is _UNKNOWN:
                continue
            keys.extend(str(k).split())
        return " ".join(keys)

    if node.type == "string":
        return _extract_string_literal(node, source_bytes)

    if node.type == "number":
        raw = _node_text(node, source_bytes).decode("utf-8", errors="replace")
        try:
            if "." in raw or "e" in raw or "E" in raw:
                return float(raw)
            # Support hex/binary/octal and BigInt (100n) literals.
            return int(raw.rstrip("n"), 0) if raw[:1] == "0" or raw.endswith("n") else int(raw)
        except ValueError:
            return _UNKNOWN

    if node.type == "true":
        return True
    if node.type == "false":
        return False
    if node.type == "undefined":
        return _UNDEFINED
    if node.type == "null":
        return None

    if node.type == "template_string":
        parts: list[str] = []
        for child in node.children:
            if child.type == "`":
                continue
            if child.type == "escape_sequence":
                parts.append(
                    _decode_js_escapes(
                        _node_text(child, source_bytes).decode(
                            "utf-8", errors="replace"
                        )
                    )
                )
            elif child.type == "string_fragment":
                parts.append(
                    _node_text(child, source_bytes).decode("utf-8", errors="replace")
                )
            elif child.type == "template_substitution":
                sub_expr: Node | None = None
                for sub_child in child.children:
                    if sub_child.type not in ("${", "}", "comment"):
                        sub_expr = sub_child
                        break
                if sub_expr is None:
                    return _UNKNOWN
                sub_val = _eval_node(sub_expr, source_bytes)
                if sub_val is _UNKNOWN:
                    return _UNKNOWN
                # Coerce with JS semantics: null/undefined render as their
                # keyword, matching binary `+` coercion (consistency fix).
                parts.append(_js_str(sub_val))
            else:
                return _UNKNOWN
        return "".join(parts)

    if node.type == "binary_expression":
        left_node = node.child_by_field_name("left")
        op_node = node.child_by_field_name("operator")
        right_node = node.child_by_field_name("right")
        if left_node is None or op_node is None or right_node is None:
            children = [c for c in node.children if c.type != "comment"]
            if len(children) == 3:
                left_node, op_node, right_node = children
            else:
                return _UNKNOWN

        op = _node_text(op_node, source_bytes).decode("utf-8", errors="replace")
        if op == "+":
            left_val = _eval_node(left_node, source_bytes)
            if left_val is _UNKNOWN:
                return _UNKNOWN
            right_val = _eval_node(right_node, source_bytes)
            if right_val is _UNKNOWN:
                return _UNKNOWN
            if isinstance(left_val, str) or isinstance(right_val, str):
                return _js_str(left_val) + _js_str(right_val)
            if (
                isinstance(left_val, (int, float))
                and not isinstance(left_val, bool)
                and isinstance(right_val, (int, float))
                and not isinstance(right_val, bool)
            ):
                return left_val + right_val
            return _UNKNOWN

        if op == "&&":
            left_val = _eval_node(left_node, source_bytes)
            if left_val is _UNKNOWN:
                return _UNKNOWN
            if not _js_truthy(left_val):
                return left_val
            return _eval_node(right_node, source_bytes)

        if op == "||":
            left_val = _eval_node(left_node, source_bytes)
            if left_val is _UNKNOWN:
                return _UNKNOWN
            if _js_truthy(left_val):
                return left_val
            return _eval_node(right_node, source_bytes)

        if op == "??":
            left_val = _eval_node(left_node, source_bytes)
            if left_val is _UNKNOWN:
                return _UNKNOWN
            # JS nullish-coalescing covers both null and undefined.
            if left_val is None or left_val is _UNDEFINED:
                return _eval_node(right_node, source_bytes)
            return left_val

        return _UNKNOWN

    if node.type == "ternary_expression":
        cond_node = node.child_by_field_name("condition")
        conseq_node = node.child_by_field_name("consequence")
        alt_node = node.child_by_field_name("alternative")
        if cond_node is None or conseq_node is None or alt_node is None:
            children = [
                c for c in node.children if c.type not in ("?", ":", "comment")
            ]
            if len(children) == 3:
                cond_node, conseq_node, alt_node = children
            else:
                return _UNKNOWN

        cond_val = _eval_node(cond_node, source_bytes)
        if cond_val is _UNKNOWN:
            return _UNKNOWN
        if _js_truthy(cond_val):
            return _eval_node(conseq_node, source_bytes)
        return _eval_node(alt_node, source_bytes)

    if node.type == "unary_expression":
        op_node = node.child_by_field_name("operator")
        arg_node = node.child_by_field_name("argument")
        if op_node is None or arg_node is None:
            children = [c for c in node.children if c.type != "comment"]
            if len(children) == 2:
                op_node, arg_node = children
            else:
                return _UNKNOWN
        op = _node_text(op_node, source_bytes).decode("utf-8", errors="replace")
        val = _eval_node(arg_node, source_bytes)
        if val is _UNKNOWN:
            return _UNKNOWN
        if op == "!":
            return not _js_truthy(val)
        if (
            op == "-"
            and isinstance(val, (int, float))
            and not isinstance(val, bool)
        ):
            return -val
        if (
            op == "+"
            and isinstance(val, (int, float))
            and not isinstance(val, bool)
        ):
            return +val
        return _UNKNOWN

    if node.type == "call_expression":
        callee_node = node.child_by_field_name("function")
        if callee_node is None:
            for child in node.children:
                if child.type != "comment":
                    callee_node = child
                    break
        if callee_node is None or callee_node.type != "identifier":
            return _UNKNOWN
        callee_name = _node_text(callee_node, source_bytes).decode(
            "utf-8", errors="replace"
        )
        if callee_name not in _WHITELISTED_CALLEES:
            return _UNKNOWN

        args_node = node.child_by_field_name("arguments")
        if args_node is None:
            for child in node.children:
                if child.type == "arguments":
                    args_node = child
                    break
        if args_node is None:
            return _UNKNOWN

        tokens: list[str] = []

        def collect_arg(arg: Node) -> None:
            if arg.type == "parenthesized_expression":
                for child in arg.children:
                    if child.type not in ("(", ")", "comment"):
                        collect_arg(child)
                return
            if arg.type == "as_expression":
                children = [c for c in arg.children if c.type not in ("as", "comment")]
                if children:
                    collect_arg(children[0])
                return
            if arg.type == "type_assertion":
                children = [
                    c for c in arg.children if c.type not in ("type_arguments", "comment")
                ]
                if children:
                    collect_arg(children[-1])
                return
            if arg.type == "satisfies_expression":
                children = [
                    c for c in arg.children if c.type not in ("satisfies", "comment")
                ]
                if children:
                    collect_arg(children[0])
                return
            if arg.type == "non_null_expression":
                children = [c for c in arg.children if c.type not in ("!", "comment")]
                if children:
                    collect_arg(children[0])
                return
            if arg.type == "spread_element":
                inner = _eval_spread(arg, source_bytes)
                if isinstance(inner, list):
                    for item in inner:
                        if isinstance(item, str):
                            tokens.extend(item.split())
                        elif (
                            isinstance(item, (int, float))
                            and not isinstance(item, bool)
                            and _js_truthy(item)
                        ):
                            tokens.append(_js_str(item))
                return
            if arg.type == "array":
                for item in arg.children:
                    if item.type not in ("[", "]", ",", "comment"):
                        collect_arg(item)
                return
            if arg.type == "object":
                obj_val = _eval_node(arg, source_bytes)
                if isinstance(obj_val, str):
                    tokens.extend(obj_val.split())
                return

            val = _eval_node(arg, source_bytes)
            if isinstance(val, str):
                tokens.extend(val.split())
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        tokens.extend(item.split())
                    elif (
                        isinstance(item, (int, float))
                        and not isinstance(item, bool)
                        and _js_truthy(item)
                    ):
                        tokens.append(_js_str(item))
            elif (
                isinstance(val, (int, float))
                and not isinstance(val, bool)
                and _js_truthy(val)
            ):
                # Falsy numbers (0) are dropped by clsx/cn — never a class token.
                tokens.append(_js_str(val))

        for arg in args_node.children:
            if arg.type not in ("(", ")", ",", "comment"):
                collect_arg(arg)

        # A fully-static call that produced no tokens resolves to "" — distinct
        # from _UNKNOWN so `className={cn("")}` behaves like `className={""}`.
        return " ".join(tokens)

    return _UNKNOWN


def _unescape_selector_ident(ident: str) -> str:
    """Decode CSS escape sequences inside a selector identifier.

    Turns ``\\:`` ``\\.`` ``\\/`` ``\\#`` etc. back into their literal
    characters so a resolved class token like ``hover:bg`` matches the
    selector ``.hover\\:bg``.
    """
    return re.sub(r"\\(.)", r"\1", ident)


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
        except Exception as exc:  # tree-sitter parse can raise broadly; surface as structured MutationResult error
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

        try:
            matches = list(self._find_matches(tree.root_node, source_bytes, parsed))
        except RecursionError:
            # Pathologically deep JSX nests can exhaust the Python stack during
            # static eval; surface a structured error rather than crashing.
            return MutationResult(
                status="error",
                patched_code=jsx_code,
                message="Match error: JSX too deeply nested",
            )
        except Exception as exc:  # static-eval must never crash the caller
            return MutationResult(
                status="error",
                patched_code=jsx_code,
                message=f"Match error: {exc}",
            )
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
        # Split on unescaped `.` and `#` boundaries only, then unescape each
        # token — CSS escapes (`\.`, `\/`, `\:`) are how Tailwind fractional /
        # variant selectors reach us from the preview iframe.
        parts = re.split(r"(?<!\\)(?=[.#])", selector)
        tag: str | None = None
        elem_id: str | None = None
        class_names: list[str] = []
        for part in parts:
            if part.startswith("#"):
                elem_id = _unescape_selector_ident(part[1:]) or None
            elif part.startswith("."):
                name = _unescape_selector_ident(part[1:])
                if name:
                    class_names.append(name)
            elif part and tag is None:
                tag = part
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

    def _resolve_jsx_expr(
        self, expr_node: Node, source_bytes: bytes
    ) -> str | None:
        """Statically evaluate a jsx_expression node, returning str or None."""
        inner: Node | None = None
        for child in expr_node.children:
            if child.type not in ("{", "}", "comment"):
                inner = child
                break
        if inner is None:
            return None
        val = _eval_node(inner, source_bytes)
        if (
            val is _UNKNOWN
            or val is _UNDEFINED
            or val is None
            or isinstance(val, bool)
        ):
            return None
        if isinstance(val, str):
            return val
        if isinstance(val, (int, float)):
            return str(val)
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
        for child in attr.children:
            if child.type == "jsx_expression":
                return self._resolve_jsx_expr(child, source_bytes)
        return None

    def _attribute_value_text(self, attr: Node, source_bytes: bytes) -> str | None:
        """Return the string value of a JSX attribute if it is a string literal."""
        for child in attr.children:
            if child.type == "string":
                # Reuse the same extractor as expression attrs so multi-fragment
                # strings and escapes are decoded identically.
                return _extract_string_literal(child, source_bytes)
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
        except Exception as exc:  # tree-sitter parse can raise broadly; wrap as MarkToolError for caller
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
        except Exception as exc:  # tree-sitter parse can raise broadly; wrap as MarkToolError for caller
            raise MarkToolError(f"Invalid replacement JSX: {exc}") from exc
        if rebuilt.root_node.has_error:
            raise MarkToolError(
                "Invalid replacement JSX: the patched file could not be parsed"
            )
        return patched
