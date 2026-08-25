"""Validation utilities for generated Web Builder projects (Story 27.1, AC-1)."""

import json
import re
from pathlib import Path

# Maximum file size to read for security text scans (1 MiB)
_MAX_SCAN_BYTES = 1_048_576


def _safe_read_text(path: Path) -> str:
    """Read at most _MAX_SCAN_BYTES of a file for pattern scanning."""
    try:
        size = path.stat().st_size
        if size > _MAX_SCAN_BYTES:
            with open(path, "rb") as f:
                raw = f.read(_MAX_SCAN_BYTES)
            return raw.decode("utf-8", errors="replace")
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"__read_error:{e}__"


def _strip_balanced_parens(text: str, regex: str) -> str:
    """Remove matched calls with balanced nested parentheses.

    Used to allowlist standard Next.js patterns such as ``next/dynamic(...)``
    and ``dynamic(...)`` before scanning for forbidden imports.
    """
    pattern = re.compile(regex, re.IGNORECASE)
    result = []
    i = 0
    for m in pattern.finditer(text):
        result.append(text[i : m.end()])
        # m.end() points at the first character after the opening '('
        depth = 1
        j = m.end()
        while j < len(text) and depth > 0:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        i = j
    result.append(text[i:])
    return "".join(result)


FORBIDDEN_PATTERNS = [
    (re.compile(r"\bchild_process\b", re.IGNORECASE), "child_process execution"),
    (
        re.compile(r"\bexecSync\b|\bspawnSync\b|\bexecFile\b|\bfork\b", re.IGNORECASE),
        "subprocess execution",
    ),
    (
        re.compile(r"\bprocess\.exit\b|\bprocess\.kill\b", re.IGNORECASE),
        "process manipulation",
    ),
    (
        re.compile(
            r"\brequire\s*\(\s*['\"](?:fs|node:fs|net|node:net|dgram|node:dgram|http|node:http|https|node:https)['\"]\s*\)",
            re.IGNORECASE,
        ),
        "unsafe system module import",
    ),
    (
        re.compile(
            r"\bimport\s+.*\s+from\s+['\"](?:fs|node:fs|net|node:net|dgram|node:dgram)['\"]",
            re.IGNORECASE,
        ),
        "unsafe system module import",
    ),
    (re.compile(r"\bdynamic\s+import\s*\(", re.IGNORECASE), "dynamic import"),
    (
        re.compile(r"(?<![{@])\bimport\s*\(", re.IGNORECASE),
        "dynamic import",
    ),
    (re.compile(r"\bnew\s+Function\s*\(", re.IGNORECASE), "dynamic code evaluation"),
    (re.compile(r"\b(?:eval|Function)\s*\(", re.IGNORECASE), "dynamic code evaluation"),
]


def _scan_text(text: str, source_name: str, issues: list[str]) -> None:
    """Apply forbidden patterns to a string and collect issues.

    Next.js ``next/dynamic`` and ``dynamic`` lazy-load calls are allowed
    because the ``import()`` inside them is intentional lazy loading, not a
    security vector. They are stripped before pattern matching.
    """
    # Allowlist standard Next.js dynamic import wrappers.
    text = _strip_balanced_parens(text, r"next/dynamic\s*\(")
    text = _strip_balanced_parens(text, r"\bdynamic\s*\(")

    for pattern, desc in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            issues.append(f"Security violation in {source_name}: forbidden {desc}")


def validate_project_structure(project_dir: str | Path) -> tuple[bool, list[str]]:
    """Validate that the generated project has the minimum required files for a runnable Next.js app.

    Returns:
        tuple[bool, list[str]]: (is_valid, list of validation issues or missing requirements)
    """
    root = Path(project_dir)
    issues: list[str] = []

    if not root.exists() or not root.is_dir():
        return False, [f"Project directory does not exist: {project_dir}"]

    # 1. Check package.json
    pkg_file = root / "package.json"
    if not pkg_file.exists():
        issues.append("Missing package.json")
    else:
        try:
            pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
            deps = {
                **pkg_data.get("dependencies", {}),
                **pkg_data.get("devDependencies", {}),
            }
            if "next" not in deps:
                issues.append("package.json missing 'next' dependency")
            if "react" not in deps:
                issues.append("package.json missing 'react' dependency")
        except Exception as e:
            issues.append(f"Invalid package.json format: {e}")

    # 2. Check entrypoint page (app/page.tsx or app/page.jsx or pages/index.tsx)
    has_page = (
        (root / "app" / "page.tsx").exists()
        or (root / "app" / "page.jsx").exists()
        or (root / "app" / "page.js").exists()
        or (root / "pages" / "index.tsx").exists()
        or (root / "pages" / "index.jsx").exists()
    )
    if not has_page:
        issues.append("Missing entrypoint page (expected app/page.tsx)")

    # 3. Check layout (app/layout.tsx or app/layout.jsx) if using App Router
    if (root / "app").exists():
        has_layout = (
            (root / "app" / "layout.tsx").exists()
            or (root / "app" / "layout.jsx").exists()
            or (root / "app" / "layout.js").exists()
        )
        if not has_layout:
            issues.append("Missing root layout (expected app/layout.tsx)")

    return len(issues) == 0, issues


