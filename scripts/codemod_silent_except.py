#!/usr/bin/env python3
"""Codemod: convert silent ``except: pass/continue/...`` blocks into
``except ... as exc: logger.debug("Suppressed %r", exc)`` (keeping ``continue``).

Usage:
    python3 scripts/codemod_silent_except.py [--apply] [paths...]

Dry-run by default; ``--apply`` rewrites files. Only touches handlers whose
entire body is a lone ``pass`` / ``continue`` / ``...`` (comments ignored).
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


def _handler_is_silent(node: ast.ExceptHandler) -> str | None:
    """Return 'pass' | 'continue' | 'ellipsis' if the handler body is a lone
    silent statement, else None."""
    if len(node.body) != 1:
        return None
    stmt = node.body[0]
    if isinstance(stmt, ast.Pass):
        return "pass"
    if isinstance(stmt, ast.Continue):
        return "continue"
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
        return "ellipsis"
    return None


def _module_logger_name(tree: ast.Module) -> str | None:
    """Existing module-level logger variable name, if any."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            src = node.value
            if (
                isinstance(src, ast.Call)
                and isinstance(src.func, ast.Attribute)
                and src.func.attr in {"getLogger", "get_logger"}
            ):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        return t.id
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name in {"logger", "log"} or (a.asname or a.name) in {"logger", "log"}:
                    return a.asname or a.name
    return None


def _first_import_block_end(tree: ast.Module) -> int:
    """Line after the first contiguous run of top-level imports (skipping the
    module docstring). Late E402 imports deeper in the file are ignored."""
    last = 0
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            last = node.end_lineno or node.lineno  # keep logger below docstring
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = max(last, node.end_lineno or node.lineno)
            continue
        if isinstance(node, ast.Try):
            continue  # optional-dependency try/import blocks
        break
    return last


def _has_logging_import(tree: ast.Module) -> bool:
    return any(
        isinstance(n, ast.Import) and any(a.name == "logging" for a in n.names)
        for n in ast.walk(tree)
    )


def process(path: Path) -> tuple[int, str]:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return 0, src
    lines = src.splitlines(keepends=True)

    edits: list[tuple[int, int, str]] = []  # (start_line0, end_line0, new_text)
    log_name0 = _module_logger_name(tree) or "logger"
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        kind = _handler_is_silent(node)
        if not kind:
            continue

        exc_line0 = node.lineno - 1  # the `except ...:` line
        body = node.body[0]
        body_line0 = body.lineno - 1
        indent = re.match(r"^\s*", lines[exc_line0]).group(0)
        inner_indent = re.match(r"^\s*", lines[body_line0]).group(0) or indent + "    "

        exc_text = lines[exc_line0].rstrip("\n")
        bound = node.name or "exc"
        debug_line = f'{inner_indent}{log_name0}.debug("Suppressed %r", {bound})'
        one_liner = body_line0 == exc_line0

        if node.name:
            # already `except E as name:` — keep head (strip one-line body)
            if one_liner:
                m = re.match(r"^(.*?:)\s*(?:pass|continue|\.\.\.)\s*(#.*)?$", exc_text)
                exc_head = (m.group(1) + ("  " + m.group(2) if m.group(2) else "")) if m else exc_text
            else:
                exc_head = exc_text
        elif one_liner:
            # `except E: pass` / `except: pass` on a single line
            m = re.match(r"^(.*?)\bexcept\b([^:]*?):\s*(pass|continue|\.\.\.)\s*(#.*)?$", exc_text)
            if m:
                comment = f"  {m.group(4)}" if m.group(4) else ""
                if node.type is None:
                    exc_head = f"{indent}except BaseException as exc:{comment}"
                else:
                    exc_head = f"{indent}except{m.group(2)} as exc:{comment}"
            else:
                continue
        elif node.type is None:
            exc_head = f"{indent}except BaseException as exc:"
        else:
            # insert `as exc` before the colon ending the clause; keep any
            # trailing inline comment separated by two spaces.
            def _add_as(m: re.Match) -> str:
                comment = m.group(2) or ""
                sep = "  " if comment else ""
                return f" as exc:{sep}{comment}"

            new_exc = re.sub(r":(\s*(#.*)?$)", _add_as, exc_text, count=1)
            exc_head = new_exc if " as exc:" in new_exc else exc_text + " as exc"

        # Preserve comment lines between the except clause and the body.
        kept = [lines[k].rstrip("\n") for k in range(exc_line0 + 1, body_line0)]
        if kind == "continue":
            replacement = "\n".join([exc_head, *kept, debug_line, lines[body_line0].rstrip()])
        else:
            # lone pass/... (or one-liner `except E: pass`) → debug replaces it
            replacement = "\n".join([exc_head, *kept, debug_line])
        edits.append((exc_line0, body_line0, replacement))

    if not edits:
        return 0, src

    # Apply edits bottom-up so line numbers stay valid.
    for start, end, text in sorted(edits, reverse=True):
        lines[start : end + 1] = [text + "\n"]

    # Ensure module logger exists.
    tree2 = ast.parse("".join(lines))
    log_name = _module_logger_name(tree2)
    if log_name is None:
        insert_at = _first_import_block_end(tree2)
        inject = []
        if not _has_logging_import(tree2):
            inject.append("import logging\n")
        inject.append("\nlogger = logging.getLogger(__name__)\n")
        lines[insert_at:insert_at] = inject

    new_src = "".join(lines)
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"  !! {path}: codemod produced syntax error: {e}")
        return 0, src
    return len(edits), new_src


def main() -> int:
    apply = "--apply" in sys.argv
    paths = [Path(a) for a in sys.argv[1:] if a != "--apply"]
    if not paths:
        paths = sorted(Path("nowing_backend/app").rglob("*.py"))
    total = 0
    for p in paths:
        n, new_src = process(p)
        if not n:
            continue
        total += n
        print(f"{p}: {n} block(s)")
        if apply:
            p.write_text(new_src, encoding="utf-8")
    print(f"TOTAL: {total} silent blocks {'rewritten' if apply else 'found'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