def validate_project_security(project_dir: str | Path) -> tuple[bool, list[str]]:
    """Scan configuration and project files for dangerous Node.js APIs or command injection vectors."""
    root = Path(project_dir)
    issues: list[str] = []

    if not root.exists() or not root.is_dir():
        return False, [f"Project directory does not exist: {project_dir}"]

    # Configuration files including .cjs and .babelrc variants
    config_files = [
        "next.config.js",
        "next.config.mjs",
        "next.config.cjs",
        "next.config.ts",
        "postcss.config.js",
        "postcss.config.mjs",
        "postcss.config.cjs",
        "tailwind.config.js",
        "tailwind.config.ts",
        ".babelrc",
        ".babelrc.js",
        ".babelrc.cjs",
    ]

    for cfg_name in config_files:
        cfg_path = root / cfg_name
        if cfg_path.exists() and cfg_path.is_file():
            try:
                content = _safe_read_text(cfg_path)
                _scan_text(content, cfg_name, issues)
            except Exception as e:
                issues.append(f"Could not read {cfg_name} for security check: {e}")

    # package.json: do not swallow parse errors; also validate scripts and bin scripts
    pkg_file = root / "package.json"
    if pkg_file.exists():
        try:
            pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
            scripts = pkg_data.get("scripts", {})
            dangerous_cmd_pattern = re.compile(
                r"\b(curl|wget|bash|sh|rm\s+-rf|nc|cat\s+/etc)\b", re.IGNORECASE
            )
            for script_name, script_cmd in scripts.items():
                if dangerous_cmd_pattern.search(str(script_cmd)):
                    issues.append(
                        f"Security violation in package.json script '{script_name}': dangerous shell command detected"
                    )

            # Scan declared bin scripts (if any)
            bin_entries = pkg_data.get("bin", {})
            if isinstance(bin_entries, str):
                bin_entries = {pkg_data.get("name", "unknown"): bin_entries}
            for bin_name, bin_path in bin_entries.items():
                bin_target = root / bin_path
                if bin_target.exists() and bin_target.is_file():
                    _scan_text(
                        _safe_read_text(bin_target),
                        f"package.json bin '{bin_name}'",
                        issues,
                    )
        except Exception as e:
            issues.append(f"Invalid package.json (security check failed): {e}")

    # package-lock.json: scan for suspicious content and validate JSON shape
    lock_file = root / "package-lock.json"
    if lock_file.exists() and lock_file.is_file():
        try:
            lock_text = _safe_read_text(lock_file)
            _scan_text(lock_text, "package-lock.json", issues)
            # Basic structural validation
            lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            if not isinstance(lock_data, dict):
                issues.append(
                    "Security violation: package-lock.json is not a valid JSON object"
                )
        except Exception as e:
            issues.append(f"Invalid package-lock.json (security check failed): {e}")

    # Source code scan for dynamic import() and new Function across JS/TS files
    source_extensions = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}
    skip_dirs = {"node_modules", ".next", ".build_logs", ".npm-cache"}
    try:
        for source_path in root.rglob("*"):
            if not source_path.is_file() or source_path.is_symlink():
                continue
            if any(part in skip_dirs for part in source_path.parts):
                continue
            if source_path.suffix not in source_extensions:
                continue
            try:
                resolved = source_path.resolve()
                if not resolved.is_relative_to(root):
                    continue
                content = _safe_read_text(source_path)
                _scan_text(content, str(source_path.relative_to(root)), issues)
            except (OSError, RuntimeError):
                # Likely a symlink loop or unreadable file; skip but log
                continue
    except (OSError, RuntimeError):
        pass

    # Dependency bin scripts: verify they resolve inside the project and scan their content.
    bin_dir = root / "node_modules" / ".bin"
    if bin_dir.exists() and bin_dir.is_dir():
        try:
            for bin_script in bin_dir.iterdir():
                scan_target = None
                source_label = f"node_modules/.bin/{bin_script.name}"

                if bin_script.is_symlink():
                    scan_target = bin_script.resolve()
                    if not scan_target.is_relative_to(root):
                        issues.append(
                            f"Security violation: dependency bin script '{bin_script.name}' resolves outside the project directory"
                        )
                        continue
                elif bin_script.is_file():
                    scan_target = bin_script

                if scan_target and scan_target.exists() and scan_target.is_file():
                    _scan_text(
                        _safe_read_text(scan_target),
                        source_label,
                        issues,
                    )
        except (OSError, RuntimeError):
            pass

    return len(issues) == 0, issues
